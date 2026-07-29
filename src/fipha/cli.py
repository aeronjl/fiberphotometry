"""Command-line entry point for configuration-first photometry analyses."""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import xarray as xr

from fipha.archive import (
    create_archive_package,
    verify_archive_package,
)
from fipha.comparison import compare_project_evidence
from fipha.compatibility import (
    MultiverseCompatibility,
    PipelineCompatibility,
    assess_multiverse_compatibility,
    assess_pipeline_compatibility,
)
from fipha.events import align_events, summarize_event_windows
from fipha.io.acquisition import detect_acquisition_format
from fipha.io.doric import (
    DoricChannel,
    DoricDigitalEvents,
    DoricSchema,
    DoricSeries,
    inspect_doric,
    load_doric_input,
)
from fipha.io.neurophotometrics import (
    NeurophotometricsChannel,
    NeurophotometricsSchema,
    inspect_neurophotometrics,
    load_neurophotometrics_input,
)
from fipha.io.nwb import (
    add_recording_to_nwb,
    from_nwb_series,
    series_provenance,
)
from fipha.io.nwb_project import (
    export_project_multiverse_nwb,
    export_project_nwb,
)
from fipha.io.pyphotometry import (
    PyPhotometryChannel,
    PyPhotometryDigitalEvents,
    PyPhotometrySchema,
    inspect_pyphotometry,
    load_pyphotometry_input,
)
from fipha.io.tabular import (
    TabularChannel,
    TabularRecordingSchema,
    load_tabular_recording,
)
from fipha.io.tdt import (
    TDTBlockSchema,
    TDTEpocEvents,
    TDTEpocValue,
    TDTStreamChannel,
    load_tdt_input,
)
from fipha.metadata import (
    MetadataCompletenessReport,
    assess_metadata_completeness,
)
from fipha.mixed import fit_scalar_mixed_model
from fipha.model import make_recording
from fipha.multiverse import (
    MultiverseReportGroup,
    MultiverseResult,
    MultiverseSpec,
    materialize_multiverse,
    run_multiverse,
)
from fipha.preprocess import baseline_dff, reference_dff
from fipha.project import (
    LoadedTabularProject,
    ProjectConfig,
    ProjectMultiverseConfig,
    SessionSource,
    load_project_config,
)
from fipha.publication import (
    sign_publication_manifest,
    verify_publication_manifest,
)
from fipha.qc import assess_recording, assess_signal_recording
from fipha.results import read_project_evidence
from fipha.transients import TransientDetectionSpec, detect_transients
from fipha.zenodo import create_zenodo_draft

ANALYSIS_COMMANDS = ("qc", "dff", "align", "transients")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command in ANALYSIS_COMMANDS:
            return _run_analysis_command(args)
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
    except CommandError as error:
        print(f"error: {error.code}: {error.message}", file=sys.stderr)
        print(f"hint: {error.hint}", file=sys.stderr)
        return 2
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
        "fipha_version": _package_version(),
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
        return version("fipha")
    except PackageNotFoundError:
        return "uninstalled"


