import numpy as np
import pytest
import xarray as xr

from fiberphotometry import align_events, make_recording, summarize_event_windows
from fiberphotometry.events import (
    condition_exclusion_warning,
    condition_reconstruction_warning,
)


def _two_event_recording() -> xr.Dataset:
    index = np.arange(400)
    time = index / 10
    signal = np.zeros(400)
    first = (index >= 80) & (index < 100)
    signal[first] = np.where(index[first] % 2 == 0, -1.0, 1.0)
    signal[(index >= 100) & (index < 120)] = 5.0
    second = (index >= 280) & (index < 300)
    signal[second] = np.where(index[second] % 2 == 0, -2.0, 2.0)
    signal[(index >= 300) & (index < 320)] = 20.0
    return make_recording(time=time, signal=signal, subject="m", session="s")


def test_align_events_retains_events_and_metadata() -> None:
    time = np.arange(0, 10.1, 0.1)
    recording = make_recording(
        time=time,
        signal=time,
        subject="mouse-1",
        session="session-1",
    )

    aligned = align_events(
        recording,
        [2, 8],
        window=(-1, 1),
        rate=10,
        variable="signal",
        event_ids=["a", "b"],
    )

    assert aligned.dims == ("event", "relative_time", "channel")
    assert aligned.sizes["event"] == 2
    assert np.isclose(aligned.sel(event="a", relative_time=0).item(), 2)
    assert aligned.attrs["subject"] == "mouse-1"


def test_summarize_event_windows_uses_acquired_samples() -> None:
    recording = make_recording(
        time=[0.0, 0.5, 1.0, 1.5, 2.0],
        signal=[0.0, 2.0, 4.0, 8.0, 16.0],
        subject="mouse",
        session="session",
    )

    summary = summarize_event_windows(
        recording,
        [1.0],
        baseline=(-1.0, 0.0),
        response=(0.0, 1.0),
        variable="signal",
    )

    assert summary.baseline_mean.item() == 1.0
    assert summary.response_mean.item() == 6.0
    assert summary.delta.item() == 5.0
    assert summary.event_disposition.item() == "complete"
    assert summary.baseline_finite_fraction.item() == 1.0
    assert summary.response_finite_fraction.item() == 1.0
    assert summary.baseline_interpolated_fraction.item() == 0.0
    assert summary.response_interpolated_fraction.item() == 0.0


def test_event_alignment_does_not_bridge_protected_nan_gap() -> None:
    recording = make_recording(
        time=[0.0, 1.0, 2.0, 3.0, 4.0],
        signal=[0.0, 1.0, np.nan, 3.0, 4.0],
        subject="mouse",
        session="gap",
    )

    aligned = align_events(recording, [2.0], window=(-1, 1), rate=2, variable="signal")
    summary = summarize_event_windows(
        recording,
        [2.0],
        baseline=(-1.0, 0.0),
        response=(0.0, 1.0),
        variable="signal",
    )

    assert np.array_equal(
        np.isfinite(aligned.values[0, :, 0]),
        [True, False, False, False, True],
    )
    assert np.isnan(summary.response_mean.item())
    assert summary.response_finite_fraction.item() == 0.0
    assert summary.event_disposition.item() == "event_inside_gap"


def test_summarize_event_windows_accepts_a_session_without_events() -> None:
    recording = make_recording(
        time=np.arange(200) / 10,
        signal=np.ones(200),
        subject="mouse",
        session="session",
    )
    populated = summarize_event_windows(
        recording,
        [10.0],
        baseline=(-5.0, 0.0),
        response=(0.0, 5.0),
        variable="signal",
    )

    empty = summarize_event_windows(
        recording,
        [],
        baseline=(-5.0, 0.0),
        response=(0.0, 5.0),
        variable="signal",
    )

    assert empty.sizes["event"] == 0
    assert empty.sizes["channel"] == populated.sizes["channel"]
    assert set(empty.data_vars) == set(populated.data_vars)
    assert empty.delta.dims == ("event", "channel")
    assert empty.event_time.dims == ("event",)
    assert empty.attrs["source_variable"] == "signal"


def test_baseline_z_summary_matches_analytic_z_scores() -> None:
    recording = _two_event_recording()

    summary = summarize_event_windows(
        recording,
        [10.0, 30.0],
        baseline=(-2.0, 0.0),
        response=(0.0, 2.0),
        variable="signal",
        normalization="baseline_z",
    )

    assert summary.baseline_mean.values[:, 0] == pytest.approx([0.0, 0.0], abs=1e-12)
    assert summary.response_mean.values[:, 0] == pytest.approx([5.0, 10.0], abs=1e-12)
    assert summary.delta.values[:, 0] == pytest.approx([5.0, 10.0], abs=1e-12)
    assert summary.attrs["normalization"] == "baseline_z"
    assert summary.attrs["units"] == "baseline SD"
    assert summary.attrs["degenerate_baseline_count"] == 0
    assert summary.response_mean.attrs["units"] == "baseline SD"


