"""Build and validate a multi-animal IBL event-level inference table."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
from one.api import ONE

from fiberphotometry import (
    Contrast,
    Estimand,
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
    create_analysis_plan,
    execute_analysis_plan,
    validate_design,
)
from fiberphotometry.events import summarize_event_windows
from fiberphotometry.io.ibl import from_ibl_tables

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
    with tempfile.TemporaryDirectory(prefix="fiberphotometry-ibl-design-") as cache:
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
            for index, value in enumerate(summary.delta.values[:, dms]):
                if np.isfinite(value) and feedback[index] in (-1, 1):
                    columns["event_id"].append(f"{eid}:{index}")
                    columns["animal"].append(animal)
                    columns["session"].append(eid)
                    columns["feedback"].append(
                        "correct" if feedback[index] == 1 else "incorrect"
                    )
                    columns["dms_delta"].append(float(value))
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
    result = execute_analysis_plan(plan, table, design)
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
                "analysis": json.loads(result.to_json()),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
