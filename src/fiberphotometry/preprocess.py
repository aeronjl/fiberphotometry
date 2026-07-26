"""Explicit, provenance-recorded preprocessing operations."""

from __future__ import annotations

import json
from itertools import pairwise
from typing import Literal

import numpy as np
import xarray as xr
from numpy.typing import NDArray
from scipy.optimize import least_squares
from scipy.signal import butter, sosfiltfilt
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve

from fiberphotometry.model import validate_recording


def baseline_dff(
    recording: xr.Dataset,
    *,
    method: str = "double_exponential",
    variable: str = "signal",
    min_tau_s: float = 5.0,
    asls_smoothness: float = 1e8,
    asls_asymmetry: float = 0.01,
    max_iterations: int = 20,
    normalization: Literal["divide", "subtract"] = "divide",
    asls_reference_rate_hz: float = 20.0,
    rolling_window_s: float = 60.0,
    rolling_gap_factor: float = 1.5,
) -> xr.Dataset:
    """Estimate a signal-only baseline and divide or subtract with provenance.

    ``double_exponential`` fits a non-negative offset plus two non-negative
    exponential decays using robust nonlinear least squares. ``asls`` estimates a
    smooth lower envelope with asymmetric least squares. ``rolling_mean`` reproduces
    a centred, full-window sample-count rolling mean, while splitting timestamp gaps.
    Neither method can identify motion or event-locked artefact from a single
    fluorescence channel. Division creates ``dff``; subtraction creates
    ``baseline_subtracted`` in acquired units.
    """
    validate_recording(recording)
    if method not in {"double_exponential", "asls", "rolling_mean"}:
        raise ValueError(
            "method must be 'double_exponential', 'asls', or 'rolling_mean'"
        )
    if variable not in recording:
        raise ValueError(f"recording does not contain baseline variable {variable!r}")
    if recording[variable].dims != ("time", "channel"):
        raise ValueError("baseline variable must have time and channel dimensions")
    if min_tau_s <= 0:
        raise ValueError("min_tau_s must be positive")
    if asls_smoothness <= 0:
        raise ValueError("asls_smoothness must be positive")
    if not 0 < asls_asymmetry < 1:
        raise ValueError("asls_asymmetry must lie between zero and one")
    if max_iterations < 1:
        raise ValueError("max_iterations must be positive")
    if normalization not in {"divide", "subtract"}:
        raise ValueError("normalization must be 'divide' or 'subtract'")
    if asls_reference_rate_hz <= 0:
        raise ValueError("asls_reference_rate_hz must be positive")
    if rolling_window_s <= 0:
        raise ValueError("rolling_window_s must be positive")
    if rolling_gap_factor <= 1:
        raise ValueError("rolling_gap_factor must be greater than one")

    time = np.asarray(recording.time.values, dtype=float)
    intervals = np.diff(time)
    sampling_rate_hz = 1 / float(np.median(intervals))
    if method == "asls" and float(np.std(intervals) / np.mean(intervals)) > 1e-6:
        raise ValueError("AsLS baseline fitting requires regularly sampled data")
    effective_smoothness = (
        asls_smoothness * (sampling_rate_hz / asls_reference_rate_hz) ** 4
    )
    source = np.asarray(recording[variable].values, dtype=float)
    baseline = np.full_like(source, np.nan)
    parameters = np.full((source.shape[1], 5), np.nan)
    failed_runs = 0
    max_gap_s = rolling_gap_factor * float(np.median(intervals))
    rolling_intervals = intervals[intervals <= max_gap_s]
    rolling_sampling_rate_hz = round(1 / float(np.mean(rolling_intervals)))
    rolling_window_samples = max(1, int(rolling_window_s * rolling_sampling_rate_hz))
    for channel in range(source.shape[1]):
        finite = np.isfinite(source[:, channel])
        runs = (
            _finite_time_runs(finite, time, max_gap_s=max_gap_s)
            if method == "rolling_mean"
            else _finite_runs(finite)
        )
        for start, stop in runs:
            run_time = time[start:stop]
            run_values = source[start:stop, channel]
            minimum_samples = {
                "double_exponential": 6,
                "asls": 3,
                "rolling_mean": rolling_window_samples,
            }[method]
            if len(run_values) < minimum_samples:
                failed_runs += 1
                continue
            if method == "double_exponential":
                fitted, fitted_parameters = _fit_double_exponential(
                    run_time, run_values, min_tau_s
                )
                parameters[channel] = fitted_parameters
            elif method == "asls":
                fitted = _fit_asls(
                    run_values,
                    smoothness=effective_smoothness,
                    asymmetry=asls_asymmetry,
                    max_iterations=max_iterations,
                )
            else:
                fitted = _fit_centered_rolling_mean(
                    run_values, window_samples=rolling_window_samples
                )
            baseline[start:stop, channel] = fitted

    corrected = source - baseline
    output = recording.copy(deep=True)
    output["fitted_baseline"] = (("time", "channel"), baseline)
    if normalization == "divide":
        divided = np.full_like(source, np.nan)
        safe = np.isfinite(baseline) & (np.abs(baseline) > np.finfo(float).eps)
        divided[safe] = corrected[safe] / baseline[safe]
        output["dff"] = (("time", "channel"), divided)
    else:
        output["baseline_subtracted"] = (("time", "channel"), corrected)
    if method == "double_exponential":
        output["baseline_fit_parameter"] = (
            ("channel", "baseline_parameter"),
            parameters,
        )
        output = output.assign_coords(
            baseline_parameter=[
                "offset",
                "amplitude_1",
                "tau_1",
                "amplitude_2",
                "tau_2",
            ]
        )
    operation: dict[str, object] = {
        "kind": "baseline_dff",
        "method": method,
        "variable": variable,
        "normalization": normalization,
        "formula": (
            "(variable - fitted_baseline) / fitted_baseline"
            if normalization == "divide"
            else "variable - fitted_baseline"
        ),
        "finite_run_policy": "independent",
        "failed_short_runs": failed_runs,
    }
    if method == "double_exponential":
        operation.update(
            {
                "loss": "soft_l1",
                "min_tau_s": min_tau_s,
                "max_tau_s": "10 * run_duration",
            }
        )
    elif method == "asls":
        operation.update(
            {
                "smoothness": asls_smoothness,
                "effective_smoothness": effective_smoothness,
                "reference_rate_hz": asls_reference_rate_hz,
                "sampling_rate_hz": sampling_rate_hz,
                "asymmetry": asls_asymmetry,
                "max_iterations": max_iterations,
            }
        )
    else:
        operation.update(
            {
                "window_s": rolling_window_s,
                "window_samples": rolling_window_samples,
                "sampling_rate_hz": rolling_sampling_rate_hz,
                "frame_rate_rounding": "round(1 / mean_contiguous_interval)",
                "center": True,
                "minimum_periods": rolling_window_samples,
                "boundary_policy": "full_window_only",
                "gap_policy": "split_finite_runs",
                "max_gap_s": max_gap_s,
                "gap_factor": rolling_gap_factor,
                "published_comparator": "Pan-Vazquez et al. 2024",
            }
        )
    output.attrs["processing_stage"] = "baseline_corrected"
    output.attrs["fiberphotometry_baseline_dff"] = json.dumps(operation, sort_keys=True)
    _append_operation(output, operation)
    return output


