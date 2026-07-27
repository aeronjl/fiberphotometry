import numpy as np

from fiberphotometry import TransientDetectionSpec, detect_transients, make_recording


def _recording(time: np.ndarray, signal: np.ndarray):
    return make_recording(
        time=time,
        signal=signal,
        channel_names=["green"],
        subject="mouse-1",
        session="session-1",
    )


def test_absolute_detector_recovers_known_gaussian_shape() -> None:
    time = np.arange(0, 20, 0.02)
    signal = np.exp(-0.5 * ((time - 10) / 0.2) ** 2)
    result = detect_transients(
        _recording(time, signal),
        variable="signal",
        spec=TransientDetectionSpec(
            threshold_mode="absolute",
            threshold=0.5,
            baseline_statistic="median",
            baseline_gap_s=1.0,
            minimum_distance_s=1,
            bin_width_s=5,
        ),
    )

    assert len(result.events) == 1
    event = result.events[0]
    assert event.peak_time == 10
    assert np.isclose(event.amplitude, 1)
    assert np.isclose(event.full_width_half_height_s, 0.47096, atol=0.002)
    assert event.auc_above_baseline > 0
    assert result.summaries[0].count == 1
    assert result.bins is not None
    assert int(result.bins["count"].sum()) == 1


def test_detector_never_bridges_gap_or_counts_gap_as_exposure() -> None:
    time = np.arange(0, 20, 0.02)
    signal = np.exp(-0.5 * ((time - 10) / 0.2) ** 2)
    signal[(time >= 10.05) & (time < 11)] = np.nan
    result = detect_transients(
        _recording(time, signal),
        variable="signal",
        spec=TransientDetectionSpec(
            threshold_mode="absolute", threshold=0.2, minimum_distance_s=1
        ),
    )

    assert not result.events
    assert any(item.reason == "incomplete_shape" for item in result.exclusions)
    assert result.summaries[0].analyzed_duration_s < 19.1


def test_named_baseline_alternatives_change_amplitude_transparently() -> None:
    time = np.arange(0, 8, 0.02)
    signal = 0.1 * time + np.exp(-0.5 * ((time - 5) / 0.12) ** 2)
    common = dict(
        threshold_mode="absolute",
        threshold=0.5,
        minimum_distance_s=1,
        baseline_duration_s=1,
        baseline_gap_s=0.1,
    )
    median = detect_transients(
        _recording(time, signal),
        variable="signal",
        spec=TransientDetectionSpec(**common, baseline_statistic="median"),
    )
    minimum = detect_transients(
        _recording(time, signal),
        variable="signal",
        spec=TransientDetectionSpec(**common, baseline_statistic="minimum"),
    )

    assert len(median.events) == len(minimum.events) == 1
    assert minimum.events[0].amplitude > median.events[0].amplitude


def test_rolling_mad_threshold_rejects_small_local_maxima() -> None:
    rng = np.random.default_rng(7)
    time = np.arange(0, 30, 0.02)
    signal = rng.normal(0, 0.02, len(time))
    signal += np.exp(-0.5 * ((time - 15) / 0.15) ** 2)
    result = detect_transients(
        _recording(time, signal),
        variable="signal",
        spec=TransientDetectionSpec(
            threshold_mode="rolling_mad",
            threshold=8,
            minimum_distance_s=0.5,
        ),
    )

    assert any(abs(event.peak_time - 15) < 0.05 for event in result.events)
    assert any(item.reason == "below_threshold" for item in result.exclusions)


def test_invalid_spec_is_rejected() -> None:
    time = np.arange(0, 2, 0.02)
    with np.testing.assert_raises_regex(ValueError, "must be positive"):
        detect_transients(
            _recording(time, np.zeros_like(time)),
            variable="signal",
            spec=TransientDetectionSpec(threshold=-1),
        )
