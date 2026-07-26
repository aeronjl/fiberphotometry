"""Event alignment that retains individual events as observations."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import xarray as xr

from fiberphotometry.model import validate_recording


def align_events(
    recording: xr.Dataset,
    event_times: Sequence[float],
    *,
    window: tuple[float, float],
    rate: float,
    variable: str = "dff",
    event_ids: Sequence[str] | None = None,
) -> xr.DataArray:
    """Interpolate a signal onto a common peri-event time axis.

    Events outside the recorded interval are retained with NaNs. No averaging is
    performed, preserving the event/session/animal hierarchy for later inference.
    """
    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    start, stop = window
    if not start < stop:
        raise ValueError("window start must be earlier than window stop")
    if rate <= 0:
        raise ValueError("rate must be positive")

    events = np.asarray(event_times, dtype=float)
    ids = list(event_ids or [str(index) for index in range(len(events))])
    if len(ids) != len(events):
        raise ValueError("event_ids must match event_times")
    sample_count = round((stop - start) * rate) + 1
    relative_time = np.linspace(start, stop, sample_count)
    source_time = np.asarray(recording["time"].values, dtype=float)
    source = np.asarray(recording[variable].values, dtype=float)
    values = np.full((len(events), len(relative_time), source.shape[1]), np.nan)

    for event_index, event_time in enumerate(events):
        target = event_time + relative_time
        within = (target >= source_time[0]) & (target <= source_time[-1])
        for channel in range(source.shape[1]):
            finite = np.isfinite(source[:, channel])
            if finite.sum() >= 2:
                values[event_index, within, channel] = np.interp(
                    target[within], source_time[finite], source[finite, channel]
                )

    return xr.DataArray(
        values,
        dims=("event", "relative_time", "channel"),
        coords={
            "event": ids,
            "event_time": ("event", events),
            "relative_time": relative_time,
            "channel": recording["channel"].values,
        },
        attrs={
            "subject": recording.attrs["subject"],
            "session": recording.attrs["session"],
            "source_variable": variable,
            "alignment_rate_hz": rate,
        },
        name=f"event_aligned_{variable}",
    )
