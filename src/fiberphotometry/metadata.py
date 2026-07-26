"""Versioned, actionable metadata completeness assessment."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal

from fiberphotometry.project import LoadedTabularProject, ProjectConfig

CheckStatus = Literal["complete", "missing"]
ReadinessStatus = Literal["ready", "incomplete"]


@dataclass(frozen=True)
class MetadataCheck:
    code: str
    label: str
    targets: tuple[str, ...]
    status: CheckStatus
    scope: str
    remediation: str | None = None


@dataclass(frozen=True)
class MetadataReadiness:
    target: str
    status: ReadinessStatus
    complete: int
    total: int
    missing_codes: tuple[str, ...]


@dataclass(frozen=True)
class MetadataCompletenessReport:
    schema_version: str
    profile: str
    checks: tuple[MetadataCheck, ...]
    readiness: tuple[MetadataReadiness, ...]
    unrecognized_fields: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


_RECOGNIZED = {
    "acquisition_system",
    "brain_regions",
    "data_license",
    "experiment_description",
    "experimenters",
    "indicator",
    "institution",
    "lab",
    "protocol",
    "species",
}


def assess_metadata_completeness(
    project: ProjectConfig, loaded: LoadedTabularProject
) -> MetadataCompletenessReport:
    """Assess readiness without inventing scientific or administrative metadata."""
    metadata = project.metadata
    checks = [
        _check(
            "analysis.session_identity",
            "Unique subject and session identities",
            ("analysis", "nwb", "publication"),
            len({(item.subject, item.session) for item in project.sources})
            == len(project.sources),
            "project",
            "Give every session a unique subject/session pair.",
        ),
        _check(
            "analysis.source_provenance",
            "Fingerprint-scoped acquisition and event sources",
            ("analysis", "nwb", "publication"),
            all(
                inspection.recording.source_sha256
                and inspection.recording.source_fingerprint_scope
                and inspection.events.source_sha256
                for inspection in loaded.inspections
            ),
            "all sessions",
            "Import through an adapter that records source fingerprints.",
        ),
        _check(
            "analysis.event_factor",
            "Declared experimental event factor",
            ("analysis", "nwb", "publication"),
            all(project.analysis.factor_name in item.columns for item in loaded.inputs),
            "all sessions",
            "Map the analysis factor in every event source.",
        ),
        _check(
            "nwb.configuration",
            "NWB export description and identifier policy",
            ("nwb",),
            project.nwb is not None,
            "project",
            "Add an [nwb] table with session_description and identifier_prefix.",
        ),
        _check(
            "session.start_time",
            "Timezone-aware acquisition start times",
            ("nwb", "publication"),
            all(
                source.session_start_time is not None
                and source.session_start_time.tzinfo is not None
                and source.session_start_time.utcoffset() is not None
                for source in project.sources
            ),
            "all sessions",
            "Add a timezone-aware session_start_time to every [[sessions]] entry.",
        ),
        _metadata_check(metadata, "experimenters", "Named experimenter(s)"),
        _metadata_check(metadata, "institution", "Institution"),
        _metadata_check(metadata, "lab", "Laboratory"),
        _metadata_check(metadata, "experiment_description", "Experimental description"),
        _metadata_check(metadata, "protocol", "Protocol or preregistration reference"),
        _metadata_check(metadata, "species", "Subject species"),
        _metadata_check(metadata, "indicator", "Fluorescent indicator"),
        _metadata_check(metadata, "brain_regions", "Recorded brain region(s)"),
        _metadata_check(metadata, "acquisition_system", "Acquisition system"),
        _metadata_check(metadata, "data_license", "Data reuse license"),
    ]
    rendered = tuple(checks)
    targets = tuple(
        _readiness(target, rendered) for target in ("analysis", "nwb", "publication")
    )
    return MetadataCompletenessReport(
        schema_version="1",
        profile="fiberphotometry-metadata-v0.1",
        checks=rendered,
        readiness=targets,
        unrecognized_fields=tuple(sorted(set(metadata) - _RECOGNIZED)),
    )


def _metadata_check(metadata: dict[str, object], key: str, label: str) -> MetadataCheck:
    return _check(
        f"publication.{key}",
        label,
        ("publication",),
        _present(metadata.get(key)),
        "metadata",
        f"Add {key} to the project [metadata] table.",
    )


def _present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple):
        return bool(value) and all(_present(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and all(_present(item) for item in value.values())
    return False


def _check(
    code: str,
    label: str,
    targets: tuple[str, ...],
    complete: bool,
    scope: str,
    remediation: str,
) -> MetadataCheck:
    return MetadataCheck(
        code,
        label,
        targets,
        "complete" if complete else "missing",
        scope,
        None if complete else remediation,
    )


def _readiness(target: str, checks: tuple[MetadataCheck, ...]) -> MetadataReadiness:
    relevant = tuple(check for check in checks if target in check.targets)
    missing = tuple(check.code for check in relevant if check.status == "missing")
    return MetadataReadiness(
        target,
        "ready" if not missing else "incomplete",
        len(relevant) - len(missing),
        len(relevant),
        missing,
    )
