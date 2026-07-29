"""Run the frozen descriptive IBL feedback multiverse v0.1."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
from one.api import ONE

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
    ResampleOperation,
    StudyDesign,
    Unit,
)
from fiberphotometry.events import summarize_event_windows
from fiberphotometry.io.ibl import from_ibl_tables
from fiberphotometry.multiverse import (
    ChoiceRef,
    DecisionAlternative,
    DecisionNode,
    MultiverseSpec,
    run_multiverse,
)
from fiberphotometry.planning import create_analysis_plan

SESSIONS = (
    ("fip_13", "b6913f93-e7b1-4faf-ab4d-54261b0e31ea"),
    ("fip_14", "09ade9f3-e9e6-41dc-8e93-1c85a3492650"),
    ("fip_15", "e8455785-cacd-4947-b2b5-89e1e6e88930"),
    ("fip_16", "d94b2ae4-e581-4dee-bc0a-5d8e2b048bf8"),
)


def load_inputs(cache: Path) -> tuple[RecordingInput, ...]:
    one = ONE(
        base_url="https://openalyx.internationalbrainlab.org",
        password="international",
        cache_dir=cache,
        silent=True,
    )
    inputs = []
    for animal, eid in SESSIONS:
        signal = one.load_dataset(
            eid, "photometry.signal.pqt", collection="alf/photometry"
        )
        roi = one.load_dataset(
            eid, "photometryROI.locations.pqt", collection="alf/photometry"
        )
        trials = one.load_object(eid, "trials", collection="alf")
        recording = from_ibl_tables(
            signal_table=signal,
            roi_locations=roi["brain_region"].to_dict(),
            subject=animal,
            session=eid,
        )
        events = np.asarray(trials["feedback_times"], dtype=float)
        feedback = np.asarray(trials["feedbackType"])
        summary = summarize_event_windows(
            recording, events, baseline=(-0.5, 0), response=(0, 0.5)
        )
        dms = int(np.flatnonzero(recording.channel.values == "DMS")[0])
        selected = [
            index
            for index, value in enumerate(summary.delta.values[:, dms])
            if np.isfinite(value) and feedback[index] in (-1, 1)
        ]
        inputs.append(
            RecordingInput(
                recording,
                events[selected],
                [f"{eid}:{index}" for index in selected],
                {
                    "animal": [animal] * len(selected),
                    "session": [eid] * len(selected),
                    "feedback": [
                        "correct" if feedback[index] == 1 else "incorrect"
                        for index in selected
                    ],
                },
            )
        )
    return tuple(inputs)


def build_spec(inputs: tuple[RecordingInput, ...]) -> MultiverseSpec:
    design = StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        factors=(Factor("feedback", "feedback", "categorical", "event"),),
    )
    estimand = Estimand(
        "dff_delta", Contrast("feedback", "correct", "incorrect"), "animal"
    )
    routing_table = ObservationTable.from_columns(
        {
            "event_id": [
                identifier for item in inputs for identifier in item.event_ids
            ],
            "animal": [value for item in inputs for value in item.columns["animal"]],
            "session": [value for item in inputs for value in item.columns["session"]],
            "feedback": [
                value for item in inputs for value in item.columns["feedback"]
            ],
            "dff_delta": [0.0] * sum(len(item.event_ids) for item in inputs),
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
        EventSummarySpec(
            (-0.5, 0), (0, 0.5), "DMS", variable="dff", output_column="dff_delta"
        ),
        design,
        plan,
        schema_version="2",
    )
    correction = DecisionNode(
        "correction",
        "preprocessing",
        (
            DecisionAlternative(
                "ols",
                "ordinary least-squares reference fit",
                (ReferenceDFFOperation("ols"),),
            ),
            DecisionAlternative(
                "irls", "robust reference fit", (ReferenceDFFOperation("irls"),)
            ),
            DecisionAlternative(
                "resample_filter_irls",
                "20 Hz resampling, 3 Hz low-pass, then robust reference fit",
                (
                    ResampleOperation(20, 0.25),
                    LowpassFilterOperation(3),
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
                "standard",
                "half-second baseline and response",
                base.event_summary,
            ),
            DecisionAlternative(
                "early",
                "early quarter-second response",
                EventSummarySpec(
                    (-0.5, 0),
                    (0, 0.25),
                    "DMS",
                    variable="dff",
                    output_column="dff_delta",
                ),
            ),
            DecisionAlternative(
                "displaced_baseline",
                "baseline ending 0.2 seconds before feedback",
                EventSummarySpec(
                    (-1.0, -0.2),
                    (0, 0.5),
                    "DMS",
                    variable="dff",
                    output_column="dff_delta",
                ),
            ),
        ),
    )
    return MultiverseSpec(
        base,
        (correction, window),
        (),
        (ChoiceRef("correction", "irls"), ChoiceRef("window", "standard")),
        "descriptive",
        direction="either",
        leave_one_unit_out=True,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fiberphotometry-ibl-multiverse-") as cache:
        inputs = load_inputs(Path(cache))
        result = run_multiverse(build_spec(inputs), inputs)
    repository = Path(__file__).resolve().parents[1]
    raw = json.loads(
        (repository / "benchmarks/ibl-feedback-analysis-v0.1.json").read_text()
    )
    payload = json.loads(result.to_json())
    payload["raw_fluorescence_comparator"] = {
        "estimate": raw["analysis"]["estimate"],
        "confidence_interval": raw["analysis"]["confidence_interval"],
        "p_value": raw["analysis"]["p_value"],
        "units": "acquired fluorescence",
        "included_in_dff_robustness_summary": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
