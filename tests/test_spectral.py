import json

import numpy as np
import pytest

from fiberphotometry.spectral import (
    AutocorrelationSpec,
    GapHandlingSpec,
    SpectralAnalysisSpec,
    StateBandPowerInferenceSpec,
    StateEpoch,
    StatePSDSession,
    autocorrelation,
    infer_state_band_power,
    spectrogram,
    state_conditioned_autocorrelation,
    state_conditioned_psd,
    state_conditioned_spectrogram,
    welch_psd,
)


def _gapped_sinusoid() -> tuple[np.ndarray, np.ndarray]:
    rate = 20.0
    time = np.concatenate((np.arange(0, 20, 1 / rate), np.arange(30, 50, 1 / rate)))
    values = np.sin(2 * np.pi * 5 * time)
    return time, values


def test_welch_psd_separates_gaps_and_recovers_frequency() -> None:
    time, values = _gapped_sinusoid()
    result = welch_psd(
        time,
        values,
        SpectralAnalysisSpec(window_duration_s=2, maximum_frequency_hz=9),
        value_unit="dF/F",
    )

    frequencies = np.asarray(result.frequencies_hz)
    power = np.asarray(result.power_density)
    assert frequencies[np.argmax(power)] == pytest.approx(5)
    assert result.windows_per_run == (19, 19)
    assert result.total_window_count == 38
    assert len(result.evidence.runs) == 2
    assert result.evidence.gap_count == 1
    assert result.power_density_unit == "dF/F^2/Hz"
    assert json.loads(result.to_json())["method"].startswith("window_weighted")


def test_autocorrelation_counts_only_within_run_pairs() -> None:
    time, values = _gapped_sinusoid()
    result = autocorrelation(
        time,
        values,
        AutocorrelationSpec(maximum_lag_s=1, detrend="constant"),
    )

    lags = np.asarray(result.lags_s)
    correlation = np.asarray(result.correlation)
    half_second = int(np.argmin(np.abs(lags - 0.2)))
    assert correlation[0] == pytest.approx(1)
    assert correlation[half_second] > 0.98
    assert result.pairs_per_lag[0] == 800
    assert result.pairs_per_lag[half_second] == 792
    assert len(result.evidence.runs) == 2


def test_spectrogram_retains_complete_window_edge_evidence() -> None:
    time, values = _gapped_sinusoid()
    result = spectrogram(
        time,
        values,
        SpectralAnalysisSpec(window_duration_s=2, overlap_fraction=0.5),
    )

    assert len(result.window_centers_s) == 38
    assert set(result.run_ids) == {0, 1}
    assert min(result.distance_to_left_edge_s) == pytest.approx(0)
    assert min(result.distance_to_right_edge_s) == pytest.approx(0)
    assert all(
        stop < 20 or start >= 30
        for start, stop in zip(result.window_start_s, result.window_stop_s, strict=True)
    )
    assert np.asarray(result.power_density).shape == (
        len(result.frequencies_hz),
        len(result.window_centers_s),
    )


def test_irregular_clock_is_refused_instead_of_silently_regularized() -> None:
    time = np.arange(400, dtype=float) / 20
    time[1:] += 0.004 * np.sin(np.arange(1, 400))
    values = np.sin(2 * np.pi * time)

    with pytest.raises(ValueError, match="resample prospectively"):
        welch_psd(
            time,
            values,
            SpectralAnalysisSpec(
                window_duration_s=2,
                gap=GapHandlingSpec(maximum_interval_cv=0.01),
            ),
        )


def test_state_conditioning_preserves_epoch_boundaries_and_labels() -> None:
    rate = 20.0
    time = np.arange(0, 40, 1 / rate)
    epochs = (
        StateEpoch("awake", 0, 10, "a1"),
        StateEpoch("sleep", 10, 20, "s1"),
        StateEpoch("awake", 20, 30, "a2"),
        StateEpoch("sleep", 30, 40, "s2"),
    )
    awake = ((time >= 0) & (time < 10)) | ((time >= 20) & (time < 30))
    values = np.where(
        awake,
        np.sin(2 * np.pi * 6 * time),
        np.sin(2 * np.pi * 2 * time),
    )
    spectral_spec = SpectralAnalysisSpec(window_duration_s=2)

    psd_result = state_conditioned_psd(time, values, epochs, spectral_spec)
    by_state = {item.state: item for item in psd_result.states}
    awake_result = by_state["awake"].result
    sleep_result = by_state["sleep"].result
    awake_peak = awake_result.frequencies_hz[int(np.argmax(awake_result.power_density))]
    sleep_peak = sleep_result.frequencies_hz[int(np.argmax(sleep_result.power_density))]
    assert awake_peak == pytest.approx(6)
    assert sleep_peak == pytest.approx(2)
    assert len(awake_result.evidence.runs) == 2
    assert len(sleep_result.evidence.runs) == 2
    assert by_state["awake"].epoch_count == 2
    assert psd_result.unassigned_sample_count == 0

    autocorrelation_result = state_conditioned_autocorrelation(
        time,
        values,
        epochs,
        AutocorrelationSpec(maximum_lag_s=0.5),
    )
    assert {item.state for item in autocorrelation_result.states} == {
        "awake",
        "sleep",
    }

    spectrogram_result = state_conditioned_spectrogram(
        time, values, epochs, spectral_spec
    )
    assert all(
        len(item.result.evidence.runs) == 2 for item in spectrogram_result.states
    )


def test_state_epochs_refuse_ambiguous_overlap() -> None:
    time = np.arange(0, 10, 0.05)
    values = np.sin(time)
    epochs = (StateEpoch("one", 0, 6), StateEpoch("two", 5, 10))

    with pytest.raises(ValueError, match="overlap_policy='error'"):
        state_conditioned_psd(
            time,
            values,
            epochs,
            SpectralAnalysisSpec(window_duration_s=2),
        )


def test_state_band_power_inference_aggregates_sessions_within_animals() -> None:
    rate = 20.0
    time = np.arange(0, 20, 1 / rate)
    epochs = (StateEpoch("active", 0, 10), StateEpoch("rest", 10, 20))
    sessions = []
    for animal_index in range(6):
        for session_index in range(2):
            amplitude = 1.5 + 0.05 * animal_index + 0.01 * session_index
            values = np.where(
                time < 10,
                amplitude * np.sin(2 * np.pi * 3 * time),
                np.sin(2 * np.pi * 3 * time),
            )
            result = state_conditioned_psd(
                time,
                values,
                epochs,
                SpectralAnalysisSpec(window_duration_s=2),
            )
            sessions.append(
                StatePSDSession(
                    f"animal-{animal_index}",
                    f"session-{session_index}",
                    result,
                )
            )

    result = infer_state_band_power(
        sessions,
        StateBandPowerInferenceSpec(
            "active",
            "rest",
            (2.0, 4.0),
            bootstrap_resamples=500,
            permutation_resamples=500,
            seed=4,
        ),
    )

    assert result.estimate > 0
    assert len(result.included_subjects) == 6
    assert len(result.estimates) == 12
    assert {item.session_count for item in result.estimates} == {2}
    assert result.interval_low > 0
    assert result.permutation_pvalue < 0.1