def resample_recording(
    recording: xr.Dataset,
    *,
    rate_hz: float,
    max_gap_s: float | None = None,
) -> xr.Dataset:
    """Linearly resample time-channel variables while retaining source arrays.

    Interpolation never crosses a source interval larger than ``max_gap_s``.
    The original arrays remain available on the separate ``source_time`` axis.
    """
    validate_recording(recording)
    if rate_hz <= 0:
        raise ValueError("rate_hz must be positive")
    if max_gap_s is not None and max_gap_s <= 0:
        raise ValueError("max_gap_s must be positive when provided")
    if "source_time" in recording.coords:
        raise ValueError("recording has already been resampled")
    unsupported = [
        name
        for name, variable in recording.data_vars.items()
        if "time" in variable.dims
        and variable.dims != ("time", "channel")
        and not (variable.dims == ("time",) and variable.dtype == bool)
    ]
    if unsupported:
        raise ValueError(f"cannot resample unsupported time variables: {unsupported}")

    source_time = np.asarray(recording.time.values, dtype=float)
    step = 1 / rate_hz
    target_time = np.arange(source_time[0], source_time[-1] + step / 2, step)
    target_time = target_time[target_time <= source_time[-1]]
    output = xr.Dataset(
        coords={
            "time": target_time,
            "channel": recording.channel.values,
            "source_time": source_time,
        },
        attrs=dict(recording.attrs),
    )
    for name, variable in recording.data_vars.items():
        if variable.dims == ("time",):
            source_mask = np.asarray(variable.values, dtype=bool)
            right = np.searchsorted(source_time, target_time, side="left")
            right = np.clip(right, 0, len(source_time) - 1)
            left = np.maximum(right - 1, 0)
            nearest = np.where(
                abs(target_time - source_time[left])
                <= abs(source_time[right] - target_time),
                left,
                right,
            )
            resampled_mask = source_mask[nearest]
            if max_gap_s is not None:
                for gap_left, gap_right in pairwise(source_time):
                    if gap_right - gap_left > max_gap_s:
                        resampled_mask[
                            (target_time > gap_left) & (target_time < gap_right)
                        ] = False
            output[name] = (("time",), resampled_mask)
            output[f"source_{name}"] = (("source_time",), source_mask.copy())
            continue
        if variable.dims != ("time", "channel"):
            output[name] = variable.copy(deep=True)
            continue
        source = np.asarray(variable.values, dtype=float)
        resampled = np.full((len(target_time), source.shape[1]), np.nan)
        for channel in range(source.shape[1]):
            finite = np.isfinite(source[:, channel])
            if finite.sum() < 2:
                continue
            valid_time = source_time[finite]
            resampled[:, channel] = np.interp(
                target_time,
                valid_time,
                source[finite, channel],
                left=np.nan,
                right=np.nan,
            )
            if max_gap_s is not None:
                for left, right in pairwise(valid_time):
                    if right - left > max_gap_s:
                        resampled[
                            (target_time > left) & (target_time < right), channel
                        ] = np.nan
        output[name] = (("time", "channel"), resampled)
        output[f"source_{name}"] = (("source_time", "channel"), source.copy())
    output.attrs["processing_stage"] = "resampled"
    _append_operation(
        output,
        {
            "kind": "resample",
            "method": "linear",
            "rate_hz": rate_hz,
            "max_gap_s": max_gap_s,
            "source_samples": len(source_time),
            "output_samples": len(target_time),
            "time_only_boolean_method": "nearest",
        },
    )
    return output


