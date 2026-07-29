import numpy as np

from fipha.simulate import simulate_recording


def test_simulation_is_reproducible_and_contains_ground_truth() -> None:
    first, first_events = simulate_recording(seed=42)
    second, second_events = simulate_recording(seed=42)

    assert np.array_equal(first.signal.values, second.signal.values)
    assert np.array_equal(first_events, second_events)
    assert "ground_truth_neural" in first
    assert first.attrs["subject"] == "synthetic-subject"
