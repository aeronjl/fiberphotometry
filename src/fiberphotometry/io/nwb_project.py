"""Atomic, provenance-complete NWB export for executed CLI projects."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fiberphotometry.io.nwb import NWBAcquisitionMetadata, add_recording_to_nwb
from fiberphotometry.metadata import assess_metadata_completeness
from fiberphotometry.multiverse import MultiverseReportGroup, MultiverseResult
from fiberphotometry.pipeline import RecordingInput, run_pipeline
from fiberphotometry.project import LoadedTabularProject, ProjectConfig
from fiberphotometry.workflow import EventAnalysisResult


def export_project_nwb(
    project: ProjectConfig,
    loaded: LoadedTabularProject,
    result: EventAnalysisResult,
    output_directory: Path,
    *,
    mixed_model_json: str | None = None,
    acquisition_metadata: Mapping[str, NWBAcquisitionMetadata] | None = None,
) -> tuple[Path, ...]:
    """Write one validated NWB file per session and return resolved paths.

    ``acquisition_metadata`` maps a recording variable name onto the
    ``ndx-fiber-photometry`` description of its channels. Variables absent from the
    mapping are written without a ``FiberPhotometryTable`` region rather than with
    invented hardware metadata.
    """
    scratch = [
        (
            "fiberphotometry_analysis",
            result.to_json(),
            "Complete population analysis, QC summaries, and processing lineage",
        )
    ]
    if mixed_model_json is not None:
        scratch.append(
            (
                "fiberphotometry_scalar_mixed_model",
                mixed_model_json,
                "Secondary scalar mixed-model sensitivity summary",
            )
        )
    return _export_project_nwb_files(
        project,
        loaded,
        output_directory,
        _NWBAnalysisExport(
            result.pipeline.processed_recordings,
            result.pipeline.quality_reports,
            result.preprocessing.output_variable,
            result.preprocessing.units,
            "ProcessedFiberPhotometrySignal",
            tuple(scratch),
            "analysis",
            dict(acquisition_metadata or {}),
        ),
    )


def export_project_multiverse_nwb(
    project: ProjectConfig,
    loaded: LoadedTabularProject,
    result: MultiverseResult,
    groups: Sequence[MultiverseReportGroup],
    output_directory: Path,
    *,
    acquisition_metadata: Mapping[str, NWBAcquisitionMetadata] | None = None,
) -> tuple[Path, ...]:
    """Archive one reference signal and the complete multiverse evidence ledger."""
    if project.nwb is None:
        return ()
    reference = next(item for item in result.universes if item.is_reference)
    if reference.status == "incompatible":
        raise ValueError("the multiverse reference workflow is incompatible")
    pipeline = run_pipeline(reference.pipeline, loaded.inputs)
    group = next(item for item in groups if reference.universe_id in item.universe_ids)
    return _export_project_nwb_files(
        project,
        loaded,
        output_directory,
        _NWBAnalysisExport(
            pipeline.processed_recordings,
            pipeline.quality_reports,
            reference.pipeline.event_summary.variable,
            group.units,
            "ReferenceWorkflowProcessedFiberPhotometrySignal",
            (
                (
                    "fiberphotometry_multiverse_result",
                    result.to_json(),
                    "Complete multiverse specification, outcomes, and retained "
                    "failures",
                ),
                (
                    "fiberphotometry_robustness_summary",
                    result.grouped_summary_json(groups),
                    "Unit-local robustness summaries and practical-effect policies",
                ),
            ),
            "multiverse",
            dict(acquisition_metadata or {}),
        ),
    )


@dataclass(frozen=True)
class _NWBAnalysisExport:
    processed_recordings: tuple[Any, ...]
    quality_reports: tuple[Any, ...]
    processed_variable: str
    processed_units: str
    processed_name: str
    population_scratch: tuple[tuple[str, str, str], ...]
    identifier_label: str
    acquisition_metadata: dict[str, NWBAcquisitionMetadata]


def _export_project_nwb_files(
    project: ProjectConfig,
    loaded: LoadedTabularProject,
    output_directory: Path,
    export: _NWBAnalysisExport,
) -> tuple[Path, ...]:
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
        export.processed_recordings,
        export.quality_reports,
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
            f"{project.fingerprint[:12]}-{export.identifier_label}"
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
            acquisition_metadata=export.acquisition_metadata.get("signal"),
        )
        if "reference" in session.recording:
            add_recording_to_nwb(
                session.recording,
                nwbfile,
                variable="reference",
                name="RawFiberPhotometryReference",
                unit="a.u.",
                acquisition_metadata=export.acquisition_metadata.get("reference"),
            )
        processing = nwbfile.create_processing_module(
            "fiberphotometry",
            "Derived photometry signals with machine-readable operation provenance",
        )
        add_recording_to_nwb(
            processed,
            nwbfile,
            variable=export.processed_variable,
            name=export.processed_name,
            unit=export.processed_units,
            processing_module=processing,
            acquisition_metadata=export.acquisition_metadata.get(
                export.processed_variable
            ),
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
        for (
            scratch_name,
            scratch_payload,
            scratch_description,
        ) in export.population_scratch:
            _add_json_scratch(
                nwbfile,
                scratch_name,
                scratch_payload,
                scratch_description,
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