class CommandError(Exception):
    """A user-facing failure carrying a stable code and a next action."""

    def __init__(self, code: str, message: str, hint: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.hint = hint


@dataclass(frozen=True)
class LoadedSource:
    """One recording plus any event times the source format carries itself."""

    path: Path
    source_format: str
    recording: xr.Dataset
    event_times: tuple[float, ...]
    event_ids: tuple[str, ...]
    event_origin: str


_TIME_COLUMN_NAMES = (
    "time",
    "times",
    "time_s",
    "time_seconds",
    "timestamp",
    "timestamps",
    "systemtimestamp",
    "seconds",
    "t",
)
_REFERENCE_TOKENS = (
    "reference",
    "isosbestic",
    "isos",
    "control",
    "violet",
    "405",
    "415",
    "_ref",
    "ref_",
)
_SIGNAL_TOKENS = (
    "signal",
    "dff",
    "gcamp",
    "dlight",
    "grab",
    "green",
    "465",
    "470",
    "560",
)


def _run_analysis_command(args: argparse.Namespace) -> int:
    """Execute one zero-configuration command on a single recording file."""
    source = _load_source(args)
    if args.command == "qc":
        return _command_qc(source, args)
    if args.command == "dff":
        return _command_dff(source, args)
    if args.command == "align":
        return _command_align(source, args)
    return _command_transients(source, args)


def _command_qc(source: LoadedSource, args: argparse.Namespace) -> int:
    """Report whether one recording is usable before any scientific claim."""
    recording = source.recording
    paired = "reference" in recording
    report = (
        assess_recording(recording) if paired else assess_signal_recording(recording)
    )
    time = np.asarray(recording.time.values, dtype=float)
    channels = [dict(item) for item in json.loads(report.to_json())["channels"]]
    warnings = [
        {"channel": str(channel["channel"]), "code": str(code)}
        for channel in channels
        for code in channel["warnings"]
    ]
    payload = {
        "artifact_type": "fipha_recording_qc",
        "schema_version": "1",
        "source": _source_json(source),
        "recording": {
            "subject": report.subject,
            "session": report.session,
            "samples": report.samples,
            "channel_names": [str(name) for name in recording.channel.values],
            "has_reference": paired,
            "start_time_s": float(time[0]),
            "end_time_s": float(time[-1]),
            "duration_s": float(time[-1] - time[0]),
            "estimated_rate_hz": report.estimated_rate_hz,
            "sampling_interval_cv": report.sampling_interval_cv,
            "large_gap_count": report.large_gap_count,
        },
        "channels": channels,
        "warnings": warnings,
        "status": "review" if warnings else "ok",
    }
    _report(
        args,
        [
            f"{source.path.name} ({source.source_format}): "
            f"{len(channels)} channel(s), {report.samples} samples, "
            f"{time[-1] - time[0]:.3f} s at {report.estimated_rate_hz:.4g} Hz",
            *(_qc_channel_line(channel, paired) for channel in channels),
            f"status: {payload['status']}",
        ],
    )
    return _emit(payload, _qc_csv(channels), args)


def _qc_channel_line(channel: dict[str, Any], paired: bool) -> str:
    codes = ", ".join(str(code) for code in channel["warnings"]) or "none"
    if not paired:
        return (
            f"  {channel['channel']}: finite={channel['finite_fraction']:.4f} "
            f"flat_steps={channel['flat_step_fraction']:.4f} warnings={codes}"
        )
    return (
        f"  {channel['channel']}: "
        f"correlation={channel['signal_reference_correlation']:.4f} "
        f"flat_steps={channel['flat_step_fraction']:.4f} "
        f"denominator_ratio={channel['fitted_denominator_min_ratio']:.4f} "
        f"warnings={codes}"
    )


def _qc_csv(channels: Sequence[dict[str, Any]]) -> str:
    keys = sorted({key for channel in channels for key in channel})
    fields = ["channel", *(key for key in keys if key not in {"channel", "warnings"})]
    rows = [
        {
            **{key: channel[key] for key in fields},
            "warnings": "|".join(str(code) for code in channel["warnings"]),
        }
        for channel in channels
    ]
    return _csv_text([*fields, "warnings"], rows)


def _command_dff(source: LoadedSource, args: argparse.Namespace) -> int:
    """Compute dF/F and keep the preprocessing decisions with the numbers."""
    processed, variable = _preprocess(source.recording, args)
    provenance = _provenance(processed)
    values = np.asarray(processed[variable].values, dtype=float)
    time = np.asarray(processed.time.values, dtype=float)
    names = [str(name) for name in processed.channel.values]
    summaries = [
        _channel_summary(name, values[:, index]) for index, name in enumerate(names)
    ]
    payload = {
        "artifact_type": "fipha_dff",
        "schema_version": "1",
        "source": _source_json(source),
        "variable": variable,
        "units": _variable_units(variable),
        "provenance": provenance,
        "summary": summaries,
        "samples": {
            "time_s": [float(item) for item in time],
            "channels": {
                name: _finite_list(values[:, index]) for index, name in enumerate(names)
            },
        },
    }
    destination = None if args.output is None else Path(args.output).resolve()
    if destination is not None and destination.suffix.lower() == ".nwb":
        _write_dff_nwb(destination, source, processed, variable, args)
        _report(
            args,
            [
                *(_dff_summary_line(item) for item in summaries),
                f"{variable} and provenance written to {destination}",
            ],
        )
        return 0
    _report(args, [_dff_summary_line(item) for item in summaries])
    return _emit(payload, _dff_csv(time, names, values, provenance, variable), args)


def _dff_summary_line(summary: dict[str, Any]) -> str:
    return (
        f"  {summary['channel']}: n={summary['finite_samples']} "
        f"mean={summary['mean']:.6g} sd={summary['sd']:.6g} "
        f"min={summary['minimum']:.6g} max={summary['maximum']:.6g}"
    )


def _dff_csv(
    time: np.ndarray,
    names: Sequence[str],
    values: np.ndarray,
    provenance: list[Any],
    variable: str,
) -> str:
    header = json.dumps(
        {"variable": variable, "operations": provenance}, sort_keys=True
    )
    rows = [
        {
            "time_s": _csv_number(time[row]),
            **{
                name: _csv_number(values[row, index])
                for index, name in enumerate(names)
            },
        }
        for row in range(len(time))
    ]
    return f"# {header}\n" + _csv_text(["time_s", *names], rows)


def _command_align(source: LoadedSource, args: argparse.Namespace) -> int:
    """Summarize peri-event windows without averaging events away."""
    processed, variable = _preprocess(source.recording, args)
    times, ids, origin = _resolve_events(source, args)
    baseline = (float(args.baseline[0]), float(args.baseline[1]))
    response = (float(args.response[0]), float(args.response[1]))
    if baseline[0] >= baseline[1] or response[0] >= response[1]:
        raise CommandError(
            "invalid_event_window",
            f"baseline {baseline} and response {response} must start before they stop",
            "pass ordered pairs, for example --baseline -1 0 --response 0 2",
        )
    window = (min(baseline[0], response[0]), max(baseline[1], response[1]))
    rate = float(args.rate) if args.rate is not None else _median_rate(processed)
    try:
        aligned = align_events(
            processed,
            times.tolist(),
            window=window,
            rate=rate,
            variable=variable,
            event_ids=ids,
            baseline=baseline,
            normalization=args.normalization,
        )
        summary = summarize_event_windows(
            processed,
            times.tolist(),
            baseline=baseline,
            response=response,
            variable=variable,
            normalization=args.normalization,
        )
    except ValueError as error:
        raise CommandError(
            "event_summary_variable_missing",
            str(error),
            "check --baseline, --response and --rate against the recorded window",
        ) from error
    names = [str(name) for name in processed.channel.values]
    rows = _alignment_rows(summary, ids, names)
    payload = {
        "artifact_type": "fipha_event_alignment",
        "schema_version": "1",
        "source": _source_json(source),
        "variable": variable,
        "units": str(summary.attrs["units"]),
        "normalization": args.normalization,
        "windows": {
            "baseline_s": list(baseline),
            "response_s": list(response),
            "alignment_s": list(window),
            "alignment_rate_hz": rate,
        },
        "events": {
            "count": len(times),
            "origin": origin,
            "degenerate_baseline_count": int(
                summary.attrs["degenerate_baseline_count"]
            ),
        },
        "provenance": _provenance(processed),
        "per_event": rows,
        "summary": [_alignment_summary(rows, name) for name in names],
        "aligned_mean": {
            "relative_time_s": [float(item) for item in aligned.relative_time.values],
            "channels": {
                name: _finite_list(_nanmean(aligned.values[:, :, index], axis=0))
                for index, name in enumerate(names)
            },
        },
    }
    _report(
        args,
        [
            f"{len(times)} event(s) from {origin} in {summary.attrs['units']!s}",
            *(
                f"  {item['channel']}: complete={item['complete_events']}"
                f"/{item['events']} mean_delta={_format(item['mean_delta'])} "
                f"sem={_format(item['sem_delta'])}"
                for item in cast(list[dict[str, Any]], payload["summary"])
            ),
        ],
    )
    return _emit(payload, _csv_text(list(rows[0]) if rows else [], rows), args)


def _alignment_rows(
    summary: xr.Dataset, ids: Sequence[str], names: Sequence[str]
) -> list[dict[str, Any]]:
    rows = []
    for event_index, identifier in enumerate(ids):
        for channel_index, name in enumerate(names):
            rows.append(
                {
                    "event_id": identifier,
                    "event_time_s": float(summary.event_time.values[event_index]),
                    "channel": name,
                    "baseline_mean": _number(
                        summary.baseline_mean.values[event_index, channel_index]
                    ),
                    "response_mean": _number(
                        summary.response_mean.values[event_index, channel_index]
                    ),
                    "delta": _number(summary.delta.values[event_index, channel_index]),
                    "baseline_finite_fraction": float(
                        summary.baseline_finite_fraction.values[
                            event_index, channel_index
                        ]
                    ),
                    "response_finite_fraction": float(
                        summary.response_finite_fraction.values[
                            event_index, channel_index
                        ]
                    ),
                    "disposition": str(
                        summary.event_disposition.values[event_index, channel_index]
                    ),
                }
            )
    return rows


def _alignment_summary(rows: Sequence[dict[str, Any]], channel: str) -> dict[str, Any]:
    selected = [row for row in rows if row["channel"] == channel]
    deltas = np.asarray(
        [row["delta"] for row in selected if row["delta"] is not None], dtype=float
    )
    responses = np.asarray(
        [row["response_mean"] for row in selected if row["response_mean"] is not None],
        dtype=float,
    )
    baselines = np.asarray(
        [row["baseline_mean"] for row in selected if row["baseline_mean"] is not None],
        dtype=float,
    )
    count = len(deltas)
    return {
        "channel": channel,
        "events": len(selected),
        "complete_events": count,
        "mean_baseline": _number(np.mean(baselines)) if len(baselines) else None,
        "mean_response": _number(np.mean(responses)) if len(responses) else None,
        "mean_delta": _number(np.mean(deltas)) if count else None,
        "sd_delta": _number(np.std(deltas, ddof=1)) if count > 1 else None,
        "sem_delta": (
            _number(np.std(deltas, ddof=1) / np.sqrt(count)) if count > 1 else None
        ),
    }


def _command_transients(source: LoadedSource, args: argparse.Namespace) -> int:
    """Detect spontaneous transients and retain every rejected candidate."""
    processed, variable = _preprocess(source.recording, args)
    spec = TransientDetectionSpec(
        threshold_mode=args.detector,
        threshold=float(args.threshold),
        baseline_statistic=args.baseline_statistic,
        baseline_duration_s=float(args.baseline_duration),
        baseline_gap_s=float(args.baseline_gap),
        minimum_distance_s=float(args.min_distance),
        bin_width_s=None if args.bin_width is None else float(args.bin_width),
    )
    try:
        result = detect_transients(processed, variable=variable, spec=spec)
    except ValueError as error:
        raise CommandError(
            "baseline_variable_missing",
            str(error),
            f"choose an available variable with --variable; {variable!r} is absent",
        ) from error
    events = [_public_dict(event) for event in result.events]
    payload = {
        "artifact_type": "fipha_transients",
        "schema_version": "1",
        "source": _source_json(source),
        "variable": variable,
        "units": _variable_units(variable),
        "detection": _public_dict(spec),
        "provenance": _provenance(processed),
        "events": events,
        "exclusions": [_public_dict(item) for item in result.exclusions],
        "summaries": [_public_dict(item) for item in result.summaries],
    }
    _report(
        args,
        [
            f"{len(events)} transient(s), "
            f"{len(result.exclusions)} rejected candidate(s)",
            *(
                f"  {item.channel}: n={item.count} "
                f"rate={item.rate_per_minute:.4g}/min "
                f"median_amplitude={_format(item.median_amplitude)} "
                f"analyzed={item.analyzed_duration_s:.4g} s"
                for item in result.summaries
            ),
        ],
    )
    return _emit(payload, _csv_text(list(events[0]) if events else [], events), args)


def _preprocess(
    recording: xr.Dataset, args: argparse.Namespace
) -> tuple[xr.Dataset, str]:
    """Return the analysed dataset and the variable the command should read."""
    variable = getattr(args, "variable", "dff")
    if variable != "dff":
        if variable not in recording:
            raise CommandError(
                "baseline_variable_missing",
                f"the recording has no {variable!r} variable",
                "available variables: "
                + ", ".join(sorted(str(name) for name in recording.data_vars)),
            )
        return recording, variable
    method = args.method
    if method == "auto":
        method = "reference" if "reference" in recording else "baseline"
    if method == "reference":
        if "reference" not in recording:
            raise CommandError(
                "reference_channel_missing",
                f"{args.file} carries no reference channel, so a reference "
                "regression cannot be fitted",
                "re-run with --method baseline (optionally "
                "--baseline-method rolling_mean) to estimate a signal-only baseline",
            )
        return reference_dff(recording, method=args.fit), "dff"
    normalization = cast(
        Literal["divide", "subtract", "both"],
        getattr(args, "normalization_kind", "divide"),
    )
    try:
        processed = baseline_dff(
            recording,
            method=args.baseline_method,
            normalization=normalization,
        )
    except ValueError as error:
        if "regularly sampled" in str(error):
            raise CommandError(
                "asls_requires_regular_sampling",
                str(error),
                "choose --baseline-method rolling_mean or double_exponential, "
                "which do not require a regular clock",
            ) from error
        raise CommandError(
            "baseline_variable_missing",
            str(error),
            "check --baseline-method against the recorded sampling",
        ) from error
    return processed, "dff" if normalization != "subtract" else "baseline_subtracted"


def _resolve_events(
    source: LoadedSource, args: argparse.Namespace
) -> tuple[np.ndarray, list[str], str]:
    if args.events is None:
        if not source.event_times:
            raise CommandError(
                "event_times_missing",
                f"{source.source_format} source {source.path.name} carries no "
                "event times",
                "pass --events EVENTS.csv, where one column holds event onset "
                "times in seconds",
            )
        return (
            np.asarray(source.event_times, dtype=float),
            list(source.event_ids),
            f"{source.source_format} source",
        )
    path = Path(args.events)
    table = _read_delimited(path)
    column = args.event_column or _guess_time_column(table)
    if column is None or column not in table.fields:
        raise CommandError(
            "event_times_missing",
            f"{path.name} has no usable event-time column",
            "name one explicitly with --event-column; the file contains: "
            + ", ".join(table.fields),
        )
    times = []
    for index, row in enumerate(table.rows):
        try:
            times.append(float(row[column]))
        except ValueError as error:
            raise CommandError(
                "event_times_missing",
                f"{path.name} row {index + 1} column {column!r} is not a number",
                "event times must be finite seconds relative to the recording clock",
            ) from error
    if not times:
        raise CommandError(
            "event_times_missing",
            f"{path.name} contains no event rows",
            "provide at least one event onset time",
        )
    identifiers = (
        [row[args.event_id_column] for row in table.rows]
        if args.event_id_column
        else [str(index) for index in range(len(times))]
    )
    if len(set(identifiers)) != len(identifiers):
        raise CommandError(
            "event_times_missing",
            f"{path.name} column {args.event_id_column!r} repeats an identifier",
            "event identifiers must be unique within a session",
        )
    return np.asarray(times, dtype=float), identifiers, path.name


@dataclass(frozen=True)
class _DelimitedTable:
    fields: tuple[str, ...]
    rows: tuple[dict[str, str], ...]
    delimiter: str


def _read_delimited(path: Path) -> _DelimitedTable:
    if not path.is_file():
        raise CommandError(
            "acquisition_source_unreadable",
            f"no such file: {path}",
            "check the path and the spelling of the file name",
        )
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            first = stream.readline()
            stream.seek(0)
            delimiter = _delimiter(path, first)
            reader = csv.DictReader(stream, delimiter=delimiter)
            fields = tuple(reader.fieldnames or ())
            rows = tuple({key: (row[key] or "") for key in fields} for row in reader)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise CommandError(
            "acquisition_source_unreadable",
            f"{path.name} could not be read as delimited text: {error}",
            "export the table as UTF-8 CSV or TSV with a single header row",
        ) from error
    if not fields:
        raise CommandError(
            "acquisition_source_unreadable",
            f"{path.name} has no header row",
            "the first line must name every column",
        )
    return _DelimitedTable(fields, rows, delimiter)


def _delimiter(path: Path, first_line: str) -> str:
    if path.suffix.lower() == ".tsv":
        return "\t"
    try:
        return str(csv.Sniffer().sniff(first_line).delimiter)
    except csv.Error:
        return ","


def _load_source(args: argparse.Namespace) -> LoadedSource:
    """Detect the acquisition format and load it without a project file."""
    path = Path(args.file)
    if not path.exists():
        raise CommandError(
            "acquisition_source_unreadable",
            f"no such file or directory: {path}",
            "pass the recording file itself, or the block directory for TDT",
        )
    subject = str(args.subject)
    session = str(args.session) if args.session else path.stem
    loaded = _dispatch_source(path, args, subject=subject, session=session)
    return _select_channels(loaded, args)


def _dispatch_source(
    path: Path, args: argparse.Namespace, *, subject: str, session: str
) -> LoadedSource:
    suffix = path.suffix.lower()
    if suffix == ".nwb":
        return _load_nwb_source(path, args, subject=subject, session=session)
    detected = detect_acquisition_format(path)
    if detected == "unknown" and suffix in {".pqt", ".parquet"}:
        detected = "neurophotometrics"
    loaders = {
        "neurophotometrics": _load_neurophotometrics_source,
        "pyphotometry": _load_pyphotometry_source,
        "doric": _load_doric_source,
        "tdt": _load_tdt_source,
        "tabular": _load_tabular_source,
    }
    if detected not in loaders:
        raise CommandError(
            "unrecognized_acquisition_format",
            f"{path.name} does not match a supported acquisition format",
            "supported sources are Neurophotometrics CSV/parquet, TDT block "
            "directories, Doric .doric, pyPhotometry .ppd, NWB .nwb, and "
            "delimited .csv/.tsv tables",
        )
    try:
        return loaders[detected](path, args, subject=subject, session=session)
    except CommandError:
        raise
    except (OSError, ValueError, KeyError, ImportError) as error:
        raise CommandError(
            "acquisition_source_unreadable",
            f"{path.name} was detected as {detected} but could not be loaded: {error}",
            "check the file, or declare the mapping explicitly in a project TOML "
            "and use 'fipha run'",
        ) from error


def _select_channels(loaded: LoadedSource, args: argparse.Namespace) -> LoadedSource:
    if not args.channel:
        return loaded
    available = [str(name) for name in loaded.recording.channel.values]
    missing = [name for name in args.channel if name not in available]
    if missing:
        raise CommandError(
            "channel_not_found",
            f"{loaded.path.name} has no channel named {', '.join(missing)}",
            "available channels: " + ", ".join(available),
        )
    selected = loaded.recording.sel(channel=list(args.channel))
    selected.attrs.update(loaded.recording.attrs)
    return LoadedSource(
        loaded.path,
        loaded.source_format,
        selected,
        loaded.event_times,
        loaded.event_ids,
        loaded.event_origin,
    )


def _load_tabular_source(
    path: Path, args: argparse.Namespace, *, subject: str, session: str
) -> LoadedSource:
    table = _read_delimited(path)
    numeric = _numeric_columns(table)
    time_column = args.time_column or _guess_time_column(table)
    if time_column is None or time_column not in table.fields:
        raise CommandError(
            "invalid_time_axis",
            f"{path.name} has no recognizable time column",
            "name it with --time-column; the file contains: " + ", ".join(table.fields),
        )
    signals, references = _guess_channel_columns(
        [name for name in numeric if name != time_column], args
    )
    if not signals:
        raise CommandError(
            "baseline_variable_missing",
            f"{path.name} has no numeric signal column besides {time_column!r}",
            "name the fluorescence columns with --signal-column (repeatable)",
        )
    if references and len(references) != len(signals):
        raise CommandError(
            "reference_channel_missing",
            f"{path.name} has {len(signals)} signal and {len(references)} "
            "reference columns, which cannot be paired",
            "pass matching --signal-column and --reference-column pairs in order",
        )
    channels = tuple(
        TabularChannel(
            name,
            name,
            references[index] if references else None,
        )
        for index, name in enumerate(signals)
    )
    schema = TabularRecordingSchema(
        time_column=time_column, channels=channels, delimiter=table.delimiter
    )
    recording = load_tabular_recording(path, schema, subject=subject, session=session)
    return LoadedSource(path, "tabular", recording, (), (), "none")


def _numeric_columns(table: _DelimitedTable) -> list[str]:
    sample = table.rows[:20]
    numeric = []
    for name in table.fields:
        values = [row[name].strip() for row in sample if row[name].strip()]
        if values and all(_is_number(value) for value in values):
            numeric.append(name)
    return numeric


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _guess_time_column(table: _DelimitedTable) -> str | None:
    numeric = _numeric_columns(table)
    for name in numeric:
        if name.strip().lower().replace(" ", "_") in _TIME_COLUMN_NAMES:
            return name
    for name in table.fields:
        if name.strip().lower().replace(" ", "_") in _TIME_COLUMN_NAMES:
            return name
    return numeric[0] if numeric else None


def _guess_channel_columns(
    candidates: Sequence[str], args: argparse.Namespace
) -> tuple[list[str], list[str]]:
    if args.signal_column:
        return list(args.signal_column), list(args.reference_column or [])
    references = [name for name in candidates if _matches(name, _REFERENCE_TOKENS)]
    if args.reference_column:
        references = list(args.reference_column)
    signals = [name for name in candidates if name not in references]
    named = [name for name in signals if _matches(name, _SIGNAL_TOKENS)]
    return (named or signals), references


def _matches(name: str, tokens: Sequence[str]) -> bool:
    lowered = name.strip().lower()
    return any(token in lowered for token in tokens)


def _load_neurophotometrics_source(
    path: Path, args: argparse.Namespace, *, subject: str, session: str
) -> LoadedSource:
    inspection = inspect_neurophotometrics(path)
    columns = args.signal_column or [
        field.key for field in inspection.fields if field.role == "signal"
    ]
    if not columns:
        raise CommandError(
            "baseline_variable_missing",
            f"{path.name} contains no Region ROI columns",
            "name the ROI columns with --signal-column (repeatable)",
        )
    attempts = (
        (470.0, 415.0),
        (560.0, 415.0),
        (470.0, None),
        (560.0, None),
        (415.0, None),
    )
    failures = []
    for signal_nm, reference_nm in attempts:
        schema = NeurophotometricsSchema(
            channels=tuple(
                NeurophotometricsChannel(name, name, signal_nm, reference_nm)
                for name in columns
            )
        )
        try:
            loaded = load_neurophotometrics_input(
                path, schema, subject=subject, session=session
            )
        except ValueError as error:
            failures.append(f"{signal_nm:g}/{reference_nm or 'none'} nm: {error}")
            continue
        return LoadedSource(
            path,
            "neurophotometrics",
            loaded.recording,
            tuple(float(item) for item in loaded.event_times),
            tuple(str(item) for item in loaded.event_ids),
            "none",
        )
    raise CommandError(
        "acquisition_source_unreadable",
        f"{path.name} has no usable excitation pattern: {'; '.join(failures)}",
        "declare the ROI columns and wavelengths in a project TOML and use 'fipha run'",
    )


def _load_pyphotometry_source(
    path: Path, args: argparse.Namespace, *, subject: str, session: str
) -> LoadedSource:
    inspection = inspect_pyphotometry(path)
    analog = [field.key for field in inspection.fields if field.role == "signal"]
    digital = [field.key for field in inspection.fields if field.role == "digital"]
    if not analog:
        raise CommandError(
            "baseline_variable_missing",
            f"{path.name} exposes no analog inputs",
            "re-export the recording from pyPhotometry",
        )
    paired = len(analog) >= 2
    schema = PyPhotometrySchema(
        channels=(PyPhotometryChannel(analog[0], 1, 2 if paired else None),),
        digital_events=tuple(
            PyPhotometryDigitalEvents(index, name)
            for index, name in enumerate(digital, start=1)
        ),
    )
    loaded = load_pyphotometry_input(path, schema, subject=subject, session=session)
    return LoadedSource(
        path,
        "pyphotometry",
        loaded.recording,
        tuple(float(item) for item in loaded.event_times),
        tuple(str(item) for item in loaded.event_ids),
        "digital inputs",
    )


def _load_doric_source(
    path: Path, args: argparse.Namespace, *, subject: str, session: str
) -> LoadedSource:
    inspection = inspect_doric(path)
    groups: dict[str, dict[str, str]] = {}
    for field in inspection.fields:
        group, _, leaf = field.key.rpartition("/")
        groups.setdefault(group, {})[leaf.lower()] = field.key
    series = {
        group: DoricSeries(members["values"], members["time"])
        for group, members in sorted(groups.items())
        if "values" in members and "time" in members
    }
    digital = {
        group: item
        for group, item in series.items()
        if _matches(group, ("digitalio", "dio", "ttl"))
    }
    analog = {group: item for group, item in series.items() if group not in digital}
    references = [
        group for group in analog if _matches(group, ("aout02", *_REFERENCE_TOKENS))
    ]
    signals = [group for group in analog if group not in references]
    if not signals:
        raise CommandError(
            "baseline_variable_missing",
            f"{path.name} contains no paired Values/Time signal series",
            "declare the dataset paths in a project TOML and use 'fipha run'",
        )
    channels = tuple(
        DoricChannel(
            group.rsplit("/", 1)[-1],
            analog[group],
            analog[references[index]] if index < len(references) else None,
        )
        for index, group in enumerate(signals)
    )
    schema = DoricSchema(
        channels=channels,
        digital_events=tuple(
            DoricDigitalEvents(group.rsplit("/", 1)[-1], item, edge="rising")
            for group, item in digital.items()
        ),
    )
    loaded = load_doric_input(path, schema, subject=subject, session=session)
    return LoadedSource(
        path,
        "doric",
        loaded.recording,
        tuple(float(item) for item in loaded.event_times),
        tuple(str(item) for item in loaded.event_ids),
        "digital series",
    )


def _tdt_reader() -> Any:
    try:
        from tdt import read_block  # type: ignore[import-untyped]
    except ImportError as error:
        raise CommandError(
            "acquisition_source_unreadable",
            "reading a TDT block requires the optional 'tdt' dependency",
            "install it with: pip install 'fipha[tdt]'",
        ) from error
    return read_block


def _load_tdt_source(
    path: Path, args: argparse.Namespace, *, subject: str, session: str
) -> LoadedSource:
    reader = _tdt_reader()
    block = reader(str(path), evtype=["streams", "epocs"], verbose=0)
    streams = _tdt_members(getattr(block, "streams", None))
    epocs = _tdt_members(getattr(block, "epocs", None))
    if not streams:
        raise CommandError(
            "baseline_variable_missing",
            f"{path.name} contains no stream stores",
            "check that the block directory holds the .tev and .tsq files",
        )
    references = [name for name in streams if _matches(name, ("405", "415"))]
    signals = [name for name in streams if name not in references]
    if not signals:
        raise CommandError(
            "baseline_variable_missing",
            f"{path.name} exposes only reference stores: {', '.join(references)}",
            "declare the store mapping in a project TOML and use 'fipha run'",
        )
    signal_store = signals[0]
    reference_store = references[0] if references else None
    count = _tdt_channel_count(streams[signal_store])
    channels = tuple(
        TDTStreamChannel(
            f"{signal_store}_{index}" if count > 1 else signal_store,
            signal_store,
            index,
            reference_store,
            index if reference_store is not None else None,
        )
        for index in range(1, count + 1)
    )
    if not epocs:
        return _tdt_stream_only_source(
            path, streams, channels, subject=subject, session=session
        )
    store = sorted(epocs)[0]
    values = np.unique(np.asarray(epocs[store].data, dtype=float))
    schema = TDTBlockSchema(
        channels=channels,
        events=TDTEpocEvents(
            store,
            "epoc_value",
            tuple(TDTEpocValue(float(value), f"{store}_{value:g}") for value in values),
        ),
    )
    loaded = load_tdt_input(
        path, schema, subject=subject, session=session, reader=reader
    )
    return LoadedSource(
        path,
        "tdt",
        loaded.recording,
        tuple(float(item) for item in loaded.event_times),
        tuple(str(item) for item in loaded.event_ids),
        f"epoc store {store}",
    )


def _tdt_stream_only_source(
    path: Path,
    streams: dict[str, Any],
    channels: tuple[TDTStreamChannel, ...],
    *,
    subject: str,
    session: str,
) -> LoadedSource:
    """Load a block that records fluorescence but declares no epoc events."""
    signal = np.column_stack(
        [_tdt_row(streams[item.signal_store], item.signal_channel) for item in channels]
    )
    reference = (
        np.column_stack(
            [
                _tdt_row(
                    streams[str(item.reference_store)], int(item.reference_channel or 1)
                )
                for item in channels
            ]
        )
        if channels[0].reference_store is not None
        else None
    )
    stream = streams[channels[0].signal_store]
    rate = float(stream.fs)
    start = float(getattr(stream, "start_time", 0.0) or 0.0)
    digest = hashlib.sha256(
        json.dumps([asdict(item) for item in channels], sort_keys=True).encode()
    )
    digest.update(np.asarray(signal, dtype="<f8").tobytes(order="C"))
    recording = make_recording(
        time=start + np.arange(signal.shape[0], dtype=float) / rate,
        signal=signal,
        reference=reference,
        channel_names=[item.name for item in channels],
        subject=subject,
        session=session,
        attrs={
            "source_format": "TDT_block",
            "source_name": path.name,
            "source_sha256": digest.hexdigest(),
            "source_fingerprint_scope": "declared_stream_channels",
            "tdt_sampling_rate_hz": rate,
            "tdt_stream_start_time_s": start,
        },
    )
    return LoadedSource(path, "tdt", recording, (), (), "none")


def _tdt_members(container: Any) -> dict[str, Any]:
    if container is None:
        return {}
    if hasattr(container, "items"):
        return {str(key): value for key, value in container.items()}
    return {str(key): value for key, value in vars(container).items()}


def _tdt_channel_count(stream: Any) -> int:
    data = np.asarray(stream.data)
    return 1 if data.ndim == 1 else int(data.shape[0])


def _tdt_row(stream: Any, channel: int) -> np.ndarray:
    data = np.asarray(stream.data, dtype=float)
    return data if data.ndim == 1 else np.asarray(data[channel - 1], dtype=float)


def _load_nwb_source(
    path: Path, args: argparse.Namespace, *, subject: str, session: str
) -> LoadedSource:
    try:
        from pynwb import NWBHDF5IO  # type: ignore[import-untyped]
    except ImportError as error:
        raise CommandError(
            "acquisition_source_unreadable",
            "reading NWB requires the optional 'nwb' dependencies",
            "install them with: pip install 'fipha[nwb]'",
        ) from error
    with NWBHDF5IO(str(path), "r", load_namespaces=True) as handle:
        nwbfile = handle.read()
        available = dict(nwbfile.acquisition)
        acquired = set(available)
        for module in nwbfile.processing.values():
            available.update(module.data_interfaces)
        series = {
            name: item
            for name, item in available.items()
            if hasattr(item, "data") and np.asarray(item.data).ndim in (1, 2)
        }
        if not series:
            raise CommandError(
                "baseline_variable_missing",
                f"{path.name} contains no readable time series",
                "export the file with a TimeSeries in acquisition or a "
                "processing module",
            )
        name = args.series or _preferred_nwb_series(
            nwbfile, series, acquired & set(series)
        )
        if name not in series:
            raise CommandError(
                "baseline_variable_missing",
                f"{path.name} has no series named {name!r}",
                "available series: " + ", ".join(sorted(series)),
            )
        recording = from_nwb_series(
            series[name],
            subject=args.subject if args.subject != "unknown" else None,
            session=args.session,
        )
        events = _nwb_trial_times(nwbfile)
    return LoadedSource(
        path,
        "nwb",
        recording,
        events,
        tuple(str(index) for index in range(len(events))),
        "trials table" if events else "none",
    )


def _preferred_nwb_series(
    nwbfile: Any, series: dict[str, Any], acquired: set[str]
) -> str:
    """Prefer the raw acquired signal, then any acquisition, then the first series."""
    for name in sorted(acquired):
        if series_provenance(nwbfile, name).get("source_variable") == "signal":
            return name
    return sorted(acquired)[0] if acquired else sorted(series)[0]


def _nwb_trial_times(nwbfile: Any) -> tuple[float, ...]:
    trials = getattr(nwbfile, "trials", None)
    if trials is None:
        return ()
    return tuple(float(value) for value in np.asarray(trials["start_time"].data))


def _write_dff_nwb(
    destination: Path,
    source: LoadedSource,
    processed: xr.Dataset,
    variable: str,
    args: argparse.Namespace,
) -> None:
    try:
        from pynwb import NWBHDF5IO, NWBFile
        from pynwb.file import Subject  # type: ignore[import-untyped]
    except ImportError as error:
        raise CommandError(
            "acquisition_source_unreadable",
            "writing NWB requires the optional 'nwb' dependencies",
            "install them with: pip install 'fipha[nwb]'",
        ) from error
    if args.session_start_time is None:
        raise CommandError(
            "nwb_session_start_time_missing",
            "a valid NWB file records when the session started, and this "
            "library does not invent that metadata",
            "re-run with --session-start-time 2026-01-01T12:00:00+00:00, or "
            "write CSV instead",
        )
    try:
        start = datetime.fromisoformat(str(args.session_start_time))
    except ValueError as error:
        raise CommandError(
            "nwb_session_start_time_missing",
            f"{args.session_start_time!r} is not an ISO-8601 timestamp",
            "use a timezone-aware value such as 2026-01-01T12:00:00+00:00",
        ) from error
    if start.tzinfo is None:
        raise CommandError(
            "nwb_session_start_time_missing",
            f"{args.session_start_time!r} has no timezone",
            "append an offset, for example 2026-01-01T12:00:00+00:00",
        )
    subject_id = str(processed.attrs["subject"])
    session_id = str(processed.attrs["session"])
    nwbfile = NWBFile(
        session_description=(
            f"Fiber photometry recording {source.path.name} preprocessed by "
            "the fipha command line"
        ),
        identifier=(
            f"fipha-{subject_id}-{session_id}-"
            f"{str(processed.attrs.get('source_sha256', ''))[:12]}"
        ),
        session_start_time=start,
        session_id=session_id,
    )
    nwbfile.subject = Subject(subject_id=subject_id)
    add_recording_to_nwb(
        processed, nwbfile, variable="signal", name="RawFiberPhotometrySignal"
    )
    if "reference" in processed:
        add_recording_to_nwb(
            processed,
            nwbfile,
            variable="reference",
            name="RawFiberPhotometryReference",
        )
    module = nwbfile.create_processing_module(
        "fipha",
        "Derived photometry signals with machine-readable operation provenance",
    )
    add_recording_to_nwb(
        processed,
        nwbfile,
        variable=variable,
        name="ProcessedFiberPhotometrySignal",
        unit=_variable_units(variable),
        processing_module=module,
    )
    nwbfile.add_scratch(
        [json.dumps(_provenance(processed), sort_keys=True)],
        name="fipha_operations",
        description="Ordered preprocessing operations applied to this recording",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _temporary_path(destination) as temporary:
        with NWBHDF5IO(str(temporary), "w") as handle:
            handle.write(nwbfile)
        temporary.replace(destination)


@contextlib.contextmanager
def _temporary_path(destination: Path) -> Iterator[Path]:
    descriptor, name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.stem}.", suffix=".tmp.nwb"
    )
    os.close(descriptor)
    temporary = Path(name)
    temporary.unlink()
    try:
        yield temporary
    finally:
        temporary.unlink(missing_ok=True)