def test_robust_z_summary_uses_the_scaled_median_absolute_deviation() -> None:
    recording = _two_event_recording()

    summary = summarize_event_windows(
        recording,
        [10.0, 30.0],
        baseline=(-2.0, 0.0),
        response=(0.0, 2.0),
        variable="signal",
        normalization="robust_z",
    )

    assert summary.response_mean.values[:, 0] == pytest.approx(
        [5.0 / 1.4826, 20.0 / (1.4826 * 2)], abs=1e-12
    )
    assert summary.attrs["units"] == "baseline robust SD (1.4826 * MAD)"


def test_unnormalized_summary_is_unchanged_by_the_new_parameter() -> None:
    recording = _two_event_recording()
    common = dict(baseline=(-2.0, 0.0), response=(0.0, 2.0), variable="signal")

    default = summarize_event_windows(recording, [10.0, 30.0], **common)
    explicit = summarize_event_windows(
        recording, [10.0, 30.0], **common, normalization="none"
    )

    assert np.array_equal(default.delta.values, explicit.delta.values)
    assert default.response_mean.values[:, 0] == pytest.approx([5.0, 20.0])
    assert default.attrs["normalization"] == "none"
    assert default.attrs["units"] == "acquired units"


def test_baseline_z_alignment_normalizes_each_event_separately() -> None:
    recording = _two_event_recording()

    aligned = align_events(
        recording,
        [10.0, 30.0],
        window=(-2.0, 2.0),
        rate=10,
        variable="signal",
        baseline=(-2.0, 0.0),
        normalization="baseline_z",
    )

    baseline = aligned.values[:, aligned.relative_time.values < 0, 0]
    assert baseline.shape == (2, 20)
    assert np.mean(baseline[0]) == pytest.approx(0, abs=1e-9)
    assert np.std(baseline[0]) == pytest.approx(1, abs=1e-9)
    assert np.std(baseline[1]) == pytest.approx(1, abs=1e-9)
    assert aligned.sel(relative_time=1.0, method="nearest").values[
        :, 0
    ] == pytest.approx([5.0, 10.0], abs=1e-9)
    assert aligned.attrs["normalization"] == "baseline_z"
    assert aligned.attrs["units"] == "baseline SD"
    assert aligned.attrs["degenerate_baseline_count"] == 0


def test_flat_baseline_yields_nan_instead_of_an_exploded_z_score() -> None:
    index = np.arange(200)
    signal = np.zeros(200)
    signal[index >= 100] = 5.0
    recording = make_recording(time=index / 10, signal=signal, subject="m", session="s")

    summary = summarize_event_windows(
        recording,
        [10.0],
        baseline=(-2.0, 0.0),
        response=(0.0, 2.0),
        variable="signal",
        normalization="baseline_z",
    )
    aligned = align_events(
        recording,
        [10.0],
        window=(-2.0, 2.0),
        rate=10,
        variable="signal",
        baseline=(-2.0, 0.0),
        normalization="robust_z",
    )

    assert np.isnan(summary.response_mean.item())
    assert np.isnan(summary.delta.item())
    assert summary.attrs["degenerate_baseline_count"] == 1
    assert not np.any(np.isfinite(aligned.values))
    assert aligned.attrs["degenerate_baseline_count"] == 1


def test_normalization_requires_a_declared_baseline_window() -> None:
    recording = _two_event_recording()

    with pytest.raises(ValueError, match="baseline"):
        align_events(
            recording,
            [10.0],
            window=(-2.0, 2.0),
            rate=10,
            variable="signal",
            normalization="baseline_z",
        )
    with pytest.raises(ValueError, match="baseline window"):
        align_events(
            recording,
            [10.0],
            window=(-2.0, 2.0),
            rate=10,
            variable="signal",
            baseline=(-5.0, 0.0),
            normalization="baseline_z",
        )


def test_alignment_and_summary_share_one_default_variable() -> None:
    time = np.arange(200) / 10
    recording = make_recording(
        time=time, signal=np.full(200, 100.0), subject="m", session="s"
    )
    recording["dff"] = (("time", "channel"), np.full((200, 1), 0.25))

    aligned = align_events(recording, [10.0], window=(-1.0, 1.0), rate=10)
    summary = summarize_event_windows(
        recording, [10.0], baseline=(-1.0, 0.0), response=(0.0, 1.0)
    )

    assert aligned.attrs["source_variable"] == "dff"
    assert summary.attrs["source_variable"] == "dff"
    assert summary.baseline_mean.item() == pytest.approx(0.25)


def test_condition_exclusion_warning_detects_imbalanced_complete_events() -> None:
    assert condition_exclusion_warning(
        ["a", "a", "b", "b"],
        ["complete", "complete", "complete", "response_intersects_gap"],
    )
    assert not condition_exclusion_warning(
        ["a", "a", "b", "b"],
        ["complete", "response_intersects_gap"] * 2,
    )
    assert condition_reconstruction_warning(["a", "a", "b", "b"], [0.0, 0.0, 0.0, 0.1])
