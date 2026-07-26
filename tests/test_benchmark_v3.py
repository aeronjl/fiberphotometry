from fiberphotometry.benchmark_v3 import run_benchmark_v3


def test_v3_detects_event_locked_motion() -> None:
    result = run_benchmark_v3(scenario="event_locked_motion", seed=2)

    assert "event_correlated_reference" in result.warnings
