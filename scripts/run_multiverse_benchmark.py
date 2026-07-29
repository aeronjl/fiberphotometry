"""Execute frozen multiverse-engine benchmark v0.9."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict

import numpy as np

from fiberphotometry import (
    Contrast,
    Estimand,
    EventSummarySpec,
    Factor,
    LowpassFilterOperation,
    ObservationTable,
    PipelineSpec,
    QualityGateSpec,
    RecordingInput,
    ReferenceDFFOperation,
    StudyDesign,
    Unit,
    make_recording,
)
from fiberphotometry.multiverse import (
    ChoiceRef,
    CompatibilityRule,
    DecisionAlternative,
    DecisionNode,
    MultiverseSpec,
    materialize_multiverse,
    run_multiverse,
)
from fiberphotometry.planning import create_analysis_plan

EVENTS = np.asarray([5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
CONDITIONS = ("control", "drug", "control", "drug", "control", "drug")


def inputs_for(scenario: str) -> tuple[RecordingInput, ...]:
    output = []
    for animal in range(8):
        rng = np.random.default_rng(1000 + animal)
        time = np.arange(0, 36, 0.05)
        event_signal = np.zeros_like(time)
        for event, condition in zip(EVENTS, CONDITIONS, strict=True):
            if condition == "drug":
                event_signal[(time >= event) & (time < event + 0.5)] = 1
        amplitude = 0.08 + 0.008 * animal
        contamination = 0.0
        if scenario == "null":
            amplitude = 0.0
        elif scenario == "reference_contamination":
            contamination = 0.25
        elif scenario == "influential_animal":
            amplitude = 0.45 if animal == 0 else 0.0
        motion = 0.12 * np.sin(time / 2.7) + 0.03 * np.sin(time * 1.9)
        reference = 1 + motion + contamination * event_signal
        reference += rng.normal(0, 0.006, len(time))
        signal = 2 + 1.4 * motion + amplitude * event_signal
        signal += rng.normal(0, 0.008, len(time))
        recording = make_recording(
            time=time,
            signal=signal,
            reference=reference,
            channel_names=["DMS"],
            subject=f"a{animal}",
            session=f"s{animal}",
        )
        output.append(
            RecordingInput(
                recording,
                EVENTS,
                [f"a{animal}-e{index}" for index in range(len(EVENTS))],
                {
                    "animal": [f"a{animal}"] * len(EVENTS),
                    "session": [f"s{animal}"] * len(EVENTS),
                    "condition": CONDITIONS,
                },
            )
        )
    return tuple(output)


def multiverse_spec(inputs: tuple[RecordingInput, ...]) -> MultiverseSpec:
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
    routing_table = ObservationTable.from_columns(
        {
            "event_id": [
                identifier for item in inputs for identifier in item.event_ids
            ],
            "animal": [value for item in inputs for value in item.columns["animal"]],
            "session": [value for item in inputs for value in item.columns["session"]],
            "condition": [
                value for item in inputs for value in item.columns["condition"]
            ],
            "dms_delta": [0.0] * (len(inputs) * len(EVENTS)),
        }
    )
    draft = create_analysis_plan(
        routing_table, design, estimand, randomized=False, intent="descriptive"
    )
    plan = create_analysis_plan(
        routing_table,
        design,
        estimand,
        randomized=False,
        intent="descriptive",
        acknowledged_assumptions=draft.required_assumptions,
    )
    base = PipelineSpec(
        (ReferenceDFFOperation(),),
        QualityGateSpec(()),
        EventSummarySpec((-0.5, 0), (0, 0.5), "DMS", output_column="dms_delta"),
        design,
        plan,
        schema_version="2",
    )
    correction = DecisionNode(
        "correction",
        "preprocessing",
        (
            DecisionAlternative(
                "ols", "ordinary reference fit", (ReferenceDFFOperation("ols"),)
            ),
            DecisionAlternative(
                "irls", "robust reference fit", (ReferenceDFFOperation("irls"),)
            ),
            DecisionAlternative(
                "filtered_irls",
                "low-pass sensitivity before robust fit",
                (
                    LowpassFilterOperation(4),
                    ReferenceDFFOperation("irls"),
                ),
            ),
            DecisionAlternative(
                "invalid_cutoff",
                "deliberate execution failure fixture",
                (
                    LowpassFilterOperation(1000),
                    ReferenceDFFOperation("irls"),
                ),
            ),
        ),
    )
    window = DecisionNode(
        "window",
        "event_summary",
        (
            DecisionAlternative(
                "wide",
                "full simulated transient",
                EventSummarySpec((-0.5, 0), (0, 0.5), "DMS", output_column="dms_delta"),
            ),
            DecisionAlternative(
                "narrow",
                "early transient sensitivity",
                EventSummarySpec(
                    (-0.25, 0), (0, 0.25), "DMS", output_column="dms_delta"
                ),
            ),
        ),
    )
    return MultiverseSpec(
        base,
        (correction, window),
        (
            CompatibilityRule(
                (
                    ChoiceRef("correction", "invalid_cutoff"),
                    ChoiceRef("window", "narrow"),
                ),
                "deliberately excluded invalid benchmark combination",
            ),
        ),
        (ChoiceRef("correction", "irls"), ChoiceRef("window", "wide")),
        "descriptive",
        smallest_effect=0.01,
        direction="positive",
        leave_one_unit_out=True,
    )


def main() -> None:
    output = {}
    stable_identifiers = True
    for scenario in (
        "positive",
        "null",
        "reference_contamination",
        "influential_animal",
    ):
        inputs = inputs_for(scenario)
        spec = multiverse_spec(inputs)
        identifiers = [item.universe_id for item in materialize_multiverse(spec)]
        stable_identifiers &= identifiers == [
            item.universe_id for item in materialize_multiverse(spec)
        ]
        result = run_multiverse(spec, inputs)
        output[scenario] = {
            "status_counts": dict(Counter(item.status for item in result.universes)),
            "summary": asdict(result.summary),
            "leave_one_out": [asdict(item) for item in result.leave_one_out],
        }
    output["engine_checks"] = {
        "stable_identifiers": stable_identifiers,
        "expected_universes": len(
            materialize_multiverse(multiverse_spec(inputs_for("positive")))
        ),
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
