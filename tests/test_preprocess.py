import json

import numpy as np
import pytest

from fipha import (
    baseline_dff,
    lowpass_filter,
    make_recording,
    reference_dff,
    resample_recording,
)


def test_double_exponential_baseline_dff_recovers_known_trace() -> None:
    time = np.arange(0, 120, 0.1)
    baseline = 1.2 + 0.6 * np.exp(-time / 15) + 0.3 * np.exp(-time / 80)
    neural = 0.04 * np.exp(-((time - 60) ** 2) / 0.5)
    recording = make_recording(
        time=time,
        signal=baseline * (1 + neural),
        subject="m",
        session="s",
    )

    result = baseline_dff(recording, method="double_exponential")

    assert np.sqrt(np.mean((result.dff.values[:, 0] - neural) ** 2)) < 0.005
    assert "fitted_baseline" not in recording
    operation = json.loads(result.attrs["fipha_baseline_dff"])
    assert operation["method"] == "double_exponential"
    assert operation["finite_run_policy"] == "independent"


def test_asls_baseline_dff_recovers_smooth_lower_envelope() -> None:
    time = np.arange(0, 100, 0.1)
    baseline = 1.5 - 0.002 * time
    neural = np.zeros_like(time)
    neural[400:420] = 0.05
    recording = make_recording(
        time=time,
        signal=baseline * (1 + neural),
        subject="m",
        session="s",
    )

    result = baseline_dff(recording, method="asls", asls_smoothness=1e7)

    assert np.median(result.dff.values[:300, 0]) == pytest.approx(0, abs=0.002)
    assert np.max(result.dff.values[:, 0]) > 0.04


def test_subtractive_baseline_output_retains_fluorescence_units() -> None:
    time = np.arange(0, 100, 0.1)
    baseline = 1 + 0.5 * np.exp(-time / 30)
    signal = baseline.copy()
    signal[500:510] += 0.1
    recording = make_recording(time=time, signal=signal, subject="m", session="s")

    result = baseline_dff(
        recording, method="double_exponential", normalization="subtract"
    )

    assert "baseline_subtracted" in result
    assert "dff" not in result
    operation = json.loads(result.attrs["fipha_baseline_dff"])
    assert operation["normalization"] == "subtract"
    assert "/ fitted_baseline" not in operation["formula"]


def test_baseline_can_expose_both_normalizations_without_refitting() -> None:
    time = np.arange(0, 100, 0.1)
    signal = 1 + 0.2 * np.exp(-time / 30)
    recording = make_recording(time=time, signal=signal, subject="m", session="s")

    result = baseline_dff(recording, method="double_exponential", normalization="both")

    assert "dff" in result
    assert "baseline_subtracted" in result
    assert np.allclose(
        result.dff.values * result.fitted_baseline.values,
        result.baseline_subtracted.values,
        equal_nan=True,
    )
    operation = json.loads(result.attrs["fipha_baseline_dff"])
    assert operation["normalization"] == "both"
    assert len(operation["formula"]) == 2


def test_asls_smoothness_scales_with_sampling_rate() -> None:
    time = np.arange(0, 30, 0.025)
    recording = make_recording(
        time=time,
        signal=1 + 0.1 * np.sin(time / 10),
        subject="m",
        session="s",
    )

    result = baseline_dff(recording, method="asls")

    operation = json.loads(result.attrs["fipha_baseline_dff"])
    assert operation["sampling_rate_hz"] == pytest.approx(40)
    assert operation["effective_smoothness"] == pytest.approx(1.6e9)


@pytest.mark.parametrize("rate_hz", [20, 50])
def test_rolling_mean_matches_published_pandas_semantics(rate_hz: int) -> None:
    pd = pytest.importorskip("pandas")
    time = np.arange(0, 80, 1 / rate_hz)
    signal = 2 + 0.1 * np.sin(time / 10)
    recording = make_recording(time=time, signal=signal, subject="m", session="s")

    result = baseline_dff(recording, method="rolling_mean", rolling_window_s=60)

    window_samples = 60 * rate_hz
    expected = pd.Series(signal).rolling(window_samples, center=True).mean().to_numpy()
    assert np.allclose(result.fitted_baseline.values[:, 0], expected, equal_nan=True)
    assert np.count_nonzero(np.isfinite(result.dff.values[:, 0])) == (
        len(time) - window_samples + 1
    )
    operation = json.loads(result.attrs["fipha_baseline_dff"])
    assert operation["window_samples"] == window_samples
    assert operation["boundary_policy"] == "full_window_only"


