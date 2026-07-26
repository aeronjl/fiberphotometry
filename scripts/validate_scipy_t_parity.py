"""Validate public t intervals against independent SciPy implementations."""

from __future__ import annotations

import json

import numpy as np
from scipy.stats import ttest_ind, ttest_rel

from fiberphotometry import (
    Contrast,
    Estimand,
    Factor,
    ObservationTable,
    StudyDesign,
    Unit,
    unit_t_interval,
)


def main() -> None:
    rng = np.random.default_rng(71)
    control, treatment = rng.normal(0, 1, 9), rng.normal(0.5, 1.7, 14)
    paired_control = rng.normal(0, 1, 12)
    paired_treatment = paired_control + rng.normal(0.4, 0.3, 12)
    comparisons = []
    for left, right, paired in (
        (control, treatment, False),
        (paired_control, paired_treatment, True),
    ):
        table, design, estimand = _table(left, right, paired)
        ours = unit_t_interval(
            table, design, estimand, mode="paired" if paired else "welch"
        )
        external = (
            ttest_rel(right, left)
            if paired
            else ttest_ind(right, left, equal_var=False)
        )
        comparisons.append(
            {
                "method": ours.method,
                "estimate_difference": abs(
                    ours.estimate - float(np.mean(right) + -np.mean(left))
                ),
                "p_value_difference": abs(ours.p_value - float(external.pvalue)),
                "interval_max_difference": float(
                    np.max(
                        np.abs(
                            np.asarray(ours.confidence_interval)
                            - np.asarray(external.confidence_interval())
                        )
                    )
                ),
            }
        )
    print(
        json.dumps(
            {
                "comparisons": comparisons,
                "pass": all(
                    max(
                        row[value]
                        for value in (
                            "estimate_difference",
                            "p_value_difference",
                            "interval_max_difference",
                        )
                    )
                    < 1e-12
                    for row in comparisons
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _table(
    control: np.ndarray, treatment: np.ndarray, paired: bool
) -> tuple[ObservationTable, StudyDesign, Estimand]:
    if paired:
        units, conditions = (
            np.repeat(np.arange(len(control)), 2),
            np.tile(["control", "drug"], len(control)),
        )
        outcomes, assignment = np.column_stack([control, treatment]).ravel(), "event"
    else:
        units = np.arange(len(control) + len(treatment))
        conditions = np.asarray(["control"] * len(control) + ["drug"] * len(treatment))
        outcomes, assignment = np.concatenate([control, treatment]), "animal"
    table = ObservationTable.from_columns(
        {
            "event_id": [f"e{i}" for i in range(len(outcomes))],
            "animal": units.tolist(),
            "condition": conditions.tolist(),
            "outcome": outcomes.tolist(),
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        factors=(Factor("condition", "condition", "categorical", assignment),),
    )
    return (
        table,
        design,
        Estimand("outcome", Contrast("condition", "drug", "control"), "animal"),
    )


if __name__ == "__main__":
    main()
