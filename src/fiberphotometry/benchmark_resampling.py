"""Reusable sharp-transient and missing-run benchmark primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class TransientSpec:
    family: Literal["gaussian", "alpha", "biphasic"]
    transient_class: Literal["ordinary", "stress"]
    width_samples: float | None = None
    rise_samples: float | None = None
    decay_samples: float | None = None
    separation_samples: float | None = None


@dataclass(frozen=True)
class ReconstructionMetrics:
    normalized_waveform_rmse: float | None
    peak_amplitude_relative_error: float | None
    peak_time_error_samples: float | None
    response_mean_relative_error: float | None
    event_contrast_relative_error: float | None
    false_peak_amplitude: float
    reconstructed_window_fraction: float
    event_disposition: str


def generate_transient(
    time: NDArray[np.float64],
    *,
    event_time: float,
    rate_hz: float,
    spec: TransientSpec,
) -> NDArray[np.float64]:
    """Generate a unit-amplitude transient from parameters expressed in samples."""
    relative = time - event_time
    if spec.family == "gaussian":
        if spec.width_samples is None:
            raise ValueError("gaussian transient requires width_samples")
        width_s = spec.width_samples / rate_hz
        values = np.exp(-0.5 * (relative / width_s) ** 2)
    elif spec.family == "alpha":
        if spec.rise_samples is None or spec.decay_samples is None:
            raise ValueError("alpha transient requires rise_samples and decay_samples")
        rise_s = spec.rise_samples / rate_hz
        decay_s = spec.decay_samples / rate_hz
        positive = np.maximum(relative, 0)
        values = (1 - np.exp(-positive / rise_s)) * np.exp(-positive / decay_s)
        values[relative < 0] = 0
    else:
        if spec.width_samples is None or spec.separation_samples is None:
            raise ValueError(
                "biphasic transient requires width_samples and separation_samples"
            )
        width_s = spec.width_samples / rate_hz
        separation_s = spec.separation_samples / rate_hz
        values = np.exp(-0.5 * (relative / width_s) ** 2)
        values -= 0.6 * np.exp(-0.5 * ((relative - separation_s) / width_s) ** 2)
    maximum = float(np.max(values))
    return values / maximum


def event_disposition(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    *,
    event_time: float,
    baseline: tuple[float, float] = (-1.0, 0.0),
    response: tuple[float, float] = (0.0, 1.0),
) -> str:
    """Classify missing coverage without silently accepting partial windows."""
    finite = np.isfinite(values)
    event_index = int(np.argmin(np.abs(time - event_time)))
    baseline_rows = (time >= event_time + baseline[0]) & (
        time < event_time + baseline[1]
    )
    response_rows = (time >= event_time + response[0]) & (
        time <= event_time + response[1]
    )
    if not finite[event_index]:
        return "event_inside_gap"
    baseline_missing = not np.all(finite[baseline_rows])
    response_missing = not np.all(finite[response_rows])
    if baseline_missing and response_missing:
        return "baseline_and_response_intersect_gap"
    if baseline_missing:
        return "baseline_intersects_gap"
    if response_missing:
        return "response_intersects_gap"
    if not np.any(baseline_rows) or not np.any(response_rows):
        return "insufficient_window_coverage"
    return "complete"


def reconstruction_metrics(
    time: NDArray[np.float64],
    truth: NDArray[np.float64],
    observed: NDArray[np.float64],
    reconstructed: NDArray[np.bool_],
    *,
    event_time: float,
    rate_hz: float,
    contrast_denominator: Literal["truth_contrast", "peak_amplitude"] = (
        "truth_contrast"
    ),
) -> ReconstructionMetrics:
    """Measure waveform and event-summary consequences on one common time grid."""
    disposition = event_disposition(time, observed, event_time=event_time)
    baseline_rows = (time >= event_time - 1) & (time < event_time)
    response_rows = (time >= event_time) & (time <= event_time + 1)
    analysis_rows = baseline_rows | response_rows
    reconstructed_fraction = float(np.mean(reconstructed[analysis_rows]))
    finite = np.isfinite(observed) & analysis_rows
    if disposition != "complete" or not np.any(finite):
        return ReconstructionMetrics(
            None,
            None,
            None,
            None,
            None,
            0.0,
            reconstructed_fraction,
            disposition,
        )
    scale = max(float(np.max(np.abs(truth[analysis_rows]))), np.finfo(float).eps)
    waveform_rmse = float(
        np.sqrt(np.mean((observed[analysis_rows] - truth[analysis_rows]) ** 2)) / scale
    )
    truth_peak_row = np.flatnonzero(response_rows)[int(np.argmax(truth[response_rows]))]
    observed_peak_row = np.flatnonzero(response_rows)[
        int(np.argmax(observed[response_rows]))
    ]
    truth_peak = float(truth[truth_peak_row])
    observed_peak = float(observed[observed_peak_row])
    peak_error = abs(observed_peak - truth_peak) / max(abs(truth_peak), 1e-12)
    peak_time_error = abs(time[observed_peak_row] - time[truth_peak_row]) * rate_hz
    truth_response = float(np.mean(truth[response_rows]))
    observed_response = float(np.mean(observed[response_rows]))
    response_error = abs(observed_response - truth_response) / max(
        abs(truth_response), 1e-12
    )
    truth_contrast = truth_response - float(np.mean(truth[baseline_rows]))
    observed_contrast = observed_response - float(np.mean(observed[baseline_rows]))
    contrast_scale = (
        abs(truth_contrast)
        if contrast_denominator == "truth_contrast"
        else float(np.max(np.abs(truth[analysis_rows])))
    )
    contrast_error = abs(observed_contrast - truth_contrast) / max(
        contrast_scale, 1e-12
    )
    return ReconstructionMetrics(
        waveform_rmse,
        peak_error,
        peak_time_error,
        response_error,
        contrast_error,
        0.0,
        reconstructed_fraction,
        disposition,
    )