def test_rolling_mean_does_not_bridge_timestamp_gaps() -> None:
    first = np.arange(0, 40, 0.05)
    second = np.arange(50, 90, 0.05)
    time = np.concatenate([first, second])
    signal = np.concatenate([np.ones_like(first), np.full_like(second, 3.0)])
    recording = make_recording(time=time, signal=signal, subject="m", session="s")

    result = baseline_dff(recording, method="rolling_mean", rolling_window_s=20)

    first_baseline = result.fitted_baseline.sel(time=20, method="nearest").item()
    second_baseline = result.fitted_baseline.sel(time=70, method="nearest").item()
    assert first_baseline == pytest.approx(1)
    assert second_baseline == pytest.approx(3)
    assert np.isnan(result.fitted_baseline.sel(time=39.95, method="nearest").item())
    assert np.isnan(result.fitted_baseline.sel(time=50, method="nearest").item())
    operation = json.loads(result.attrs["fipha_baseline_dff"])
    assert operation["gap_policy"] == "split_finite_runs"


def test_rolling_mean_short_runs_are_retained_as_failures() -> None:
    time = np.arange(0, 10, 0.05)
    recording = make_recording(
        time=time, signal=np.ones_like(time), subject="m", session="s"
    )

    result = baseline_dff(recording, method="rolling_mean", rolling_window_s=60)

    assert np.all(np.isnan(result.dff.values))
    operation = json.loads(result.attrs["fipha_baseline_dff"])
    assert operation["failed_short_runs"] == 1


def test_reference_dff_recovers_known_linear_baseline() -> None:
    time = np.arange(100, dtype=float)
    reference = 1 + 0.01 * time
    signal = 2 + 3 * reference
    signal[50] += 2
    recording = make_recording(
        time=time,
        signal=signal,
        reference=reference,
        subject="m",
        session="s",
    )
    corrected = reference_dff(recording, method="irls")

    coefficients = corrected.reference_fit_coefficient.values[0]
    assert np.allclose(coefficients, [2, 3], atol=0.05)
    assert corrected.dff.values[50, 0] > 0.2
    assert json.loads(corrected.attrs["fipha_reference_dff"])["method"] == "irls"
    assert "dff" not in recording


def test_irls_is_less_affected_by_transients_than_ols() -> None:
    time = np.arange(200, dtype=float)
    reference = 1 + time / 200
    signal = 1 + 2 * reference
    signal[::10] += 5
    recording = make_recording(
        time=time, signal=signal, reference=reference, subject="m", session="s"
    )

    robust = reference_dff(recording, method="irls")
    ols = reference_dff(recording, method="ols")

    robust_error = abs(robust.reference_fit_coefficient.values[0, 1] - 2)
    ols_error = abs(ols.reference_fit_coefficient.values[0, 1] - 2)
    assert robust_error < ols_error


def test_resampling_retains_source_and_does_not_bridge_large_gap() -> None:
    recording = make_recording(
        time=[0.0, 1.0, 4.0, 5.0],
        signal=[0.0, 1.0, 4.0, 5.0],
        reference=[1.0, 1.0, 1.0, 1.0],
        subject="m",
        session="s",
    )
    recording["included"] = (("time",), [True, True, False, True])

    result = resample_recording(recording, rate_hz=2, max_gap_s=1.1)

    assert result.sizes["time"] == 11
    assert result.sizes["source_time"] == 4
    assert np.array_equal(result.source_signal.values[:, 0], [0, 1, 4, 5])
    assert np.isnan(result.signal.sel(time=2.0).item())
    assert not result.included.sel(time=2.0).item()
    assert np.array_equal(result.source_included.values, [True, True, False, True])
    assert result.protected_gap.sel(time=2.0).item()
    assert not result.interpolated.sel(time=2.0).item()
    operation = json.loads(result.attrs["fipha_operations"])[0]
    assert operation["kind"] == "resample"
    assert operation["max_gap_s"] == 1.1
    assert operation["time_only_boolean_method"] == "interval_overlap"


def test_downsampling_retains_every_behavioural_event_sample() -> None:
    time = np.arange(0, 60, 0.01)
    recording = make_recording(
        time=time,
        signal=np.full_like(time, 1000.0),
        subject="m",
        session="s",
    )
    event_times = [5.0, 10.0, 15.02, 20.0, 25.03, 30.0]
    lick = np.zeros(time.size, dtype=bool)
    for event in event_times:
        lick[int(np.argmin(np.abs(time - event)))] = True
    recording["lick"] = (("time",), lick)

    result = resample_recording(recording, rate_hz=5.0)

    expected = np.zeros(result.sizes["time"], dtype=bool)
    for event in event_times:
        expected[int(np.argmin(np.abs(result.time.values - event)))] = True
    assert np.array_equal(result.lick.values, expected)
    assert int(result.lick.values.sum()) == 6
    operation = json.loads(result.attrs["fipha_operations"])[0]
    assert operation["time_only_boolean_true_counts"]["lick"] == {
        "source_true_count": 6,
        "output_true_count": 6,
        "dropped_true_count": 0,
        "merged_true_count": 0,
    }


