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
) -> tuple[xr.Dataset, np.ndarray]:
    """Generate a recording with known neural transients and shared artefact."""
    rng = np.random.default_rng(seed)
    time = np.arange(0, duration, 1 / rate)
    event_times = np.arange(10, duration - 5, 15)
    neural = np.zeros_like(time)
    for event in event_times:
        after = time >= event
        neural[after] += np.exp(-(time[after] - event) / 1.2)
    shared_artifact = artifact_scale * np.sin(time / 3) + 0.1 * np.exp(-time / 80)
    reference = 1.0 + shared_artifact + rng.normal(0, 0.01, len(time))
    signal = (
        2.0 + 1.4 * shared_artifact + 0.08 * neural + rng.normal(0, 0.01, len(time))
    )
    recording = make_recording(
        time=time,
        signal=signal,
        reference=reference,
        subject="synthetic-subject",
        session="synthetic-session",
    )
    recording["ground_truth_neural"] = (("time", "channel"), neural[:, None])
    return recording, event_times
