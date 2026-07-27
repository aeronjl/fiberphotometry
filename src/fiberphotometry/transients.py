"""Experimental, gap-aware detection of spontaneous fluorescence transients."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

import numpy as np
import xarray as xr
from scipy.signal import find_peaks

from fiberphotometry.model import validate_recording

BaselineStatistic = Literal["mean", "median", "minimum"]
ThresholdMode = Literal["absolute", "global_mad", "rolling_mad"]


@dataclass(frozen=True)
class TransientDetectionSpec:
    """Declare one reproducible spontaneous-transient detection universe."""

    threshold_mode: ThresholdMode = "rolling_mad"
    threshold: float = 3.0
    baseline_duration_s: float = 0.9
    baseline_gap_s: float = 0.1
    baseline_statistic: BaselineStatistic = "median"
    noise_window_s: float = 15.0
    minimum_distance_s: float = 0.2
    maximum_gap_factor: float = 3.0
    require_complete_shape: bool = True
    bin_width_s: float | None = 30.0


@dataclass(frozen=True)
class TransientEvent:
    """Measurements for one accepted candidate, relative to its local baseline."""

    channel: str
    peak_time: float
    peak_value: float
    baseline: float
    amplitude: float
    threshold: float
    onset_half_height_time: float
    offset_half_height_time: float
    rise_half_height_s: float
    fall_half_height_s: float
    full_width_half_height_s: float
    auc_above_baseline: float
    previous_interval_s: float | None


@dataclass(frozen=True)
class TransientExclusion:
    """A local maximum that was considered but not accepted."""

    channel: str
    peak_time: float
    reason: Literal[
        "insufficient_baseline",
        "below_threshold",
        "incomplete_shape",
        "nonpositive_amplitude",
    ]


@dataclass(frozen=True)
class TransientChannelSummary:
    """Session-level summary that uses acquired, finite duration as denominator."""

    channel: str
    analyzed_duration_s: float
    count: int
    rate_per_minute: float
    median_amplitude: float | None
    median_width_s: float | None
    median_auc: float | None
    median_interval_s: float | None


@dataclass(frozen=True)
class TransientDetectionResult:
    """Accepted events, rejected candidates, summaries, and long-window bins."""

    spec: TransientDetectionSpec
    events: tuple[TransientEvent, ...]
    exclusions: tuple[TransientExclusion, ...]
    summaries: tuple[TransientChannelSummary, ...]
    bins: xr.Dataset | None


def detect_transients(
    recording: xr.Dataset,
    *,
    variable: str = "dff",
    spec: TransientDetectionSpec | None = None,
) -> TransientDetectionResult:
    """Detect spontaneous transients without bridging missing acquisition.

    This experimental method intentionally exposes choices that differ across the
    literature. MAD thresholds are robust-sigma estimates (``1.4826 * MAD``).
    Shape measurements and AUC use half-height crossings relative to the local
    pre-peak baseline. Long-window bins are descriptive summaries, not a claim
    that their variation is a biological "tonic" component.
    """
    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    chosen = spec or TransientDetectionSpec()
    _validate_spec(chosen)
    time = np.asarray(recording.time.values, dtype=float)
    values = np.asarray(recording[variable].values, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(time):
        raise ValueError("variable must have ('time', 'channel') shape")
    sample_step = float(np.median(np.diff(time)))
    maximum_gap = chosen.maximum_gap_factor * sample_step
    minimum_distance = max(1, int(np.ceil(chosen.minimum_distance_s / sample_step)))
    events: list[TransientEvent] = []
    exclusions: list[TransientExclusion] = []
    summaries: list[TransientChannelSummary] = []
    channel_names = [str(item) for item in recording.channel.values]

    for channel_index, channel in enumerate(channel_names):
        signal = values[:, channel_index]
        channel_events: list[TransientEvent] = []
        for run in _finite_runs(time, signal, maximum_gap):
            if len(run) < 3:
                continue
            previous_peak_time: float | None = None
            candidates, _ = find_peaks(signal[run], distance=minimum_distance)
            run_scale = _robust_scale(signal[run])
            for relative_peak in candidates:
                peak = int(run[relative_peak])
                baseline_rows = run[
                    (
                        time[run]
                        >= time[peak]
                        - chosen.baseline_gap_s
                        - chosen.baseline_duration_s
                    )
                    & (time[run] < time[peak] - chosen.baseline_gap_s)
                ]
                if len(baseline_rows) < 2:
                    exclusions.append(
                        TransientExclusion(
                            channel, float(time[peak]), "insufficient_baseline"
                        )
                    )
                    continue
                baseline = _baseline(signal[baseline_rows], chosen.baseline_statistic)
                amplitude = float(signal[peak] - baseline)
                if amplitude <= 0:
                    exclusions.append(
                        TransientExclusion(
                            channel, float(time[peak]), "nonpositive_amplitude"
                        )
                    )
                    continue
                threshold = _threshold(time, signal, run, peak, chosen, run_scale)
                if amplitude < threshold:
                    exclusions.append(
                        TransientExclusion(
                            channel, float(time[peak]), "below_threshold"
                        )
                    )
                    continue
                crossings = _half_height_crossings(time, signal, run, peak, baseline)
                if crossings is None:
                    exclusions.append(
                        TransientExclusion(
                            channel, float(time[peak]), "incomplete_shape"
                        )
                    )
                    if chosen.require_complete_shape:
                        continue
                    onset = offset = float("nan")
                    auc = float("nan")
                else:
                    onset, offset, left_row, right_row = crossings
                    integration_rows = run[(run >= left_row) & (run <= right_row)]
                    auc = float(
                        np.trapezoid(
                            signal[integration_rows] - baseline, time[integration_rows]
                        )
                    )
                previous = (
                    float(time[peak] - previous_peak_time)
                    if previous_peak_time is not None
                    else None
                )
                event = TransientEvent(
                    channel=channel,
                    peak_time=float(time[peak]),
                    peak_value=float(signal[peak]),
                    baseline=baseline,
                    amplitude=amplitude,
                    threshold=threshold,
                    onset_half_height_time=onset,
                    offset_half_height_time=offset,
                    rise_half_height_s=float(time[peak] - onset),
                    fall_half_height_s=float(offset - time[peak]),
                    full_width_half_height_s=float(offset - onset),
                    auc_above_baseline=auc,
                    previous_interval_s=previous,
                )
                channel_events.append(event)
                events.append(event)
                previous_peak_time = float(time[peak])
        duration = _analyzed_duration(time, signal, maximum_gap)
        summaries.append(_summarize_channel(channel, duration, channel_events))

    bins = _bin_events(time, values, channel_names, events, chosen, maximum_gap)
    return TransientDetectionResult(
        spec=chosen,
        events=tuple(events),
        exclusions=tuple(exclusions),
        summaries=tuple(summaries),
        bins=bins,
    )


def _validate_spec(spec: TransientDetectionSpec) -> None:
    positive = {
        "threshold": spec.threshold,
        "baseline_duration_s": spec.baseline_duration_s,
        "noise_window_s": spec.noise_window_s,
        "minimum_distance_s": spec.minimum_distance_s,
        "maximum_gap_factor": spec.maximum_gap_factor,
    }
    if any(value <= 0 for value in positive.values()):
        raise ValueError(
            "threshold, window, distance, and gap parameters must be positive"
        )
    if spec.baseline_gap_s < 0:
        raise ValueError("baseline_gap_s cannot be negative")
    if spec.bin_width_s is not None and spec.bin_width_s <= 0:
        raise ValueError("bin_width_s must be positive when provided")


def _finite_runs(
    time: np.ndarray, signal: np.ndarray, maximum_gap: float
) -> list[np.ndarray]:
    finite = np.flatnonzero(np.isfinite(signal))
    if not len(finite):
        return []
    breaks = (np.diff(finite) > 1) | (np.diff(time[finite]) > maximum_gap)
    return [run for run in np.split(finite, np.flatnonzero(breaks) + 1) if len(run)]


def _baseline(values: np.ndarray, statistic: BaselineStatistic) -> float:
    if statistic == "mean":
        return float(np.mean(values))
    if statistic == "minimum":
        return float(np.min(values))
    return float(np.median(values))


def _robust_scale(values: np.ndarray) -> float:
    median = float(np.median(values))
    return max(1.4826 * float(np.median(np.abs(values - median))), np.finfo(float).eps)


def _threshold(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    peak: int,
    spec: TransientDetectionSpec,
    run_scale: float,
) -> float:
    if spec.threshold_mode == "absolute":
        return spec.threshold
    scale = run_scale
    if spec.threshold_mode == "rolling_mad":
        half = spec.noise_window_s / 2
        local = run[(time[run] >= time[peak] - half) & (time[run] <= time[peak] + half)]
        if len(local) >= 3:
            scale = _robust_scale(signal[local])
    return float(spec.threshold * scale)


def _half_height_crossings(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    peak: int,
    baseline: float,
) -> tuple[float, float, int, int] | None:
    target = baseline + (float(signal[peak]) - baseline) / 2
    position = int(np.flatnonzero(run == peak)[0])
    left_candidates = np.flatnonzero(signal[run[:position]] <= target)
    right_candidates = np.flatnonzero(signal[run[position + 1 :]] <= target)
    if not len(left_candidates) or not len(right_candidates):
        return None
    left_low_position = int(left_candidates[-1])
    left_low = int(run[left_low_position])
    left_high = int(run[left_low_position + 1])
    right_low_position = position + int(right_candidates[0])
    right_high = int(run[right_low_position])
    right_low = int(run[right_low_position + 1])
    onset = _interpolate_crossing(time, signal, left_low, left_high, target)
    offset = _interpolate_crossing(time, signal, right_high, right_low, target)
    return onset, offset, left_low, right_low


def _interpolate_crossing(
    time: np.ndarray, signal: np.ndarray, first: int, second: int, target: float
) -> float:
    change = float(signal[second] - signal[first])
    if change == 0:
        return float(time[first])
    fraction = (target - float(signal[first])) / change
    return float(time[first] + fraction * (time[second] - time[first]))


def _analyzed_duration(
    time: np.ndarray, signal: np.ndarray, maximum_gap: float
) -> float:
    return float(
        sum(
            time[run[-1]] - time[run[0]]
            for run in _finite_runs(time, signal, maximum_gap)
            if len(run) > 1
        )
    )


def _summarize_channel(
    channel: str, duration: float, events: list[TransientEvent]
) -> TransientChannelSummary:
    intervals = [
        event.previous_interval_s
        for event in events
        if event.previous_interval_s is not None
    ]

    def median(values: list[float]) -> float | None:
        return float(np.median(values)) if values else None

    return TransientChannelSummary(
        channel=channel,
        analyzed_duration_s=duration,
        count=len(events),
        rate_per_minute=(60 * len(events) / duration if duration > 0 else 0.0),
        median_amplitude=median([event.amplitude for event in events]),
        median_width_s=median([event.full_width_half_height_s for event in events]),
        median_auc=median([event.auc_above_baseline for event in events]),
        median_interval_s=median(intervals),
    )


def _bin_events(
    time: np.ndarray,
    values: np.ndarray,
    channels: list[str],
    events: list[TransientEvent],
    spec: TransientDetectionSpec,
    maximum_gap: float,
) -> xr.Dataset | None:
    if spec.bin_width_s is None:
        return None
    edges = np.arange(time[0], time[-1] + spec.bin_width_s, spec.bin_width_s)
    if len(edges) < 2 or edges[-1] < time[-1]:
        edges = np.append(edges, time[-1])
    shape = (len(edges) - 1, len(channels))
    count = np.zeros(shape, dtype=int)
    coverage = np.zeros(shape, dtype=float)
    median_amplitude = np.full(shape, np.nan)
    for channel_index, channel in enumerate(channels):
        channel_events = [event for event in events if event.channel == channel]
        for bin_index, (start, stop) in enumerate(pairwise(edges)):
            selected = [
                event for event in channel_events if start <= event.peak_time < stop
            ]
            count[bin_index, channel_index] = len(selected)
            if selected:
                median_amplitude[bin_index, channel_index] = float(
                    np.median([event.amplitude for event in selected])
                )
            for run in _finite_runs(time, values[:, channel_index], maximum_gap):
                coverage[bin_index, channel_index] += max(
                    0.0, min(stop, time[run[-1]]) - max(start, time[run[0]])
                )
    rate = np.divide(
        60 * count, coverage, out=np.zeros_like(coverage), where=coverage > 0
    )
    return xr.Dataset(
        data_vars={
            "count": (("bin", "channel"), count),
            "analyzed_duration_s": (("bin", "channel"), coverage),
            "rate_per_minute": (("bin", "channel"), rate),
            "median_amplitude": (("bin", "channel"), median_amplitude),
        },
        coords={
            "bin": np.arange(len(edges) - 1),
            "bin_start": ("bin", edges[:-1]),
            "bin_stop": ("bin", edges[1:]),
            "channel": channels,
        },
        attrs={
            "interpretation": "descriptive transient bins; not a tonic-signal estimate"
        },
    )
