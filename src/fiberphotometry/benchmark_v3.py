"""Event-aware diagnostic benchmark frozen in protocol v0.3."""

from __future__ import annotations

from dataclasses import dataclass

from fiberphotometry.benchmark_v2 import _parameters, run_benchmark_v2
from fiberphotometry.event_qc import assess_event_confounds
from fiberphotometry.simulate import simulate_recording


@dataclass(frozen=True)
class BenchmarkV3Result:
    scenario: str
    seed: int
    warnings: tuple[str, ...]
    reference_event_effect_sd: float
    derivative_best_lag_s: float
    derivative_lag_improvement: float
    v2_ground_truth_correlation: float
    v2_ground_truth_rmse: float


def run_benchmark_v3(*, scenario: str, seed: int) -> BenchmarkV3Result:
    """Run one frozen v0.3 event-diagnostic scenario using IRLS correction."""
    recording, events = simulate_recording(seed=seed, **_parameters(scenario))
    event_qc = assess_event_confounds(recording, events.tolist()).channels[0]
    v2 = run_benchmark_v2(scenario=scenario, method="irls", seed=seed)
    return BenchmarkV3Result(
        scenario=scenario,
        seed=seed,
        warnings=event_qc.warnings,
        reference_event_effect_sd=event_qc.reference_event_effect_sd,
        derivative_best_lag_s=event_qc.derivative_best_lag_s,
        derivative_lag_improvement=event_qc.derivative_lag_improvement,
        v2_ground_truth_correlation=v2.ground_truth_correlation,
        v2_ground_truth_rmse=v2.ground_truth_rmse,
    )
