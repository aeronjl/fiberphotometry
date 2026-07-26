import json

import numpy as np
import pytest

from fiberphotometry import (
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
    operation = json.loads(result.attrs["fiberphotometry_baseline_dff"])
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
    assert (
        json.loads(corrected.attrs["fiberphotometry_reference_dff"])["method"] == "irls"
    )
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
    operation = json.loads(result.attrs["fiberphotometry_operations"])[0]
    assert operation["kind"] == "resample"
    assert operation["max_gap_s"] == 1.1
    assert operation["time_only_boolean_method"] == "nearest"


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
    operation = json.loads(result.attrs["fiberphotometry_operations"])[0]
    assert operation["method"] == "butterworth_sosfiltfilt"
    assert operation["edge_padding_samples"] > 0
