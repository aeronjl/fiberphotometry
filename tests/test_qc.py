import numpy as np
import pytest

from fiberphotometry import make_recording
from fiberphotometry.qc import assess_recording, assess_signal_recording


def test_qc_reports_sampling_fit_and_missingness() -> None:
    time = np.arange(100, dtype=float) / 10
    reference = 1 + 0.1 * np.sin(time)
    signal = 2 + 3 * reference
    signal[30:55] = np.nan
    reference[30:55] = np.nan
    recording = make_recording(
        time=time,
        signal=signal,
        reference=reference,
        subject="mouse",
        session="session",
    )

    result = assess_recording(recording)
    channel = result.channels[0]

    assert np.isclose(result.estimated_rate_hz, 10)
    assert np.isclose(channel.finite_paired_fraction, 0.75)
    assert np.isclose(channel.irls_slope, 3)
    assert np.isclose(channel.longest_valid_segment_s, 4.5)
    assert "low_valid_fraction" in channel.warnings


def test_signal_only_qc_reports_available_metrics_without_reference() -> None:
    time = np.arange(100, dtype=float) / 20
    signal = np.sin(time)
    signal[:25] = np.nan
    recording = make_recording(time=time, signal=signal, subject="m", session="s")

    report = assess_signal_recording(recording)

    assert report.estimated_rate_hz == pytest.approx(20)
    assert report.channels[0].finite_fraction == 0.75
    assert report.channels[0].warnings == ("low_valid_fraction",)
    assert "signal_reference_correlation" not in report.to_json()
