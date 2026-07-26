import matplotlib
import pytest

from fiberphotometry.plotting import (
    SpecificationCurveEntry,
    plot_event_diagnostics,
    plot_specification_curve,
)
from fiberphotometry.simulate import simulate_recording

matplotlib.use("Agg")


def test_plot_event_diagnostics_returns_three_axes() -> None:
    recording, events = simulate_recording(duration=35, seed=1)

    figure, axes = plot_event_diagnostics(recording, events)

    assert len(axes) == 3
    figure.clear()


def test_plot_specification_curve_orders_estimates_and_marks_decisions() -> None:
    entries = (
        SpecificationCurveEntry(
            "higher", 0.2, (0.1, 0.3), (("fit", "robust"), ("window", "late")), True
        ),
        SpecificationCurveEntry(
            "lower", 0.1, (-0.1, 0.25), (("fit", "ols"), ("window", "early"))
        ),
    )

    figure, axes = plot_specification_curve(entries, effect_label="Difference")

    assert len(axes) == 2
    assert axes[0].get_ylabel() == "Difference"
    assert axes[1].get_yticklabels()[0].get_text() == "fit: ols"
    assert len(axes[1].collections) == 4
    figure.canvas.draw()
    figure.clear()


def test_plot_specification_curve_rejects_inconsistent_decisions() -> None:
    entries = (
        SpecificationCurveEntry("one", 0.1, (0.0, 0.2), (("fit", "ols"),)),
        SpecificationCurveEntry("two", 0.2, (0.1, 0.3), (("window", "late"),)),
    )

    with pytest.raises(ValueError, match="same unique decisions"):
        plot_specification_curve(entries)
