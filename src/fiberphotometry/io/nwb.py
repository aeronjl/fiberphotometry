"""Community-standard NWB interchange built on ``ndx-fiber-photometry``.

Recordings are written as :class:`ndx_fiber_photometry.FiberPhotometryResponseSeries`
objects. When acquisition metadata is supplied the writer also builds the
``FiberPhotometryTable``, ``Indicator`` and ``ndx-ophys-devices`` objects the
community model expects and links each series to its table rows. Nothing about the
optical hardware is invented: a recording exported without
:class:`NWBAcquisitionMetadata` produces a response series with no table region.

Metadata the extension has no slot for -- package channel labels and preprocessing
provenance -- is written to two documented scratch ``DynamicTable`` objects,
``fiberphotometry_series_channels`` and ``fiberphotometry_series_attributes``,
rather than to any free-text field.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import xarray as xr

from fiberphotometry.model import make_recording, validate_recording

CHANNEL_TABLE_NAME = "fiberphotometry_series_channels"
ATTRIBUTE_TABLE_NAME = "fiberphotometry_series_attributes"
FIBER_PHOTOMETRY_LAB_METADATA_NAME = "fiber_photometry"
FIBER_PHOTOMETRY_TABLE_NAME = "fiber_photometry_table"
LEGACY_COMMENT_SCHEMA = "fiberphotometry-core-nwb-v1"

_TABLE_FIELDS = (
    "location",
    "excitation_wavelength_in_nm",
    "emission_wavelength_in_nm",
    "indicator",
    "optical_fiber",
    "excitation_source",
    "photodetector",
    "coordinates",
    "notes",
)


@dataclass(frozen=True)
class NWBDeviceMetadata:
    """One declared acquisition device written as an ``ndx-ophys-devices`` object.

    Only the identity of the device is carried here. ``ndx-ophys-devices`` moved
    manufacturer and model number onto ``DeviceModel`` objects, which additionally
    require numerical aperture, detector type or excitation mode. Pass a
    fully-populated ``ndx-ophys-devices`` container in place of this dataclass when
    those values are known.
    """

    name: str
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("device name must not be empty")


@dataclass(frozen=True)
class NWBIndicatorMetadata:
    """The genetically encoded indicator recorded on a photometry channel."""

    name: str
    label: str
    description: str | None = None
    manufacturer: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("indicator name must not be empty")
        if not self.label.strip():
            raise ValueError("indicator label must not be empty")


@dataclass(frozen=True)
class NWBChannelMetadata:
    """Acquisition metadata for one channel, as ``FiberPhotometryTable`` requires.

    Every field the extension marks required is required here. The package never
    supplies a default excitation wavelength, emission wavelength or indicator,
    because those are experimental facts rather than formatting choices.
    """

    location: str
    excitation_wavelength_nm: float
    emission_wavelength_nm: float
    indicator: NWBIndicatorMetadata | Any
    optical_fiber: NWBDeviceMetadata | Any
    excitation_source: NWBDeviceMetadata | Any
    photodetector: NWBDeviceMetadata | Any
    coordinates_mm: tuple[float, float, float] | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.location.strip():
            raise ValueError("channel location must not be empty")
        for field_name in ("excitation_wavelength_nm", "emission_wavelength_nm"):
            value = float(getattr(self, field_name))
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{field_name} must be a positive finite wavelength")


@dataclass(frozen=True)
class NWBAcquisitionMetadata:
    """The ``ndx-fiber-photometry`` description of one written variable's channels."""

    channels: tuple[NWBChannelMetadata, ...]
    description: str = "Fiber photometry acquisition channels"

    def __post_init__(self) -> None:
        if not self.channels:
            raise ValueError("acquisition metadata must describe at least one channel")
        located = [channel.coordinates_mm is not None for channel in self.channels]
        if any(located) and not all(located):
            raise ValueError(
                "supply coordinates_mm for every channel or for none of them"
            )


