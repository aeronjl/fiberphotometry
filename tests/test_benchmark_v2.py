from fiberphotometry.benchmark_v2 import run_benchmark_v2


def test_v2_clean_scenario_recovers_ground_truth() -> None:
    result = run_benchmark_v2(scenario="clean_linear", method="irls", seed=2)

    assert result.ground_truth_correlation > 0.9
    assert result.ground_truth_rmse < 0.02
