from fipha.benchmark import run_reference_benchmark


def test_large_transient_benchmark_reports_recovery_metrics() -> None:
    robust = run_reference_benchmark(
        scenario="large_neural_transients", seed=4, method="irls"
    )
    ols = run_reference_benchmark(
        scenario="large_neural_transients", seed=4, method="ols"
    )

    assert robust.neural_correlation > 0.8
    assert robust.null_rms < ols.null_rms
    assert robust.scenario == ols.scenario == "large_neural_transients"
