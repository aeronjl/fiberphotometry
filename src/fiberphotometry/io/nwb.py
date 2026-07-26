"""NWB interchange without inventing unavailable experimental metadata."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import numpy as np
import xarray as xr

from fiberphotometry.model import make_recording, validate_recording


def add_recording_to_nwb(
    recording: xr.Dataset,
    nwbfile: Any,
    *,
    variable: str = "signal",
    name: str = "FiberPhotometrySignal",
    unit: str = "a.u.",
) -> Any:
    """Add a recording as a standard NWB ``TimeSeries`` acquisition.

    This representation is intentionally valid core NWB. It stores channel and
    provenance metadata in JSON comments and can therefore be round-tripped when
    detailed ``ndx-fiber-photometry`` hardware objects are unavailable.
    """
    from pynwb import TimeSeries  # type: ignore[import-untyped]

    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    metadata = {
        "schema": "fiberphotometry-core-nwb-v1",
        "channels": [str(value) for value in recording.channel.values],
        "subject": str(recording.attrs["subject"]),
        "session": str(recording.attrs["session"]),
        "source_variable": variable,
        "recording_attrs": _json_attrs(recording.attrs),
    }
    series = TimeSeries(
        name=name,
        data=np.asarray(recording[variable].values),
        timestamps=np.asarray(recording.time.values, dtype=float),
        unit=unit,
        description="Fiber photometry signal exported by fiberphotometry",
        comments=json.dumps(metadata, sort_keys=True),
    )
    nwbfile.add_acquisition(series)
    return series


def from_nwb_series(
    series: Any,
    *,
    subject: str | None = None,
    session: str | None = None,
) -> xr.Dataset:
    """Read a core or ``ndx-fiber-photometry`` response series."""
    metadata = _comment_metadata(getattr(series, "comments", ""))
    data = np.asarray(series.data[:])
    if data.ndim == 1:
        data = data[:, np.newaxis]
    timestamps = _timestamps(series, len(data))
    channel_names = metadata.get("channels")
    extension_metadata = _extension_channel_metadata(series)
    if not channel_names and extension_metadata:
        channel_names = [
            str(row.get("location") or f"channel_{index}")
            for index, row in enumerate(extension_metadata)
        ]
    recording = make_recording(
        time=timestamps,
        signal=data,
        channel_names=channel_names,
        subject=subject or str(metadata.get("subject", "unknown")),
        session=session or str(metadata.get("session", "unknown")),
        attrs={
            "source_format": "NWB",
            "nwb_series_name": str(series.name),
            "nwb_neurodata_type": type(series).__name__,
        },
    )
    if extension_metadata:
        recording.attrs["ndx_fiber_photometry_channels"] = json.dumps(
            extension_metadata, sort_keys=True
        )
    return recording


def _timestamps(series: Any, length: int) -> np.ndarray:
    if getattr(series, "timestamps", None) is not None:
        return np.asarray(series.timestamps[:], dtype=float)
    rate = getattr(series, "rate", None)
    if rate is None or rate <= 0:
        raise ValueError("NWB series needs timestamps or a positive rate")
    starting_time = float(getattr(series, "starting_time", 0.0) or 0.0)
    return starting_time + np.arange(length, dtype=float) / float(rate)


def _comment_metadata(comments: str) -> dict[str, Any]:
    try:
        value = json.loads(comments)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _extension_channel_metadata(series: Any) -> list[dict[str, Any]]:
    region = getattr(series, "fiber_photometry_table_region", None)
    if region is None:
        return []
    try:
        frame = region.table[region.data[:]]
        rows = frame.to_dict(orient="records")
    except (AttributeError, KeyError, TypeError, ValueError):
        return []
    fields = (
        "location",
        "excitation_wavelength_in_nm",
        "emission_wavelength_in_nm",
        "indicator",
        "optical_fiber",
    )
    return [
        {field: _nwb_value(row[field]) for field in fields if field in row}
        for row in rows
    ]


def _nwb_value(value: Any) -> str | float | int | bool | None:
    if value is None or isinstance(value, (str, float, int, bool)):
        return value
    return str(getattr(value, "name", value))


def _json_attrs(attrs: Mapping[Any, Any]) -> dict[str, str | float | int | bool]:
    output: dict[str, str | float | int | bool] = {}
    for key, value in attrs.items():
        output[str(key)] = (
            value if isinstance(value, (str, float, int, bool)) else str(value)
        )
    return output
