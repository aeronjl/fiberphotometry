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
from typing import Any, cast

from fiberphotometry.archive import (
    create_archive_package,
    verify_archive_package,
)
from fiberphotometry.comparison import compare_project_evidence
from fiberphotometry.compatibility import (
    MultiverseCompatibility,
    PipelineCompatibility,
    assess_multiverse_compatibility,
    assess_pipeline_compatibility,
)
from fiberphotometry.io.nwb_project import (
    export_project_multiverse_nwb,
    export_project_nwb,
)
from fiberphotometry.metadata import (
    MetadataCompletenessReport,
    assess_metadata_completeness,
)
from fiberphotometry.mixed import fit_scalar_mixed_model
from fiberphotometry.multiverse import (
    MultiverseReportGroup,
    MultiverseResult,
    MultiverseSpec,
    materialize_multiverse,
    run_multiverse,
)
from fiberphotometry.project import (
    LoadedTabularProject,
    ProjectConfig,
    ProjectMultiverseConfig,
    SessionSource,
    load_project_config,
)
from fiberphotometry.publication import (
    sign_publication_manifest,
    verify_publication_manifest,
)
from fiberphotometry.results import read_project_evidence
from fiberphotometry.zenodo import create_zenodo_draft


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            comparison = compare_project_evidence(
                read_project_evidence(args.left),
                read_project_evidence(args.right),
                absolute_tolerance=args.absolute_tolerance,
                relative_tolerance=args.relative_tolerance,
            )
            if args.output is None:
                print(comparison.to_markdown(), end="")
            else:
                destination = Path(args.output).resolve()
                content = (
                    comparison.to_json()
                    if destination.suffix.lower() == ".json"
                    else comparison.to_markdown()
                )
                _atomic_write(destination, content)
                print(f"Comparison written to {destination}")
            return 0
        if args.command == "sign":
            attestation = sign_publication_manifest(
                args.bundle,
                key=args.key,
                signer_identity=args.identity,
                overwrite=args.force,
            )
            print(attestation.to_json(), end="")
            return 0
        if args.command == "verify-signature":
            verification = verify_publication_manifest(
                args.bundle, allowed_signers=args.allowed_signers
            )
            print(verification.to_json())
            return 0
        if args.command == "archive":
            package = create_archive_package(
                args.bundle,
                metadata=args.metadata,
                output=args.output,
                overwrite=args.force,
            )
            print(package.to_json())
            return 0
        if args.command == "verify-archive":
            print(verify_archive_package(args.archive).to_json())
            return 0
        if args.command == "zenodo-draft":
            receipt = create_zenodo_draft(
                args.archive,
                token_env=args.token_env,
                production=args.production,
            )
            print(receipt.to_json())
            return 0
        project = load_project_config(args.project)
        loaded = project.load()
        if args.command == "inspect":
            completeness = assess_metadata_completeness(project, loaded)
            payload = _preflight_json(project, loaded, completeness)
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
        if args.command == "multiverse":
            artifacts = run_project_multiverse(project, loaded, output)
            print(f"Robustness artifacts written to {artifacts}")
            return 0
        artifacts = run_project(project, loaded, output)
        print(f"Analysis artifacts written to {artifacts}")
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def run_project(
    project: ProjectConfig,
    loaded: LoadedTabularProject,
    output_directory: Path,
) -> Path:
    """Execute one loaded project and atomically materialize its artifacts."""
    output_directory.mkdir(parents=True, exist_ok=True)
    completeness = assess_metadata_completeness(project, loaded)
    compatibility = _pipeline_compatibility(project, loaded)
    metadata = completeness.to_json()
    preflight = _preflight_json(project, loaded, completeness)
    _atomic_write(output_directory / "preflight.json", preflight)
    _atomic_write(output_directory / "metadata.json", metadata)
    initial_hashes = {
        "metadata.json": _text_sha256(metadata),
        "preflight.json": _text_sha256(preflight),
    }
    _atomic_write(
        output_directory / "manifest.json",
        _manifest(
            project,
            "running",
            initial_hashes,
        ),
    )
    if compatibility.status != "compatible":
        codes = sorted({issue.code for issue in compatibility.issues})
        error = "pipeline structurally incompatible: " + ", ".join(codes)
        _atomic_write(
            output_directory / "manifest.json",
            _manifest(project, "failed", initial_hashes, error=error),
        )
        raise ValueError(error)
    study = project.build_analysis(loaded.sessions)
    try:
        result = study.run(
            acknowledged_assumptions=project.analysis.acknowledged_assumptions
        )
        mixed_result = (
            fit_scalar_mixed_model(
                result.pipeline.observation_table,
                result.spec.design,
                result.spec.analysis_plan.estimand,
            )
            if project.analysis.scalar_mixed_model
            else None
        )
        mixed_model = mixed_result.to_json() if mixed_result is not None else None
    except ValueError as error:
        for stale_name in (
            "analysis.json",
            "mixed-model.html",
            "mixed-model.json",
            "report.html",
        ):
            (output_directory / stale_name).unlink(missing_ok=True)
        failure_manifest = _manifest(
            project,
            "failed",
            initial_hashes,
            error=str(error),
        )
        _atomic_write(output_directory / "manifest.json", failure_manifest)
        raise
    artifacts = {
        "metadata.json": metadata,
        "preflight.json": preflight,
        "analysis.json": result.to_json(),
        "report.html": result.to_html(),
    }
    if mixed_result is not None and mixed_model is not None:
        artifacts["mixed-model.json"] = mixed_model
        artifacts["mixed-model.html"] = mixed_result.to_html()
    else:
        (output_directory / "mixed-model.json").unlink(missing_ok=True)
        (output_directory / "mixed-model.html").unlink(missing_ok=True)
    for name, content in artifacts.items():
        if name in {"metadata.json", "preflight.json"}:
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
        nwb_paths = export_project_nwb(
            project,
            loaded,
            result,
            output_directory,
            mixed_model_json=mixed_model,
        )
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


