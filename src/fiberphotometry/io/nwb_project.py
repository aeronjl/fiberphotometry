"""Atomic, provenance-complete NWB export for executed CLI projects."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from fiberphotometry.io.nwb import add_recording_to_nwb
from fiberphotometry.metadata import assess_metadata_completeness
from fiberphotometry.pipeline import RecordingInput
from fiberphotometry.project import LoadedTabularProject, ProjectConfig
from fiberphotometry.workflow import EventAnalysisResult


def export_project_nwb(
    project: ProjectConfig,
    loaded: LoadedTabularProject,
    result: EventAnalysisResult,
    output_directory: Path,
    *,
    mixed_model_json: str | None = None,
) -> tuple[Path, ...]:
    """Write one validated NWB file per session and return resolved paths."""
    if project.nwb is None:
        return ()
    try:
        from pynwb import NWBHDF5IO, NWBFile, validate  # type: ignore[import-untyped]
        from pynwb.file import Subject  # type: ignore[import-untyped]
    except ImportError as error:
        raise ValueError(
            "NWB export requires the optional 'nwb' dependencies"
        ) from error

    nwb_directory = output_directory / "nwb"
    nwb_directory.mkdir(parents=True, exist_ok=True)
    paths = []
    completeness = assess_metadata_completeness(project, loaded)
    names = set()
    for source, session, item, inspection, processed, quality in zip(
        project.sources,
        loaded.sessions,
        loaded.inputs,
        loaded.inspections,
        result.pipeline.processed_recordings,
        result.pipeline.quality_reports,
        strict=True,
    ):
        if source.session_start_time is None:
            raise ValueError("NWB export requires an explicit session_start_time")
        stem = f"{_safe_name(source.subject)}__{_safe_name(source.session)}"
        if stem in names:
            raise ValueError(
                "session identities collide after NWB filename sanitization"
            )
        names.add(stem)
        destination = nwb_directory / f"{stem}.nwb"
        identifier = (
            f"{project.nwb.identifier_prefix}-{source.subject}-{source.session}-"
            f"{project.fingerprint[:12]}"
        )
        nwbfile = NWBFile(
            session_description=project.nwb.session_description,
            identifier=identifier,
            session_start_time=source.session_start_time,
            session_id=source.session,
            experiment_description=(
                "Fiber photometry project exported by fiberphotometry; see scratch "
                "datasets for the complete configuration, QC, and analysis record."
            ),
        )
        nwbfile.subject = Subject(subject_id=source.subject)
        add_recording_to_nwb(
            session.recording,
            nwbfile,
            variable="signal",
            name="RawFiberPhotometrySignal",
            unit="a.u.",
        )
        if "reference" in session.recording:
            add_recording_to_nwb(
                session.recording,
                nwbfile,
                variable="reference",
                name="RawFiberPhotometryReference",
                unit="a.u.",
            )
        processing = nwbfile.create_processing_module(
            "fiberphotometry",
            "Derived photometry signals with machine-readable operation provenance",
        )
        add_recording_to_nwb(
            processed,
            nwbfile,
            variable=result.preprocessing.output_variable,
            name="ProcessedFiberPhotometrySignal",
            unit=result.preprocessing.units,
            processing_module=processing,
        )
        _add_events(nwbfile, item)
        _add_json_scratch(
            nwbfile,
            "fiberphotometry_metadata_completeness",
            completeness.to_json(),
            "Metadata readiness for analysis, NWB export, and publication reuse",
        )
        _add_json_scratch(
            nwbfile,
            "fiberphotometry_project",
            project.normalized_json(),
            "Normalized project configuration and project SHA-256",
        )
        _add_json_scratch(
            nwbfile,
            "fiberphotometry_analysis",
            result.to_json(),
            "Complete population analysis, QC summaries, and processing lineage",
        )
        if mixed_model_json is not None:
            _add_json_scratch(
                nwbfile,
                "fiberphotometry_scalar_mixed_model",
                mixed_model_json,
                "Secondary scalar mixed-model sensitivity summary",
            )
        _add_json_scratch(
            nwbfile,
            "fiberphotometry_session_preflight",
            inspection.to_json(),
            "Input fingerprints, sampling diagnostics, and event clock coverage",
        )
        _add_json_scratch(
            nwbfile,
            "fiberphotometry_session_qc",
            quality.to_json(),
            "Channel-level quality-control results for this session",
        )
        _atomic_write_nwb(destination, nwbfile, NWBHDF5IO)
        errors = validate(path=str(destination))
        if errors:
            destination.unlink(missing_ok=True)
            rendered = "; ".join(str(error) for error in errors)
            raise ValueError(f"exported NWB failed validation: {rendered}")
        paths.append(destination.resolve())
    return tuple(paths)


def _add_events(nwbfile: Any, item: RecordingInput) -> None:
    nwbfile.add_trial_column("event_id", "Stable event identifier from source data")
    reserved = {"start_time", "stop_time", "event_id"}
    for name in item.columns:
        if name in reserved:
            raise ValueError(f"event metadata column {name!r} is reserved by NWB")
        nwbfile.add_trial_column(name, f"Event metadata column {name}")
    for index, (event_time, event_id) in enumerate(
        zip(item.event_times, item.event_ids, strict=True)
    ):
        metadata = {name: values[index] for name, values in item.columns.items()}
        nwbfile.add_trial(
            start_time=float(event_time),
            stop_time=float(event_time),
            event_id=str(event_id),
            **metadata,
        )


def _add_json_scratch(nwbfile: Any, name: str, payload: str, description: str) -> None:
    # A one-element sequence avoids HDF5 scalar-string edge cases while remaining
    # directly recoverable as JSON.
    nwbfile.add_scratch([payload], name=name, description=description)


def _atomic_write_nwb(path: Path, nwbfile: Any, io_type: Any) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp.nwb"
    )
    os.close(descriptor)
    Path(temporary_name).unlink()
    try:
        with io_type(temporary_name, "w") as io:
            io.write(nwbfile)
        Path(temporary_name).replace(path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _safe_name(value: str) -> str:
    rendered = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    if not rendered:
        raise ValueError("subject and session identifiers need filename-safe content")
    return rendered
