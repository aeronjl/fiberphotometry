import numpy as np

from fiberphotometry.benchmark_control_free import (
    run_baseline_fidelity_benchmark,
    run_control_free_benchmark,
    run_normalization_benchmark,
)


def test_control_free_benchmark_recovers_single_exponential() -> None:
    result = run_control_free_benchmark(
        scenario="single_exponential", method="double_exponential", seed=0
    )

    assert np.isfinite(result.ground_truth_correlation)
    assert result.ground_truth_rmse < 0.015
    assert abs(result.event_amplitude_relative_bias) < 0.2


def test_v2_reports_baseline_error_separately() -> None:
    result = run_baseline_fidelity_benchmark(
        scenario="single_exponential",
        method="double_exponential",
        seed=0,
        rate_hz=10,
    )

    assert result.baseline_relative_rmse < 0.01
    assert result.effective_asls_smoothness is None


def test_division_preserves_indicator_bleaching_amplitude() -> None:
    result = run_normalization_benchmark(
        mechanism="indicator_bleaching", normalization="divide", seed=0
    )

    assert abs(result.fractional_amplitude_change) < 0.1
