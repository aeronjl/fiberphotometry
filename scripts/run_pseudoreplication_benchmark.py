"""Execute the frozen pseudoreplication benchmark protocol v0.4."""

from __future__ import annotations

import json

import numpy as np

from fiberphotometry import (
    Contrast,
    Estimand,
    Factor,
    ObservationTable,
    ResamplingPlan,
    StudyDesign,
    Unit,
    hierarchical_bootstrap,
)


def main() -> None:
    rows = [_run_study(seed) for seed in range(100)]
    naive_rate = float(np.mean([row["naive_positive"] for row in rows]))
    hierarchical_rate = float(np.mean([row["hierarchical_positive"] for row in rows]))
    acceptance = {
        "pseudoreplication_challenge": naive_rate >= 0.30,
        "hierarchical_false_positive_rate": hierarchical_rate <= 0.15,
        "hierarchical_improvement": hierarchical_rate <= naive_rate - 0.20,
    }
    print(
        json.dumps(
            {
                "protocol": "v0.4",
                "studies": 100,
                "draws_per_study": 400,
                "naive_false_positive_rate": naive_rate,
                "hierarchical_false_positive_rate": hierarchical_rate,
                "acceptance": acceptance,
                "all_acceptance_met": all(acceptance.values()),
                "runs": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _run_study(seed: int) -> dict[str, float | bool | int]:
    rng = np.random.default_rng(seed)
    animal_ids = np.repeat(np.arange(12), 100)
    conditions_by_animal = np.asarray(["control"] * 6 + ["drug"] * 6)
    conditions = conditions_by_animal[animal_ids]
    animal_intercepts = rng.normal(0, 1, 12)
    outcome = animal_intercepts[animal_ids] + rng.normal(0, 0.3, len(animal_ids))
    table = ObservationTable.from_columns(
        {
            "event_id": [f"e{index}" for index in range(len(animal_ids))],
            "animal": animal_ids.tolist(),
            "condition": conditions.tolist(),
            "outcome": outcome.tolist(),
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        factors=(Factor("condition", "condition", "categorical", "animal"),),
    )
    estimand = Estimand("outcome", Contrast("condition", "drug", "control"), "animal")
    hierarchical = hierarchical_bootstrap(
        table,
        design,
        estimand,
        ResamplingPlan(("animal", "event")),
        interval_method="percentile",
        draws=400,
        seed=seed + 10_000,
    )
    naive_distribution = np.asarray(
        [_naive_difference(outcome, conditions, rng) for _ in range(400)]
    )
    naive_interval = np.quantile(naive_distribution, [0.025, 0.975])
    return {
        "seed": seed,
        "estimate": hierarchical.estimate,
        "naive_positive": bool(naive_interval[0] > 0 or naive_interval[1] < 0),
        "hierarchical_positive": bool(
            hierarchical.confidence_interval[0] > 0
            or hierarchical.confidence_interval[1] < 0
        ),
    }


def _naive_difference(
    outcome: np.ndarray, conditions: np.ndarray, rng: np.random.Generator
) -> float:
    rows = rng.integers(0, len(outcome), len(outcome))
    return float(
        np.mean(outcome[rows][conditions[rows] == "drug"])
        - np.mean(outcome[rows][conditions[rows] == "control"])
    )


if __name__ == "__main__":
    main()
