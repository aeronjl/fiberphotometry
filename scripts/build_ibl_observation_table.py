"""Build and validate a multi-animal IBL event-level inference table."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
from one.api import ONE

from fipha import (
    Contrast,
    Estimand,
    EventSummarySpec,
    Factor,
    ObservationTable,
    PipelineSpec,
    PreprocessingSpec,
    QualityGateSpec,
    RecordingInput,
    StudyDesign,
    Unit,
    run_pipeline,
    validate_design,
)
from fipha.events import summarize_event_windows
from fipha.io.ibl import from_ibl_tables
from fipha.planning import create_analysis_plan

SESSIONS = (
    ("fip_13", "b6913f93-e7b1-4faf-ab4d-54261b0e31ea"),
    ("fip_14", "09ade9f3-e9e6-41dc-8e93-1c85a3492650"),
    ("fip_15", "e8455785-cacd-4947-b2b5-89e1e6e88930"),
    ("fip_16", "d94b2ae4-e581-4dee-bc0a-5d8e2b048bf8"),
)


def main() -> None:
    columns: dict[str, list[object]] = {
        name: [] for name in ("event_id", "animal", "session", "feedback", "dms_delta")
    }
    pipeline_inputs = []
    with tempfile.TemporaryDirectory(prefix="fipha-ibl-design-") as cache:
        one = ONE(
            base_url="https://openalyx.internationalbrainlab.org",
            password="international",
            cache_dir=Path(cache),
            silent=True,
        )
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
            summary = summarize_event_windows(
                recording, events, baseline=(-0.5, 0), response=(0, 0.5)
            )
            dms = int(np.flatnonzero(recording.channel.values == "DMS")[0])
            feedback = np.asarray(trials["feedbackType"])
            selected_indices = []
            for index, value in enumerate(summary.delta.values[:, dms]):
                if np.isfinite(value) and feedback[index] in (-1, 1):
                    selected_indices.append(index)
                    columns["event_id"].append(f"{eid}:{index}")
                    columns["animal"].append(animal)
                    columns["session"].append(eid)
                    columns["feedback"].append(
                        "correct" if feedback[index] == 1 else "incorrect"
                    )
                    columns["dms_delta"].append(float(value))
            pipeline_inputs.append(
                RecordingInput(
                    recording=recording,
                    event_times=events[selected_indices],
                    event_ids=[f"{eid}:{index}" for index in selected_indices],
                    columns={
                        "animal": [animal] * len(selected_indices),
                        "session": [eid] * len(selected_indices),
                        "feedback": [
                            "correct" if feedback[index] == 1 else "incorrect"
                            for index in selected_indices
                        ],
                    },
                )
            )
    table = ObservationTable.from_columns(columns)
    design = StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        factors=(Factor("feedback", "feedback", "categorical", "event"),),
    )
    report = validate_design(table, design)
    estimand = Estimand(
        "dms_delta", Contrast("feedback", "correct", "incorrect"), "animal"
    )
    draft = create_analysis_plan(
        table, design, estimand, randomized=False, intent="descriptive"
    )
    plan = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=False,
        intent="descriptive",
        acknowledged_assumptions=draft.required_assumptions,
    )
    pipeline = run_pipeline(
        PipelineSpec(
            preprocessing=PreprocessingSpec(),
            quality_gate=QualityGateSpec(()),
            event_summary=EventSummarySpec(
                baseline=(-0.5, 0),
                response=(0, 0.5),
                channel="DMS",
                variable="signal",
                output_column="dms_delta",
            ),
            design=design,
            analysis_plan=plan,
        ),
        pipeline_inputs,
    )
    if pipeline.observation_table.columns != table.columns or pipeline.analysis is None:
        raise RuntimeError(
            "pipeline result diverged from the frozen direct calculation"
        )
    print(
        json.dumps(
            {
                "observations": len(table),
                "animals": report.unit_counts["animal"],
                "sessions": report.unit_counts["session"],
                "feedback_counts": {
                    level: columns["feedback"].count(level)
                    for level in ("correct", "incorrect")
                },
                "design_valid": report.valid,
                "design": json.loads(design.to_json()),
                "pipeline_blocked_by": pipeline.blocked_by,
                "analysis": json.loads(pipeline.analysis.to_json()),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
