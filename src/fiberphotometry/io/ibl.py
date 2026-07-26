"""Adapter for International Brain Laboratory photometry tables."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import xarray as xr
from numpy.typing import ArrayLike

from fiberphotometry.model import make_recording


def from_ibl_tables(
    *,
    signal_table: Mapping[str, ArrayLike],
    roi_locations: Mapping[str, str],
    subject: str,
    session: str,
    signal_wavelength: float = 470.0,
    reference_wavelength: float | None = 415.0,
) -> xr.Dataset:
    """Convert IBL ``photometry.signal`` and ROI metadata to a recording.

    Alternating wavelength samples are selected independently. Reference samples
    are linearly interpolated to signal-frame times. Rows excluded by IBL's
    manually curated ``include`` column become NaN rather than being dropped, so
    discontinuities remain explicit.
    """
    times = _column(signal_table, "times", dtype=float)
    wavelengths = _column(signal_table, "wavelength", dtype=float)
    include = (
        _column(signal_table, "include", dtype=bool)
        if "include" in signal_table
        else np.ones(len(times), dtype=bool)
    )
    if not (len(times) == len(wavelengths) == len(include)):
        raise ValueError("IBL time, wavelength, and include columns must align")

    roi_columns = [name for name in roi_locations if name in signal_table]
    if not roi_columns:
        raise ValueError("no ROI columns from roi_locations occur in signal_table")
    signal_rows = np.isclose(wavelengths, signal_wavelength)
    if signal_rows.sum() < 2:
        raise ValueError(
            f"fewer than two samples at signal wavelength {signal_wavelength}"
        )

    signal_times = times[signal_rows]
    signals = np.column_stack(
        [_column(signal_table, roi, dtype=float)[signal_rows] for roi in roi_columns]
    )
    signal_included = include[signal_rows]
    signals[~signal_included, :] = np.nan

    references: np.ndarray | None = None
    if reference_wavelength is not None:
        reference_rows = np.isclose(wavelengths, reference_wavelength)
        if reference_rows.sum() < 2:
            raise ValueError(
                f"fewer than two samples at reference wavelength {reference_wavelength}"
            )
        reference_times = times[reference_rows]
        reference_included = include[reference_rows]
        references = np.full_like(signals, np.nan)
        for index, roi in enumerate(roi_columns):
            values = _column(signal_table, roi, dtype=float)[reference_rows]
            valid = (
                reference_included & np.isfinite(values) & np.isfinite(reference_times)
            )
            if valid.sum() >= 2:
                within = (signal_times >= reference_times[valid].min()) & (
                    signal_times <= reference_times[valid].max()
                )
                references[within, index] = np.interp(
                    signal_times[within], reference_times[valid], values[valid]
                )

    recording = make_recording(
        time=signal_times,
        signal=signals,
        reference=references,
        channel_names=[roi_locations[name] for name in roi_columns],
        subject=subject,
        session=session,
        attrs={
            "source_format": "IBL_ALF_photometry.signal",
            "signal_wavelength_nm": signal_wavelength,
            "reference_wavelength_nm": reference_wavelength
            if reference_wavelength is not None
            else "none",
            "ibl_roi_columns": ",".join(roi_columns),
        },
    )
    recording["included"] = (("time",), signal_included)
    return recording


def _column(
    table: Mapping[str, ArrayLike], name: str, *, dtype: type[float] | type[bool]
) -> np.ndarray:
    try:
        values = table[name]
    except KeyError as error:
        raise ValueError(f"IBL signal table is missing {name!r}") from error
    return np.asarray(values, dtype=dtype)
