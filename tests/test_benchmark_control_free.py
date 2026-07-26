import numpy as np

from fiberphotometry.benchmark_control_free import run_control_free_benchmark


def test_control_free_benchmark_recovers_single_exponential() -> None:
    result = run_control_free_benchmark(
        scenario="single_exponential", method="double_exponential", seed=0
    )

    assert np.isfinite(result.ground_truth_correlation)
    assert result.ground_truth_rmse < 0.015
    assert abs(result.event_amplitude_relative_bias) < 0.2
