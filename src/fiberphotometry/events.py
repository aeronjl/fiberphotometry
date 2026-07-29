"""Event alignment that retains individual events as observations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import xarray as xr
from numpy.typing import NDArray

from fiberphotometry.model import validate_recording


def align_events(
    recording: xr.Dataset,
    event_times: Sequence[float],
    *,
    window: tuple[float, float],
    rate: float,
    variable: str = "dff",
    event_ids: Sequence[str] | None = None,
    max_gap_s: float | None = None,
    baseline: tuple[float, float] | None = None,
    normalization: Literal["none", "baseline_z", "robust_z"] = "none",
) -> xr.DataArray:
    """Interpolate a signal onto a common peri-event time axis.

    Events outside the recorded interval are retained with NaNs. No averaging is
    performed, preserving the event/session/animal hierarchy for later inference.

    ``normalization`` rescales each event and channel by statistics of its own
    ``baseline`` window, measured on the aligned grid with an inclusive start and
    an exclusive stop. ``baseline_z`` divides the mean-centred trace by the
    baseline standard deviation; ``robust_z`` divides the median-centred trace by
    ``1.4826 * MAD``. An event whose baseline scale is zero or non-finite becomes
    NaN rather than an arbitrarily large number, and is counted in the output
    ``degenerate_baseline_count`` attribute.
    """
    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    start, stop = window
    if not start < stop:
        raise ValueError("window start must be earlier than window stop")
    if rate <= 0:
        raise ValueError("rate must be positive")
    if max_gap_s is not None and max_gap_s <= 0:
        raise ValueError("max_gap_s must be positive when provided")
    if normalization not in {"none", "baseline_z", "robust_z"}:
        raise ValueError("normalization must be 'none', 'baseline_z', or 'robust_z'")
    if normalization != "none" and baseline is None:
        raise ValueError("normalization requires a baseline window")
    if baseline is not None and not start <= baseline[0] < baseline[1] <= stop:
        raise ValueError("baseline window must lie inside the alignment window")

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
            values[event_index, within, channel] = _interpolate_finite_runs(
                source_time,
                source[:, channel],
                target[within],
                max_gap_s=max_gap_s,
            )

    degenerate = 0
    if normalization != "none" and baseline is not None:
        selected = (relative_time >= baseline[0]) & (relative_time < baseline[1])
        if selected.sum() < 2:
            raise ValueError("baseline window must span at least two aligned samples")
        center, scale = _baseline_statistics(
            values[:, selected, :], normalization, axis=1
        )
        usable, safe_scale = _usable_baseline(center, scale)
        degenerate = int(np.count_nonzero(~usable))
        values = np.where(
            usable[:, np.newaxis, :],
            (values - center[:, np.newaxis, :]) / safe_scale[:, np.newaxis, :],
            np.nan,
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
            "max_bridgeable_gap_s": max_gap_s,
            "normalization": normalization,
            "baseline_window": str(baseline),
            "units": _normalized_units(variable, normalization),
            "degenerate_baseline_count": degenerate,
        },
        name=f"event_aligned_{variable}",
    )


def summarize_event_windows(
    recording: xr.Dataset,
    event_times: Sequence[float],
    *,
    baseline: tuple[float, float],
    response: tuple[float, float],
    variable: str = "dff",
    normalization: Literal["none", "baseline_z", "robust_z"] = "none",
) -> xr.Dataset:
    """Summarize actual acquired samples without interpolating or averaging events.

    Window starts are inclusive and stops exclusive. Events remain a dimension,
    so downstream inference retains the session and animal hierarchy. A session
    with no events of a condition returns an empty result rather than raising.

    ``normalization`` rescales each event and channel by statistics of its own
    ``baseline`` window. ``baseline_z`` divides by the baseline standard
    deviation about the baseline mean; ``robust_z`` divides by ``1.4826 * MAD``
    about the baseline median. Because both are affine, applying them to the
    window means is identical to applying them sample by sample. An event whose
    baseline scale is zero or non-finite becomes NaN rather than an arbitrarily
    large number, and is counted in the ``degenerate_baseline_count`` attribute.
    """
    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    if baseline[0] >= baseline[1] or response[0] >= response[1]:
        raise ValueError("window starts must be earlier than stops")
    if normalization not in {"none", "baseline_z", "robust_z"}:
        raise ValueError("normalization must be 'none', 'baseline_z', or 'robust_z'")
    events = np.asarray(event_times, dtype=float)
    times = np.asarray(recording.time.values, dtype=float)
    values = np.asarray(recording[variable].values, dtype=float)
    baseline_means, baseline_fraction = _window_means(values, times, events, baseline)
    response_means, response_fraction = _window_means(values, times, events, response)
    baseline_interpolated = _window_flag_fraction(
        recording, times, events, baseline, "interpolated"
    )
    response_interpolated = _window_flag_fraction(
        recording, times, events, response, "interpolated"
    )
    disposition = np.full(baseline_means.shape, "complete", dtype="U40")
    baseline_missing = baseline_fraction < 1
    response_missing = response_fraction < 1
    disposition[baseline_missing] = "baseline_intersects_gap"
    disposition[response_missing] = "response_intersects_gap"
    disposition[baseline_missing & response_missing] = (
        "baseline_and_response_intersect_gap"
    )
    event_rows = np.asarray(
        [int(np.argmin(abs(times - event))) for event in events], dtype=int
    )
    event_missing = ~np.isfinite(values[event_rows, :])
    disposition[event_missing] = "event_inside_gap"
    degenerate = 0
    if normalization != "none":
        center, scale = _window_baseline_statistics(
            values, times, events, baseline, normalization
        )
        usable, safe_scale = _usable_baseline(center, scale)
        degenerate = int(np.count_nonzero(~usable))
        baseline_means = np.where(
            usable, (baseline_means - center) / safe_scale, np.nan
        )
        response_means = np.where(
            usable, (response_means - center) / safe_scale, np.nan
        )
    units = _normalized_units(variable, normalization)
    return xr.Dataset(
        data_vars={
            "baseline_mean": (("event", "channel"), baseline_means, {"units": units}),
            "response_mean": (("event", "channel"), response_means, {"units": units}),
            "delta": (
                ("event", "channel"),
                response_means - baseline_means,
                {"units": units},
            ),
            "baseline_finite_fraction": (
                ("event", "channel"),
                baseline_fraction,
            ),
            "response_finite_fraction": (
                ("event", "channel"),
                response_fraction,
            ),
            "event_disposition": (("event", "channel"), disposition),
            "baseline_interpolated_fraction": (
                ("event",),
                baseline_interpolated,
            ),
            "response_interpolated_fraction": (
                ("event",),
                response_interpolated,
            ),
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
            "normalization": normalization,
            "units": units,
            "degenerate_baseline_count": degenerate,
        },
    )


def _window_means(
    values: np.ndarray,
    times: np.ndarray,
    events: np.ndarray,
    window: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    output = np.full((len(events), values.shape[1]), np.nan)
    fractions = np.zeros((len(events), values.shape[1]), dtype=float)
    for index, event in enumerate(events):
        if not np.isfinite(event):
            continue
        selected = (times >= event + window[0]) & (times < event + window[1])
        if selected.any():
            selected_values = values[selected]
            finite = np.isfinite(selected_values)
            counts = finite.sum(axis=0)
            fractions[index] = counts / selected.sum()
            sums = np.where(finite, selected_values, 0.0).sum(axis=0)
            valid = counts == selected.sum()
            output[index, valid] = sums[valid] / counts[valid]
    return output, fractions


def _window_baseline_statistics(
    values: np.ndarray,
    times: np.ndarray,
    events: np.ndarray,
    window: tuple[float, float],
    normalization: str,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Measure each event's and channel's baseline centre and scale."""
    center = np.full((len(events), values.shape[1]), np.nan)
    scale = np.full((len(events), values.shape[1]), np.nan)
    for index, event in enumerate(events):
        if not np.isfinite(event):
            continue
        selected = (times >= event + window[0]) & (times < event + window[1])
        if selected.sum() < 2:
            continue
        center[index], scale[index] = _baseline_statistics(
            values[selected], normalization
        )
    return center, scale


