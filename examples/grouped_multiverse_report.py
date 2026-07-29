"""Create the frozen synthetic report used by the formative usability study."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from fipha import (
    BaselineDFFOperation,
    Contrast,
    Estimand,
    EventSummarySpec,
    Factor,
    LowpassFilterOperation,
    ObservationTable,
    PipelineSpec,
    PreprocessingSpec,
    QualityGateSpec,
    RecordingInput,
    StudyDesign,
    Unit,
    make_recording,
)
from fipha.multiverse import (
    ChoiceRef,
    CompatibilityRule,
    DecisionAlternative,
    DecisionNode,
    MultiverseReportGroup,
    MultiverseResult,
    MultiverseSpec,
    RobustnessSummary,
    UniverseResult,
    materialize_multiverse,
)
from fipha.planning import create_analysis_plan


def _inputs() -> tuple[RecordingInput, ...]:
    inputs = []
    for index in range(6):
        time = np.arange(0, 50, 0.05)
        signal = 2.0 + 0.08 * np.sin(time / 7) + 0.015 * np.sin(3 * time)
        event_times = [10.0, 16.0, 22.0, 28.0, 34.0, 40.0]
        conditions = ["control", "drug"] * 3
        for event_time, condition in zip(event_times, conditions, strict=True):
            if condition == "drug":
                signal[(time >= event_time) & (time < event_time + 0.5)] += (
                    0.055 + 0.004 * index
                )
        recording = make_recording(
            time=time,
            signal=signal,
            channel_names=["DMS"],
            subject=f"mouse-{index + 1:02d}",
            session=f"session-{index + 1:02d}",
        )
        inputs.append(
            RecordingInput(
                recording,
                event_times,
                [f"event-{index + 1:02d}-{event + 1:02d}" for event in range(6)],
                {
                    "animal": [f"mouse-{index + 1:02d}"] * 6,
                    "session": [f"session-{index + 1:02d}"] * 6,
                    "condition": conditions,
                },
            )
        )
    return tuple(inputs)


def _base_pipeline(inputs: tuple[RecordingInput, ...]) -> PipelineSpec:
    design = StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand("dms_delta", Contrast("condition", "drug", "control"), "animal")
    table = ObservationTable.from_columns(
        {
            "event_id": [event for item in inputs for event in item.event_ids],
            "animal": [value for item in inputs for value in item.columns["animal"]],
            "session": [value for item in inputs for value in item.columns["session"]],
            "condition": [
                value for item in inputs for value in item.columns["condition"]
            ],
            "dms_delta": [0.0] * 36,
        }
    )
    draft = create_analysis_plan(
        table, design, estimand, randomized=False, intent="exploratory"
    )
    plan = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=False,
        intent="exploratory",
        acknowledged_assumptions=draft.required_assumptions,
    )
    return PipelineSpec(
        PreprocessingSpec(method="ols"),
        QualityGateSpec(()),
        EventSummarySpec((-0.5, 0), (0, 0.5), "DMS", output_column="dms_delta"),
        design,
        plan,
    )


def main() -> None:
    inputs = _inputs()
    base = replace(_base_pipeline(inputs), schema_version="2")
    preprocessing = DecisionNode(
        "normalization",
        "preprocessing",
        (
            DecisionAlternative(
                "divide_4s",
                "published rolling baseline with divisive normalization",
                (
                    BaselineDFFOperation(
                        "rolling_mean", normalization="divide", rolling_window_s=4
                    ),
                ),
            ),
            DecisionAlternative(
                "divide_8s",
                "longer rolling baseline sensitivity analysis",
                (
                    BaselineDFFOperation(
                        "rolling_mean", normalization="divide", rolling_window_s=8
                    ),
                ),
            ),
            DecisionAlternative(
                "subtract_4s",
                "published rolling baseline with subtractive normalization",
                (
                    BaselineDFFOperation(
                        "rolling_mean", normalization="subtract", rolling_window_s=4
                    ),
                ),
            ),
            DecisionAlternative(
                "subtract_8s",
                "longer rolling baseline sensitivity analysis",
                (
                    BaselineDFFOperation(
                        "rolling_mean", normalization="subtract", rolling_window_s=8
                    ),
                ),
            ),
            DecisionAlternative(
                "divide_invalid_filter",
                "retained execution-failure fixture",
                (
                    LowpassFilterOperation(cutoff_hz=1000),
                    BaselineDFFOperation(
                        "rolling_mean", normalization="divide", rolling_window_s=4
                    ),
                ),
            ),
        ),
    )
    windows = DecisionNode(
        "response_window",
        "event_summary",
        (
            DecisionAlternative(
                "500ms",
                "frozen primary response window",
                EventSummarySpec((-0.5, 0), (0, 0.5), "DMS", output_column="dms_delta"),
            ),
            DecisionAlternative(
                "250ms",
                "short response-window sensitivity analysis",
                EventSummarySpec(
                    (-0.5, 0), (0, 0.25), "DMS", output_column="dms_delta"
                ),
            ),
        ),
    )
    spec = MultiverseSpec(
        base,
        (preprocessing, windows),
        (
            CompatibilityRule(
                (
                    ChoiceRef("normalization", "divide_invalid_filter"),
                    ChoiceRef("response_window", "250ms"),
                ),
                "failure fixture is retained once and not duplicated across windows",
            ),
        ),
        (
            ChoiceRef("normalization", "divide_4s"),
            ChoiceRef("response_window", "500ms"),
        ),
        "exploratory",
        smallest_effect=0.005,
        direction="positive",
        leave_one_unit_out=True,
    )
    # This is an interface-comprehension stimulus, not a scientific benchmark.
    # Deterministic illustrative outcomes ensure both unit lanes and every status
    # class under test remain present even as analysis engines evolve.
    estimates = {
        ("divide_4s", "500ms"): 0.032,
        ("divide_4s", "250ms"): 0.028,
        ("divide_8s", "500ms"): 0.030,
        ("divide_8s", "250ms"): 0.026,
        ("subtract_4s", "500ms"): 0.064,
        ("subtract_4s", "250ms"): 0.056,
        ("subtract_8s", "500ms"): 0.060,
        ("subtract_8s", "250ms"): 0.052,
    }
    universes = []
    for universe in materialize_multiverse(spec):
        choices = {choice.node: choice.alternative for choice in universe.choices}
        key = (choices["normalization"], choices["response_window"])
        if universe.incompatibility is not None:
            universes.append(
                UniverseResult(
                    universe.universe_id,
                    universe.choices,
                    "incompatible",
                    None,
                    None,
                    None,
                    universe.pipeline,
                    error=universe.incompatibility,
                )
            )
        elif choices["normalization"] == "divide_invalid_filter":
            universes.append(
                UniverseResult(
                    universe.universe_id,
                    universe.choices,
                    "failed",
                    None,
                    None,
                    None,
                    universe.pipeline,
                    error="cutoff_hz exceeds the Nyquist frequency",
                )
            )
        else:
            estimate = estimates[key]
            universes.append(
                UniverseResult(
                    universe.universe_id,
                    universe.choices,
                    "success",
                    estimate,
                    (estimate * 0.55, estimate * 1.45),
                    0.018,
                    universe.pipeline,
                    is_reference=key == ("divide_4s", "500ms"),
                )
            )
    result = MultiverseResult(
        spec,
        tuple(universes),
        RobustnessSummary(
            total_universes=10,
            valid_universes=9,
            successful_universes=8,
            blocked_universes=0,
            failed_universes=1,
            incompatible_universes=1,
            estimate_range=None,
            median_estimate=None,
            fraction_positive=None,
            fraction_negative=None,
            fraction_meeting_practical_effect=None,
            reference_estimate=0.032,
            decision_summaries=(),
        ),
    )
    groups = (
        MultiverseReportGroup.from_choice(
            result,
            name="Divisive normalization",
            units="ΔF/F",
            node="normalization",
            alternatives=("divide_4s", "divide_8s", "divide_invalid_filter"),
        ),
        MultiverseReportGroup.from_choice(
            result,
            name="Subtractive normalization",
            units="acquired fluorescence",
            node="normalization",
            alternatives=("subtract_4s", "subtract_8s"),
        ),
    )
    destination = result.write_grouped_html(
        Path("usability-study-report.html"),
        groups,
        title="Drug-aligned DMS response robustness",
    )
    print(f"Report written to {destination}")


if __name__ == "__main__":
    main()
