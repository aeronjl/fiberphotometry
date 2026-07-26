"""Explicit, provenance-recorded preprocessing operations."""

from __future__ import annotations

import json

import numpy as np
import xarray as xr
from numpy.typing import NDArray

from fiberphotometry.model import validate_recording


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
    return output


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