def add_recording_to_nwb(
    recording: xr.Dataset,
    nwbfile: Any,
    *,
    variable: str = "signal",
    name: str = "FiberPhotometrySignal",
    unit: str = "a.u.",
    processing_module: Any | None = None,
    acquisition_metadata: NWBAcquisitionMetadata | None = None,
) -> Any:
    """Add a recording as an ``ndx-fiber-photometry`` response series.

    Supplying ``acquisition_metadata`` links the series to ``FiberPhotometryTable``
    rows describing wavelengths, indicator and hardware. Omitting it writes the same
    community neurodata type without a table region, which is what a bare CSV import
    can honestly support.
    """
    response_series = _response_series_type()
    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    channel_names = [str(value) for value in recording.channel.values]
    region = None
    if acquisition_metadata is not None:
        if len(acquisition_metadata.channels) != len(channel_names):
            raise ValueError(
                "acquisition metadata must describe every recording channel: "
                f"{len(acquisition_metadata.channels)} declared, "
                f"{len(channel_names)} present"
            )
        region = _fiber_photometry_region(nwbfile, acquisition_metadata, name)
    series = response_series(
        name=name,
        data=np.asarray(recording[variable].values),
        timestamps=np.asarray(recording.time.values, dtype=float),
        unit=unit,
        description=_series_description(variable, acquisition_metadata),
        fiber_photometry_table_region=region,
    )
    if processing_module is None:
        nwbfile.add_acquisition(series)
    else:
        processing_module.add(series)
    _record_series_channels(nwbfile, name, channel_names)
    _record_series_attributes(nwbfile, name, variable, recording.attrs)
    return series


def from_nwb_series(
    series: Any,
    *,
    subject: str | None = None,
    session: str | None = None,
    max_samples: int | None = None,
) -> xr.Dataset:
    """Read an ``ndx-fiber-photometry`` response series or a core ``TimeSeries``.

    Files written by earlier releases, which carried a
    ``fiberphotometry-core-nwb-v1`` JSON document in ``comments``, still load.
    """
    if max_samples is not None and max_samples < 1:
        raise ValueError("max_samples must be positive")
    legacy = _legacy_comment_metadata(getattr(series, "comments", ""))
    nwbfile = _ancestor_nwbfile(series)
    series_name = str(getattr(series, "name", ""))
    stored_attrs = series_provenance(nwbfile, series_name)
    sample_slice = slice(None, max_samples)
    data = np.asarray(series.data[sample_slice])
    if data.ndim == 1:
        data = data[:, np.newaxis]
    timestamps = _timestamps(series, len(data), sample_slice=sample_slice)
    extension_metadata = _extension_channel_metadata(series)
    channel_names = _channel_names(
        nwbfile, series_name, legacy, extension_metadata, data.shape[1]
    )
    attrs: dict[str, str | float | int | bool] = {
        key: value
        for key, value in stored_attrs.items()
        if key not in {"subject", "session", "source_variable"}
    }
    attrs.update(
        {
            "source_format": "NWB",
            "nwb_series_name": series_name,
            "nwb_neurodata_type": type(series).__name__,
        }
    )
    recording = make_recording(
        time=timestamps,
        signal=data,
        channel_names=channel_names,
        subject=_identity(subject, "subject", nwbfile, stored_attrs, legacy),
        session=_identity(session, "session", nwbfile, stored_attrs, legacy),
        attrs=attrs,
    )
    if extension_metadata:
        recording.attrs["ndx_fiber_photometry_channels"] = json.dumps(
            extension_metadata, sort_keys=True
        )
    return recording


def series_provenance(nwbfile: Any, series_name: str) -> dict[str, str]:
    """Return the package attributes recorded for one series, if any were written."""
    table = _scratch_table(nwbfile, ATTRIBUTE_TABLE_NAME)
    if table is None or not series_name:
        return {}
    names = [str(value) for value in table["series_name"][:]]
    keys = [str(value) for value in table["key"][:]]
    values = [str(value) for value in table["value"][:]]
    return {
        key: value
        for name, key, value in zip(names, keys, values, strict=True)
        if name == series_name
    }


