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


def simulate_bleaching_recording(
    *,
    scenario: str,
    seed: int = 0,
    duration: float = 300.0,
    rate: float = 20.0,
) -> tuple[xr.Dataset, np.ndarray]:
    """Generate a signal-only recording with known bleaching and neural dF/F."""
    scenarios = {
        "single_exponential",
        "double_exponential",
        "large_transients",
        "slow_drift",
        "motion_without_control",
        "event_locked_artifact",
    }
    if scenario not in scenarios:
        raise ValueError(f"unknown bleaching scenario {scenario!r}")
    rng = np.random.default_rng(seed)
    time = np.arange(0, duration, 1 / rate)
    event_times = np.arange(15, duration - 5, 20)
    neural = np.zeros_like(time)
    for event in event_times:
        after = time >= event
        neural[after] += np.exp(-(time[after] - event) / 0.8)
    scale = 0.15 if scenario == "large_transients" else 0.03
    ground_truth_dff = scale * neural
    if scenario == "single_exponential":
        baseline = 1.2 + 0.8 * np.exp(-time / 70)
    else:
        baseline = 1.1 + 0.55 * np.exp(-time / 25) + 0.4 * np.exp(-time / 180)
    if scenario == "slow_drift":
        baseline = baseline * (1 + 0.035 * np.sin(2 * np.pi * time / 150))
    nuisance = np.zeros_like(time)
    if scenario == "motion_without_control":
        nuisance += 0.04 * np.sin(2 * np.pi * time / 7)
    if scenario == "event_locked_artifact":
        nuisance += 0.04 * neural
    signal = baseline * (1 + ground_truth_dff + nuisance)
    signal += rng.normal(0, 0.004, len(time))
    recording = make_recording(
        time=time,
        signal=signal,
        subject="synthetic-subject",
        session=f"bleaching-{scenario}-{seed}",
    )
    recording["ground_truth_baseline"] = (("time", "channel"), baseline[:, None])
    recording["ground_truth_dff"] = (("time", "channel"), ground_truth_dff[:, None])
    return recording, event_times


def simulate_normalization_recording(
    *,
    mechanism: str,
    seed: int = 0,
    duration: float = 300.0,
    rate: float = 20.0,
) -> tuple[xr.Dataset, np.ndarray]:
    """Simulate indicator or autofluorescence bleaching with stable neural dF/F."""
    if mechanism not in {"indicator_bleaching", "autofluorescence_bleaching"}:
        raise ValueError(f"unknown bleaching mechanism {mechanism!r}")
    rng = np.random.default_rng(seed)
    time = np.arange(0, duration, 1 / rate)
    event_times = np.arange(15, duration - 5, 15)
    neural_dff = np.zeros_like(time)
    for event in event_times:
        after = time >= event
        neural_dff[after] += 0.03 * np.exp(-(time[after] - event) / 0.8)
    decay = 0.8 * np.exp(-time / 70)
    if mechanism == "indicator_bleaching":
        baseline = 1.0 + decay
        signal = baseline * (1 + neural_dff)
    else:
        indicator_baseline = 1.0
        baseline = indicator_baseline + decay
        signal = baseline + indicator_baseline * neural_dff
    signal += rng.normal(0, 0.002, len(time))
    recording = make_recording(
        time=time,
        signal=signal,
        subject="synthetic-subject",
        session=f"normalization-{mechanism}-{seed}",
    )
    recording["ground_truth_baseline"] = (("time", "channel"), baseline[:, None])
    recording["ground_truth_dff"] = (("time", "channel"), neural_dff[:, None])
    return recording, event_times
