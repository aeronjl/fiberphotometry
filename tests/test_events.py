import numpy as np

from fiberphotometry import (
    align_events,
    condition_exclusion_warning,
    condition_reconstruction_warning,
    make_recording,
    summarize_event_windows,
)


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
    )

    assert np.array_equal(
        np.isfinite(aligned.values[0, :, 0]),
        [True, False, False, False, True],
    )
    assert np.isnan(summary.response_mean.item())
    assert summary.response_finite_fraction.item() == 0.0
    assert summary.event_disposition.item() == "event_inside_gap"


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