def _response_series_type() -> Any:
    try:
        from ndx_fiber_photometry import (  # type: ignore[import-untyped]
            FiberPhotometryResponseSeries,
        )
    except ImportError as error:
        raise ValueError(
            "NWB interchange requires the optional 'nwb' dependencies"
        ) from error
    return FiberPhotometryResponseSeries


def _series_description(
    variable: str, acquisition_metadata: NWBAcquisitionMetadata | None
) -> str:
    if acquisition_metadata is None:
        return (
            f"Fiber photometry {variable} exported by fiberphotometry; no optical "
            "acquisition metadata was supplied, so no FiberPhotometryTable region "
            "is linked"
        )
    return (
        f"Fiber photometry {variable} exported by fiberphotometry with declared "
        "ndx-fiber-photometry acquisition metadata"
    )


def _fiber_photometry_region(
    nwbfile: Any, metadata: NWBAcquisitionMetadata, series_name: str
) -> Any:
    table = _fiber_photometry_table(nwbfile, metadata)
    rows = [_table_row(nwbfile, table, channel) for channel in metadata.channels]
    return table.create_fiber_photometry_table_region(
        region=rows, description=f"Acquisition channels recorded in {series_name}"
    )


def _fiber_photometry_table(nwbfile: Any, metadata: NWBAcquisitionMetadata) -> Any:
    from ndx_fiber_photometry import (
        FiberPhotometry,
        FiberPhotometryIndicators,
        FiberPhotometryTable,
    )

    existing = nwbfile.lab_meta_data.get(FIBER_PHOTOMETRY_LAB_METADATA_NAME)
    if existing is not None:
        return existing.fiber_photometry_table
    table = FiberPhotometryTable(
        name=FIBER_PHOTOMETRY_TABLE_NAME, description=metadata.description
    )
    indicators = FiberPhotometryIndicators(
        indicators=[_indicator(nwbfile, metadata.channels[0].indicator)]
    )
    nwbfile.add_lab_meta_data(
        FiberPhotometry(
            name=FIBER_PHOTOMETRY_LAB_METADATA_NAME,
            fiber_photometry_table=table,
            fiber_photometry_indicators=indicators,
        )
    )
    return table


def _indicator(nwbfile: Any, metadata: NWBIndicatorMetadata | Any) -> Any:
    from ndx_ophys_devices import Indicator  # type: ignore[import-untyped]

    group = _indicator_group(nwbfile)
    if not isinstance(metadata, NWBIndicatorMetadata):
        if group is not None and metadata.name not in group.indicators:
            group.add_indicators(metadata)
        return metadata
    if group is not None:
        known = group.indicators.get(metadata.name)
        if known is not None:
            if str(known.label) != metadata.label:
                raise ValueError(
                    f"indicator {metadata.name!r} is already declared with a "
                    f"different label ({known.label!r})"
                )
            return known
    created = Indicator(
        name=metadata.name,
        label=metadata.label,
        description=metadata.description,
        manufacturer=metadata.manufacturer,
    )
    if group is not None:
        group.add_indicators(created)
    return created


def _indicator_group(nwbfile: Any) -> Any:
    existing = nwbfile.lab_meta_data.get(FIBER_PHOTOMETRY_LAB_METADATA_NAME)
    return None if existing is None else existing.fiber_photometry_indicators


def _device(nwbfile: Any, metadata: NWBDeviceMetadata | Any, kind: str) -> Any:
    existing = nwbfile.devices.get(metadata.name)
    if existing is not None:
        return existing
    if not isinstance(metadata, NWBDeviceMetadata):
        nwbfile.add_device(metadata)
        return metadata
    from ndx_ophys_devices import (
        ExcitationSource,
        FiberInsertion,
        OpticalFiber,
        Photodetector,
    )

    common = {"name": metadata.name, "description": metadata.description}
    if kind == "optical_fiber":
        device = OpticalFiber(fiber_insertion=FiberInsertion(), **common)
    elif kind == "excitation_source":
        device = ExcitationSource(**common)
    else:
        device = Photodetector(**common)
    nwbfile.add_device(device)
    return device