def _baseline_statistics(
    values: NDArray[np.float64], normalization: str, *, axis: int = 0
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the centre and dispersion the requested normalization divides by.

    A non-finite baseline sample propagates to both statistics, so an incomplete
    baseline window is rejected rather than silently summarized over the rest.
    """
    if normalization == "baseline_z":
        return (
            np.asarray(np.mean(values, axis=axis), dtype=np.float64),
            np.asarray(np.std(values, axis=axis), dtype=np.float64),
        )
    median = np.median(values, axis=axis, keepdims=True)
    deviation = 1.4826 * np.median(np.abs(values - median), axis=axis)
    return (
        np.asarray(np.squeeze(median, axis=axis), dtype=np.float64),
        np.asarray(deviation, dtype=np.float64),
    )


def _usable_baseline(
    center: NDArray[np.float64], scale: NDArray[np.float64]
) -> tuple[NDArray[np.bool_], NDArray[np.float64]]:
    """Reject a baseline whose scale cannot normalize, never clamping it to eps."""
    usable = np.isfinite(center) & np.isfinite(scale) & (scale > 0)
    return usable, np.where(usable, scale, 1.0)


def _normalized_units(variable: str, normalization: str) -> str:
    if normalization == "baseline_z":
        return "baseline SD"
    if normalization == "robust_z":
        return "baseline robust SD (1.4826 * MAD)"
    return "dF/F" if variable == "dff" else "acquired units"


def condition_exclusion_warning(
    conditions: Sequence[str], dispositions: Sequence[str]
) -> bool:
    """Warn when complete-event fractions differ across conditions."""
    labels = np.asarray(conditions, dtype=str)
    status = np.asarray(dispositions, dtype=str)
    if len(labels) != len(status):
        raise ValueError("conditions and dispositions must have equal length")
    fractions = [
        float(np.mean(status[labels == label] == "complete"))
        for label in np.unique(labels)
    ]
    return len(fractions) > 1 and not np.allclose(fractions, fractions[0])


def condition_reconstruction_warning(
    conditions: Sequence[str], reconstructed_fractions: Sequence[float]
) -> bool:
    """Warn when mean reconstructed coverage differs across conditions."""
    labels = np.asarray(conditions, dtype=str)
    fractions = np.asarray(reconstructed_fractions, dtype=float)
    if len(labels) != len(fractions):
        raise ValueError(
            "conditions and reconstructed_fractions must have equal length"
        )
    condition_means = [
        float(np.mean(fractions[labels == label])) for label in np.unique(labels)
    ]
    return len(condition_means) > 1 and not np.allclose(
        condition_means, condition_means[0]
    )


def _window_flag_fraction(
    recording: xr.Dataset,
    times: np.ndarray,
    events: np.ndarray,
    window: tuple[float, float],
    variable: str,
) -> np.ndarray:
    output = np.zeros(len(events), dtype=float)
    if variable not in recording:
        return output
    flags = np.asarray(recording[variable].values, dtype=bool)
    for index, event in enumerate(events):
        selected = (times >= event + window[0]) & (times < event + window[1])
        if np.any(selected):
            output[index] = float(np.mean(flags[selected]))
    return output


def _interpolate_finite_runs(
    source_time: np.ndarray,
    source: np.ndarray,
    target: np.ndarray,
    *,
    max_gap_s: float | None,
) -> np.ndarray:
    output = np.full(len(target), np.nan)
    finite_rows = np.flatnonzero(np.isfinite(source))
    if not len(finite_rows):
        return output
    split = np.flatnonzero(np.diff(finite_rows) > 1) + 1
    groups = np.split(finite_rows, split)
    for group in groups:
        if max_gap_s is not None and len(group) > 1:
            time_splits = np.flatnonzero(np.diff(source_time[group]) > max_gap_s) + 1
            runs = np.split(group, time_splits)
        else:
            runs = [group]
        for run in runs:
            if len(run) < 2:
                continue
            within = (target >= source_time[run[0]]) & (target <= source_time[run[-1]])
            output[within] = np.interp(target[within], source_time[run], source[run])
    return output
