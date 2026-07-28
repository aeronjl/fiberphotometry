"""Scientist-facing workflow for a common event-contrast analysis."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypeVar

import numpy as np
import xarray as xr

from fiberphotometry.coverage import (
    EventCoverageRecord,
    EventCoverageReport,
    assess_event_coverage,
)
from fiberphotometry.design import Factor, ObservationTable, StudyDesign, Unit
from fiberphotometry.events import align_events
from fiberphotometry.inference import Contrast, Estimand
from fiberphotometry.pipeline import (
    BaselineDFFOperation,
    EventSummarySpec,
    PipelineResult,
    PipelineSpec,
    PreprocessingOperation,
    QualityGateSpec,
    RecordingInput,
    ReferenceDFFOperation,
    ResampleOperation,
    run_pipeline,
)
from fiberphotometry.planning import AnalysisPlan, create_analysis_plan
from fiberphotometry.timecourse import (
    PeriEventInferenceResult,
    PeriEventInferenceSpec,
    infer_peri_event_contrast,
)

T = TypeVar("T")


@dataclass(frozen=True)
class EventSession:
    """One recording and the categorical labels attached to its events."""

    recording: xr.Dataset
    event_times: tuple[float, ...]
    conditions: tuple[str, ...]
    event_ids: tuple[str, ...]
    eligible: tuple[bool, ...]
    exclusion_reasons: tuple[str, ...]

    @classmethod
    def from_arrays(
        cls,
        recording: xr.Dataset,
        event_times: Sequence[float],
        conditions: Sequence[str],
        *,
        event_ids: Sequence[str] | None = None,
        eligible: Sequence[bool] | None = None,
        exclusion_reasons: Sequence[str] | None = None,
    ) -> EventSession:
        """Create a session with stable generated event IDs when none are supplied."""
        times = tuple(float(value) for value in event_times)
        labels = tuple(str(value) for value in conditions)
        if len(times) != len(labels):
            raise ValueError("event_times and conditions must have equal length")
        session = str(recording.attrs.get("session", "session"))
        generated_ids = [f"{session}:{i}" for i in range(len(times))]
        identifiers = tuple(str(value) for value in (event_ids or generated_ids))
        if len(identifiers) != len(times):
            raise ValueError("event_ids must match event_times")
        eligibility_values = eligible if eligible is not None else [True] * len(times)
        eligibility = tuple(bool(value) for value in eligibility_values)
        if len(eligibility) != len(times):
            raise ValueError("eligible must match event_times")
        reasons = tuple(
            str(value)
            for value in (
                exclusion_reasons
                if exclusion_reasons is not None
                else ["eligibility_gate"] * len(times)
            )
        )
        if len(reasons) != len(times):
            raise ValueError("exclusion_reasons must match event_times")
        excluded = (
            reason
            for include, reason in zip(eligibility, reasons, strict=True)
            if not include
        )
        if any(not reason.strip() for reason in excluded):
            raise ValueError("ineligible events require an exclusion reason")
        return cls(recording, times, labels, identifiers, eligibility, reasons)


@dataclass(frozen=True)
class Preprocessing:
    """A named preprocessing recipe with an explicit output variable and units."""

    label: str
    operations: tuple[PreprocessingOperation, ...]
    output_variable: Literal["dff", "baseline_subtracted"]
    units: str

    @classmethod
    def reference(cls, *, method: Literal["irls", "ols"] = "irls") -> Preprocessing:
        """Fit an explicitly supplied reference channel."""
        return cls(
            f"{method.upper()} reference correction",
            (ReferenceDFFOperation(method=method),),
            "dff",
            "ΔF/F",
        )

    @classmethod
    def signal_only(
        cls,
        *,
        method: Literal["double_exponential", "asls", "rolling_mean"],
        normalization: Literal["divide", "subtract"] = "divide",
        rolling_window_s: float = 60.0,
        resample_rate_hz: float | Literal["median"] | None = None,
        resample_max_gap_factor: float | None = None,
    ) -> Preprocessing:
        """Apply a declared signal-only baseline without claiming artefact removal."""
        variable: Literal["dff", "baseline_subtracted"] = (
            "dff" if normalization == "divide" else "baseline_subtracted"
        )
        units = "ΔF/F" if normalization == "divide" else "acquired fluorescence"
        regularization: tuple[PreprocessingOperation, ...] = (
            (
                ResampleOperation(
                    rate_hz=resample_rate_hz,
                    max_gap_factor=resample_max_gap_factor,
                ),
            )
            if resample_rate_hz is not None
            else ()
        )
        return cls(
            f"{method.replace('_', ' ')} ({normalization})",
            (
                *regularization,
                BaselineDFFOperation(
                    method=method,
                    normalization=normalization,
                    rolling_window_s=rolling_window_s,
                ),
            ),
            variable,
            units,
        )


@dataclass(frozen=True)
class EventAnalysisResult:
    """Completed pipeline plus enough declared context to render or serialize it."""

    pipeline: PipelineResult
    spec: PipelineSpec
    title: str
    preprocessing: Preprocessing
    coverage: EventCoverageReport
    timecourse: PeriEventInferenceResult | None = None
    configuration_fingerprint: str | None = None

    def to_json(self) -> str:
        analysis = self.pipeline.analysis
        table = self.pipeline.observation_table
        animals = set(table.values("animal").tolist())
        sessions = set(table.values("session").tolist())
        payload = {
            "artifact_type": "event_analysis_result",
            "schema_version": "1",
            "title": self.title,
            "preprocessing": asdict(self.preprocessing),
            "spec": json.loads(self.spec.to_json()),
            "blocked_by": self.pipeline.blocked_by,
            "analysis": (
                json.loads(analysis.to_json()) if analysis is not None else None
            ),
            "configuration_sha256": self.configuration_fingerprint,
            "event_coverage": json.loads(self.coverage.to_json()),
            "timecourse": (
                json.loads(self.timecourse.to_json())
                if self.timecourse is not None
                else None
            ),
            "data_summary": {
                "animals": len(animals),
                "sessions": len(sessions),
                "events": len(table),
            },
            "quality_reports": [
                json.loads(report.to_json()) for report in self.pipeline.quality_reports
            ],
            "processing_lineage": [
                {
                    "subject": recording.attrs["subject"],
                    "session": recording.attrs["session"],
                    "operations": json.loads(
                        str(recording.attrs.get("fiberphotometry_operations", "[]"))
                    ),
                }
                for recording in self.pipeline.processed_recordings
            ],
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    def to_html(self) -> str:
        """Render a self-contained evidence report without external assets."""
        from fiberphotometry.report import render_event_analysis_report

        return render_event_analysis_report(self)

    def write_html(self, path: str | Path) -> Path:
        """Write the self-contained report and return its resolved path."""
        destination = Path(path)
        destination.write_text(self.to_html(), encoding="utf-8")
        return destination.resolve()

    def write_json(self, path: str | Path) -> Path:
        """Write the machine-readable result and return its resolved path."""
        destination = Path(path)
        destination.write_text(self.to_json(), encoding="utf-8")
        return destination.resolve()


@dataclass(frozen=True)
class EventAnalysis:
    """High-level workflow for a paired or independent animal event contrast."""

    sessions: tuple[EventSession, ...]
    numerator: str
    denominator: str
    channel: str
    preprocessing: Preprocessing
    baseline: tuple[float, float] = (-0.5, 0.0)
    response: tuple[float, float] = (0.0, 0.5)
    factor_name: str = "condition"
    factor_assignment_unit: Literal["event", "session", "animal"] = "event"
    title: str = "Fiber photometry event contrast"
    randomized: bool | None = False
    intent: Literal["confirmatory", "exploratory", "descriptive"] = "exploratory"
    blocking_warnings: tuple[str, ...] = ()
    contrast_unit: Literal["session"] | None = None
    timecourse: PeriEventInferenceSpec | None = None
    configuration_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.sessions:
            raise ValueError("analysis requires at least one event session")
        if self.numerator == self.denominator:
            raise ValueError("contrast levels must differ")
        levels = {
            label
            for session in self.sessions
            for label, eligible in zip(
                session.conditions, session.eligible, strict=True
            )
            if eligible
        }
        missing = {self.numerator, self.denominator} - levels
        if missing:
            raise ValueError(f"contrast levels absent from sessions: {sorted(missing)}")
        if self.timecourse is not None:
            expected = (
                "independent" if self.factor_assignment_unit == "animal" else "paired"
            )
            if self.timecourse.design != expected:
                raise ValueError(
                    "time-course design conflicts with factor_assignment_unit: "
                    f"expected {expected!r}"
                )

    def plan(self, *, acknowledged_assumptions: Sequence[str] = ()) -> AnalysisPlan:
        """Create the inference plan without reading fluorescence outcome values."""
        table = self._routing_table()
        return create_analysis_plan(
            table,
            self._design(),
            self._estimand(),
            randomized=self.randomized,
            intent=self.intent,
            acknowledged_assumptions=tuple(acknowledged_assumptions),
        )

    def run(self, *, acknowledged_assumptions: Sequence[str]) -> EventAnalysisResult:
        """Execute only after the caller explicitly acknowledges plan assumptions."""
        spec = self.pipeline_spec(acknowledged_assumptions=acknowledged_assumptions)
        plan = spec.analysis_plan
        if not plan.executable:
            missing = sorted(
                set(plan.required_assumptions) - set(plan.acknowledged_assumptions)
            )
            message = "unacknowledged analysis assumptions: " + ", ".join(missing)
            raise ValueError(message)
        inputs = self._inputs()
        pipeline = run_pipeline(spec, inputs)
        return EventAnalysisResult(
            pipeline,
            spec,
            self.title,
            self.preprocessing,
            self._coverage(pipeline),
            self._timecourse(pipeline),
            self.configuration_fingerprint,
        )

    def pipeline_spec(
        self, *, acknowledged_assumptions: Sequence[str] = ()
    ) -> PipelineSpec:
        """Build the complete typed pipeline without accessing outcome values."""
        plan = self.plan(acknowledged_assumptions=acknowledged_assumptions)
        return PipelineSpec(
            self.preprocessing.operations,
            QualityGateSpec(self.blocking_warnings),
            EventSummarySpec(
                self.baseline,
                self.response,
                self.channel,
                variable=self.preprocessing.output_variable,
                output_column="event_response",
            ),
            self._design(),
            plan,
            schema_version="2",
        )

    def _inputs(self) -> tuple[RecordingInput, ...]:
        return tuple(
            RecordingInput(
                session.recording,
                _selected(session.event_times, session.eligible),
                _selected(session.event_ids, session.eligible),
                {
                    "animal": [str(session.recording.attrs["subject"])]
                    * sum(session.eligible),
                    "session": [str(session.recording.attrs["session"])]
                    * sum(session.eligible),
                    self.factor_name: _selected(session.conditions, session.eligible),
                },
            )
            for session in self.sessions
            if any(session.eligible)
        )

    def _design(self) -> StudyDesign:
        return StudyDesign(
            observation_id="event_id",
            units=(
                Unit("animal", "animal"),
                Unit("session", "session", "animal"),
                Unit("event", "event_id", "session"),
            ),
            factors=(
                Factor(
                    self.factor_name,
                    self.factor_name,
                    "categorical",
                    self.factor_assignment_unit,
                ),
            ),
        )

    def _estimand(self) -> Estimand:
        return Estimand(
            "event_response",
            Contrast(self.factor_name, self.numerator, self.denominator),
            "animal",
            contrast_unit=self.contrast_unit,
        )

    def _routing_table(self) -> ObservationTable:
        columns: dict[str, list[str | float]] = {
            "event_id": [],
            "animal": [],
            "session": [],
            self.factor_name: [],
            "event_response": [],
        }
        for session in self.sessions:
            count = sum(session.eligible)
            columns["event_id"].extend(_selected(session.event_ids, session.eligible))
            columns["animal"].extend([str(session.recording.attrs["subject"])] * count)
            columns["session"].extend([str(session.recording.attrs["session"])] * count)
            columns[self.factor_name].extend(
                _selected(session.conditions, session.eligible)
            )
            columns["event_response"].extend([0.0] * count)
        return ObservationTable.from_columns(columns)

    def _coverage(self, pipeline: PipelineResult) -> EventCoverageReport:
        records: list[EventCoverageRecord] = []
        summary_index = 0
        for session in self.sessions:
            dispositions: list[str] = []
            if any(session.eligible):
                summary = pipeline.event_summaries[summary_index]
                recording = pipeline.processed_recordings[summary_index]
                matches = np.flatnonzero(
                    np.asarray(recording.channel.values) == self.channel
                )
                channel_index = int(matches[0])
                dispositions = np.asarray(
                    summary.event_disposition.values[:, channel_index], dtype=str
                ).tolist()
                summary_index += 1
            eligible_index = 0
            animal = str(session.recording.attrs["subject"])
            session_id = str(session.recording.attrs["session"])
            for event_id, condition, eligible, reason in zip(
                session.event_ids,
                session.conditions,
                session.eligible,
                session.exclusion_reasons,
                strict=True,
            ):
                if eligible:
                    disposition = dispositions[eligible_index]
                    eligible_index += 1
                else:
                    disposition = reason
                records.append(
                    EventCoverageRecord(
                        event_id,
                        condition,
                        animal,
                        session_id,
                        eligible,
                        eligible and disposition == "complete",
                        disposition,
                    )
                )
        return assess_event_coverage(tuple(records))

    def _timecourse(self, pipeline: PipelineResult) -> PeriEventInferenceResult | None:
        if self.timecourse is None:
            return None
        matrices = []
        animals: list[str] = []
        sessions: list[str] = []
        conditions: list[str] = []
        processed_index = 0
        for session in self.sessions:
            if not any(session.eligible):
                continue
            recording = pipeline.processed_recordings[processed_index]
            processed_index += 1
            event_times = _selected(session.event_times, session.eligible)
            event_ids = _selected(session.event_ids, session.eligible)
            aligned = align_events(
                recording,
                event_times,
                window=self.timecourse.window,
                rate=self.timecourse.rate_hz,
                variable=self.preprocessing.output_variable,
                event_ids=event_ids,
            )
            matches = np.flatnonzero(
                np.asarray(recording.channel.values) == self.channel
            )
            channel_index = int(matches[0])
            matrices.append(
                np.asarray(aligned.values[:, :, channel_index], dtype=float)
            )
            count = sum(session.eligible)
            animals.extend([str(session.recording.attrs["subject"])] * count)
            sessions.extend([str(session.recording.attrs["session"])] * count)
            conditions.extend(_selected(session.conditions, session.eligible))
        values = np.concatenate(matrices, axis=0)
        relative_time = np.linspace(
            self.timecourse.window[0],
            self.timecourse.window[1],
            round(
                (self.timecourse.window[1] - self.timecourse.window[0])
                * self.timecourse.rate_hz
            )
            + 1,
        )
        return infer_peri_event_contrast(
            values,
            relative_time,
            animals=tuple(animals),
            sessions=tuple(sessions),
            conditions=tuple(conditions),
            numerator=self.numerator,
            denominator=self.denominator,
            design=self.timecourse.design,
            confidence=self.timecourse.confidence,
            draws=self.timecourse.draws,
            seed=self.timecourse.seed,
        )


def _selected(values: Sequence[T], eligible: Sequence[bool]) -> tuple[T, ...]:
    return tuple(
        value for value, include in zip(values, eligible, strict=True) if include
    )
