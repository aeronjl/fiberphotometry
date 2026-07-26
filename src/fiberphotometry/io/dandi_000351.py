"""Pinned adapter for the draft NWB layout in DANDI:000351."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from fiberphotometry.model import make_recording

RAW_PATH = "acquisition/photometry"
ARCHIVED_PATH = "processing/photometry/dff"


def from_dandi_000351_nwb(path: str | Path) -> xr.Dataset:
    """Load paired raw signals and archived percentage dF/F from one asset."""
    import h5py  # type: ignore[import-untyped]

    with h5py.File(path, "r") as nwb:
        raw_group = nwb[RAW_PATH]
        identity = _text(raw_group.attrs.get("data_identity", ""))
        if identity != "raw405,raw470":
            raise ValueError(
                "DANDI:000351 requires data_identity 'raw405,raw470'; "
                f"found {identity!r}"
            )
        raw = np.asarray(raw_group["data"][:], dtype=float)
        if raw.ndim != 2 or raw.shape[1] != 2:
            raise ValueError("DANDI:000351 raw photometry must have two columns")
        time = np.asarray(raw_group["timestamps"][:], dtype=float)
        archived_group = nwb[ARCHIVED_PATH]
        archived = np.asarray(archived_group["data"][:], dtype=float)
        archived_time = np.asarray(archived_group["timestamps"][:], dtype=float)
        if not (len(time) == len(archived_time) == len(archived) == len(raw)):
            raise ValueError("DANDI:000351 raw and archived arrays differ in length")
        timestamp_error = float(np.nanmax(np.abs(time - archived_time)))
        if timestamp_error > 1e-6:
            raise ValueError(
                "DANDI:000351 raw and archived timestamps differ by more than 1 us"
            )
        subject = _text(nwb["general/subject/subject_id"][()])
        session = _text(nwb["identifier"][()])

    recording = make_recording(
        time=time,
        signal=raw[:, 1],
        reference=raw[:, 0],
        channel_names=["dLight"],
        subject=subject,
        session=session,
        attrs={
            "source_format": "NWB",
            "source_dataset": "DANDI:000351/draft",
            "raw_column_identity": identity,
            "timestamp_max_abs_error_s": timestamp_error,
            "archived_dff_unit": "%",
        },
    )
    recording["archived_dff_percentage"] = (
        ("time", "channel"),
        archived[:, np.newaxis],
    )
    return recording


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
