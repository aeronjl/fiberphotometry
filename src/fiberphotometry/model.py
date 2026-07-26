"""Canonical labelled representation for a photometry recording."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import xarray as xr
from numpy.typing import ArrayLike


def make_recording(
    *,
    time: ArrayLike,
    signal: ArrayLike,
    reference: ArrayLike | None = None,
    channel_names: Sequence[str] | None = None,
    subject: str,
    session: str,
    attrs: Mapping[str, str | float | int | bool] | None = None,
) -> xr.Dataset:
    """Create a validated recording without modifying the supplied arrays.

    Signals are stored as ``(time, channel)`` even for a single channel. This
    prevents downstream functions from treating regions or fluorophores as
    interchangeable observations.
    """
    time_array = np.asarray(time, dtype=float)
    signal_array = _as_time_channel(signal)
    names = list(
        channel_names or [f"channel_{i}" for i in range(signal_array.shape[1])]
    )
    if len(names) != signal_array.shape[1]:
        raise ValueError("channel_names must match the number of signal channels")

    data_vars: dict[str, tuple[tuple[str, str], np.ndarray]] = {
        "signal": (("time", "channel"), signal_array.copy())
    }
    if reference is not None:
        reference_array = _as_time_channel(reference)
        if reference_array.shape != signal_array.shape:
            raise ValueError("reference and signal must have the same shape")
        data_vars["reference"] = (("time", "channel"), reference_array.copy())

    metadata: dict[str, str | float | int | bool] = {
        "subject": subject,
        "session": session,
        "processing_stage": "raw",
    }
    metadata.update(attrs or {})
    recording = xr.Dataset(
        data_vars=data_vars,
        coords={"time": time_array.copy(), "channel": names},
        attrs=metadata,
    )
    return validate_recording(recording)


def validate_recording(recording: xr.Dataset) -> xr.Dataset:
    """Validate the minimum invariants required by processing functions."""
    if "signal" not in recording:
        raise ValueError("recording must contain a signal variable")
    if recording["signal"].dims != ("time", "channel"):
        raise ValueError("signal dimensions must be ('time', 'channel')")
    if "subject" not in recording.attrs or "session" not in recording.attrs:
        raise ValueError("recording attrs must identify subject and session")
    time = np.asarray(recording["time"].values, dtype=float)
    if time.ndim != 1 or len(time) < 2:
        raise ValueError("time must contain at least two samples")
    if not np.all(np.isfinite(time)):
        raise ValueError("time must be finite")
    if not np.all(np.diff(time) > 0):
        raise ValueError("time must be strictly increasing")
    return recording


def _as_time_channel(values: ArrayLike) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        array = array[:, np.newaxis]
    if array.ndim != 2:
        raise ValueError("signal arrays must be one- or two-dimensional")
    return array