def lowpass_filter(
    recording: xr.Dataset,
    *,
    cutoff_hz: float,
    order: int = 4,
    variables: tuple[str, ...] = ("signal", "reference"),
) -> xr.Dataset:
    """Zero-phase low-pass finite runs and retain every pre-filter variable."""
    validate_recording(recording)
    intervals = np.diff(np.asarray(recording.time.values, dtype=float))
    rate_hz = 1 / float(np.median(intervals))
    if float(np.std(intervals) / np.mean(intervals)) > 1e-6:
        raise ValueError("low-pass filtering requires regularly sampled data")
    if not 0 < cutoff_hz < rate_hz / 2:
        raise ValueError("cutoff_hz must lie between zero and the Nyquist frequency")
    if order < 1:
        raise ValueError("filter order must be positive")
    sos = butter(order, cutoff_hz, btype="lowpass", fs=rate_hz, output="sos")
    padlen = 3 * (
        2 * len(sos) + 1 - min(int(np.sum(sos[:, 2] == 0)), int(np.sum(sos[:, 5] == 0)))
    )
    output = recording.copy(deep=True)
    short_segments: dict[str, int] = {}
    for name in variables:
        if name not in recording:
            raise ValueError(f"recording does not contain filter variable {name!r}")
        if f"prefilter_{name}" in recording:
            raise ValueError(f"variable {name!r} has already been filtered")
        source = np.asarray(recording[name].values, dtype=float)
        filtered = np.full_like(source, np.nan)
        short = 0
        for channel in range(source.shape[1]):
            for start, stop in _finite_runs(np.isfinite(source[:, channel])):
                if stop - start <= padlen:
                    short += 1
                    continue
                filtered[start:stop, channel] = sosfiltfilt(
                    sos, source[start:stop, channel], padlen=padlen
                )
        output[f"prefilter_{name}"] = recording[name].copy(deep=True)
        output[name] = (("time", "channel"), filtered)
        short_segments[name] = short
    output.attrs["processing_stage"] = "filtered"
    _append_operation(
        output,
        {
            "kind": "lowpass_filter",
            "method": "butterworth_sosfiltfilt",
            "cutoff_hz": cutoff_hz,
            "order": order,
            "sampling_rate_hz": rate_hz,
            "edge_padding_samples": padlen,
            "variables": variables,
            "short_segments_set_to_nan": short_segments,
        },
    )
    return output