def _emit(payload: dict[str, Any], table: str, args: argparse.Namespace) -> int:
    content = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else table
    )
    if args.output is None:
        sys.stdout.write(content)
        return 0
    destination = Path(args.output).resolve()
    _atomic_write(destination, content)
    if args.format != "json":
        _atomic_write(
            destination.with_suffix(destination.suffix + ".provenance.json"),
            json.dumps(
                {key: value for key, value in payload.items() if key != "samples"},
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    _report(args, [f"written to {destination}"])
    return 0


def _report(args: argparse.Namespace, lines: Sequence[str]) -> None:
    if args.quiet:
        return
    for line in lines:
        print(line, file=sys.stderr)


def _source_json(source: LoadedSource) -> dict[str, Any]:
    attrs = source.recording.attrs
    return {
        "path": str(source.path),
        "name": source.path.name,
        "format": source.source_format,
        "sha256": str(attrs.get("source_sha256", "")),
        "fingerprint_scope": str(attrs.get("source_fingerprint_scope", "file_content")),
        "subject": str(attrs["subject"]),
        "session": str(attrs["session"]),
    }


def _provenance(recording: xr.Dataset) -> list[Any]:
    return cast(
        list[Any],
        json.loads(str(recording.attrs.get("fipha_operations", "[]"))),
    )


def _variable_units(variable: str) -> str:
    return "dF/F" if variable == "dff" else "acquired units"


def _channel_summary(name: str, values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    return {
        "channel": name,
        "finite_samples": int(finite.size),
        "mean": _number(np.mean(finite)) if finite.size else None,
        "sd": _number(np.std(finite, ddof=1)) if finite.size > 1 else None,
        "minimum": _number(np.min(finite)) if finite.size else None,
        "maximum": _number(np.max(finite)) if finite.size else None,
    }


def _median_rate(recording: xr.Dataset) -> float:
    intervals = np.diff(np.asarray(recording.time.values, dtype=float))
    return float(1 / np.median(intervals))


def _nanmean(values: np.ndarray, *, axis: int) -> np.ndarray:
    counts = np.sum(np.isfinite(values), axis=axis)
    totals = np.sum(np.where(np.isfinite(values), values, 0.0), axis=axis)
    return np.where(counts > 0, totals / np.maximum(counts, 1), np.nan)


def _finite_list(values: np.ndarray) -> list[float | None]:
    return [_number(item) for item in np.asarray(values, dtype=float)]


def _number(value: Any) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def _format(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6g}"


def _csv_number(value: float) -> str:
    return "" if not np.isfinite(value) else repr(float(value))


def _public_dict(item: Any) -> dict[str, Any]:
    return {
        key: (_number(value) if isinstance(value, float) else value)
        for key, value in asdict(item).items()
    }


def _csv_text(fields: Sequence[str], rows: Sequence[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(fields), lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _cell(row.get(key)) for key in fields})
    return buffer.getvalue()


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(float(value))
    return str(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fipha",
        description="Inspect and run reproducible fiber-photometry projects.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_analysis_commands(subparsers)
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


def _add_analysis_commands(subparsers: Any) -> None:
    """Register the single-file commands that need no project configuration."""
    qc = subparsers.add_parser("qc", help="report whether one recording file is usable")
    _add_source_arguments(qc)
    dff = subparsers.add_parser(
        "dff", help="compute dF/F for one recording file with full provenance"
    )
    _add_source_arguments(dff)
    _add_preprocessing_arguments(dff)
    dff.add_argument(
        "--normalization",
        dest="normalization_kind",
        choices=("divide", "subtract", "both"),
        default="divide",
        help="signal-only baseline normalization (default: divide)",
    )
    dff.add_argument(
        "--session-start-time",
        help="timezone-aware ISO-8601 start time, required for NWB output",
    )
    align = subparsers.add_parser(
        "align", help="summarize peri-event windows around known event times"
    )
    _add_source_arguments(align)
    _add_preprocessing_arguments(align, variable=True)
    align.add_argument(
        "--events", type=Path, help="CSV or TSV file holding event onset times"
    )
    align.add_argument("--event-column", help="event-time column in the events file")
    align.add_argument(
        "--event-id-column", help="unique event identifier column in the events file"
    )
    align.add_argument(
        "--baseline",
        nargs=2,
        type=float,
        default=(-1.0, 0.0),
        metavar=("START", "STOP"),
        help="baseline window in seconds relative to each event (default: -1 0)",
    )
    align.add_argument(
        "--response",
        nargs=2,
        type=float,
        default=(0.0, 1.0),
        metavar=("START", "STOP"),
        help="response window in seconds relative to each event (default: 0 1)",
    )
    align.add_argument(
        "--normalization",
        choices=("none", "baseline_z", "robust_z"),
        default="none",
        help="per-event rescaling by its own baseline window (default: none)",
    )
    align.add_argument(
        "--rate",
        type=float,
        help="peri-event grid rate in Hz (default: the recorded median rate)",
    )
    transients = subparsers.add_parser(
        "transients", help="detect spontaneous transients and retain rejections"
    )
    _add_source_arguments(transients)
    _add_preprocessing_arguments(transients, variable=True)
    transients.add_argument(
        "--detector",
        choices=("absolute", "global_mad", "rolling_mad"),
        default="rolling_mad",
        help="threshold family (default: rolling_mad)",
    )
    transients.add_argument(
        "--threshold",
        type=float,
        default=3.0,
        help="threshold in robust sigma, or in signal units for the absolute "
        "detector (default: 3)",
    )
    transients.add_argument(
        "--baseline-statistic",
        choices=("mean", "median", "minimum"),
        default="median",
        help="pre-peak baseline statistic (default: median)",
    )
    transients.add_argument(
        "--baseline-duration",
        type=float,
        default=0.9,
        help="pre-peak baseline duration in seconds (default: 0.9)",
    )
    transients.add_argument(
        "--baseline-gap",
        type=float,
        default=0.1,
        help="gap between the baseline window and the peak (default: 0.1)",
    )
    transients.add_argument(
        "--min-distance",
        type=float,
        default=0.2,
        help="minimum separation between peaks in seconds (default: 0.2)",
    )
    transients.add_argument(
        "--bin-width",
        type=float,
        help="optional descriptive bin width in seconds",
    )


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "file", type=Path, help="recording file, or block directory for TDT"
    )
    parser.add_argument(
        "--channel",
        action="append",
        help="restrict the analysis to one named channel (repeatable)",
    )
    parser.add_argument(
        "--output", type=Path, help="write to this path instead of stdout"
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="machine-readable output format (default: json)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress the stderr summary"
    )
    parser.add_argument(
        "--subject", default="unknown", help="subject identifier for provenance"
    )
    parser.add_argument("--session", help="session identifier (default: the file stem)")
    parser.add_argument("--time-column", help="time column of a delimited table")
    parser.add_argument(
        "--signal-column",
        action="append",
        help="fluorescence column or Neurophotometrics ROI (repeatable)",
    )
    parser.add_argument(
        "--reference-column",
        action="append",
        help="reference column paired with each signal column (repeatable)",
    )
    parser.add_argument("--series", help="series name to read from an NWB file")


def _add_preprocessing_arguments(
    parser: argparse.ArgumentParser, *, variable: bool = False
) -> None:
    parser.add_argument(
        "--method",
        choices=("auto", "reference", "baseline"),
        default="auto",
        help="dF/F family; auto uses the reference channel when one exists",
    )
    parser.add_argument(
        "--fit",
        choices=("irls", "ols"),
        default="irls",
        help="reference regression estimator (default: irls)",
    )
    parser.add_argument(
        "--baseline-method",
        choices=("double_exponential", "asls", "rolling_mean"),
        default="double_exponential",
        help="signal-only baseline family (default: double_exponential)",
    )
    if variable:
        parser.add_argument(
            "--variable",
            default="dff",
            help="analysed variable; anything but 'dff' skips preprocessing",
        )


if __name__ == "__main__":
    raise SystemExit(main())
