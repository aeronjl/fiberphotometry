"""Outcome-blind structural compatibility checks for declared pipelines."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import numpy as np

from fiberphotometry.multiverse import MultiverseSpec, materialize_multiverse
from fiberphotometry.pipeline import (
    BaselineDFFOperation,
    LowpassFilterOperation,
    PipelineSpec,
    PreprocessingSpec,
    RecordingInput,
    ReferenceDFFOperation,
    ResampleOperation,
)


@dataclass(frozen=True)
class CompatibilityIssue:
    code: str
    session: str
    operation_index: int | None
    message: str


@dataclass(frozen=True)
class PipelineCompatibility:
    status: str
    issues: tuple[CompatibilityIssue, ...]
    outcome_values_accessed: bool = False
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class UniverseCompatibility:
    universe_id: str
    status: str
    issues: tuple[CompatibilityIssue, ...]


@dataclass(frozen=True)
class MultiverseCompatibility:
    universes: tuple[UniverseCompatibility, ...]
    outcome_values_accessed: bool = False
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def assess_pipeline_compatibility(
    spec: PipelineSpec, inputs: tuple[RecordingInput, ...]
) -> PipelineCompatibility:
    """Check shapes, clocks, masks, and declared operations without using values."""
    issues = []
    for item in inputs:
        session = str(item.recording.attrs.get("session", "unknown"))
        time = np.asarray(item.recording.time.values, dtype=float)
        intervals = np.diff(time)
        if len(intervals) == 0 or not np.all(np.isfinite(intervals)):
            issues.append(
                CompatibilityIssue(
                    "invalid_time_axis", session, None, "time intervals must be finite"
                )
            )
            continue
        regular = float(np.std(intervals) / np.mean(intervals)) <= 1e-6
        rate = 1 / float(np.median(intervals))
        variables = set(item.recording.data_vars)
        operations = (
            (ReferenceDFFOperation(spec.preprocessing.method),)
            if isinstance(spec.preprocessing, PreprocessingSpec)
            else spec.preprocessing
        )
        for index, operation in enumerate(operations):
            if isinstance(operation, ResampleOperation):
                valid_resampling = True
                if operation.rate_hz != "median" and operation.rate_hz <= 0:
                    valid_resampling = False
                    issues.append(
                        CompatibilityIssue(
                            "invalid_resampling_rate",
                            session,
                            index,
                            "resampling rate must be positive or 'median'",
                        )
                    )
                if operation.max_gap_s is not None and operation.max_gap_s <= 0:
                    valid_resampling = False
                    issues.append(
                        CompatibilityIssue(
                            "invalid_resampling_gap",
                            session,
                            index,
                            "max_gap_s must be positive",
                        )
                    )
                if (
                    operation.max_gap_s is not None
                    and operation.max_gap_factor is not None
                ):
                    valid_resampling = False
                    issues.append(
                        CompatibilityIssue(
                            "ambiguous_resampling_gap_policy",
                            session,
                            index,
                            "declare max_gap_s or max_gap_factor, not both",
                        )
                    )
                if (
                    operation.max_gap_factor is not None
                    and operation.max_gap_factor <= 1
                ):
                    valid_resampling = False
                    issues.append(
                        CompatibilityIssue(
                            "invalid_resampling_gap_factor",
                            session,
                            index,
                            "max_gap_factor must be greater than one",
                        )
                    )
                if valid_resampling:
                    regular = True
                    rate = (
                        1 / float(np.median(intervals))
                        if operation.rate_hz == "median"
                        else operation.rate_hz
                    )
            elif isinstance(operation, LowpassFilterOperation):
                if operation.cutoff_hz >= rate / 2:
                    issues.append(
                        CompatibilityIssue(
                            "filter_above_nyquist",
                            session,
                            index,
                            "low-pass cutoff must be below the effective Nyquist rate",
                        )
                    )
            elif isinstance(operation, ReferenceDFFOperation):
                if "reference" not in variables:
                    issues.append(
                        CompatibilityIssue(
                            "reference_channel_missing",
                            session,
                            index,
                            "reference correction requires a reference variable",
                        )
                    )
                variables.add("dff")
            elif isinstance(operation, BaselineDFFOperation):
                if operation.variable not in variables:
                    issues.append(
                        CompatibilityIssue(
                            "baseline_variable_missing",
                            session,
                            index,
                            f"baseline variable {operation.variable!r} is absent",
                        )
                    )
                if operation.method == "asls" and not regular:
                    issues.append(
                        CompatibilityIssue(
                            "asls_requires_regular_sampling",
                            session,
                            index,
                            "AsLS requires explicit regularization of this time axis",
                        )
                    )
                if operation.normalization in {"divide", "both"}:
                    variables.add("dff")
                if operation.normalization in {"subtract", "both"}:
                    variables.add("baseline_subtracted")
        if spec.event_summary.variable not in variables:
            issues.append(
                CompatibilityIssue(
                    "event_summary_variable_missing",
                    session,
                    None,
                    f"event summary variable {spec.event_summary.variable!r} is absent",
                )
            )
    rendered = tuple(issues)
    return PipelineCompatibility(
        "compatible" if not rendered else "incompatible", rendered
    )


def assess_multiverse_compatibility(
    spec: MultiverseSpec, inputs: tuple[RecordingInput, ...]
) -> MultiverseCompatibility:
    """Preflight every universe without fitting or summarizing fluorescence values."""
    output = []
    for universe in materialize_multiverse(spec):
        if universe.incompatibility is not None:
            output.append(
                UniverseCompatibility(universe.universe_id, "declared_incompatible", ())
            )
            continue
        report = assess_pipeline_compatibility(universe.pipeline, inputs)
        output.append(
            UniverseCompatibility(universe.universe_id, report.status, report.issues)
        )
    return MultiverseCompatibility(tuple(output))