def reference_dff(
    recording: xr.Dataset,
    *,
    method: str = "irls",
    max_iterations: int = 50,
    tolerance: float = 1e-8,
) -> xr.Dataset:
    """Fit the reference to each signal channel and calculate ``dF/F``.

    ``irls`` uses Huber iteratively reweighted least squares; ``ols`` is provided
    as an explicit comparator. Non-finite samples are excluded channel-wise.
    The fitted baseline is ``intercept + slope * reference`` and the corrected
    trace is ``(signal - fitted) / fitted``.

    This operation does not assert that a reference channel is biologically
    inert. Users must inspect diagnostics and controls for that assumption.
    """
    validate_recording(recording)
    if "reference" not in recording:
        raise ValueError("reference_dff requires a reference variable")
    if method not in {"irls", "ols"}:
        raise ValueError("method must be 'irls' or 'ols'")

    signal = np.asarray(recording["signal"].values, dtype=float)
    reference = np.asarray(recording["reference"].values, dtype=float)
    fitted = np.full_like(signal, np.nan)
    corrected = np.full_like(signal, np.nan)
    coefficients = np.full((signal.shape[1], 2), np.nan)

    for channel in range(signal.shape[1]):
        valid = np.isfinite(signal[:, channel]) & np.isfinite(reference[:, channel])
        if valid.sum() < 3:
            continue
        design = np.column_stack([np.ones(valid.sum()), reference[valid, channel]])
        response = signal[valid, channel]
        beta = (
            _fit_irls(design, response, max_iterations, tolerance)
            if method == "irls"
            else _fit_ols(design, response)
        )
        channel_fitted = beta[0] + beta[1] * reference[valid, channel]
        safe = np.abs(channel_fitted) > np.finfo(float).eps
        valid_indices = np.flatnonzero(valid)
        fitted[valid_indices, channel] = channel_fitted
        corrected[valid_indices[safe], channel] = (
            signal[valid_indices[safe], channel] - channel_fitted[safe]
        ) / channel_fitted[safe]
        coefficients[channel] = beta

    output = recording.copy(deep=True)
    output["fitted_reference"] = (("time", "channel"), fitted)
    output["dff"] = (("time", "channel"), corrected)
    output["reference_fit_coefficient"] = (
        ("channel", "coefficient"),
        coefficients,
    )
    output = output.assign_coords(coefficient=["intercept", "slope"])
    output.attrs["processing_stage"] = "reference_corrected"
    output.attrs["fiberphotometry_reference_dff"] = json.dumps(
        {
            "method": method,
            "max_iterations": max_iterations,
            "tolerance": tolerance,
            "formula": "(signal - fitted_reference) / fitted_reference",
        },
        sort_keys=True,
    )
    _append_operation(
        output,
        {
            "kind": "reference_dff",
            "method": method,
            "max_iterations": max_iterations,
            "tolerance": tolerance,
        },
    )
    return output


def _finite_runs(values: NDArray[np.bool_]) -> list[tuple[int, int]]:
    padded = np.concatenate([[False], values, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[::2].tolist(), edges[1::2].tolist(), strict=True))


def _finite_time_runs(
    finite: NDArray[np.bool_],
    time: NDArray[np.float64],
    *,
    max_gap_s: float,
) -> list[tuple[int, int]]:
    """Return finite runs, additionally splitting across timestamp gaps."""
    gap_starts = np.flatnonzero(np.diff(time) > max_gap_s) + 1
    boundaries = {0, len(finite), *gap_starts.tolist()}
    output: list[tuple[int, int]] = []
    ordered = sorted(boundaries)
    for segment_start, segment_stop in pairwise(ordered):
        for start, stop in _finite_runs(finite[segment_start:segment_stop]):
            output.append((segment_start + start, segment_start + stop))
    return output


def _fit_centered_rolling_mean(
    values: NDArray[np.float64], *, window_samples: int
) -> NDArray[np.float64]:
    """Match pandas' centred full-window rolling mean without a runtime dependency."""
    baseline = np.full_like(values, np.nan)
    cumulative = np.concatenate([[0.0], np.cumsum(values, dtype=np.float64)])
    means = (
        cumulative[window_samples:] - cumulative[:-window_samples]
    ) / window_samples
    first_center = window_samples // 2
    baseline[first_center : first_center + len(means)] = means
    return baseline


