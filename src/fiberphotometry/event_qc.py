"""Event-aware diagnostics for reference-channel confounds and timing lag."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np
import xarray as xr

from fiberphotometry.events import summarize_event_windows
from fiberphotometry.model import validate_recording


@dataclass(frozen=True)
class EventChannelQC:
    """Diagnostics for one channel relative to a specified event series."""

    channel: str
    valid_events: int
    reference_event_effect_sd: float
    signal_reference_event_correlation: float
    derivative_zero_lag_correlation: float
    derivative_best_lag_correlation: float
    derivative_best_lag_s: float
    derivative_lag_improvement: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class EventQC:
    """Event-aware QC result retaining the tested windows and lag range."""

    subject: str
    session: str
    baseline: tuple[float, float]
    response: tuple[float, float]
    maximum_lag_s: float
    channels: tuple[EventChannelQC, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def assess_event_confounds(
    recording: xr.Dataset,
    event_times: Sequence[float],
    *,
    baseline: tuple[float, float] = (-0.5, 0.0),
    response: tuple[float, float] = (0.0, 0.5),
    maximum_lag_s: float = 1.0,
) -> EventQC:
    """Flag event-correlated reference responses and signal/reference lag.

    These diagnostics require user-supplied event times and therefore complement,
    rather than replace, recording-level QC. Warnings are advisory; no events or
    samples are excluded.
    """
    validate_recording(recording)
    if "reference" not in recording:
        raise ValueError("event QC requires a reference variable")
    if maximum_lag_s <= 0:
        raise ValueError("maximum_lag_s must be positive")
    signal_events = summarize_event_windows(
        recording,
        event_times,
        baseline=baseline,
        response=response,
        variable="signal",
    )
    reference_events = summarize_event_windows(
        recording,
        event_times,
        baseline=baseline,
        response=response,
        variable="reference",
    )
    time = np.asarray(recording.time.values, dtype=float)
    median_interval = float(np.median(np.diff(time)))
    maximum_lag_samples = max(1, round(maximum_lag_s / median_interval))
    channels = tuple(
        _assess_channel(
            recording,
            signal_events,
            reference_events,
            index,
            median_interval,
            maximum_lag_samples,
        )
        for index in range(recording.sizes["channel"])
    )
    return EventQC(
        subject=str(recording.attrs["subject"]),
        session=str(recording.attrs["session"]),
        baseline=baseline,
        response=response,
        maximum_lag_s=maximum_lag_s,
        channels=channels,
    )


def _assess_channel(
    recording: xr.Dataset,
    signal_events: xr.Dataset,
    reference_events: xr.Dataset,
    index: int,
    interval: float,
    maximum_lag_samples: int,
) -> EventChannelQC:
    signal_delta = np.asarray(signal_events.delta.values[:, index], dtype=float)
    reference_delta = np.asarray(reference_events.delta.values[:, index], dtype=float)
    event_valid = np.isfinite(signal_delta) & np.isfinite(reference_delta)
    reference = np.asarray(recording.reference.values[:, index], dtype=float)
    reference_scale = max(float(np.nanstd(reference)), np.finfo(float).eps)
    effect = float(np.nanmedian(reference_delta) / reference_scale)
    event_correlation = _correlation(
        signal_delta[event_valid], reference_delta[event_valid]
    )
    signal = np.asarray(recording.signal.values[:, index], dtype=float)
    zero, best, lag = _derivative_lag(signal, reference, maximum_lag_samples)
    improvement = abs(best) - abs(zero)
    warnings = []
    if abs(effect) >= 0.5:
        warnings.append("event_correlated_reference")
    if abs(lag * interval) >= 0.1 and improvement >= 0.05:
        warnings.append("signal_reference_lag")
    return EventChannelQC(
        channel=str(recording.channel.values[index]),
        valid_events=int(event_valid.sum()),
        reference_event_effect_sd=effect,
        signal_reference_event_correlation=event_correlation,
        derivative_zero_lag_correlation=zero,
        derivative_best_lag_correlation=best,
        derivative_best_lag_s=float(lag * interval),
        derivative_lag_improvement=float(improvement),
        warnings=tuple(warnings),
    )


def _derivative_lag(
    signal: np.ndarray, reference: np.ndarray, maximum_lag: int
) -> tuple[float, float, int]:
    signal_diff = np.diff(signal)
    reference_diff = np.diff(reference)
    correlations = []
    lags = range(-maximum_lag, maximum_lag + 1)
    for lag in lags:
        if lag < 0:
            left, right = signal_diff[-lag:], reference_diff[:lag]
        elif lag > 0:
            left, right = signal_diff[:-lag], reference_diff[lag:]
        else:
            left, right = signal_diff, reference_diff
        valid = np.isfinite(left) & np.isfinite(right)
        correlations.append(_correlation(left[valid], right[valid]))
    values = np.asarray(correlations)
    best_index = int(np.nanargmax(np.abs(values)))
    return float(values[maximum_lag]), float(values[best_index]), list(lags)[best_index]


def _correlation(left: np.ndarray, right: np.ndarray) -> float:
    if len(left) < 3 or np.std(left) == 0 or np.std(right) == 0:
        return float("nan")
    return float(np.corrcoef(left, right)[0, 1])
