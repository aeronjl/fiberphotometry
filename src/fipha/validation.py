"""Numerical validation metrics against independently processed signals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class DffReproduction:
    """Comparison of calculated and archived fitted-baseline dF/F."""

    correlation: float
    rmse: float
    mean_bias: float
    max_absolute_error: float
    median_channel_correlation: float
    median_channel_offset: float
    offset_adjusted_rmse: float


def compare_fitted_baseline_dff(
    *, raw: ArrayLike, baseline: ArrayLike, archived_dff: ArrayLike
) -> DffReproduction:
    """Compare ``(raw - baseline) / baseline`` with an archived dF/F array."""
    raw_array = _matrix(raw, "raw")
    baseline_array = _matrix(baseline, "baseline")
    archived_array = _matrix(archived_dff, "archived_dff")
    if not (raw_array.shape == baseline_array.shape == archived_array.shape):
        raise ValueError("raw, baseline, and archived_dff must have the same shape")
    calculated = (raw_array - baseline_array) / baseline_array
    finite = (
        np.isfinite(calculated)
        & np.isfinite(archived_array)
        & np.isfinite(baseline_array)
    )
    if finite.sum() < 2:
        raise ValueError("at least two finite paired values are required")
    difference = np.where(finite, calculated - archived_array, np.nan)
    offsets = np.nanmean(difference, axis=0)
    adjusted_difference = difference - offsets[np.newaxis, :]
    channel_correlations = []
    for channel in range(calculated.shape[1]):
        valid = finite[:, channel]
        if valid.sum() >= 2:
            channel_correlations.append(
                float(
                    np.corrcoef(
                        calculated[valid, channel], archived_array[valid, channel]
                    )[0, 1]
                )
            )
    return DffReproduction(
        correlation=float(
            np.corrcoef(calculated[finite], archived_array[finite])[0, 1]
        ),
        rmse=float(np.sqrt(np.nanmean(np.square(difference)))),
        mean_bias=float(np.nanmean(difference)),
        max_absolute_error=float(np.nanmax(np.abs(difference))),
        median_channel_correlation=float(np.median(channel_correlations)),
        median_channel_offset=float(np.nanmedian(offsets)),
        offset_adjusted_rmse=float(np.sqrt(np.nanmean(np.square(adjusted_difference)))),
    )


def _matrix(values: ArrayLike, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        array = array[:, np.newaxis]
    if array.ndim != 2:
        raise ValueError(f"{name} must be one- or two-dimensional")
    return array
