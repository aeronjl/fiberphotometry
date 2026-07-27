"""Native reader for Neurophotometrics Bonsai CSV and parquet exports."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypeAlias

import numpy as np

from fiberphotometry.io.acquisition import (
    AcquisitionField,
    AcquisitionInspection,
    file_sha256,
    validate_acquisition_input,
)
from fiberphotometry.model import make_recording
from fiberphotometry.pipeline import RecordingInput

TimeUnit: TypeAlias = Literal["seconds", "milliseconds"]
EventEdge: TypeAlias = Literal["rising", "falling", "both"]

WAVELENGTH_BITS = {415.0: 1, 470.0: 2, 560.0: 4}


@dataclass(frozen=True)
class NeurophotometricsChannel:
    """Map one ROI column and excitation wavelengths to an anatomical channel."""

    name: str
    roi_column: str
    signal_wavelength: float = 470.0
    reference_wavelength: float | None = 415.0


@dataclass(frozen=True)
class NeurophotometricsDigitalEvents:
    """Decode an acquisition flag bit into named transition events."""

    name: str
    mask: int
    edge: EventEdge = "rising"


@dataclass(frozen=True)
class NeurophotometricsSchema:
    """Explicit ROI/wavelength meaning with conservative column-name discovery."""

    channels: tuple[NeurophotometricsChannel, ...]
    digital_events: tuple[NeurophotometricsDigitalEvents, ...] = ()
    timestamp_column: str | None = None
    led_state_column: str | None = None
    time_unit: TimeUnit = "seconds"
    drop_first_row: bool = False
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def inspect_neurophotometrics(path: str | Path) -> AcquisitionInspection:
    """Inventory export columns and flag unsupported simultaneous-LED rows."""
    source = Path(path)
    table = _read_table(source)
    timestamp = _choose_column(table, None, ("SystemTimestamp", "Timestamp"), "time")
    led_state = _choose_column(table, None, ("LedState", "Flags"), "LED state")
    fields = tuple(
        AcquisitionField(
            key,
            len(values),
            str(values.dtype),
            "time"
            if key == timestamp
            else "digital"
            if key == led_state
            else "signal"
            if key.startswith("Region")
            else "metadata",
        )
        for key, values in table.items()
    )
    states = _numeric(table, led_state, integer=True).astype(int)
    simultaneous = int(np.count_nonzero(~np.isin(states & 0b111, [0, 1, 2, 4])))
    warnings = (
        (f"{simultaneous} rows contain simultaneous or unknown excitation LEDs",)
        if simultaneous
        else ()
    )
    version = (
        "version_5"
        if "SystemTimestamp" in table
        else "version_2"
        if "LedState" in table
        else "version_1"
    )
    return AcquisitionInspection(
        "neurophotometrics",
        source.name,
        file_sha256(source),
        fields,
        (("detected_layout", version),),
        warnings,
    )


def load_neurophotometrics_input(
    path: str | Path,
    schema: NeurophotometricsSchema,
    *,
    subject: str,
    session: str,
) -> RecordingInput:
    """Load alternating excitation rows and interpolate reference onto signal time."""
    _validate_schema(schema)
    if not subject.strip() or not session.strip():
        raise ValueError("subject and session identifiers must be non-empty")
    source = Path(path)
    table = _read_table(source)
    timestamp_key = _choose_column(
        table, schema.timestamp_column, ("SystemTimestamp", "Timestamp"), "time"
    )
    state_key = _choose_column(
        table, schema.led_state_column, ("LedState", "Flags"), "LED state"
    )
    missing_roi = [
        channel.roi_column
        for channel in schema.channels
        if channel.roi_column not in table
    ]
    if missing_roi:
        raise ValueError(f"Neurophotometrics ROI columns are missing: {missing_roi}")
    times = _numeric(table, timestamp_key) * _time_scale(schema.time_unit)
    states = _numeric(table, state_key, integer=True).astype(int)
    if schema.drop_first_row:
        times = times[1:]
        states = states[1:]
        table = {key: values[1:] for key, values in table.items()}
    signal_times: list[np.ndarray] = []
    signals: list[np.ndarray] = []
    references: list[np.ndarray] = []
    for channel in schema.channels:
        values = _numeric(table, channel.roi_column)
        signal_rows = (states & 0b111) == _wavelength_bit(channel.signal_wavelength)
        if signal_rows.sum() < 2:
            raise ValueError(
                f"Neurophotometrics {channel.roi_column!r} has fewer than two "
                f"samples at {channel.signal_wavelength:g} nm"
            )
        channel_times = times[signal_rows]
        if not np.all(np.isfinite(channel_times)) or not np.all(
            np.diff(channel_times) > 0
        ):
            raise ValueError(
                "Neurophotometrics signal timestamps must increase strictly"
            )
        signal_times.append(channel_times)
        signals.append(values[signal_rows])
        if channel.reference_wavelength is not None:
            reference_rows = (states & 0b111) == _wavelength_bit(
                channel.reference_wavelength
            )
            if reference_rows.sum() < 2:
                raise ValueError(
                    f"Neurophotometrics {channel.roi_column!r} has fewer than two "
                    f"samples at {channel.reference_wavelength:g} nm"
                )
            references.append(
                _interpolate_reference(
                    times[reference_rows], values[reference_rows], channel_times
                )
            )
    canonical_time = signal_times[0]
    for channel, channel_time in zip(
        schema.channels[1:], signal_times[1:], strict=True
    ):
        if len(channel_time) != len(canonical_time) or not np.allclose(
            channel_time, canonical_time, rtol=0, atol=1e-9
        ):
            raise ValueError(
                f"Neurophotometrics signal time for {channel.name!r} is not aligned"
            )
    event_rows = _digital_events(times, states, schema.digital_events, session)
    recording = make_recording(
        time=canonical_time,
        signal=np.column_stack(signals),
        reference=np.column_stack(references) if references else None,
        channel_names=[channel.name for channel in schema.channels],
        subject=subject,
        session=session,
        attrs={
            "source_format": "Neurophotometrics_Bonsai",
            "source_name": source.name,
            "source_sha256": file_sha256(source),
            "source_fingerprint_scope": "file_content",
            "neurophotometrics_schema": schema.to_json(),
            "timestamp_column": timestamp_key,
            "led_state_column": state_key,
        },
    )
    recording["led_state"] = (
        ("time",),
        states[
            (states & 0b111) == _wavelength_bit(schema.channels[0].signal_wavelength)
        ],
    )
    loaded = RecordingInput(
        recording,
        tuple(row[0] for row in event_rows),
        tuple(row[1] for row in event_rows),
        {
            "event": tuple(row[2] for row in event_rows),
            "edge": tuple(row[3] for row in event_rows),
            "flag_mask": tuple(row[4] for row in event_rows),
        },
    )
    return validate_acquisition_input(loaded)


def _read_table(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise ValueError(f"Neurophotometrics source does not exist: {path}")
    if path.suffix.lower() in {".pqt", ".parquet"}:
        try:
            import pandas as pd  # type: ignore[import-untyped]
        except ImportError as error:  # pragma: no cover - optional environment
            raise ImportError(
                "Neurophotometrics parquet support requires the 'acquisition' extra"
            ) from error
        frame = pd.read_parquet(path)
        return {str(column): frame[column].to_numpy() for column in frame.columns}
    if path.suffix.lower() not in {".csv", ".tsv", ".txt"}:
        raise ValueError("Neurophotometrics input must be CSV, TSV, PQT, or parquet")
    delimiter = "\t" if path.suffix.lower() == ".tsv" else None
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        if delimiter is None:
            sample = stream.read(4096)
            stream.seek(0)
            delimiter = csv.Sniffer().sniff(sample).delimiter
        reader = csv.DictReader(stream, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("Neurophotometrics table has no header")
        columns: dict[str, list[str]] = {str(name): [] for name in reader.fieldnames}
        for row in reader:
            for name in columns:
                columns[name].append(row.get(name, ""))
    if not columns or not next(iter(columns.values())):
        raise ValueError("Neurophotometrics table has no data rows")
    return {name: np.asarray(values, dtype=str) for name, values in columns.items()}


def _choose_column(
    table: dict[str, np.ndarray],
    explicit: str | None,
    candidates: tuple[str, ...],
    label: str,
) -> str:
    if explicit is not None:
        if explicit not in table:
            raise ValueError(
                f"Neurophotometrics {label} column is missing: {explicit!r}"
            )
        return explicit
    found = [candidate for candidate in candidates if candidate in table]
    if len(found) != 1:
        raise ValueError(
            f"Neurophotometrics {label} column is ambiguous; declare it explicitly"
        )
    return found[0]


def _numeric(
    table: dict[str, np.ndarray], key: str, *, integer: bool = False
) -> np.ndarray:
    try:
        values = np.asarray(table[key], dtype=int if integer else float)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Neurophotometrics column {key!r} must be numeric") from error
    if values.ndim != 1:
        raise ValueError(f"Neurophotometrics column {key!r} must be one-dimensional")
    return values


def _interpolate_reference(
    reference_time: np.ndarray,
    reference: np.ndarray,
    signal_time: np.ndarray,
) -> np.ndarray:
    valid = np.isfinite(reference_time) & np.isfinite(reference)
    if valid.sum() < 2 or not np.all(np.diff(reference_time[valid]) > 0):
        raise ValueError(
            "Neurophotometrics reference timestamps must increase strictly"
        )
    output = np.full(len(signal_time), np.nan)
    within = (signal_time >= reference_time[valid].min()) & (
        signal_time <= reference_time[valid].max()
    )
    output[within] = np.interp(
        signal_time[within], reference_time[valid], reference[valid]
    )
    return output


def _digital_events(
    times: np.ndarray,
    states: np.ndarray,
    specs: tuple[NeurophotometricsDigitalEvents, ...],
    session: str,
) -> list[tuple[float, str, str, str, int]]:
    rows: list[tuple[float, str, str, str, int]] = []
    for spec in specs:
        active = (states & spec.mask) != 0
        transitions = np.diff(active.astype(np.int8))
        if spec.edge == "rising":
            indices = 1 + np.flatnonzero(transitions == 1)
        elif spec.edge == "falling":
            indices = 1 + np.flatnonzero(transitions == -1)
        else:
            indices = 1 + np.flatnonzero(transitions != 0)
        for event_index, index in enumerate(indices, start=1):
            edge = "rising" if transitions[index - 1] == 1 else "falling"
            rows.append(
                (
                    float(times[index]),
                    f"{session}:{spec.name}:{event_index}",
                    spec.name,
                    edge,
                    spec.mask,
                )
            )
    rows.sort(key=lambda row: (row[0], row[2], row[1]))
    return rows


def _validate_schema(schema: NeurophotometricsSchema) -> None:
    if schema.schema_version != "1" or not schema.channels:
        raise ValueError(
            "Neurophotometrics schema version 1 requires at least one channel"
        )
    names = [channel.name for channel in schema.channels]
    rois = [channel.roi_column for channel in schema.channels]
    if any(not name.strip() for name in names) or len(names) != len(set(names)):
        raise ValueError("Neurophotometrics channel names must be non-empty and unique")
    if any(not roi.strip() for roi in rois) or len(rois) != len(set(rois)):
        raise ValueError("Neurophotometrics ROI mappings must be non-empty and unique")
    references = [
        channel.reference_wavelength is not None for channel in schema.channels
    ]
    if len(set(references)) > 1:
        raise ValueError(
            "Neurophotometrics references must be declared for every channel or none"
        )
    for channel in schema.channels:
        _wavelength_bit(channel.signal_wavelength)
        if channel.reference_wavelength is not None:
            _wavelength_bit(channel.reference_wavelength)
            if channel.reference_wavelength == channel.signal_wavelength:
                raise ValueError("signal and reference wavelengths must differ")
    event_names = [event.name for event in schema.digital_events]
    if any(not name.strip() for name in event_names) or len(event_names) != len(
        set(event_names)
    ):
        raise ValueError(
            "Neurophotometrics digital event names must be non-empty and unique"
        )
    if any(event.mask < 8 for event in schema.digital_events):
        raise ValueError("Neurophotometrics event masks cannot overlap excitation bits")


def _wavelength_bit(wavelength: float) -> int:
    for known, bit in WAVELENGTH_BITS.items():
        if np.isclose(wavelength, known):
            return bit
    raise ValueError("Neurophotometrics wavelength must be 415, 470, or 560 nm")


def _time_scale(unit: TimeUnit) -> float:
    return 1.0 if unit == "seconds" else 0.001