def test_boolean_resampling_preserves_event_count_when_upsampling() -> None:
    time = np.arange(0, 10, 0.1)
    recording = make_recording(
        time=time,
        signal=np.full_like(time, 1.0),
        subject="m",
        session="s",
    )
    lick = np.zeros(time.size, dtype=bool)
    lick[[10, 47, 80]] = True
    recording["lick"] = (("time",), lick)

    result = resample_recording(recording, rate_hz=40)

    assert int(result.lick.values.sum()) == 3
    assert np.array_equal(
        np.round(result.time.values[result.lick.values], 3), [1.0, 4.7, 8.0]
    )


def test_boolean_resampling_never_moves_an_event_across_a_gap() -> None:
    recording = make_recording(
        time=[0.0, 0.5, 1.6, 4.4, 5.0],
        signal=[1.0, 1.0, 1.0, 1.0, 1.0],
        subject="m",
        session="s",
    )
    recording["lick"] = (("time",), [False, False, True, True, False])

    result = resample_recording(recording, rate_hz=1, max_gap_s=1.5)

    assert np.array_equal(result.time.values, [0, 1, 2, 3, 4, 5])
    assert np.array_equal(result.lick.values, [False, True, False, False, False, True])
    assert np.array_equal(
        result.protected_gap.values, [False, False, True, True, True, False]
    )
    assert not np.any(result.lick.values & result.protected_gap.values)
    operation = json.loads(result.attrs["fipha_operations"])[0]
    assert operation["time_only_boolean_true_counts"]["lick"]["dropped_true_count"] == 0


def test_unrepresentable_event_is_warned_about_rather_than_silently_dropped() -> None:
    recording = make_recording(
        time=[0.0, 0.5, 1.6, 4.4, 5.0],
        signal=[1.0, 1.0, 1.0, 1.0, 1.0],
        subject="m",
        session="s",
    )
    recording["lick"] = (("time",), [False, False, True, True, False])

    with pytest.warns(UserWarning, match="dropped 1 of 2 True samples"):
        result = resample_recording(recording, rate_hz=1, max_gap_s=1.0)

    assert int(result.lick.values.sum()) == 1
    counts = json.loads(result.attrs["fipha_operations"])[0][
        "time_only_boolean_true_counts"
    ]["lick"]
    assert counts["dropped_true_count"] == 1
    assert counts["output_true_count"] == 1


def test_median_rate_regularization_reports_jitter_and_preserves_smooth_signal() -> (
    None
):
    regular_time = np.arange(0, 20, 0.02)
    jitter = 0.0001 * np.sin(np.arange(len(regular_time)) * 0.7)
    irregular_time = regular_time + jitter
    signal = np.sin(2 * np.pi * 0.5 * irregular_time)
    recording = make_recording(
        time=irregular_time,
        signal=signal,
        subject="m",
        session="jittered",
    )

    result = resample_recording(recording, rate_hz="median", max_gap_factor=1.5)

    operation = json.loads(result.attrs["fipha_operations"])[0]
    expected = np.sin(2 * np.pi * 0.5 * result.time.values)
    error = np.sqrt(np.nanmean((result.signal.values[:, 0] - expected) ** 2))
    assert error < 5e-5
    assert operation["rate_policy"] == "median"
    assert operation["rate_hz"] == pytest.approx(50, rel=0.01)
    assert operation["max_gap_factor"] == 1.5
    assert operation["resolved_max_gap_s"] == pytest.approx(0.03, rel=0.01)
    assert operation["source_interval_cv"] > 0
    assert operation["gap_masked_target_fraction"] == 0
    assert operation["nearest_source_distance_max_s"] < 0.002
    assert operation["interpolated_target_fraction"] > 0


def test_lowpass_retains_input_and_reports_edge_handling() -> None:
    time = np.arange(0, 10, 0.01)
    low = np.sin(2 * np.pi * time)
    high = 0.5 * np.sin(2 * np.pi * 20 * time)
    recording = make_recording(
        time=time,
        signal=low + high,
        reference=1 + high,
        subject="m",
        session="s",
    )

    result = lowpass_filter(recording, cutoff_hz=5, order=4)

    assert np.array_equal(result.prefilter_signal.values, recording.signal.values)
    assert np.std(result.signal.values[:, 0] - low) < 0.03
    operation = json.loads(result.attrs["fipha_operations"])[0]
    assert operation["method"] == "butterworth_sosfiltfilt"
    assert operation["edge_padding_samples"] > 0
