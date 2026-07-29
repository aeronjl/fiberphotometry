import numpy as np
import pytest

from fiberphotometry.cross_spectral import (
    coherence_phase,
    state_conditioned_coherence,
    summarize_coherence_band,
)
from fiberphotometry.multisignal import ChannelIdentity, SignalPairMetadata
from fiberphotometry.spectral import SpectralAnalysisSpec, StateEpoch


def _pair(subject: str = "mouse-01", session: str = "session-01") -> SignalPairMetadata:
    return SignalPairMetadata(
        subject,
        session,
        "green__red",
        ChannelIdentity("green", "DMS", "dLight", "sensor", "dF/F"),
        ChannelIdentity("red", "NAcC", "rDA", "sensor", "dF/F"),
        "photometry-clock",
        "native_shared_clock",
        "sha256:processed",
    )


def test_coherence_and_phase_pool_cross_spectra_by_complete_windows() -> None:
    rate = 50.0
    time = np.concatenate((np.arange(0, 20, 1 / rate), np.arange(30, 50, 1 / rate)))
    rng = np.random.default_rng(2)
    phase = 0.7
    first = np.sin(2 * np.pi * 4 * time) + rng.normal(0, 0.1, len(time))
    second = np.sin(2 * np.pi * 4 * time + phase) + rng.normal(0, 0.1, len(time))
    result = coherence_phase(
        time,
        first,
        second,
        _pair(),
        SpectralAnalysisSpec(
            window_duration_s=4,
            overlap_fraction=0.5,
            maximum_frequency_hz=10,
        ),
    )

    frequencies = np.asarray(result.frequencies_hz)
    index = int(np.argmin(np.abs(frequencies - 4)))
    assert result.coherence[index] > 0.95
    assert result.phase_radians[index] == pytest.approx(phase, abs=0.08)
    assert result.windows_per_run == (9, 9)
    assert result.total_window_count == 18
    assert result.evidence.continuity.gap_count == 1

    summary = summarize_coherence_band(result, (3.5, 4.5))
    assert summary.mean_coherence > 0.7
    assert summary.cross_spectrum_phase_radians == pytest.approx(phase, abs=0.1)
    assert summary.total_window_count == 18


def test_state_coherence_keeps_repeated_labels_in_separate_epochs() -> None:
    rate = 20.0
    time = np.arange(0, 40, 1 / rate)
    rng = np.random.default_rng(13)
    first = rng.normal(size=len(time))
    second = rng.normal(size=len(time))
    coupled = ((time >= 0) & (time < 10)) | ((time >= 20) & (time < 30))
    second[coupled] = first[coupled] + rng.normal(0, 0.1, np.count_nonzero(coupled))
    epochs = (
        StateEpoch("coupled", 0, 10, "c1"),
        StateEpoch("uncoupled", 10, 20, "u1"),
        StateEpoch("coupled", 20, 30, "c2"),
        StateEpoch("uncoupled", 30, 40, "u2"),
    )
    result = state_conditioned_coherence(
        time,
        first,
        second,
        _pair(),
        epochs,
        SpectralAnalysisSpec(window_duration_s=2, maximum_frequency_hz=8),
    )

    by_state = {item.state: item for item in result.states}
    assert len(by_state["coupled"].result.evidence.continuity.runs) == 2
    assert len(by_state["uncoupled"].result.evidence.continuity.runs) == 2
    assert by_state["coupled"].epoch_count == 2
    assert by_state["coupled"].result.evidence.total_sample_count == 400
    assert by_state["coupled"].result.evidence.joint_valid_sample_count == 400
    assert result.unassigned_sample_count == 0
    coupled_band = summarize_coherence_band(by_state["coupled"].result, (1, 6))
    uncoupled_band = summarize_coherence_band(by_state["uncoupled"].result, (1, 6))
    assert coupled_band.mean_coherence > uncoupled_band.mean_coherence + 0.5