def _table_row(nwbfile: Any, table: Any, channel: NWBChannelMetadata) -> int:
    row = {
        "location": channel.location,
        "excitation_wavelength_in_nm": float(channel.excitation_wavelength_nm),
        "emission_wavelength_in_nm": float(channel.emission_wavelength_nm),
        "indicator": _indicator(nwbfile, channel.indicator),
        "optical_fiber": _device(nwbfile, channel.optical_fiber, "optical_fiber"),
        "excitation_source": _device(
            nwbfile, channel.excitation_source, "excitation_source"
        ),
        "photodetector": _device(nwbfile, channel.photodetector, "photodetector"),
    }
    if channel.coordinates_mm is not None:
        row["coordinates"] = [float(value) for value in channel.coordinates_mm]
    columns = set(table.colnames)
    located = channel.coordinates_mm is not None
    if len(table) and ("coordinates" in columns) != located:
        raise ValueError(
            "coordinates_mm must be declared consistently for every channel written "
            "to one NWB file"
        )
    if len(table) and channel.notes is not None and "notes" not in columns:
        table.add_column(
            name="notes", description="Description of system", data=[""] * len(table)
        )
        columns = set(table.colnames)
    if channel.notes is not None or "notes" in columns:
        row["notes"] = channel.notes or ""
    existing = _matching_row(table, row)
    if existing is not None:
        return existing
    table.add_row(**row)
    return int(len(table) - 1)


def _matching_row(table: Any, row: Mapping[str, Any]) -> int | None:
    for index in range(len(table)):
        if all(_cell_matches(table, field, index, row) for field in _TABLE_FIELDS):
            return index
    return None


def _cell_matches(table: Any, field: str, index: int, row: Mapping[str, Any]) -> bool:
    if field not in table.colnames:
        return field not in row
    stored = table[field][index]
    expected: Any = row.get(field)
    if field == "coordinates":
        return bool(
            np.allclose(
                np.asarray(stored, dtype=float), np.asarray(expected, dtype=float)
            )
        )
    if field in {"location", "notes"}:
        return str(stored) == str(expected)
    if field.endswith("_in_nm"):
        return bool(np.isclose(float(stored), float(expected)))
    return bool(getattr(stored, "name", None) == getattr(expected, "name", object()))


def _record_series_channels(
    nwbfile: Any, series_name: str, channel_names: Sequence[str]
) -> None:
    table = _ensure_scratch_table(
        nwbfile,
        CHANNEL_TABLE_NAME,
        "Package channel labels for each fiber photometry response series",
        (
            ("series_name", "Name of the response series these channels belong to"),
            ("channel_index", "Zero-based column index within the series data"),
            ("channel_name", "Channel label used by the fiberphotometry package"),
        ),
    )
    for index, channel_name in enumerate(channel_names):
        table.add_row(
            series_name=series_name,
            channel_index=int(index),
            channel_name=str(channel_name),
        )


def _record_series_attributes(
    nwbfile: Any, series_name: str, variable: str, attrs: Mapping[Any, Any]
) -> None:
    table = _ensure_scratch_table(
        nwbfile,
        ATTRIBUTE_TABLE_NAME,
        "Recording attributes and preprocessing provenance for each response series",
        (
            ("series_name", "Name of the response series these attributes describe"),
            ("key", "Recording attribute name"),
            ("value", "Recording attribute value rendered as text"),
        ),
    )
    recorded = {str(key): _text(value) for key, value in attrs.items()}
    recorded["source_variable"] = variable
    for key, value in sorted(recorded.items()):
        table.add_row(series_name=series_name, key=key, value=value)


