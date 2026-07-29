"""Verified readers for JSON/HTML directories and standalone NWB evidence files."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

EvidenceKind = Literal["analysis", "multiverse", "incomplete"]
EvidenceFormat = Literal["directory", "nwb"]


@dataclass(frozen=True)
class EvidenceFile:
    """One evidence artifact and its manifest-verification state."""

    name: str
    path: Path
    sha256: str
    expected_sha256: str | None
    verified: bool | None


@dataclass(frozen=True)
class ProjectEvidenceBundle:
    """Normalized records recovered from a project directory or one NWB file."""

    source: Path
    source_format: EvidenceFormat
    kind: EvidenceKind
    status: str
    project_name: str
    project_sha256: str
    records: Mapping[str, Any]
    files: tuple[EvidenceFile, ...]
    manifest_verified: bool | None
    manifest: Mapping[str, Any] | None = None

    @property
    def analysis(self) -> Mapping[str, Any] | None:
        return _record(self.records, "analysis.json", "fipha_analysis")

    @property
    def multiverse(self) -> Mapping[str, Any] | None:
        return _record(
            self.records,
            "multiverse.json",
            "fipha_multiverse_result",
        )

    @property
    def robustness_summary(self) -> Mapping[str, Any] | None:
        return _record(
            self.records,
            "robustness-summary.json",
            "fipha_robustness_summary",
        )

    @property
    def metadata(self) -> Mapping[str, Any] | None:
        return _record(
            self.records,
            "metadata.json",
            "fipha_metadata_completeness",
        )

    @property
    def preflight(self) -> Mapping[str, Any] | None:
        return _record(
            self.records,
            "preflight.json",
            "fipha_session_preflight",
        )

    @property
    def project(self) -> Mapping[str, Any] | None:
        return _record(self.records, "fipha_project")


def read_project_evidence(path: str | Path) -> ProjectEvidenceBundle:
    """Read and normalize one manifest directory or standalone NWB evidence file."""
    source = Path(path).resolve()
    if source.is_dir():
        return _read_directory(source)
    if source.is_file() and source.suffix.lower() == ".nwb":
        return _read_nwb(source)
    if not source.exists():
        raise ValueError(f"evidence source does not exist: {source}")
    raise ValueError("evidence source must be an artifact directory or .nwb file")


def _read_directory(root: Path) -> ProjectEvidenceBundle:
    manifest_path = root / "manifest.json"
    manifest = _json_object(manifest_path)
    unknown_manifest = set(manifest) - {
        "schema_version",
        "fipha_version",
        "project",
        "status",
        "artifacts",
        "error",
    }
    if unknown_manifest:
        raise ValueError(
            f"unknown evidence manifest fields: {sorted(unknown_manifest)}"
        )
    if manifest.get("schema_version") != "1":
        raise ValueError("unsupported evidence manifest schema_version")
    project = manifest.get("project")
    if not isinstance(project, dict):
        raise ValueError("evidence manifest project must be an object")
    if set(project) != {"name", "sha256"}:
        raise ValueError("evidence manifest project fields are invalid")
    project_name = _required_string(project, "name", "manifest.project")
    project_sha256 = _sha256_string(project.get("sha256"), "manifest.project.sha256")
    status = _required_string(manifest, "status", "manifest")
    if status not in {"running", "complete", "blocked", "failed"}:
        raise ValueError("evidence manifest status is invalid")
    declared = manifest.get("artifacts")
    if not isinstance(declared, dict):
        raise ValueError("evidence manifest artifacts must be an object")
    files = []
    records: dict[str, Any] = {}
    for name, declaration in declared.items():
        if not isinstance(name, str) or not name:
            raise ValueError("evidence artifact names must be non-empty strings")
        if not isinstance(declaration, dict):
            raise ValueError(f"manifest artifact {name!r} must be an object")
        if set(declaration) != {"sha256"}:
            raise ValueError(f"manifest artifact {name!r} fields are invalid")
        expected = _sha256_string(
            declaration.get("sha256"), f"manifest.artifacts.{name}.sha256"
        )
        artifact = _safe_artifact_path(root, name)
        if not artifact.is_file():
            raise ValueError(f"manifest artifact is missing: {name}")
        observed = _file_sha256(artifact)
        if observed != expected:
            raise ValueError(f"manifest checksum mismatch for artifact: {name}")
        files.append(EvidenceFile(name, artifact, observed, expected, True))
        if artifact.suffix.lower() == ".json":
            records[name] = _json_value(artifact)
    kind = _evidence_kind(records)
    return ProjectEvidenceBundle(
        root,
        "directory",
        kind,
        status,
        project_name,
        project_sha256,
        records,
        tuple(files),
        True,
        manifest,
    )


def _read_nwb(source: Path) -> ProjectEvidenceBundle:
    try:
        from pynwb import NWBHDF5IO  # type: ignore[import-untyped]
    except ImportError as error:
        raise ValueError(
            "NWB evidence reading requires the optional 'nwb' dependencies"
        ) from error
    scratch_names = {
        "fipha_analysis",
        "fipha_metadata_completeness",
        "fipha_multiverse_result",
        "fipha_project",
        "fipha_robustness_summary",
        "fipha_session_preflight",
        "fipha_session_qc",
        "fipha_scalar_mixed_model",
    }
    records = {}
    with NWBHDF5IO(source, "r") as io:
        nwbfile = io.read()
        for name in scratch_names & set(nwbfile.scratch):
            records[name] = _json_text_value(
                nwbfile.scratch[name].data, f"NWB scratch {name!r}"
            )
    project = _record(records, "fipha_project")
    if project is None:
        raise ValueError("NWB evidence lacks fipha_project provenance")
    project_sha256 = _sha256_string(
        project.get("project_sha256"), "fipha_project.project_sha256"
    )
    kind = _evidence_kind(records)
    if kind == "incomplete":
        raise ValueError("NWB evidence lacks an analysis or multiverse result")
    status = _nwb_status(kind, records)
    observed = _file_sha256(source)
    return ProjectEvidenceBundle(
        source,
        "nwb",
        kind,
        status,
        source.name,
        project_sha256,
        records,
        (EvidenceFile(source.name, source, observed, None, None),),
        None,
        None,
    )


def _nwb_status(kind: EvidenceKind, records: Mapping[str, Any]) -> str:
    if kind == "analysis":
        analysis = _record(records, "fipha_analysis")
        return (
            "complete"
            if analysis is not None and analysis.get("analysis")
            else "blocked"
        )
    multiverse = _record(records, "fipha_multiverse_result")
    if multiverse is None:
        return "failed"
    summary = multiverse.get("summary")
    return (
        "complete"
        if isinstance(summary, dict) and summary.get("successful_universes", 0) > 0
        else "blocked"
    )


def _evidence_kind(records: Mapping[str, Any]) -> EvidenceKind:
    has_analysis = any(name in records for name in ("analysis.json", "fipha_analysis"))
    has_multiverse = any(
        name in records for name in ("multiverse.json", "fipha_multiverse_result")
    )
    if has_analysis and has_multiverse:
        raise ValueError("evidence source contains both primary and multiverse results")
    if has_multiverse:
        return "multiverse"
    if has_analysis:
        return "analysis"
    return "incomplete"


def _safe_artifact_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
        raise ValueError(f"unsafe manifest artifact path: {name!r}")
    destination = (root / relative).resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"unsafe manifest artifact path: {name!r}")
    return destination


def _record(records: Mapping[str, Any], *names: str) -> Mapping[str, Any] | None:
    for name in names:
        value = records.get(name)
        if value is not None:
            if not isinstance(value, dict):
                raise ValueError(f"evidence record {name!r} must be a JSON object")
            return value
    return None


def _json_text_value(value: Any, name: str) -> Any:
    if not isinstance(value, str):
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
    if not isinstance(value, str):
        raise ValueError(f"{name} must contain one JSON string")
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{name} contains invalid JSON") from error


def _json_object(path: Path) -> dict[str, Any]:
    value = _json_value(path)
    if not isinstance(value, dict):
        raise ValueError(f"JSON artifact must contain an object: {path.name}")
    return value


def _json_value(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"required evidence artifact is missing: {path.name}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON evidence artifact: {path.name}") from error


def _required_string(payload: Mapping[str, Any], key: str, section: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{section}.{key} must be a non-empty string")
    return value


def _sha256_string(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
