"""Execute the frozen vectorized scalar-calibration protocol v0.6."""

from __future__ import annotations

import json
from statistics import NormalDist

import numpy as np

SCENARIOS = (
    "gaussian",
    "student_t",
    "heteroscedastic",
    "unequal_counts",
    "informative_missing",
)
METHODS = ("percentile", "basic", "bca")


def main() -> None:
    rows = [_scenario(name, effect) for name in SCENARIOS for effect in (0.0, 0.8)]
    summary = {row["key"]: row for row in rows}
    coverage = {
        method: [summary[f"{name}:0.0"][f"{method}_rate"] for name in SCENARIOS]
        for method in METHODS
    }
    acceptance = {
        "coverage_four_of_five": all(
            sum(0.90 <= value <= 0.99 for value in values) >= 4
            for values in coverage.values()
        ),
        "scenario_has_acceptable_method": all(
            any(0.88 <= coverage[method][index] <= 1.0 for method in METHODS)
            for index in range(len(SCENARIOS))
        ),
        "gaussian_power": max(
            summary["gaussian:0.8"][f"{method}_rate"] for method in METHODS
        )
        > 0.5,
        "unequal_count_power": max(
            summary["unequal_counts:0.8"][f"{method}_rate"] for method in METHODS
        )
        > 0.5,
    }
    eligible = [
        method
        for method, values in coverage.items()
        if all(0.90 <= value <= 0.99 for value in values)
    ]
    print(
        json.dumps(
            {
                "protocol": "v0.6",
                "studies_per_cell": 500,
                "draws": 500,
                "results": summary,
                "acceptance": acceptance,
                "all_acceptance_met": all(acceptance.values()),
                "default_eligible_methods": eligible,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _scenario(name: str, effect: float) -> dict[str, str | float]:
    rejected = {method: [] for method in METHODS}
    widths = {method: [] for method in METHODS}
    for seed in range(500):
        rng = np.random.default_rng(seed + int(effect * 10_000))
        counts = (
            rng.integers(30, 151, 12) if name == "unequal_counts" else np.full(12, 100)
        )
        animal = rng.normal(0, 1, 12)
        means = np.empty(12)
        for index, count in enumerate(counts):
            scale = 0.6 if name == "heteroscedastic" and index >= 6 else 0.3
            noise = (
                rng.standard_t(3, count) * scale / np.sqrt(3)
                if name == "student_t"
                else rng.normal(0, scale, count)
            )
            values = animal[index] + effect * (index >= 6) + noise
            if name == "informative_missing":
                probability = 1 / (1 + np.exp(-values))
                values = values[rng.random(count) > 0.35 * probability]
            means[index] = np.mean(values)
        estimate = float(np.mean(means[6:]) - np.mean(means[:6]))
        control = means[:6][rng.integers(0, 6, (500, 6))].mean(axis=1)
        treatment = means[6:][rng.integers(0, 6, (500, 6))].mean(axis=1)
        distribution = treatment - control
        percentile = np.quantile(distribution, [0.025, 0.975])
        basic = np.asarray([2 * estimate - percentile[1], 2 * estimate - percentile[0]])
        bca = _bca(distribution, means, estimate)
        for method, interval in zip(METHODS, (percentile, basic, bca), strict=True):
            rejected[method].append(not (interval[0] <= 0 <= interval[1]))
            widths[method].append(float(interval[1] - interval[0]))
    return (
        {"key": f"{name}:{effect}", "scenario": name, "effect": effect}
        | {
            f"{method}_rate": float(np.mean(rejected[method]))
            if effect
            else 1 - float(np.mean(rejected[method]))
            for method in METHODS
        }
        | {
            f"{method}_median_width": float(np.median(widths[method]))
            for method in METHODS
        }
    )


def _bca(distribution: np.ndarray, means: np.ndarray, estimate: float) -> np.ndarray:
    jackknife = np.asarray(
        [np.mean(np.delete(means[6:], i)) - np.mean(means[:6]) for i in range(6)]
        + [np.mean(means[6:]) - np.mean(np.delete(means[:6], i)) for i in range(6)]
    )
    centered = np.mean(jackknife) - jackknife
    denominator = 6 * np.sum(centered**2) ** 1.5
    acceleration = np.sum(centered**3) / denominator if denominator else 0.0
    normal = NormalDist()
    bias = normal.inv_cdf(
        float(np.clip(np.mean(distribution < estimate), 1e-6, 1 - 1e-6))
    )
    adjusted = [
        normal.cdf(
            bias + (bias + (z := normal.inv_cdf(p))) / (1 - acceleration * (bias + z))
        )
        for p in (0.025, 0.975)
    ]
    return np.quantile(distribution, adjusted)


if __name__ == "__main__":
    main()