def run_project_multiverse(
    project: ProjectConfig,
    loaded: LoadedTabularProject,
    output_directory: Path,
) -> Path:
    """Execute the declared project multiverse and materialize evidence artifacts."""
    spec = _multiverse_spec(project, loaded)
    output_directory.mkdir(parents=True, exist_ok=True)
    completeness = assess_metadata_completeness(project, loaded)
    preflight = _preflight_json(project, loaded, completeness)
    metadata = completeness.to_json()
    _atomic_write(output_directory / "preflight.json", preflight)
    _atomic_write(output_directory / "metadata.json", metadata)
    compatibility = _multiverse_compatibility(project, loaded)
    incompatible = [
        universe.universe_id
        for universe in compatibility.universes
        if universe.status == "incompatible"
    ]
    initial = {
        "metadata.json": _text_sha256(metadata),
        "preflight.json": _text_sha256(preflight),
    }
    if incompatible:
        error = (
            "multiverse structurally incompatible before outcome access: "
            + ", ".join(incompatible)
        )
        _atomic_write(
            output_directory / "manifest.json",
            _manifest(project, "failed", initial, error=error),
        )
        raise ValueError(error)
    result = run_multiverse(spec, loaded.inputs)
    groups = _multiverse_report_groups(project, result)
    artifacts = {
        "metadata.json": metadata,
        "preflight.json": preflight,
        "multiverse.json": result.to_json(),
        "robustness-summary.json": result.grouped_summary_json(groups),
        "robustness.html": result.to_grouped_html(
            groups, title=f"{project.analysis.title}: robustness"
        ),
    }
    for name, content in artifacts.items():
        if name not in {"metadata.json", "preflight.json"}:
            _atomic_write(output_directory / name, content)
    hashes = {name: _text_sha256(content) for name, content in artifacts.items()}
    if project.nwb is not None:
        nwb_directory = output_directory / "nwb"
        if nwb_directory.is_dir():
            for stale in nwb_directory.glob("*.nwb"):
                stale.unlink()
    try:
        nwb_paths = export_project_multiverse_nwb(
            project, loaded, result, groups, output_directory
        )
    except ValueError as error:
        nwb_directory = output_directory / "nwb"
        if nwb_directory.is_dir():
            for incomplete in nwb_directory.glob("*.nwb"):
                incomplete.unlink()
        _atomic_write(
            output_directory / "manifest.json",
            _manifest(project, "failed", hashes, error=str(error)),
        )
        raise
    for path in nwb_paths:
        hashes[str(path.relative_to(output_directory))] = _file_sha256(path)
    status = "complete" if result.summary.successful_universes else "blocked"
    _atomic_write(
        output_directory / "manifest.json", _manifest(project, status, hashes)
    )
    return output_directory.resolve()