def _append_operation(recording: xr.Dataset, operation: dict[str, object]) -> None:
    key = "fiberphotometry_operations"
    operations = json.loads(str(recording.attrs.get(key, "[]")))
    operations.append(operation)
    recording.attrs[key] = json.dumps(operations, sort_keys=True)


def _fit_ols(
    design: NDArray[np.float64], response: NDArray[np.float64]
) -> NDArray[np.float64]:
    coefficients = np.linalg.lstsq(design, response, rcond=None)[0]
    return np.asarray(coefficients, dtype=np.float64)


def _fit_irls(
    design: NDArray[np.float64],
    response: NDArray[np.float64],
    max_iterations: int,
    tolerance: float,
) -> NDArray[np.float64]:
    beta = _fit_ols(design, response)
    for _ in range(max_iterations):
        residual = response - design @ beta
        scale = 1.4826 * np.median(np.abs(residual - np.median(residual)))
        if not np.isfinite(scale) or scale <= np.finfo(float).eps:
            break
        cutoff = 1.345 * scale
        absolute = np.abs(residual)
        weights = np.ones_like(residual)
        outliers = absolute > cutoff
        weights[outliers] = cutoff / absolute[outliers]
        weighted_design = design * np.sqrt(weights)[:, np.newaxis]
        weighted_response = response * np.sqrt(weights)
        updated = _fit_ols(weighted_design, weighted_response)
        if np.linalg.norm(updated - beta) <= tolerance * (1 + np.linalg.norm(beta)):
            beta = updated
            break
        beta = updated
    return beta


def _fit_double_exponential(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    min_tau_s: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    relative_time = time - time[0]
    duration = max(float(relative_time[-1]), min_tau_s)
    low = max(float(np.percentile(values, 5)), np.finfo(float).eps)
    high = max(float(np.percentile(values, 95)), low)
    amplitude = max(high - low, np.finfo(float).eps)
    initial = np.array(
        [low, amplitude * 0.6, max(min_tau_s, duration / 10), amplitude * 0.4, duration]
    )
    lower = np.array([np.finfo(float).eps, 0.0, min_tau_s, 0.0, min_tau_s])
    upper = np.array([high * 2, high * 2, duration * 10, high * 2, duration * 10])

    sample_index = np.linspace(0, len(values) - 1, min(len(values), 2000), dtype=int)
    fit_time = relative_time[sample_index]
    fit_values = values[sample_index]

    def residual(parameters: NDArray[np.float64]) -> NDArray[np.float64]:
        offset, amplitude_1, tau_1, amplitude_2, tau_2 = parameters
        fitted = (
            offset
            + amplitude_1 * np.exp(-fit_time / tau_1)
            + amplitude_2 * np.exp(-fit_time / tau_2)
        )
        return np.asarray(fitted - fit_values, dtype=np.float64)

    result = least_squares(
        residual,
        np.clip(initial, lower, upper),
        bounds=(lower, upper),
        loss="soft_l1",
        f_scale=max(float(np.std(fit_values)) * 0.1, np.finfo(float).eps),
        max_nfev=2000,
    )
    parameters = np.asarray(result.x, dtype=np.float64)
    offset, amplitude_1, tau_1, amplitude_2, tau_2 = parameters
    fitted = (
        offset
        + amplitude_1 * np.exp(-relative_time / tau_1)
        + amplitude_2 * np.exp(-relative_time / tau_2)
    )
    return np.asarray(fitted, dtype=np.float64), parameters


def _fit_asls(
    values: NDArray[np.float64],
    *,
    smoothness: float,
    asymmetry: float,
    max_iterations: int,
) -> NDArray[np.float64]:
    count = len(values)
    difference = diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(count - 2, count))
    penalty = smoothness * (difference.T @ difference)
    weights = np.ones(count)
    baseline = values.copy()
    for _ in range(max_iterations):
        weight_matrix = diags(weights, 0, shape=(count, count))
        system = (weight_matrix + penalty).tocsc()
        baseline = np.asarray(spsolve(system, weights * values))
        updated = np.where(values > baseline, asymmetry, 1 - asymmetry)
        if np.array_equal(updated, weights):
            break
        weights = updated
    return np.asarray(baseline, dtype=np.float64)
