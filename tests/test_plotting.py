import matplotlib

from fiberphotometry.plotting import plot_event_diagnostics
from fiberphotometry.simulate import simulate_recording

matplotlib.use("Agg")


def test_plot_event_diagnostics_returns_three_axes() -> None:
    recording, events = simulate_recording(duration=35, seed=1)

    figure, axes = plot_event_diagnostics(recording, events)

    assert len(axes) == 3
    figure.clear()