def _multiverse_report_groups(
    project: ProjectConfig, result: MultiverseResult
) -> tuple[MultiverseReportGroup, ...]:
    config = project.multiverse
    if config is None:
        raise ValueError("project does not declare a [multiverse] configuration")
    unit_groups = config.preprocessing_unit_groups()
    if unit_groups:
        return tuple(
            _multiverse_choice_group(config, result, units, alternatives)
            for units, alternatives in unit_groups.items()
        )
    compatible_ids = tuple(
        universe.universe_id
        for universe in result.universes
        if universe.status != "incompatible"
    )
    units = (
        "acquired fluorescence"
        if project.analysis.preprocessing_kind == "signal_only"
        and project.analysis.normalization == "subtract"
        else "ΔF/F"
    )
    threshold = config.effect_threshold(units)
    return (
        MultiverseReportGroup(
            "Declared workflows",
            units,
            compatible_ids,
            threshold.smallest_effect
            if threshold is not None
            else config.smallest_effect,
            cast(
                Any, threshold.direction if threshold is not None else config.direction
            ),
        ),
    )


def _multiverse_choice_group(
    config: ProjectMultiverseConfig,
    result: MultiverseResult,
    units: str,
    alternatives: tuple[str, ...],
) -> MultiverseReportGroup:
    threshold = config.effect_threshold(units)
    return MultiverseReportGroup.from_choice(
        result,
        name=(
            "Divisive normalization" if units == "ΔF/F" else "Subtractive normalization"
        ),
        units=units,
        node="preprocessing",
        alternatives=alternatives,
        smallest_effect=(
            threshold.smallest_effect
            if threshold is not None
            else config.smallest_effect
        ),
        direction=cast(
            Any, threshold.direction if threshold is not None else config.direction
        ),
    )


def _manifest(
    project: ProjectConfig,
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


def _preflight_json(
    project: ProjectConfig,
    loaded: LoadedTabularProject,
    completeness: MetadataCompletenessReport,
) -> str:
    compatibility = _pipeline_compatibility(project, loaded)
    sessions = []
    sources = cast(tuple[SessionSource, ...], project.sources)
    for source, inspection in zip(sources, loaded.inspections, strict=True):
        sessions.append(
            {
                "subject": source.subject,
                "session": source.session,
                "inspection": json.loads(inspection.to_json()),
            }
        )
    payload = {
        "schema_version": "1",
        "project_sha256": project.fingerprint,
        "metadata_completeness": json.loads(completeness.to_json()),
        "pipeline_compatibility": json.loads(compatibility.to_json()),
        "sessions": sessions,
    }
    if project.multiverse is not None:
        spec = _multiverse_spec(project, loaded)
        payload["multiverse"] = {
            "compatibility": json.loads(
                assess_multiverse_compatibility(spec, loaded.inputs).to_json()
            ),
            "universes": [
                {
                    "universe_id": universe.universe_id,
                    "choices": [
                        {"node": choice.node, "alternative": choice.alternative}
                        for choice in universe.choices
                    ],
                }
                for universe in materialize_multiverse(spec)
            ],
        }
    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )


