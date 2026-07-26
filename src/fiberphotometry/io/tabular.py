"""Explicit, dependency-free adapters for ordinary CSV and TSV photometry data."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, TypeAlias

import numpy as np
import xarray as xr

from fiberphotometry.design import Scalar
from fiberphotometry.model import make_recording
from fiberphotometry.pipeline import RecordingInput

TimeUnit = Literal["seconds", "milliseconds"]
EventValueKind = Literal["string", "float", "int", "bool"]
PathLike: TypeAlias = str | Path


@dataclass(frozen=True)
class TabularChannel:
    """Explicit mapping from source columns to one anatomical signal channel."""

    name: str
    signal_column: str
    reference_column: str | None = None


@dataclass(frozen=True)
class TabularRecordingSchema:
    """Versioned mapping for one wide recording table."""

    time_column: str
    channels: tuple[TabularChannel, ...]
    time_unit: TimeUnit = "seconds"
    delimiter: str | None = None
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class TabularEventColumn:
    """Map and type one event metadata column."""

    source: str
    name: str | None = None
    kind: EventValueKind = "string"


@dataclass(frozen=True)
class TabularEventSchema:
    """Versioned mapping for an event table associated with one recording."""

    time_column: str
    event_id_column: str
    columns: tuple[TabularEventColumn, ...]
    time_unit: TimeUnit = "seconds"
    delimiter: str | None = None
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class TabularChannelInspection:
    channel: str
    signal_finite_fraction: float
    reference_finite_fraction: float | None


@dataclass(frozen=True)
class TabularInspection:
    """Machine-readable metadata and acquisition diagnostics for one source file."""

    source_name: str
    source_sha256: str
    row_count: int
    start_time_s: float
    end_time_s: float
    duration_s: float
    estimated_rate_hz: float
    irregular_interval_fraction: float
    channels: tuple[TabularChannelInspection, ...]
    warnings: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class TabularEvents:
    event_times: tuple[float, ...]
    event_ids: tuple[str, ...]
    columns: Mapping[str, tuple[Scalar, ...]]
    source_name: str
    source_sha256: str


@dataclass(frozen=True)
class TabularEventInspection:
    source_name: str
    source_sha256: str
    row_count: int
    start_time_s: float
    end_time_s: float
    metadata_columns: tuple[str, ...]


@dataclass(frozen=True)
class TabularInputInspection:
    """Preflight diagnostics spanning the acquisition and event clocks."""

    recording: TabularInspection
    events: TabularEventInspection
    warnings: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def load_tabular_recording(
    path: PathLike,
    schema: TabularRecordingSchema,
    *,
    subject: str,
    session: str,
) -> xr.Dataset:
    """Load a wide CSV/TSV recording through explicit scientific mappings."""
    _validate_recording_schema(schema)
    if not subject.strip() or not session.strip():
        raise ValueError("subject and session identifiers must be non-empty")
    source = Path(path)
    rows, headings = _read_rows(source, schema.delimiter)
    required = {
        schema.time_column,
        *(channel.signal_column for channel in schema.channels),
        *(
            channel.reference_column
            for channel in schema.channels
            if channel.reference_column is not None
        ),
    }
    _require_columns(headings, required, table="recording")
    scale = _time_scale(schema.time_unit)
    times = (
        np.asarray(
            [
                _required_float(row[schema.time_column], schema.time_column)
                for row in rows
            ]
        )
        * scale
    )
    signals = np.column_stack(
        [
            [_optional_float(row[channel.signal_column]) for row in rows]
            for channel in schema.channels
        ]
    )
    references = (
        np.column_stack(
            [
                [_optional_float(row[str(channel.reference_column)]) for row in rows]
                for channel in schema.channels
            ]
        )
        if schema.channels[0].reference_column is not None
        else None
    )
    fingerprint = _fingerprint(source)
    return make_recording(
        time=times,
        signal=signals,
        reference=references,
        channel_names=[channel.name for channel in schema.channels],
        subject=subject,
        session=session,
        attrs={
            "source_format": "delimited_text",
            "source_name": source.name,
            "source_sha256": fingerprint,
            "tabular_schema": schema.to_json(),
            "time_unit_original": schema.time_unit,
        },
    )


def load_tabular_events(path: PathLike, schema: TabularEventSchema) -> TabularEvents:
    """Load event times, identifiers, and explicitly typed metadata columns."""
    _validate_event_schema(schema)
    source = Path(path)
    rows, headings = _read_rows(source, schema.delimiter)
    required = {
        schema.time_column,
        schema.event_id_column,
        *(column.source for column in schema.columns),
    }
    _require_columns(headings, required, table="event")
    scale = _time_scale(schema.time_unit)
    event_times = tuple(
        _required_float(row[schema.time_column], schema.time_column) * scale
        for row in rows
    )
    event_ids = tuple(row[schema.event_id_column].strip() for row in rows)
    if any(not identifier for identifier in event_ids):
        raise ValueError("event identifiers must be non-empty")
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("event identifiers must be unique within a session")
    columns = {
        column.name or column.source: tuple(
            _event_value(row[column.source], column) for row in rows
        )
        for column in schema.columns
    }
    return TabularEvents(
        event_times,
        event_ids,
        columns,
        source.name,
        _fingerprint(source),
    )


def load_tabular_input(
    recording_path: PathLike,
    recording_schema: TabularRecordingSchema,
    event_path: PathLike,
    event_schema: TabularEventSchema,
    *,
    subject: str,
    session: str,
) -> RecordingInput:
    """Load one complete pipeline input without conflating samples and events."""
    recording = load_tabular_recording(
        recording_path, recording_schema, subject=subject, session=session
    )
    events = load_tabular_events(event_path, event_schema)
    recording.attrs["event_source_name"] = events.source_name
    recording.attrs["event_source_sha256"] = events.source_sha256
    return RecordingInput(
        recording,
        events.event_times,
        events.event_ids,
        events.columns,
    )


def inspect_tabular_recording(
    path: PathLike,
    schema: TabularRecordingSchema,
    *,
    subject: str,
    session: str,
) -> TabularInspection:
    """Load and summarize a source before selecting an analysis workflow."""
    recording = load_tabular_recording(path, schema, subject=subject, session=session)
    times = np.asarray(recording.time.values, dtype=float)
    intervals = np.diff(times)
    median_interval = float(np.median(intervals))
    relative_deviation = np.abs(intervals - median_interval) / median_interval
    irregular_fraction = float(np.mean(relative_deviation > 0.01))
    channel_inspections = []
    for index, channel in enumerate(recording.channel.values):
        signal_fraction = float(np.mean(np.isfinite(recording.signal.values[:, index])))
        reference_fraction = (
            float(np.mean(np.isfinite(recording.reference.values[:, index])))
            if "reference" in recording
            else None
        )
        channel_inspections.append(
            TabularChannelInspection(str(channel), signal_fraction, reference_fraction)
        )
    warnings = []
    if irregular_fraction > 0.01:
        warnings.append("irregular_sampling")
    if any(item.signal_finite_fraction < 1 for item in channel_inspections):
        warnings.append("missing_signal_values")
    if any(
        item.reference_finite_fraction is not None
        and item.reference_finite_fraction < 1
        for item in channel_inspections
    ):
        warnings.append("missing_reference_values")
    return TabularInspection(
        source_name=str(recording.attrs["source_name"]),
        source_sha256=str(recording.attrs["source_sha256"]),
        row_count=len(times),
        start_time_s=float(times[0]),
        end_time_s=float(times[-1]),
        duration_s=float(times[-1] - times[0]),
        estimated_rate_hz=1 / median_interval,
        irregular_interval_fraction=irregular_fraction,
        channels=tuple(channel_inspections),
        warnings=tuple(warnings),
    )


def inspect_tabular_input(
    recording_path: PathLike,
    recording_schema: TabularRecordingSchema,
    event_path: PathLike,
    event_schema: TabularEventSchema,
    *,
    subject: str,
    session: str,
) -> TabularInputInspection:
    """Inspect recording integrity and clock coverage before analysis."""
    recording = inspect_tabular_recording(
        recording_path, recording_schema, subject=subject, session=session
    )
    events = load_tabular_events(event_path, event_schema)
    event_inspection = TabularEventInspection(
        source_name=events.source_name,
        source_sha256=events.source_sha256,
        row_count=len(events.event_times),
        start_time_s=min(events.event_times),
        end_time_s=max(events.event_times),
        metadata_columns=tuple(events.columns),
    )
    warnings = list(recording.warnings)
    if event_inspection.start_time_s < recording.start_time_s:
        warnings.append("events_before_recording")
    if event_inspection.end_time_s > recording.end_time_s:
        warnings.append("events_after_recording")
    return TabularInputInspection(recording, event_inspection, tuple(warnings))


def _validate_recording_schema(schema: TabularRecordingSchema) -> None:
    if schema.schema_version != "1":
        raise ValueError("unsupported tabular recording schema version")
    if not schema.time_column.strip():
        raise ValueError("time_column must be non-empty")
    if not schema.channels:
        raise ValueError("at least one explicitly mapped channel is required")
    names = [channel.name for channel in schema.channels]
    signals = [channel.signal_column for channel in schema.channels]
    if any(not value.strip() for value in [*names, *signals]):
        raise ValueError("channel names and signal columns must be non-empty")
    if len(names) != len(set(names)):
        raise ValueError("channel names must be unique")
    if len(signals) != len(set(signals)):
        raise ValueError("signal columns must be unique")
    reference_presence = {
        channel.reference_column is not None for channel in schema.channels
    }
    if len(reference_presence) != 1:
        raise ValueError(
            "reference columns must be explicitly mapped for every channel or none"
        )
    references = [
        str(channel.reference_column)
        for channel in schema.channels
        if channel.reference_column is not None
    ]
    if len(references) != len(set(references)):
        raise ValueError("reference columns must be unique")
    mapped = [schema.time_column, *signals, *references]
    if len(mapped) != len(set(mapped)):
        raise ValueError("time, signal, and reference columns must not overlap")
    _validate_delimiter(schema.delimiter)
    _time_scale(schema.time_unit)


def _validate_event_schema(schema: TabularEventSchema) -> None:
    if schema.schema_version != "1":
        raise ValueError("unsupported tabular event schema version")
    if not schema.time_column.strip() or not schema.event_id_column.strip():
        raise ValueError("event time and identifier columns must be non-empty")
    output_names = [column.name or column.source for column in schema.columns]
    if any(
        not column.source.strip() or not name.strip()
        for column, name in zip(schema.columns, output_names, strict=True)
    ):
        raise ValueError("event metadata column names must be non-empty")
    if len(output_names) != len(set(output_names)):
        raise ValueError("event metadata output names must be unique")
    valid_kinds = {"string", "float", "int", "bool"}
    invalid_kinds = sorted(
        {column.kind for column in schema.columns if column.kind not in valid_kinds}
    )
    if invalid_kinds:
        raise ValueError(f"unsupported event value kinds: {', '.join(invalid_kinds)}")
    _validate_delimiter(schema.delimiter)
    _time_scale(schema.time_unit)


def _read_rows(
    path: Path, delimiter: str | None
) -> tuple[list[dict[str, str]], set[str]]:
    if not path.is_file():
        raise ValueError(f"tabular source does not exist: {path}")
    selected_delimiter = delimiter or (
        "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    )
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=selected_delimiter)
        if reader.fieldnames is None:
            raise ValueError("tabular source requires a header row")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("tabular source column names must be unique")
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("tabular source must contain at least one data row")
    return rows, set(reader.fieldnames)


def _require_columns(headings: set[str], required: set[str], *, table: str) -> None:
    missing = sorted(required - headings)
    if missing:
        raise ValueError(f"{table} table is missing columns: {', '.join(missing)}")


def _required_float(value: str, column: str) -> float:
    parsed = _optional_float(value)
    if not np.isfinite(parsed):
        raise ValueError(f"column {column!r} requires finite numeric values")
    return parsed


def _optional_float(value: str) -> float:
    stripped = value.strip()
    if stripped.lower() in {"", "na", "nan", "null", "none"}:
        return float("nan")
    try:
        return float(stripped)
    except ValueError as error:
        raise ValueError(f"expected a numeric value, received {value!r}") from error


def _event_value(value: str, column: TabularEventColumn) -> Scalar:
    converters: dict[EventValueKind, Callable[[str], Scalar]] = {
        "string": lambda item: item.strip(),
        "float": lambda item: _required_float(item, column.source),
        "int": _integer,
        "bool": _boolean,
    }
    return converters[column.kind](value)


def _integer(value: str) -> int:
    stripped = value.strip()
    try:
        return int(stripped)
    except ValueError as error:
        raise ValueError(f"expected an integer value, received {value!r}") from error


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"expected a boolean value, received {value!r}")


def _time_scale(unit: TimeUnit) -> float:
    if unit == "seconds":
        return 1.0
    if unit == "milliseconds":
        return 0.001
    raise ValueError(f"unsupported time unit: {unit}")


def _validate_delimiter(delimiter: str | None) -> None:
    if delimiter is not None and len(delimiter) != 1:
        raise ValueError("delimiter must be exactly one character")


def _fingerprint(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
