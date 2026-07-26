"""Scientist-facing workflow for a common event-contrast analysis."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import xarray as xr

from fiberphotometry.design import Factor, ObservationTable, StudyDesign, Unit
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
    run_pipeline,
)
from fiberphotometry.planning import AnalysisPlan, create_analysis_plan


@dataclass(frozen=True)
class EventSession:
    """One recording and the categorical labels attached to its events."""

    recording: xr.Dataset
    event_times: tuple[float, ...]
    conditions: tuple[str, ...]
    event_ids: tuple[str, ...]

    @classmethod
    def from_arrays(
        cls,
        recording: xr.Dataset,
        event_times: Sequence[float],
        conditions: Sequence[str],
        *,
        event_ids: Sequence[str] | None = None,
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
        return cls(recording, times, labels, identifiers)


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
    ) -> Preprocessing:
        """Apply a declared signal-only baseline without claiming artefact removal."""
        variable: Literal["dff", "baseline_subtracted"] = (
            "dff" if normalization == "divide" else "baseline_subtracted"
        )
        units = "ΔF/F" if normalization == "divide" else "acquired fluorescence"
        return cls(
            f"{method.replace('_', ' ')} ({normalization})",
            (
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
    configuration_fingerprint: str | None = None

    def to_json(self) -> str:
        analysis = self.pipeline.analysis
        table = self.pipeline.observation_table
        animals = set(table.values("animal").tolist())
        sessions = set(table.values("session").tolist())
        payload = {
            "title": self.title,
            "preprocessing": asdict(self.preprocessing),
            "spec": json.loads(self.spec.to_json()),
            "blocked_by": self.pipeline.blocked_by,
            "analysis": (
                json.loads(analysis.to_json()) if analysis is not None else None
            ),
            "configuration_sha256": self.configuration_fingerprint,
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
    """High-level, explicit workflow for a within-animal event contrast."""

    sessions: tuple[EventSession, ...]
    numerator: str
    denominator: str
    channel: str
    preprocessing: Preprocessing
    baseline: tuple[float, float] = (-0.5, 0.0)
    response: tuple[float, float] = (0.0, 0.5)
    factor_name: str = "condition"
    title: str = "Fiber photometry event contrast"
    randomized: bool | None = False
    intent: Literal["confirmatory", "exploratory", "descriptive"] = "exploratory"
    blocking_warnings: tuple[str, ...] = ()
    configuration_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.sessions:
            raise ValueError("analysis requires at least one event session")
        if self.numerator == self.denominator:
            raise ValueError("contrast levels must differ")
        levels = {label for session in self.sessions for label in session.conditions}
        missing = {self.numerator, self.denominator} - levels
        if missing:
            raise ValueError(f"contrast levels absent from sessions: {sorted(missing)}")

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
        plan = self.plan(acknowledged_assumptions=acknowledged_assumptions)
        if not plan.executable:
            missing = sorted(
                set(plan.required_assumptions) - set(plan.acknowledged_assumptions)
            )
            message = "unacknowledged analysis assumptions: " + ", ".join(missing)
            raise ValueError(message)
        spec = PipelineSpec(
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
        inputs = tuple(
            RecordingInput(
                session.recording,
                session.event_times,
                session.event_ids,
                {
                    "animal": [str(session.recording.attrs["subject"])]
                    * len(session.event_times),
                    "session": [str(session.recording.attrs["session"])]
                    * len(session.event_times),
                    self.factor_name: session.conditions,
                },
            )
            for session in self.sessions
        )
        return EventAnalysisResult(
            run_pipeline(spec, inputs),
            spec,
            self.title,
            self.preprocessing,
            self.configuration_fingerprint,
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
                Factor(self.factor_name, self.factor_name, "categorical", "event"),
            ),
        )

    def _estimand(self) -> Estimand:
        return Estimand(
            "event_response",
            Contrast(self.factor_name, self.numerator, self.denominator),
            "animal",
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
            count = len(session.event_times)
            columns["event_id"].extend(session.event_ids)
            columns["animal"].extend([str(session.recording.attrs["subject"])] * count)
            columns["session"].extend([str(session.recording.attrs["session"])] * count)
            columns[self.factor_name].extend(session.conditions)
            columns["event_response"].extend([0.0] * count)
        return ObservationTable.from_columns(columns)
