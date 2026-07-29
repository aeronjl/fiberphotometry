"""Bounded remote integration with public DANDI NWB assets."""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Any
from urllib.request import urlopen

import numpy as np

from fipha.io.nwb import from_nwb_series

DANDI_ASSET_API = "https://api.dandiarchive.org/api/assets/{asset_id}/"


@dataclass(frozen=True)
class RemoteSeriesSummary:
    """Bounded validation summary for one remote response series."""

    path: str
    neurodata_type: str
    full_shape: tuple[int, ...]
    samples_read: int
    channels_read: int
    finite_fraction: float
    time_start: float
    time_stop: float
    channel_preview: tuple[str, ...]


@dataclass(frozen=True)
class RemoteNWBValidation:
    """Results copied from a remote NWB file before its handles are closed."""

    asset_id: str
    identifier: str
    response_series: tuple[RemoteSeriesSummary, ...]
    schema_warning_count: int
    schema_warning_preview: tuple[str, ...]

    def to_json(self) -> str:
        """Return stable, human-readable validation output."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def validate_remote_nwb_asset(
    asset_id: str,
    *,
    max_samples: int = 1_000,
    max_series: int | None = None,
) -> RemoteNWBValidation:
    """Stream only bounded photometry slices from a DANDI NWB asset.

    HDF5 range requests may retrieve metadata and chunks larger than the requested
    slice, but this function never indexes more than ``max_samples`` rows from a
    response series and never writes the asset to disk.
    """
    if max_samples < 1:
        raise ValueError("max_samples must be positive")
    download_url = resolve_dandi_download_url(asset_id)

    _response_series_type()

    import h5py  # type: ignore[import-untyped]
    import remfile  # type: ignore[import-untyped]
    from pynwb import NWBHDF5IO  # type: ignore[import-untyped]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        remote = remfile.File(download_url)
        with (
            h5py.File(remote, "r") as h5_file,
            NWBHDF5IO(file=h5_file, mode="r", load_namespaces=True) as io,
        ):
            nwbfile = io.read()
            summaries = []
            for path, series in _response_series(nwbfile):
                recording = from_nwb_series(
                    series,
                    subject=_subject_id(nwbfile),
                    session=str(nwbfile.identifier),
                    max_samples=max_samples,
                )
                values = np.asarray(recording.signal.values)
                summaries.append(
                    RemoteSeriesSummary(
                        path=path,
                        neurodata_type=type(series).__name__,
                        full_shape=tuple(int(value) for value in series.data.shape),
                        samples_read=int(values.shape[0]),
                        channels_read=int(values.shape[1]),
                        finite_fraction=float(np.isfinite(values).mean()),
                        time_start=float(recording.time.values[0]),
                        time_stop=float(recording.time.values[-1]),
                        channel_preview=tuple(
                            str(value) for value in recording.channel.values[:5]
                        ),
                    )
                )
                if max_series is not None and len(summaries) >= max_series:
                    break
            identifier = str(nwbfile.identifier)
    schema_warnings = tuple(
        str(item.message)
        for item in caught
        if "schema" in str(item.message).lower() or "Device.model" in str(item.message)
    )
    return RemoteNWBValidation(
        asset_id=asset_id,
        identifier=identifier,
        response_series=tuple(summaries),
        schema_warning_count=len(schema_warnings),
        schema_warning_preview=schema_warnings[:3],
    )


def resolve_dandi_download_url(asset_id: str) -> str:
    """Resolve the stable S3 content URL advertised by the DANDI API."""
    with urlopen(DANDI_ASSET_API.format(asset_id=asset_id), timeout=30) as response:
        payload = json.load(response)
    urls = payload.get("contentUrl", [])
    s3_urls = [url for url in urls if "dandiarchive.s3.amazonaws.com" in url]
    if not s3_urls:
        raise RuntimeError(f"DANDI asset {asset_id} has no public S3 content URL")
    return str(s3_urls[0])


def _response_series(nwbfile: Any) -> Iterator[tuple[str, Any]]:
    response_series = _response_series_type()
    for name, value in nwbfile.acquisition.items():
        if isinstance(value, response_series):
            yield f"acquisition/{name}", value
    for module_name, module in nwbfile.processing.items():
        for name, value in module.data_interfaces.items():
            if isinstance(value, response_series):
                yield f"processing/{module_name}/{name}", value


def _response_series_type() -> type:
    try:
        from ndx_fiber_photometry import (  # type: ignore[import-untyped]
            FiberPhotometryResponseSeries,
        )
    except ImportError as error:
        raise ValueError(
            "reading fiber photometry NWB assets requires the optional 'nwb' "
            "dependencies"
        ) from error
    return FiberPhotometryResponseSeries  # type: ignore[no-any-return]


def _subject_id(nwbfile: Any) -> str:
    subject = getattr(nwbfile, "subject", None)
    return str(getattr(subject, "subject_id", None) or "unknown")
