"""Command-line entry point for configuration-first photometry analyses."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fiberphotometry.io.nwb_project import export_project_nwb
from fiberphotometry.project import LoadedTabularProject, TabularProjectConfig


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        project = TabularProjectConfig.from_toml(args.project)
        loaded = project.load()
        if args.command == "inspect":
            payload = _preflight_json(project, loaded)
            if args.output is None:
                print(payload)
            else:
                destination = Path(args.output).resolve()
                _atomic_write(destination, payload)
                print(f"Preflight written to {destination}")
            return 0
        output = (
            Path(args.output_dir).resolve()
            if args.output_dir is not None
            else project.output_directory
        )
        artifacts = run_project(project, loaded, output)
        print(f"Analysis artifacts written to {artifacts}")
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def run_project(
    project: TabularProjectConfig,
    loaded: LoadedTabularProject,
    output_directory: Path,
) -> Path:
    """Execute one loaded project and atomically materialize its artifacts."""
    output_directory.mkdir(parents=True, exist_ok=True)
    preflight = _preflight_json(project, loaded)
    _atomic_write(output_directory / "preflight.json", preflight)
    _atomic_write(
        output_directory / "manifest.json",
        _manifest(
            project,
            "running",
            {"preflight.json": _text_sha256(preflight)},
        ),
    )
    study = project.build_analysis(loaded.sessions)
    try:
        result = study.run(
            acknowledged_assumptions=project.analysis.acknowledged_assumptions
        )
    except ValueError as error:
        for stale_name in ("analysis.json", "report.html"):
            (output_directory / stale_name).unlink(missing_ok=True)
        failure_manifest = _manifest(
            project,
            "failed",
            {"preflight.json": _text_sha256(preflight)},
            error=str(error),
        )
        _atomic_write(output_directory / "manifest.json", failure_manifest)
        raise
    artifacts = {
        "preflight.json": preflight,
        "analysis.json": result.to_json(),
        "report.html": result.to_html(),
    }
    for name, content in artifacts.items():
        if name == "preflight.json":
            continue
        _atomic_write(output_directory / name, content)
    artifact_hashes = {
        name: _text_sha256(content) for name, content in artifacts.items()
    }
    if project.nwb is not None:
        nwb_directory = output_directory / "nwb"
        if nwb_directory.is_dir():
            for stale in nwb_directory.glob("*.nwb"):
                stale.unlink()
    try:
        nwb_paths = export_project_nwb(project, loaded, result, output_directory)
    except ValueError as error:
        nwb_directory = output_directory / "nwb"
        if nwb_directory.is_dir():
            for incomplete in nwb_directory.glob("*.nwb"):
                incomplete.unlink()
        failure_manifest = _manifest(
            project,
            "failed",
            artifact_hashes,
            error=str(error),
        )
        _atomic_write(output_directory / "manifest.json", failure_manifest)
        raise
    for path in nwb_paths:
        artifact_hashes[str(path.relative_to(output_directory))] = _file_sha256(path)
    manifest = _manifest(
        project,
        "complete" if result.pipeline.analysis is not None else "blocked",
        artifact_hashes,
    )
    _atomic_write(output_directory / "manifest.json", manifest)
    return output_directory.resolve()


def _manifest(
    project: TabularProjectConfig,
    status: str,
    artifact_hashes: dict[str, str],
    *,
    error: str | None = None,
) -> str:
    payload = {
        "schema_version": "1",
        "fiberphotometry_version": _package_version(),
        "project": {
            "name": project.source_path.name,
            "sha256": project.fingerprint,
        },
        "status": status,
        "artifacts": {
            name: {"sha256": fingerprint}
            for name, fingerprint in artifact_hashes.items()
        },
    }
    if error is not None:
        payload["error"] = error
    return json.dumps(payload, indent=2, sort_keys=True)


def _preflight_json(project: TabularProjectConfig, loaded: LoadedTabularProject) -> str:
    sessions = []
    for source, inspection in zip(project.sources, loaded.inspections, strict=True):
        sessions.append(
            {
                "subject": source.subject,
                "session": source.session,
                "inspection": json.loads(inspection.to_json()),
            }
        )
    return json.dumps(
        {
            "schema_version": "1",
            "project_sha256": project.fingerprint,
            "sessions": sessions,
        },
        indent=2,
        sort_keys=True,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _text_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version() -> str:
    try:
        return version("fiberphotometry")
    except PackageNotFoundError:
        return "uninstalled"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fiberphotometry",
        description="Inspect and run reproducible fiber-photometry projects.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser(
        "inspect", help="validate input schemas and report preflight diagnostics"
    )
    inspect.add_argument("project", type=Path, help="path to a project TOML file")
    inspect.add_argument("--output", type=Path, help="write JSON instead of stdout")
    run = subparsers.add_parser(
        "run", help="execute the declared analysis and write evidence artifacts"
    )
    run.add_argument("project", type=Path, help="path to a project TOML file")
    run.add_argument(
        "--output-dir",
        type=Path,
        help="override the project output directory",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
