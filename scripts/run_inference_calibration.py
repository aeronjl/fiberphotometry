"""Execute the frozen scalar-inference calibration protocol v0.5."""

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

SCENARIOS = (
    "between_12_balanced",
    "between_24_balanced",
    "between_12_imbalanced",
    "between_12_missing",
    "within_12_paired",
)


def main() -> None:
    runs = [_run(scenario, seed) for scenario in SCENARIOS for seed in range(40)]
    coverage = {
        scenario: {
            method: float(
                np.mean(
                    [
                        row[f"{method}_covers_zero"]
                        for row in runs
                        if row["scenario"] == scenario
                    ]
                )
            )
            for method in ("percentile", "basic", "bca")
        }
        for scenario in SCENARIOS
    }
    at_least_one = all(max(methods.values()) >= 0.8 for methods in coverage.values())
    bca = all(methods["bca"] >= 0.8 for methods in coverage.values())
    eligible_defaults = [
        method
        for method in ("percentile", "basic", "bca")
        if all(0.85 <= methods[method] <= 1.0 for methods in coverage.values())
    ]
    payload = {
        "protocol": "v0.5",
        "studies_per_scenario": 40,
        "draws_per_study": 250,
        "coverage": coverage,
        "acceptance": {
            "at_least_one_method_each_scenario": at_least_one,
            "bca_minimum_coverage": bca,
        },
        "default_eligible_methods": eligible_defaults,
        "runs": runs,
    }
    payload["all_acceptance_met"] = all(payload["acceptance"].values())
    print(json.dumps(payload, indent=2, sort_keys=True))


def _run(scenario: str, seed: int) -> dict[str, str | int | bool]:
    table, design, estimand = _simulate(scenario, seed)
    result = hierarchical_bootstrap(
        table,
        design,
        estimand,
        ResamplingPlan(("animal", "event")),
        draws=250,
        seed=seed + 10_000,
        interval_method="bca",
    )
    finite = result.distribution[np.isfinite(result.distribution)]
    percentile = np.quantile(finite, [0.025, 0.975])
    basic = np.asarray(
        [2 * result.estimate - percentile[1], 2 * result.estimate - percentile[0]]
    )
    return {
        "scenario": scenario,
        "seed": seed,
        "percentile_covers_zero": _covers(percentile),
        "basic_covers_zero": _covers(basic),
        "bca_covers_zero": _covers(np.asarray(result.confidence_interval)),
    }


def _simulate(
    scenario: str, seed: int
) -> tuple[ObservationTable, StudyDesign, Estimand]:
    rng = np.random.default_rng(seed)
    animals = 24 if scenario == "between_24_balanced" else 12
    paired = scenario == "within_12_paired"
    if paired:
        animal_ids = np.repeat(np.arange(animals), 100)
        conditions = np.tile(np.repeat(["control", "drug"], 50), animals)
    else:
        animal_ids = np.repeat(np.arange(animals), 100)
        if scenario == "between_12_imbalanced":
            labels = np.asarray(["control"] * 8 + ["drug"] * 4)
        else:
            labels = np.asarray(
                ["control"] * (animals // 2) + ["drug"] * (animals // 2)
            )
        conditions = labels[animal_ids]
    outcome = rng.normal(0, 1, animals)[animal_ids] + rng.normal(
        0, 0.3, len(animal_ids)
    )
    keep = np.ones(len(outcome), dtype=bool)
    if scenario == "between_12_missing":
        keep = rng.random(len(outcome)) >= 0.3
    animal_ids, conditions, outcome = animal_ids[keep], conditions[keep], outcome[keep]
    table = ObservationTable.from_columns(
        {
            "event_id": [f"e{index}" for index in range(len(outcome))],
            "animal": animal_ids.tolist(),
            "condition": conditions.tolist(),
            "outcome": outcome.tolist(),
        }
    )
    design = StudyDesign(
        observation_id="event_id",
        units=(Unit("animal", "animal"), Unit("event", "event_id", "animal")),
        factors=(
            Factor(
                "condition",
                "condition",
                "categorical",
                "event" if paired else "animal",
            ),
        ),
    )
    estimand = Estimand("outcome", Contrast("condition", "drug", "control"), "animal")
    return table, design, estimand


def _covers(interval: np.ndarray) -> bool:
    return bool(interval[0] <= 0 <= interval[1])


if __name__ == "__main__":
    main()