def _ensure_scratch_table(
    nwbfile: Any,
    name: str,
    description: str,
    columns: Sequence[tuple[str, str]],
) -> Any:
    existing = _scratch_table(nwbfile, name)
    if existing is not None:
        return existing
    from hdmf.common import DynamicTable, VectorData  # type: ignore[import-untyped]

    table = DynamicTable(
        name=name,
        description=description,
        columns=[
            VectorData(name=column, description=column_description)
            for column, column_description in columns
        ],
    )
    nwbfile.add_scratch(table)
    return table


def _scratch_table(nwbfile: Any, name: str) -> Any:
    scratch = getattr(nwbfile, "scratch", None)
    if scratch is None:
        return None
    table = scratch.get(name)
    return table if hasattr(table, "colnames") else None


def _ancestor_nwbfile(series: Any) -> Any:
    ancestor = getattr(series, "get_ancestor", None)
    if ancestor is None:
        return None
    return ancestor("NWBFile")


def _identity(
    override: str | None,
    key: str,
    nwbfile: Any,
    stored_attrs: Mapping[str, str],
    legacy: Mapping[str, Any],
) -> str:
    candidates = (
        override,
        _nwbfile_identity(nwbfile, key),
        stored_attrs.get(key),
        legacy.get(key),
    )
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return "unknown"


def _nwbfile_identity(nwbfile: Any, key: str) -> str | None:
    if nwbfile is None:
        return None
    if key == "session":
        return _text_or_none(getattr(nwbfile, "session_id", None))
    subject = getattr(nwbfile, "subject", None)
    return _text_or_none(getattr(subject, "subject_id", None))


def _channel_names(
    nwbfile: Any,
    series_name: str,
    legacy: Mapping[str, Any],
    extension_metadata: Sequence[Mapping[str, Any]],
    width: int,
) -> list[str] | None:
    recorded = _recorded_channel_names(nwbfile, series_name)
    if len(recorded) == width:
        return recorded
    legacy_names = legacy.get("channels")
    if isinstance(legacy_names, list) and len(legacy_names) == width:
        return [str(value) for value in legacy_names]
    if len(extension_metadata) == width:
        return [
            str(row.get("location") or f"channel_{index}")
            for index, row in enumerate(extension_metadata)
        ]
    return None


def _recorded_channel_names(nwbfile: Any, series_name: str) -> list[str]:
    table = _scratch_table(nwbfile, CHANNEL_TABLE_NAME)
    if table is None or not series_name:
        return []
    names = [str(value) for value in table["series_name"][:]]
    indices = [int(value) for value in table["channel_index"][:]]
    labels = [str(value) for value in table["channel_name"][:]]
    rows = [
        (index, label)
        for name, index, label in zip(names, indices, labels, strict=True)
        if name == series_name
    ]
    return [label for _, label in sorted(rows)]


def _timestamps(series: Any, length: int, *, sample_slice: slice) -> np.ndarray:
    if getattr(series, "timestamps", None) is not None:
        return np.asarray(series.timestamps[sample_slice], dtype=float)
    rate = getattr(series, "rate", None)
    if rate is None or rate <= 0:
        raise ValueError("NWB series needs timestamps or a positive rate")
    starting_time = float(getattr(series, "starting_time", 0.0) or 0.0)
    return starting_time + np.arange(length, dtype=float) / float(rate)


def _legacy_comment_metadata(comments: str) -> dict[str, Any]:
    try:
        value = json.loads(comments)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(value, dict) or value.get("schema") != LEGACY_COMMENT_SCHEMA:
        return {}
    return value


def _extension_channel_metadata(series: Any) -> list[dict[str, Any]]:
    try:
        response_series = _response_series_type()
    except ValueError:
        return []
    if not isinstance(series, response_series):
        return []
    region = series.fiber_photometry_table_region
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
        "excitation_source",
        "photodetector",
    )
    return [
        {field: _nwb_value(row[field]) for field in fields if field in row}
        for row in rows
    ]


def _nwb_value(value: Any) -> str | float | int | bool | None:
    if value is None or isinstance(value, (str, float, int, bool)):
        return value
    return str(getattr(value, "name", value))


def _text(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None
