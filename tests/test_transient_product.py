import json

import numpy as np
import pytest

from fiberphotometry import (
    GuppyTransientDetectorSpec,
    PastaTransientDetectorSpec,
    ProminenceTransientDetectorSpec,
    TransientCandidate,
    TransientCandidateResult,
    TransientQuantificationSpec,
    TransientThresholdCalibrationSpec,
    TransientWaveformSpec,
    calibrate_transient_thresholds,
    cut_transient_waveforms,
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


def test_control_threshold_is_frozen_bound_and_applied_to_pasta_scores() -> None:
    rng = np.random.default_rng(91)
    time = np.arange(0, 120, 0.05)
    control = rng.normal(0, 0.03, len(time))
    control_recording = _recording(time, dff=control)
    detector = PastaTransientDetectorSpec(
        amplitude_threshold=0.01,
        baseline_start_s=1,
        baseline_end_s=0.2,
        minimum_distance_s=0.1,
    )
    calibration = TransientThresholdCalibrationSpec(
        estimator="empirical_quantile",
        quantile=0.995,
        minimum_score_count=100,
    )

    frozen = calibrate_transient_thresholds(
        control_recording,
        variable="dff",
        detector_spec=detector,
        source_role="negative_control",
        source_id="fluorophore-negative-control-01",
        preprocessing_fingerprint="sha256:control-pipeline",
        calibration_spec=calibration,
    )
    repeated = calibrate_transient_thresholds(
        control_recording,
        variable="dff",
        detector_spec=detector,
        source_role="negative_control",
        source_id="fluorophore-negative-control-01",
        preprocessing_fingerprint="sha256:control-pipeline",
        calibration_spec=calibration,
    )

    threshold = frozen.for_channel("green").threshold
    assert threshold > detector.amplitude_threshold
    assert frozen.calibration_fingerprint == repeated.calibration_fingerprint
    assert len(frozen.calibration_fingerprint) == 64
    assert json.loads(frozen.to_json())["source_role"] == "negative_control"

    outcome = rng.normal(0, 0.01, len(time))
    outcome += 0.5 * threshold * np.exp(-0.5 * ((time - 40) / 0.08) ** 2)
    outcome += 3.0 * threshold * np.exp(-0.5 * ((time - 80) / 0.08) ** 2)
    result = detect_transient_candidates(
        _recording(time, dff=outcome),
        variable="dff",
        spec=detector,
        frozen_thresholds=frozen,
    )

    assert any(abs(item.peak_time - 80) < 0.1 for item in result.candidates)
    assert all(item.frozen_score_threshold == threshold for item in result.candidates)
    rejected = [
        item for item in result.exclusions if item.reason == "below_frozen_threshold"
    ]
    assert rejected
    assert any(abs(item.peak_time - 40) < 0.1 for item in rejected)
    assert all(item.required_score == threshold for item in rejected)
    with pytest.raises(ValueError, match="different detector spec"):
        detect_transient_candidates(
            _recording(time, dff=outcome),
            variable="dff",
            spec=PastaTransientDetectorSpec(
                amplitude_threshold=0.02,
                baseline_start_s=1,
                baseline_end_s=0.2,
                minimum_distance_s=0.1,
            ),
            frozen_thresholds=frozen,
        )


@pytest.mark.parametrize(
    "detector",
    [
        GuppyTransientDetectorSpec(
            chunk_duration_s=10,
            high_amplitude_mad=4,
            detection_mad=3,
        ),
        ProminenceTransientDetectorSpec(
            minimum_height_z=0.5,
            minimum_prominence_z=0.5,
            minimum_distance_s=0.1,
            detrend_window_s=None,
        ),
    ],
)
def test_frozen_threshold_calibration_supports_all_score_families(detector) -> None:
    rng = np.random.default_rng(8)
    time = np.arange(0, 90, 0.05)
    recording = _recording(time, detection=rng.normal(0, 1, len(time)))

    frozen = calibrate_transient_thresholds(
        recording,
        variable="detection",
        detector_spec=detector,
        source_role="baseline",
        source_id="pre-task-baseline",
        preprocessing_fingerprint="sha256:detection-stream",
        calibration_spec=TransientThresholdCalibrationSpec(
            estimator="median_mad",
            mad_multiplier=4,
            minimum_score_count=50,
        ),
    )

    assert frozen.detector_spec.family == detector.family
    assert frozen.for_channel("green").score_count >= 50
    assert frozen.for_channel("green").threshold > 0

    outcome = rng.normal(0, 1, len(time))
    outcome[len(time) // 2] = 20
    detected = detect_transient_candidates(
        _recording(time, detection=outcome),
        variable="detection",
        spec=detector,
        frozen_thresholds=frozen,
    )
    assert any(item.sample_index == len(time) // 2 for item in detected.candidates)
    assert all(
        item.frozen_score_threshold == frozen.for_channel("green").threshold
        for item in detected.candidates
    )


def _manual_candidate(index: int, time: np.ndarray) -> TransientCandidate:
    return TransientCandidate(
        candidate_id=f"green:manual:{index}",
        family="pasta",
        channel="green",
        sample_index=index,
        peak_time=float(time[index]),
        detection_value=1.0,
        detection_baseline=0.0,
        detection_amplitude=1.0,
        detection_threshold=0.1,
        detection_score=1.0,
    )


def test_gap_bounded_waveforms_retain_qc_and_gate_quantification() -> None:
    time = np.arange(0, 10, 0.01)
    signal = np.exp(-0.5 * ((time - 2) / 0.08) ** 2)
    signal += np.exp(-0.5 * ((time - 5) / 0.08) ** 2)
    signal[(time >= 5.45) & (time < 6.0)] = np.nan
    recording = _recording(time, dff=signal)
    detector = PastaTransientDetectorSpec(
        amplitude_threshold=0.1,
        baseline_start_s=0.8,
        baseline_end_s=0.2,
    )
    candidates = TransientCandidateResult(
        detector,
        "dff",
        (_manual_candidate(200, time), _manual_candidate(500, time)),
        (),
    )

    waveforms = cut_transient_waveforms(
        recording,
        candidates,
        variable="dff",
        spec=TransientWaveformSpec(pre_peak_s=0.5, post_peak_s=1.0),
    )

    clean = waveforms.for_candidate("green:manual:200")
    truncated = waveforms.for_candidate("green:manual:500")
    assert clean.status == "pass"
    assert truncated.status == "fail"
    assert truncated.post_coverage_s < 0.5
    assert "post_window_truncated" in {item.code for item in truncated.issues}
    assert np.all(np.diff(truncated.relative_time_s) > 0)
    assert max(truncated.relative_time_s) < 0.5
    assert len(waveforms.evidence_fingerprint) == 64
    dataset = waveforms.to_xarray()
    assert dataset.sizes["event"] == 2
    assert dataset.attrs["interpretation"].endswith("no interpolation")

    quantified = quantify_transient_candidates(
        recording,
        candidates,
        variable="dff",
        spec=TransientQuantificationSpec(
            baseline_start_s=0.8,
            baseline_end_s=0.2,
            require_waveform_qc=True,
        ),
        waveforms=waveforms,
    )
    assert [item.candidate_id for item in quantified.events] == ["green:manual:200"]
    assert quantified.waveform_fingerprint == waveforms.evidence_fingerprint
    assert [item.reason for item in quantified.exclusions] == ["waveform_qc_failed"]


def test_waveform_qc_flags_nearby_events_flat_steps_and_detector_rails() -> None:
    time = np.arange(0, 6, 0.01)
    signal = np.ones(len(time))
    recording = _recording(time, dff=signal)
    detector = PastaTransientDetectorSpec(amplitude_threshold=0.1)
    candidates = TransientCandidateResult(
        detector,
        "dff",
        (_manual_candidate(250, time), _manual_candidate(280, time)),
        (),
    )

    result = cut_transient_waveforms(
        recording,
        candidates,
        variable="dff",
        spec=TransientWaveformSpec(
            pre_peak_s=0.5,
            post_peak_s=0.5,
            detector_floor=-1,
            detector_ceiling=1,
        ),
    )
    first = result.waveforms[0]
    codes = {item.code for item in first.issues}
    assert first.status == "fail"
    assert {
        "flat_step_fraction",
        "detector_saturation_fraction",
        "nearby_candidate_in_window",
    } <= codes
    assert first.nearby_candidate_ids == ("green:manual:280",)


def test_quantification_requires_matching_waveform_evidence_when_requested() -> None:
    time = np.arange(0, 5, 0.01)
    signal = np.exp(-0.5 * ((time - 2.5) / 0.1) ** 2)
    recording = _recording(time, dff=signal)
    candidates = TransientCandidateResult(
        PastaTransientDetectorSpec(amplitude_threshold=0.1),
        "dff",
        (_manual_candidate(250, time),),
        (),
    )
    with pytest.raises(ValueError, match="requires waveform evidence"):
        quantify_transient_candidates(
            recording,
            candidates,
            variable="dff",
            spec=TransientQuantificationSpec(require_waveform_qc=True),
        )
