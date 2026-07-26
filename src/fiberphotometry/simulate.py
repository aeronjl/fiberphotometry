"""Small ground-truth simulations for method tests and examples."""

from __future__ import annotations

import numpy as np
import xarray as xr

from fiberphotometry.model import make_recording


def simulate_recording(
    *,
    duration: float = 120.0,
    rate: float = 20.0,
    seed: int = 0,
    artifact_scale: float = 0.25,
    transient_scale: float = 0.08,
    reference_contamination: float = 0.0,
    event_artifact_scale: float = 0.0,
    nonlinear_signal_scale: float = 0.0,
    reference_lag_s: float = 0.0,
    dropout_fraction: float = 0.0,
) -> tuple[xr.Dataset, np.ndarray]:
    """Generate a recording with known neural transients and shared artefact."""
    rng = np.random.default_rng(seed)
    time = np.arange(0, duration, 1 / rate)
    event_times = np.arange(10, duration - 5, 15)
    neural = np.zeros_like(time)
    for event in event_times:
        after = time >= event
        neural[after] += np.exp(-(time[after] - event) / 1.2)
    shared_artifact = (
        artifact_scale * np.sin(time / 3)
        + 0.1 * np.exp(-time / 80)
        + event_artifact_scale * neural
    )
    lag_samples = round(reference_lag_s * rate)
    reference_artifact = np.roll(shared_artifact, lag_samples)
    if lag_samples > 0:
        reference_artifact[:lag_samples] = shared_artifact[0]
    reference = (
        1.0
        + reference_artifact
        + reference_contamination * neural
        + rng.normal(0, 0.01, len(time))
    )
    signal_baseline = (
        2.0 + 1.4 * shared_artifact + nonlinear_signal_scale * shared_artifact**2
    )
    signal = signal_baseline + transient_scale * neural + rng.normal(0, 0.01, len(time))
    if dropout_fraction > 0:
        block_length = round(len(time) * dropout_fraction / 3)
        for fraction in (0.2, 0.5, 0.8):
            start = round(len(time) * fraction)
            signal[start : start + block_length] = np.nan
            reference[start : start + block_length] = np.nan
    recording = make_recording(
        time=time,
        signal=signal,
        reference=reference,
        subject="synthetic-subject",
        session="synthetic-session",
    )
    recording["ground_truth_neural"] = (("time", "channel"), neural[:, None])
    recording["ground_truth_dff"] = (
        ("time", "channel"),
        (transient_scale * neural / signal_baseline)[:, None],
    )
    return recording, event_times
