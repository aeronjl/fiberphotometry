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


def summarize_event_windows(
    recording: xr.Dataset,
    event_times: Sequence[float],
    *,
    baseline: tuple[float, float],
    response: tuple[float, float],
    variable: str = "signal",
) -> xr.Dataset:
    """Summarize actual acquired samples without interpolating or averaging events.

    Window starts are inclusive and stops exclusive. Events remain a dimension,
    so downstream inference retains the session and animal hierarchy.
    """
    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    if baseline[0] >= baseline[1] or response[0] >= response[1]:
        raise ValueError("window starts must be earlier than stops")
    events = np.asarray(event_times, dtype=float)
    times = np.asarray(recording.time.values, dtype=float)
    values = np.asarray(recording[variable].values, dtype=float)
    baseline_means = _window_means(values, times, events, baseline)
    response_means = _window_means(values, times, events, response)
    return xr.Dataset(
        data_vars={
            "baseline_mean": (("event", "channel"), baseline_means),
            "response_mean": (("event", "channel"), response_means),
            "delta": (("event", "channel"), response_means - baseline_means),
        },
        coords={
            "event": np.arange(len(events)),
            "event_time": ("event", events),
            "channel": recording.channel.values,
        },
        attrs={
            "subject": recording.attrs["subject"],
            "session": recording.attrs["session"],
            "source_variable": variable,
            "baseline_window": str(baseline),
            "response_window": str(response),
        },
    )


def _window_means(
    values: np.ndarray,
    times: np.ndarray,
    events: np.ndarray,
    window: tuple[float, float],
) -> np.ndarray:
    output = np.full((len(events), values.shape[1]), np.nan)
    for index, event in enumerate(events):
        if not np.isfinite(event):
            continue
        selected = (times >= event + window[0]) & (times < event + window[1])
        if selected.any():
            selected_values = values[selected]
            finite = np.isfinite(selected_values)
            counts = finite.sum(axis=0)
            sums = np.where(finite, selected_values, 0.0).sum(axis=0)
            valid = counts > 0
            output[index, valid] = sums[valid] / counts[valid]
    return output
