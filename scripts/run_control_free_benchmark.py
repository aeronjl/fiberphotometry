"""Execute the frozen control-free bleaching benchmark v0.1."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from fipha.benchmark_control_free import run_control_free_benchmark

SCENARIOS = (
    "single_exponential",
    "double_exponential",
    "large_transients",
    "slow_drift",
    "motion_without_control",
    "event_locked_artifact",
)
METHODS = ("double_exponential", "asls")
RECOVERABLE = SCENARIOS[:4]


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "benchmarks/control-free-v0.1.json",
    )
    args = parser.parse_args()
    runs = [
        run_control_free_benchmark(scenario=scenario, method=method, seed=seed)
        for scenario in SCENARIOS
        for method in METHODS
        for seed in range(20)
    ]
    summaries = {}
    for scenario in SCENARIOS:
        summaries[scenario] = {}
        for method in METHODS:
            selected = [
                run for run in runs if run.scenario == scenario and run.method == method
            ]
            correlation = float(
                np.median([run.ground_truth_correlation for run in selected])
            )
            rmse = float(np.median([run.ground_truth_rmse for run in selected]))
            bias = float(
                np.median([run.event_amplitude_relative_bias for run in selected])
            )
            summaries[scenario][method] = {
                "ground_truth_correlation_median": correlation,
                "ground_truth_rmse_median": rmse,
                "event_amplitude_relative_bias_median": bias,
                "passes": correlation >= 0.9 and rmse <= 0.015 and abs(bias) <= 0.2,
            }
    acceptance = {
        scenario: any(summaries[scenario][method]["passes"] for method in METHODS)
        for scenario in RECOVERABLE
    }
    payload = json.dumps(
        {
            "protocol": "control-free-v0.1",
            "summaries": summaries,
            "acceptance": acceptance,
            "all_acceptance_met": all(acceptance.values()),
            "runs": [asdict(run) for run in runs],
        },
        indent=2,
        sort_keys=True,
    )
    args.output.write_text(f"{payload}\n")


if __name__ == "__main__":
    main()
