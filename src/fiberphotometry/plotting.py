"""Optional diagnostic plots that expose raw signals and QC assumptions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import xarray as xr

from fiberphotometry.event_qc import assess_event_confounds
from fiberphotometry.events import align_events
from fiberphotometry.model import validate_recording
from fiberphotometry.preprocess import reference_dff


def plot_event_diagnostics(
    recording: xr.Dataset,
    event_times: Sequence[float],
    *,
    channel: str | int = 0,
    window: tuple[float, float] = (-1.0, 2.0),
) -> tuple[Any, np.ndarray]:
    """Plot raw traces, peri-event signal/reference means, and corrected dF/F."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ImportError(
            "diagnostic plots require `fiberphotometry[plots]`"
        ) from error
    validate_recording(recording)
    index = (
        int(np.flatnonzero(recording.channel.values == channel)[0])
        if isinstance(channel, str)
        else channel
    )
    rate = 1 / float(np.median(np.diff(recording.time.values)))
    corrected = reference_dff(recording)
    signal = align_events(
        recording, event_times, window=window, rate=rate, variable="signal"
    )
    reference = align_events(
        recording, event_times, window=window, rate=rate, variable="reference"
    )
    dff = align_events(corrected, event_times, window=window, rate=rate, variable="dff")
    qc = assess_event_confounds(recording, event_times).channels[index]
    figure, axes = plt.subplots(3, 1, figsize=(9, 8), constrained_layout=True)
    axes[0].plot(
        recording.time, recording.signal[:, index], label="signal", linewidth=0.8
    )
    axes[0].plot(
        recording.time, recording.reference[:, index], label="reference", linewidth=0.8
    )
    axes[0].legend()
    for axis, aligned, label in (
        (axes[1], signal, "signal"),
        (axes[1], reference, "reference"),
        (axes[2], dff, "IRLS dF/F"),
    ):
        axis.plot(
            aligned.relative_time, np.nanmean(aligned[:, :, index], axis=0), label=label
        )
        axis.axvline(0, color="black", linewidth=0.8, linestyle="--")
        axis.legend()
    axes[0].set_title(
        f"{qc.channel}: {', '.join(qc.warnings) or 'no event-QC warning'}"
    )
    axes[2].set_xlabel("Time from event (s)")
    return figure, axes
