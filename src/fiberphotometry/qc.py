"""Channel-level quality diagnostics that warn without silently excluding data."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import numpy as np
import xarray as xr

from fiberphotometry.model import validate_recording
from fiberphotometry.preprocess import reference_dff


@dataclass(frozen=True)
class ChannelQC:
    """Auditable diagnostics for one signal/reference channel pair."""

    channel: str
    samples: int
    finite_paired_fraction: float
    longest_valid_segment_s: float
    signal_reference_correlation: float
    extreme_repeat_fraction: float
    flat_step_fraction: float
    ols_intercept: float
    ols_slope: float
    irls_intercept: float
    irls_slope: float
    relative_slope_difference: float
    ols_residual_rmse: float
    irls_residual_rmse: float
    fitted_denominator_min_ratio: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RecordingQC:
    """Recording-wide sampling metrics and per-channel diagnostics."""

    subject: str
    session: str
    samples: int
    estimated_rate_hz: float
    sampling_interval_cv: float
    large_gap_count: int
    channels: tuple[ChannelQC, ...]

    def to_json(self) -> str:
        """Return deterministic machine-readable QC output."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class SignalChannelQC:
    """Diagnostics available when no independent reference channel exists."""

    channel: str
    samples: int
    finite_fraction: float
    longest_valid_segment_s: float
    extreme_repeat_fraction: float
    flat_step_fraction: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SignalRecordingQC:
    """Recording-wide signal-only QC without invented reference metrics."""

    subject: str
    session: str
    samples: int
    estimated_rate_hz: float
    sampling_interval_cv: float
    large_gap_count: int
    channels: tuple[SignalChannelQC, ...]

    def to_json(self) -> str:
        """Return deterministic machine-readable QC output."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def assess_recording(recording: xr.Dataset) -> RecordingQC:
    """Calculate transparent QC metrics without changing or rejecting samples."""
    validate_recording(recording)
    if "reference" not in recording:
        raise ValueError("QC requires a reference variable")
    time = np.asarray(recording.time.values, dtype=float)
    intervals = np.diff(time)
    median_interval = float(np.median(intervals))
    rate = 1 / median_interval
    interval_cv = float(np.std(intervals) / np.mean(intervals))
    gap_count = int(np.sum(intervals > 1.5 * median_interval))
    ols = reference_dff(recording, method="ols")
    irls = reference_dff(recording, method="irls")
    channels = tuple(
        _assess_channel(recording, ols, irls, index, median_interval)
        for index in range(recording.sizes["channel"])
    )
    return RecordingQC(
        subject=str(recording.attrs["subject"]),
        session=str(recording.attrs["session"]),
        samples=recording.sizes["time"],
        estimated_rate_hz=rate,
        sampling_interval_cv=interval_cv,
        large_gap_count=gap_count,
        channels=channels,
    )


def assess_signal_recording(recording: xr.Dataset) -> SignalRecordingQC:
    """Calculate diagnostics that do not require a reference channel."""
    validate_recording(recording)
    time = np.asarray(recording.time.values, dtype=float)
    intervals = np.diff(time)
    median_interval = float(np.median(intervals))
    channels = []
    for index, name in enumerate(recording.channel.values):
        signal = np.asarray(recording.signal.values[:, index], dtype=float)
        finite = np.isfinite(signal)
        finite_values = signal[finite]
        finite_fraction = float(finite.mean())
        extreme_fraction = _extreme_repeat_fraction(finite_values)
        flat_fraction = _flat_step_fraction(finite_values)
        warnings = []
        if finite_fraction < 0.8:
            warnings.append("low_valid_fraction")
        if extreme_fraction > 0.01:
            warnings.append("repeated_extreme_values")
        if flat_fraction > 0.01:
            warnings.append("flat_steps")
        channels.append(
            SignalChannelQC(
                str(name),
                len(signal),
                finite_fraction,
                _longest_true_run(finite) * median_interval,
                extreme_fraction,
                flat_fraction,
                tuple(warnings),
            )
        )
    return SignalRecordingQC(
        subject=str(recording.attrs["subject"]),
        session=str(recording.attrs["session"]),
        samples=recording.sizes["time"],
        estimated_rate_hz=1 / median_interval,
        sampling_interval_cv=float(np.std(intervals) / np.mean(intervals)),
        large_gap_count=int(np.sum(intervals > 1.5 * median_interval)),
        channels=tuple(channels),
    )


def _assess_channel(
    recording: xr.Dataset,
    ols: xr.Dataset,
    irls: xr.Dataset,
    index: int,
    median_interval: float,
) -> ChannelQC:
    signal = np.asarray(recording.signal.values[:, index], dtype=float)
    reference = np.asarray(recording.reference.values[:, index], dtype=float)
    paired = np.isfinite(signal) & np.isfinite(reference)
    paired_fraction = float(paired.mean())
    segment_samples = _longest_true_run(paired)
    correlation = (
        float(np.corrcoef(signal[paired], reference[paired])[0, 1])
        if paired.sum() >= 2
        else float("nan")
    )
    finite_signal = signal[np.isfinite(signal)]
    extreme_fraction = _extreme_repeat_fraction(finite_signal)
    flat_fraction = _flat_step_fraction(finite_signal)
    ols_coefficients = ols.reference_fit_coefficient.values[index]
    irls_coefficients = irls.reference_fit_coefficient.values[index]
    ols_fitted = np.asarray(ols.fitted_reference.values[:, index], dtype=float)
    irls_fitted = np.asarray(irls.fitted_reference.values[:, index], dtype=float)
    ols_rmse = _residual_rmse(signal, ols_fitted)
    irls_rmse = _residual_rmse(signal, irls_fitted)
    slope_scale = max(abs(float(ols_coefficients[1])), np.finfo(float).eps)
    relative_slope_difference = float(
        abs(irls_coefficients[1] - ols_coefficients[1]) / slope_scale
    )
    fitted_valid = np.abs(irls_fitted[np.isfinite(irls_fitted)])
    denominator_ratio = (
        float(np.min(fitted_valid) / np.median(fitted_valid))
        if len(fitted_valid)
        else float("nan")
    )
    warnings = _warnings(
        paired_fraction=paired_fraction,
        correlation=correlation,
        extreme_fraction=extreme_fraction,
        flat_fraction=flat_fraction,
        relative_slope_difference=relative_slope_difference,
        denominator_ratio=denominator_ratio,
    )
    return ChannelQC(
        channel=str(recording.channel.values[index]),
        samples=len(signal),
        finite_paired_fraction=paired_fraction,
        longest_valid_segment_s=segment_samples * median_interval,
        signal_reference_correlation=correlation,
        extreme_repeat_fraction=extreme_fraction,
        flat_step_fraction=flat_fraction,
        ols_intercept=float(ols_coefficients[0]),
        ols_slope=float(ols_coefficients[1]),
        irls_intercept=float(irls_coefficients[0]),
        irls_slope=float(irls_coefficients[1]),
        relative_slope_difference=relative_slope_difference,
        ols_residual_rmse=ols_rmse,
        irls_residual_rmse=irls_rmse,
        fitted_denominator_min_ratio=denominator_ratio,
        warnings=warnings,
    )


def _longest_true_run(values: np.ndarray) -> int:
    padded = np.concatenate([[False], values, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return int(np.max(edges[1::2] - edges[::2], initial=0))


def _extreme_repeat_fraction(values: np.ndarray) -> float:
    if not len(values):
        return float("nan")
    minimum_count = int(np.sum(values == np.min(values)))
    maximum_count = int(np.sum(values == np.max(values)))
    repeated = max(minimum_count - 1, 0) + max(maximum_count - 1, 0)
    return float(repeated / len(values))


def _flat_step_fraction(values: np.ndarray) -> float:
    if len(values) < 2:
        return float("nan")
    scale = max(float(np.nanstd(values)), np.finfo(float).eps)
    return float(np.mean(np.abs(np.diff(values)) <= scale * 1e-12))


def _residual_rmse(signal: np.ndarray, fitted: np.ndarray) -> float:
    valid = np.isfinite(signal) & np.isfinite(fitted)
    return (
        float(np.sqrt(np.mean(np.square(signal[valid] - fitted[valid]))))
        if valid.any()
        else float("nan")
    )


def _warnings(
    *,
    paired_fraction: float,
    correlation: float,
    extreme_fraction: float,
    flat_fraction: float,
    relative_slope_difference: float,
    denominator_ratio: float,
) -> tuple[str, ...]:
    warnings = []
    if paired_fraction < 0.8:
        warnings.append("low_valid_fraction")
    if np.isfinite(correlation) and abs(correlation) < 0.1:
        warnings.append("weak_signal_reference_correlation")
    if extreme_fraction > 0.01:
        warnings.append("repeated_extreme_values")
    if flat_fraction > 0.01:
        warnings.append("flat_steps")
    if relative_slope_difference > 0.25:
        warnings.append("fit_method_sensitive")
    if np.isfinite(denominator_ratio) and denominator_ratio < 0.1:
        warnings.append("unstable_dff_denominator")
    return tuple(warnings)
