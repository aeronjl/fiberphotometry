"""Typed composition of preprocessing, QC, event summaries, and inference."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import xarray as xr

from fiberphotometry.design import (
    ObservationTable,
    Scalar,
    StudyDesign,
    validate_design,
)
from fiberphotometry.events import summarize_event_windows
from fiberphotometry.planning import AnalysisPlan, AnalysisResult, execute_analysis_plan
from fiberphotometry.preprocess import reference_dff
from fiberphotometry.qc import RecordingQC, assess_recording


@dataclass(frozen=True)
class PreprocessingSpec:
    """Reference-correction choice and its complete numerical parameters."""

    method: Literal["irls", "ols"] = "irls"
    max_iterations: int = 50
    tolerance: float = 1e-8


@dataclass(frozen=True)
class QualityGateSpec:
    """QC warning codes that block inference without deleting observations."""

    blocking_warnings: tuple[str, ...]
    scope: Literal["selected_channel", "all_channels"] = "selected_channel"


@dataclass(frozen=True)
class EventSummarySpec:
    """Acquired-sample event summary to expose as an observation-table column."""

    baseline: tuple[float, float]
    response: tuple[float, float]
    channel: str
    statistic: Literal["baseline_mean", "response_mean", "delta"] = "delta"
    variable: str = "dff"
    output_column: str = "outcome"


@dataclass(frozen=True)
class PipelineSpec:
    """Versioned scientific choices; open event metadata stays outside the schema."""

    preprocessing: PreprocessingSpec
    quality_gate: QualityGateSpec
    event_summary: EventSummarySpec
    design: StudyDesign
    analysis_plan: AnalysisPlan
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class RecordingInput:
    """One recording plus event identifiers and arbitrary per-event metadata."""

    recording: xr.Dataset
    event_times: Sequence[float]
    event_ids: Sequence[str]
    columns: Mapping[str, Sequence[Scalar]]


@dataclass(frozen=True)
class PipelineResult:
    """All intermediate products, including a useful result when QC blocks inference."""

    processed_recordings: tuple[xr.Dataset, ...]
    event_summaries: tuple[xr.Dataset, ...]
    quality_reports: tuple[RecordingQC, ...]
    observation_table: ObservationTable
    blocked_by: tuple[str, ...]
    analysis: AnalysisResult | None

    @property
    def inference_executed(self) -> bool:
        return self.analysis is not None


def run_pipeline(
    spec: PipelineSpec, inputs: Sequence[RecordingInput]
) -> PipelineResult:
    """Run a declared scalar workflow while retaining all intermediate products."""
    if spec.schema_version != "1":
        raise ValueError("unsupported pipeline schema version")
    if not inputs:
        raise ValueError("pipeline requires at least one recording")
    if spec.analysis_plan.estimand.outcome != spec.event_summary.output_column:
        raise ValueError(
            "analysis estimand outcome must match event-summary output_column"
        )

    columns: dict[str, list[Scalar]] = {
        spec.design.observation_id: [],
        spec.event_summary.output_column: [],
    }
    processed: list[xr.Dataset] = []
    summaries: list[xr.Dataset] = []
    reports: list[RecordingQC] = []
    blocked: list[str] = []

    for item in inputs:
        event_count = len(item.event_times)
        if len(item.event_ids) != event_count:
            raise ValueError("event_ids must match event_times")
        if spec.design.observation_id in item.columns:
            raise ValueError("input columns must not replace the observation ID")
        if spec.event_summary.output_column in item.columns:
            raise ValueError("input columns must not replace the pipeline outcome")
        for name, values in item.columns.items():
            if len(values) != event_count:
                raise ValueError(f"column {name!r} must match event_times")

        report = assess_recording(item.recording)
        channel_index = _channel_index(item.recording, spec.event_summary.channel)
        checked = (
            report.channels
            if spec.quality_gate.scope == "all_channels"
            else (report.channels[channel_index],)
        )
        for channel in checked:
            for warning in channel.warnings:
                if warning in spec.quality_gate.blocking_warnings:
                    blocked.append(
                        f"{report.subject}/{report.session}/{channel.channel}:{warning}"
                    )

        preprocessing = spec.preprocessing
        corrected = reference_dff(
            item.recording,
            method=preprocessing.method,
            max_iterations=preprocessing.max_iterations,
            tolerance=preprocessing.tolerance,
        )
        summary = summarize_event_windows(
            corrected,
            item.event_times,
            baseline=spec.event_summary.baseline,
            response=spec.event_summary.response,
            variable=spec.event_summary.variable,
        )
        outcome = np.asarray(
            summary[spec.event_summary.statistic].values[:, channel_index], dtype=float
        )
        columns[spec.design.observation_id].extend(item.event_ids)
        columns[spec.event_summary.output_column].extend(outcome.tolist())
        for name, values in item.columns.items():
            columns.setdefault(name, []).extend(values)
        processed.append(corrected)
        summaries.append(summary)
        reports.append(report)

    lengths = {len(values) for values in columns.values()}
    if len(lengths) != 1:
        raise ValueError("every input must provide the same metadata columns")
    table = ObservationTable.from_columns(columns)
    validate_design(table, spec.design).raise_for_errors()
    analysis = (
        None
        if blocked
        else execute_analysis_plan(spec.analysis_plan, table, spec.design)
    )
    return PipelineResult(
        tuple(processed),
        tuple(summaries),
        tuple(reports),
        table,
        tuple(sorted(set(blocked))),
        analysis,
    )


def _channel_index(recording: xr.Dataset, channel: str) -> int:
    matches = np.flatnonzero(np.asarray(recording.channel.values) == channel)
    if len(matches) != 1:
        raise ValueError(
            f"recording must contain exactly one channel named {channel!r}"
        )
    return int(matches[0])
