"""Pinned adapter for the raw photometry layout in DANDI:000971."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from fipha.model import make_recording

SERIES_PATH = "acquisition/fiber_photometry_response_series"
TABLE_PATH = "general/fiber_photometry/fiber_photometry_table"
REGIONS = ("DMS", "DLS")


def from_dandi_000971_nwb(
    path: str | Path, *, target_rate_hz: float = 20.0
) -> xr.Dataset:
    """Load raw calcium/control pairs from a local DANDI:000971 NWB asset.

    This intentionally targets one pinned public schema. It validates the four
    expected columns before reducing the approximately 1 kHz recordings by
    non-overlapping block means, keeping memory use bounded for the pilot.
    """
    if target_rate_hz <= 0:
        raise ValueError("target_rate_hz must be positive")

    import h5py  # type: ignore[import-untyped]

    with h5py.File(path, "r") as nwb:
        series = nwb[SERIES_PATH]
        data = series["data"]
        source_rate = _source_rate(series)
        block_size = max(1, round(source_rate / target_rate_hz))
        mapping = _column_mapping(nwb, nwb[TABLE_PATH])
        columns = [
            mapping[(region, kind)]
            for kind in ("calcium", "isosbestic")
            for region in REGIONS
        ]
        reduced, discarded = _block_mean_columns(data, columns, block_size)
        subject = _text(nwb["general/subject/subject_id"][()])
        session = _text(nwb["identifier"][()])

    signal = reduced[:, : len(REGIONS)]
    reference = reduced[:, len(REGIONS) :]
    achieved_rate = source_rate / block_size
    time = np.arange(len(reduced), dtype=float) / achieved_rate
    return make_recording(
        time=time,
        signal=signal,
        reference=reference,
        channel_names=REGIONS,
        subject=subject,
        session=session,
        attrs={
            "source_format": "NWB",
            "source_dataset": "DANDI:000971/0.260213.1851",
            "source_rate_hz": source_rate,
            "downsample_block_size": block_size,
            "sampling_rate_hz": achieved_rate,
            "discarded_tail_samples": discarded,
        },
    )


def rewarded_unrewarded_nose_pokes(
    path: str | Path, *, tolerance_s: float = 1e-9
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Read active nose pokes and classify the rewarded subset.

    DANDI:000971 stores active-poke and reward timestamps as separate behavioral
    series.  The conversion audit records each reward timestamp as a member of the
    active-poke series.  This adapter validates that relationship instead of
    guessing an active side or matching a reward to a merely nearby action.
    """
    if tolerance_s < 0:
        raise ValueError("tolerance_s must be nonnegative")

    import h5py

    with h5py.File(path, "r") as nwb:
        behavior_path = "processing/behavior"
        if behavior_path not in nwb:
            raise ValueError("DANDI:000971 asset has no behavioral processing module")
        behavior = nwb[behavior_path]
        candidates = []
        for side in ("left", "right"):
            poke_name = f"{side}_nose_poke_times"
            reward_name = f"{side}_reward_times"
            if poke_name not in behavior or reward_name not in behavior:
                continue
            pokes = np.asarray(behavior[poke_name]["timestamps"][:], dtype=float)
            rewards = np.asarray(behavior[reward_name]["timestamps"][:], dtype=float)
            if len(pokes) and len(rewards):
                candidates.append((side, pokes, rewards))
        if len(candidates) != 1:
            raise ValueError(
                "DANDI:000971 requires exactly one rewarded active nose-poke side"
            )
        _, pokes, rewards = candidates[0]

    rewarded = np.zeros(len(pokes), dtype=bool)
    for reward in rewards:
        matches = np.flatnonzero(np.isclose(pokes, reward, rtol=0, atol=tolerance_s))
        if len(matches) != 1:
            raise ValueError(
                "every reward timestamp must match exactly one active nose poke"
            )
        rewarded[int(matches[0])] = True
    if rewarded.all():
        raise ValueError("session contains no unrewarded active nose pokes")
    labels = tuple("rewarded" if value else "unrewarded" for value in rewarded)
    return pokes, labels


def _column_mapping(nwb: Any, table: Any) -> dict[tuple[str, str], int]:
    if "name" in table:  # small synthetic fixtures and possible future exports
        names = [_text(value) for value in table["name"][:]]
    else:
        names = [
            nwb[value].name.rsplit("/", 1)[-1]
            for value in table["commanded_voltage_series"][:]
        ]
    locations = [_text(value) for value in table["location"][:]]
    if len(names) != len(locations):
        raise ValueError("DANDI:000971 photometry table columns are inconsistent")
    mapping: dict[tuple[str, str], int] = {}
    for index, (name, location) in enumerate(zip(names, locations, strict=True)):
        lower = name.lower()
        if "calcium_signal" in lower:
            kind = "calcium"
        elif "isosbestic_control" in lower:
            kind = "isosbestic"
        else:
            kind = None
        if kind is not None and location in REGIONS:
            mapping[(location, kind)] = index
    expected = {
        (region, kind) for region in REGIONS for kind in ("calcium", "isosbestic")
    }
    if set(mapping) != expected:
        missing = sorted(expected - set(mapping))
        raise ValueError(
            f"DANDI:000971 expected calcium/control schema is absent: {missing}"
        )
    return mapping


def _source_rate(series: Any) -> float:
    starting_time = series["starting_time"]
    rate = float(starting_time.attrs["rate"])
    if not np.isfinite(rate) or rate <= 0:
        raise ValueError("DANDI:000971 response series has no positive rate")
    return rate


def _block_mean_columns(
    data: Any, columns: list[int], block_size: int
) -> tuple[np.ndarray, int]:
    rows = int(data.shape[0])
    usable = rows - rows % block_size
    if usable < block_size:
        raise ValueError("recording is too short for the requested target rate")
    # h5py requires list-style column indices to be sorted. These assets store
    # columns region-first, while the canonical output groups signals first.
    values = np.asarray(data[:usable, :], dtype=float)[:, columns]
    reduced = values.reshape(-1, block_size, len(columns)).mean(axis=1)
    return reduced, rows - usable


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
