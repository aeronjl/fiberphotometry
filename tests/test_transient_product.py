import numpy as np
import pytest

from fiberphotometry import (
    GuppyTransientDetectorSpec,
    PastaTransientDetectorSpec,
    ProminenceTransientDetectorSpec,
    TransientQuantificationSpec,
    detect_transient_candidates,
    make_recording,
    quantify_transient_candidates,
)


def _recording(time: np.ndarray, **variables: np.ndarray):
    first = next(iter(variables.values()))
    recording = make_recording(
        time=time,
        signal=first,
        channel_names=["green"],
        subject="mouse-1",
        session="session-1",
    )
    for name, values in variables.items():
        recording[name] = (("time", "channel"), values[:, None])
    return recording


def test_prominence_detection_is_separate_from_raw_quantification() -> None:
    time = np.arange(0, 20, 0.02)
    raw = 0.2 + 0.7 * np.exp(-0.5 * ((time - 10) / 0.2) ** 2)
    detection = (raw - np.mean(raw)) / np.std(raw)
    recording = _recording(time, raw_dff=raw, detection_z=detection)

    candidates = detect_transient_candidates(
        recording,
        variable="detection_z",
        spec=ProminenceTransientDetectorSpec(
            minimum_height_z=1,
            minimum_prominence_z=2,
            detrend_window_s=None,
        ),
    )
    quantified = quantify_transient_candidates(
        recording,
        candidates,
        variable="raw_dff",
        spec=TransientQuantificationSpec(
            baseline_start_s=2,
            baseline_end_s=1,
            baseline_method="mean",
        ),
    )

    assert len(candidates.candidates) == len(quantified.events) == 1
    assert candidates.variable == "detection_z"
    assert quantified.variable == "raw_dff"
    assert quantified.detector_variable == "detection_z"
    assert quantified.events[0].detection_value > 5
    assert quantified.events[0].amplitude == pytest.approx(0.7, abs=1e-4)
    assert quantified.events[0].detection_family == "prominence"


def test_pasta_last_local_minimum_controls_candidate_amplitude() -> None:
    time = np.arange(0, 8, 0.1)
    signal = 0.05 * time
    signal += 0.15 * np.exp(-0.5 * ((time - 4.2) / 0.12) ** 2)
    signal += 1.0 * np.exp(-0.5 * ((time - 5.0) / 0.12) ** 2)
    recording = _recording(time, dff=signal)

    candidates = detect_transient_candidates(
        recording,
        variable="dff",
        spec=PastaTransientDetectorSpec(
            amplitude_threshold=0.5,
            baseline_method="last_local_minimum",
            baseline_start_s=1.5,
            baseline_end_s=0.2,
        ),
    )

    assert len(candidates.candidates) == 1
    candidate = candidates.candidates[0]
    assert candidate.peak_time == pytest.approx(5.0)
    assert candidate.detection_baseline is not None
    assert candidate.detection_amplitude == pytest.approx(
        candidate.detection_value - candidate.detection_baseline
    )


def test_guppy_two_threshold_mad_excludes_large_values_before_second_threshold() -> (
    None
):
    rng = np.random.default_rng(42)
    time = np.arange(0, 10, 0.1)
    signal = rng.normal(0, 1, len(time))
    signal[50] = 10.0
    recording = _recording(time, zscore=signal)

    candidates = detect_transient_candidates(
        recording,
        variable="zscore",
        spec=GuppyTransientDetectorSpec(
            chunk_duration_s=10,
            high_amplitude_mad=4,
            detection_mad=5,
        ),
    )

    assert [candidate.sample_index for candidate in candidates.candidates] == [50]
    candidate = candidates.candidates[0]
    without_high_event = np.delete(signal, 50)
    expected_median = np.median(without_high_event)
    expected_mad = np.median(np.abs(without_high_event - expected_median))
    assert candidate.detection_baseline == pytest.approx(expected_median)
    assert candidate.detection_threshold == pytest.approx(
        expected_median + 5 * expected_mad
    )
    assert candidate.detection_score == pytest.approx(10 - expected_median)


def test_quantification_does_not_bridge_gap_and_retains_detection() -> None:
    time = np.arange(0, 12, 0.02)
    signal = np.exp(-0.5 * ((time - 6) / 0.2) ** 2)
    signal[(time > 6.05) & (time < 7)] = np.nan
    recording = _recording(time, dff=signal)
    candidates = detect_transient_candidates(
        recording,
        variable="dff",
        spec=PastaTransientDetectorSpec(
            amplitude_threshold=0.3,
            baseline_start_s=1.5,
            baseline_end_s=0.5,
        ),
    )

    quantified = quantify_transient_candidates(recording, candidates, variable="dff")

    assert candidates.candidates
    assert not quantified.events
    assert any(
        exclusion.reason == "incomplete_shape" for exclusion in quantified.exclusions
    )


def test_close_quantified_candidates_receive_compound_group_and_rank() -> None:
    time = np.arange(0, 15, 0.02)
    signal = np.zeros_like(time)
    signal += np.exp(-0.5 * ((time - 8) / 0.1) ** 2)
    signal += 0.8 * np.exp(-0.5 * ((time - 8.8) / 0.1) ** 2)
    recording = _recording(time, dff=signal)
    candidates = detect_transient_candidates(
        recording,
        variable="dff",
        spec=PastaTransientDetectorSpec(
            amplitude_threshold=0.4,
            baseline_start_s=1,
            baseline_end_s=0.2,
        ),
    )

    quantified = quantify_transient_candidates(
        recording,
        candidates,
        variable="dff",
        spec=TransientQuantificationSpec(
            baseline_start_s=1,
            baseline_end_s=0.2,
            compound_window_s=2,
        ),
    )

    assert len(quantified.events) == 2
    assert [event.compound_group for event in quantified.events] == [1, 1]
    assert [event.compound_rank for event in quantified.events] == [1, 2]
    assert quantified.summaries[0].count == 2
