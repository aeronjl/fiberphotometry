from fiberphotometry import assess_event_confounds
from fiberphotometry.simulate import simulate_recording


def test_event_qc_flags_event_correlated_reference() -> None:
    recording, events = simulate_recording(event_artifact_scale=0.5, seed=3)

    result = assess_event_confounds(recording, events)

    assert "event_correlated_reference" in result.channels[0].warnings


def test_event_qc_flags_lagged_reference() -> None:
    recording, events = simulate_recording(reference_lag_s=0.5, seed=3)

    result = assess_event_confounds(recording, events)

    assert "signal_reference_lag" in result.channels[0].warnings
    assert abs(result.channels[0].derivative_best_lag_s) >= 0.1
