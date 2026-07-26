"""Execute and summarize the frozen preprocessing benchmark protocol v0.2."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict

import numpy as np

from fiberphotometry.benchmark_v2 import run_benchmark_v2

SCENARIOS = (
    "clean_linear",
    "large_transients",
    "dropout_blocks",
    "event_locked_motion",
    "nonlinear_coupling",
    "lagged_reference",
    "reference_contamination",
)
METHODS = ("ols", "irls")


def main() -> None:
    runs = [
        run_benchmark_v2(scenario=scenario, method=method, seed=seed)
        for scenario in SCENARIOS
        for method in METHODS
        for seed in range(20)
    ]
    summaries = {}
    for scenario in SCENARIOS:
        for method in METHODS:
            selected = [
                run for run in runs if run.scenario == scenario and run.method == method
            ]
            warnings: Counter[str] = Counter()
            for run in selected:
                warnings.update(run.warnings)
            summaries[f"{scenario}:{method}"] = {
                metric: float(np.median([getattr(run, metric) for run in selected]))
                for metric in (
                    "ground_truth_correlation",
                    "ground_truth_rmse",
                    "event_amplitude_bias",
                    "null_rms",
                    "shared_artifact_slope_error",
                )
            } | {
                "warning_runs": sum(run.warning_count > 0 for run in selected),
                "warning_counts": dict(sorted(warnings.items())),
            }

    clean = summaries["clean_linear:irls"]
    large_ols = summaries["large_transients:ols"]
    large_irls = summaries["large_transients:irls"]
    dropout = summaries["dropout_blocks:irls"]
    criteria = {
        "clean_irls_correlation": clean["ground_truth_correlation"] >= 0.90,
        "clean_irls_event_bias": abs(clean["event_amplitude_bias"]) <= 0.005,
        "large_transient_irls_null_rms": (
            large_irls["null_rms"] <= 0.75 * large_ols["null_rms"]
        ),
        "dropout_irls_correlation": (
            dropout["ground_truth_correlation"]
            >= clean["ground_truth_correlation"] - 0.03
        ),
        "dropout_irls_event_bias": (
            abs(dropout["event_amplitude_bias"])
            <= abs(clean["event_amplitude_bias"]) + 0.005
        ),
    }
    for scenario in SCENARIOS[3:]:
        challenge = summaries[f"{scenario}:irls"]
        correlation_degradation = (
            challenge["ground_truth_correlation"]
            <= 0.8 * clean["ground_truth_correlation"]
        )
        rmse_degradation = (
            challenge["ground_truth_rmse"] >= 1.2 * clean["ground_truth_rmse"]
        )
        criteria[f"{scenario}_diagnostic"] = bool(
            challenge["warning_runs"] or correlation_degradation or rmse_degradation
        )
    payload = {
        "protocol": "v0.2",
        "seeds": list(range(20)),
        "summaries": summaries,
        "acceptance": criteria,
        "all_acceptance_met": all(criteria.values()),
        "runs": [asdict(run) for run in runs],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
