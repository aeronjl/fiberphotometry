"""Execute and summarize the frozen event-aware benchmark protocol v0.3."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict

import numpy as np

from fiberphotometry.benchmark_v3 import run_benchmark_v3

SCENARIOS = (
    "clean_linear",
    "large_transients",
    "dropout_blocks",
    "event_locked_motion",
    "nonlinear_coupling",
    "lagged_reference",
    "reference_contamination",
)


def main() -> None:
    runs = [
        run_benchmark_v3(scenario=scenario, seed=seed)
        for scenario in SCENARIOS
        for seed in range(20)
    ]
    summaries = {}
    for scenario in SCENARIOS:
        selected = [run for run in runs if run.scenario == scenario]
        warnings: Counter[str] = Counter()
        for run in selected:
            warnings.update(run.warnings)
        summaries[scenario] = {
            "warning_counts": dict(sorted(warnings.items())),
            "reference_event_effect_sd_median": float(
                np.median([run.reference_event_effect_sd for run in selected])
            ),
            "best_lag_s_median": float(
                np.median([run.derivative_best_lag_s for run in selected])
            ),
            "lag_improvement_median": float(
                np.median([run.derivative_lag_improvement for run in selected])
            ),
        }
    acceptance = {
        "event_locked_motion_detected": summaries["event_locked_motion"][
            "warning_counts"
        ].get("event_correlated_reference", 0)
        >= 18,
        "lagged_reference_detected": summaries["lagged_reference"][
            "warning_counts"
        ].get("signal_reference_lag", 0)
        >= 18,
        "reference_contamination_detected": summaries["reference_contamination"][
            "warning_counts"
        ].get("event_correlated_reference", 0)
        >= 18,
        "clean_false_warnings": sum(
            summaries["clean_linear"]["warning_counts"].values()
        )
        <= 2,
    }
    payload = {
        "protocol": "v0.3",
        "summaries": summaries,
        "acceptance": acceptance,
        "all_acceptance_met": all(acceptance.values()),
        "runs": [asdict(run) for run in runs],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
