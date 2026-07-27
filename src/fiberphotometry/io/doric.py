"""Native, schema-first reader for Doric HDF5 ``.doric`` files."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias

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


@dataclass(frozen=True)
class DoricSeries:
    """One numeric Doric dataset and its associated time dataset."""

    values_path: str
    time_path: str
    time_unit: TimeUnit = "seconds"


@dataclass(frozen=True)
class DoricChannel:
    """Explicit Doric series mapping for one anatomical signal channel."""

    name: str
    signal: DoricSeries
    reference: DoricSeries | None = None


@dataclass(frozen=True)
class DoricDigitalEvents:
    """Convert threshold crossings in one Doric series to named events."""

    name: str
    series: DoricSeries
    threshold: float = 0.5
    edge: EventEdge = "rising"


@dataclass(frozen=True)
class DoricSchema:
    """Versioned scientific mapping independent of mutable HDF5 hierarchy names."""

    channels: tuple[DoricChannel, ...]
    digital_events: tuple[DoricDigitalEvents, ...] = ()
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def inspect_doric(path: str | Path) -> AcquisitionInspection:
    """List one-dimensional numeric datasets without guessing channel identity."""
    source = Path(path)
    _require_doric(source)
    h5py = _h5py()
    fields: list[AcquisitionField] = []
    metadata: list[tuple[str, str]] = []
    with h5py.File(source, "r") as file:
        for key, value in sorted(file.attrs.items()):
            metadata.append((str(key), _text(value)))

        def collect(name: str, item: Any) -> None:
            if not isinstance(item, h5py.Dataset) or item.ndim != 1:
                return
            if item.dtype.kind not in "biuf":
                return
            basename = name.rsplit("/", 1)[-1].lower()
            role: Literal["signal", "time", "digital", "metadata", "unknown"]
            if basename == "time" or "timestamp" in basename:
                role = "time"
            elif any(token in basename for token in ("digital", "ttl", "dio")):
                role = "digital"
            else:
                role = "signal"
            units = next(
                (
                    _text(item.attrs[key])
                    for key in ("Unit", "Units", "unit", "units")
                    if key in item.attrs
                ),
                None,
            )
            fields.append(
                AcquisitionField(name, int(item.shape[0]), str(item.dtype), role, units)
            )

        file.visititems(collect)
    warnings = () if fields else ("no one-dimensional numeric datasets were found",)
    return AcquisitionInspection(
        "doric",
        source.name,
        file_sha256(source),
        tuple(fields),
        tuple(metadata),
        warnings,
    )


def load_doric_input(
    path: str | Path,
    schema: DoricSchema,
    *,
    subject: str,
    session: str,
) -> RecordingInput:
    """Load explicitly mapped Doric series through the canonical recording boundary."""
    _validate_schema(schema)
    if not subject.strip() or not session.strip():
        raise ValueError("subject and session identifiers must be non-empty")
    source = Path(path)
    _require_doric(source)
    h5py = _h5py()
    with h5py.File(source, "r") as file:
        signals: list[np.ndarray] = []
        signal_times: list[np.ndarray] = []
        references: list[np.ndarray] = []
        for channel in schema.channels:
            times, values = _read_series(file, channel.signal)
            signal_times.append(times)
            signals.append(values)
            if channel.reference is not None:
                reference_times, reference_values = _read_series(
                    file, channel.reference
                )
                references.append(
                    _interpolate_series(
                        reference_times,
                        reference_values,
                        times,
                        label=f"reference for {channel.name!r}",
                    )
                )
        canonical_time = signal_times[0]
        for channel, times in zip(schema.channels[1:], signal_times[1:], strict=True):
            if len(times) != len(canonical_time) or not np.allclose(
                times, canonical_time, rtol=0, atol=1e-9
            ):
                raise ValueError(
                    f"Doric signal time for {channel.name!r} is not aligned; "
                    "resampling must be an explicit preprocessing operation"
                )
        event_rows: list[tuple[float, str, str, str]] = []
        for event_spec in schema.digital_events:
            times, values = _read_series(file, event_spec.series)
            state = values >= event_spec.threshold
            transitions = np.diff(state.astype(np.int8))
            if event_spec.edge == "rising":
                indices = 1 + np.flatnonzero(transitions == 1)
                polarities = ("rising" for _ in indices)
            elif event_spec.edge == "falling":
                indices = 1 + np.flatnonzero(transitions == -1)
                polarities = ("falling" for _ in indices)
            else:
                indices = 1 + np.flatnonzero(transitions != 0)
                polarities = (
                    "rising" if transitions[index - 1] == 1 else "falling"
                    for index in indices
                )
            for event_index, (index, polarity) in enumerate(
                zip(indices, polarities, strict=True), start=1
            ):
                event_rows.append(
                    (
                        float(times[index]),
                        f"{session}:{event_spec.name}:{event_index}",
                        event_spec.name,
                        polarity,
                    )
                )
    fingerprint = file_sha256(source)
    recording = make_recording(
        time=canonical_time,
        signal=np.column_stack(signals),
        reference=np.column_stack(references) if references else None,
        channel_names=[channel.name for channel in schema.channels],
        subject=subject,
        session=session,
        attrs={
            "source_format": "Doric_HDF5",
            "source_name": source.name,
            "source_sha256": fingerprint,
            "source_fingerprint_scope": "file_content",
            "doric_schema": schema.to_json(),
        },
    )
    event_rows.sort(key=lambda row: (row[0], row[2], row[1]))
    loaded = RecordingInput(
        recording,
        tuple(row[0] for row in event_rows),
        tuple(row[1] for row in event_rows),
        {
            "event": tuple(row[2] for row in event_rows),
            "edge": tuple(row[3] for row in event_rows),
        },
    )
    return validate_acquisition_input(loaded)


def _read_series(file: Any, series: DoricSeries) -> tuple[np.ndarray, np.ndarray]:
    values = _dataset(file, series.values_path)
    times = _dataset(file, series.time_path) * _time_scale(series.time_unit)
    if len(values) != len(times):
        raise ValueError(
            f"Doric values {series.values_path!r} and time "
            f"{series.time_path!r} do not align"
        )
    if (
        len(times) < 2
        or not np.all(np.isfinite(times))
        or not np.all(np.diff(times) > 0)
    ):
        raise ValueError(
            f"Doric time dataset {series.time_path!r} must increase strictly"
        )
    return times, values


def _dataset(file: Any, path: str) -> np.ndarray:
    key = path.strip("/")
    if key not in file:
        raise ValueError(f"Doric dataset does not exist: {path!r}")
    dataset = file[key]
    if getattr(dataset, "ndim", None) != 1 or dataset.dtype.kind not in "biuf":
        raise ValueError(f"Doric dataset must be one-dimensional and numeric: {path!r}")
    return np.asarray(dataset, dtype=float)


def _interpolate_series(
    source_time: np.ndarray,
    source_values: np.ndarray,
    target_time: np.ndarray,
    *,
    label: str,
) -> np.ndarray:
    valid = np.isfinite(source_values)
    if valid.sum() < 2:
        raise ValueError(f"Doric {label} has fewer than two finite samples")
    output = np.full(len(target_time), np.nan)
    within = (target_time >= source_time[valid].min()) & (
        target_time <= source_time[valid].max()
    )
    output[within] = np.interp(
        target_time[within], source_time[valid], source_values[valid]
    )
    return output


def _validate_schema(schema: DoricSchema) -> None:
    if schema.schema_version != "1" or not schema.channels:
        raise ValueError("Doric schema version 1 requires at least one channel")
    names = [channel.name for channel in schema.channels]
    if any(not name.strip() for name in names) or len(names) != len(set(names)):
        raise ValueError("Doric channel names must be non-empty and unique")
    references = [channel.reference is not None for channel in schema.channels]
    if len(set(references)) > 1:
        raise ValueError("Doric references must be declared for every channel or none")
    for channel in schema.channels:
        _validate_series(channel.signal)
        if channel.reference is not None:
            _validate_series(channel.reference)
    event_names = [event.name for event in schema.digital_events]
    if any(not name.strip() for name in event_names) or len(event_names) != len(
        set(event_names)
    ):
        raise ValueError("Doric digital event names must be non-empty and unique")
    for event in schema.digital_events:
        _validate_series(event.series)
        if not np.isfinite(event.threshold):
            raise ValueError("Doric digital thresholds must be finite")


def _validate_series(series: DoricSeries) -> None:
    if not series.values_path.strip() or not series.time_path.strip():
        raise ValueError("Doric series paths must be explicit")


def _require_doric(path: Path) -> None:
    if not path.is_file() or path.suffix.lower() != ".doric":
        raise ValueError(f"Doric input must be an existing .doric file: {path}")


def _h5py() -> Any:
    try:
        import h5py  # type: ignore[import-untyped]
    except ImportError as error:  # pragma: no cover - depends on optional environment
        raise ImportError(
            "Doric support requires the 'acquisition' extra: "
            "pip install fiberphotometry[acquisition]"
        ) from error
    return h5py


def _time_scale(unit: TimeUnit) -> float:
    return 1.0 if unit == "seconds" else 0.001


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray):
        return json.dumps(value.tolist(), default=str)
    return str(value)
