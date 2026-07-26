"""Execute the frozen control-free bleaching benchmark v0.2."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from fiberphotometry.benchmark_control_free import (
    run_baseline_fidelity_benchmark,
    run_normalization_benchmark,
)

SCENARIOS = ("single_exponential", "double_exponential", "slow_drift")
METHODS = ("double_exponential", "asls")
RATES = (10.0, 20.0, 40.0)
MECHANISMS = ("indicator_bleaching", "autofluorescence_bleaching")
NORMALIZATIONS = ("divide", "subtract")


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "benchmarks/control-free-v0.2.json",
    )
    args = parser.parse_args()
    baseline_runs = [
        run_baseline_fidelity_benchmark(
            scenario=scenario, method=method, rate_hz=rate, seed=seed
        )
        for scenario in SCENARIOS
        for method in METHODS
        for rate in RATES
        for seed in range(20)
    ]
    baseline_summaries: dict[str, dict[str, dict[str, object]]] = {}
    acceptance: dict[str, bool] = {}
    for scenario in SCENARIOS:
        baseline_summaries[scenario] = {}
        method_passes = []
        for method in METHODS:
            rates = {}
            method_cell_passes = []
            rate_baseline_rmse = []
            for rate in RATES:
                selected = [
                    run
                    for run in baseline_runs
                    if run.scenario == scenario
                    and run.method == method
                    and run.rate_hz == rate
                ]
                baseline_rmse = _median(selected, "baseline_relative_rmse")
                event_bias = _median(selected, "event_amplitude_relative_bias")
                cell_passes = baseline_rmse <= 0.01 and abs(event_bias) <= 0.1
                rates[str(rate)] = {
                    "baseline_relative_rmse_median": baseline_rmse,
                    "corrected_trace_correlation_median": _median(
                        selected, "corrected_trace_correlation"
                    ),
                    "corrected_trace_rmse_median": _median(
                        selected, "corrected_trace_rmse"
                    ),
                    "event_amplitude_relative_bias_median": event_bias,
                    "passes": cell_passes,
                }
                rate_baseline_rmse.append(baseline_rmse)
                method_cell_passes.append(cell_passes)
            rate_range = max(rate_baseline_rmse) - min(rate_baseline_rmse)
            method_passes_all = all(method_cell_passes) and rate_range <= 0.005
            baseline_summaries[scenario][method] = {
                "rates": rates,
                "baseline_rmse_range_across_rates": rate_range,
                "passes_all_rates": method_passes_all,
            }
            method_passes.append(method_passes_all)
        acceptance[f"baseline_{scenario}"] = any(method_passes)

    normalization_runs = [
        run_normalization_benchmark(
            mechanism=mechanism,
            normalization=normalization,
            seed=seed,  # type: ignore[arg-type]
        )
        for mechanism in MECHANISMS
        for normalization in NORMALIZATIONS
        for seed in range(20)
    ]
    normalization_summaries = {}
    matched = {
        "indicator_bleaching": "divide",
        "autofluorescence_bleaching": "subtract",
    }
    for mechanism in MECHANISMS:
        normalization_summaries[mechanism] = {}
        for normalization in NORMALIZATIONS:
            selected = [
                run
                for run in normalization_runs
                if run.mechanism == mechanism and run.normalization == normalization
            ]
            change = _median(selected, "fractional_amplitude_change")
            normalization_summaries[mechanism][normalization] = {
                "fractional_amplitude_change_median": change,
                "mechanism_matched": normalization == matched[mechanism],
            }
            if normalization == matched[mechanism]:
                acceptance[f"normalization_{mechanism}"] = abs(change) <= 0.1

    payload = {
        "protocol": "control-free-v0.2",
        "baseline_summaries": baseline_summaries,
        "normalization_summaries": normalization_summaries,
        "acceptance": acceptance,
        "all_acceptance_met": all(acceptance.values()),
        "baseline_runs": [asdict(run) for run in baseline_runs],
        "normalization_runs": [asdict(run) for run in normalization_runs],
    }
    args.output.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")


def _median(runs: list[object], attribute: str) -> float:
    return float(np.median([getattr(run, attribute) for run in runs]))


if __name__ == "__main__":
    main()