def _pipeline_compatibility(
    project: ProjectConfig, loaded: LoadedTabularProject
) -> PipelineCompatibility:
    study = project.build_analysis(loaded.sessions)
    spec = study.pipeline_spec(
        acknowledged_assumptions=project.analysis.acknowledged_assumptions
    )
    return assess_pipeline_compatibility(spec, loaded.inputs)


def _multiverse_spec(
    project: ProjectConfig, loaded: LoadedTabularProject
) -> MultiverseSpec:
    if project.multiverse is None:
        raise ValueError("project does not declare a [multiverse] configuration")
    study = project.build_analysis(loaded.sessions)
    base = study.pipeline_spec(
        acknowledged_assumptions=project.analysis.acknowledged_assumptions
    )
    return project.multiverse.build(base)


def _multiverse_compatibility(
    project: ProjectConfig, loaded: LoadedTabularProject
) -> MultiverseCompatibility:
    return assess_multiverse_compatibility(
        _multiverse_spec(project, loaded), loaded.inputs
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
    multiverse = subparsers.add_parser(
        "multiverse",
        help="execute declared robustness workflows and write evidence artifacts",
    )
    multiverse.add_argument("project", type=Path, help="path to a project TOML file")
    multiverse.add_argument(
        "--output-dir",
        type=Path,
        help="override the project output directory",
    )
    compare = subparsers.add_parser(
        "compare",
        help="compare two result directories or NWB evidence files",
    )
    compare.add_argument("left", type=Path, help="first evidence source")
    compare.add_argument("right", type=Path, help="second evidence source")
    compare.add_argument(
        "--absolute-tolerance",
        type=float,
        default=0.0,
        help="absolute numeric tolerance",
    )
    compare.add_argument(
        "--relative-tolerance",
        type=float,
        default=0.0,
        help="relative numeric tolerance",
    )
    compare.add_argument(
        "--output", type=Path, help="write Markdown or JSON based on the extension"
    )
    sign = subparsers.add_parser(
        "sign", help="create a detached OpenSSH publication attestation"
    )
    sign.add_argument("bundle", type=Path, help="complete artifact directory")
    sign.add_argument("--key", type=Path, required=True, help="OpenSSH signing key")
    sign.add_argument(
        "--identity", required=True, help="signer identity used by allowed_signers"
    )
    sign.add_argument(
        "--force", action="store_true", help="replace an existing attestation"
    )
    verify = subparsers.add_parser(
        "verify-signature", help="verify a detached publication attestation"
    )
    verify.add_argument("bundle", type=Path, help="artifact directory")
    verify.add_argument(
        "--allowed-signers",
        type=Path,
        required=True,
        help="OpenSSH allowed_signers trust file",
    )
    archive = subparsers.add_parser(
        "archive", help="create a validated repository-ready deposit ZIP"
    )
    archive.add_argument("bundle", type=Path, help="complete artifact directory")
    archive.add_argument(
        "--metadata", type=Path, required=True, help="archive metadata JSON"
    )
    archive.add_argument("--output", type=Path, required=True, help="output .zip path")
    archive.add_argument(
        "--force", action="store_true", help="replace an existing archive"
    )
    verify_archive = subparsers.add_parser(
        "verify-archive", help="verify an archival package and its inventory"
    )
    verify_archive.add_argument("archive", type=Path, help="deposit .zip path")
    zenodo = subparsers.add_parser(
        "zenodo-draft", help="upload an archive as an unpublished Zenodo draft"
    )
    zenodo.add_argument("archive", type=Path, help="validated deposit .zip path")
    zenodo.add_argument(
        "--token-env",
        help="environment variable containing the access token",
    )
    zenodo.add_argument(
        "--production",
        action="store_true",
        help="create a production draft instead of a sandbox draft",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
