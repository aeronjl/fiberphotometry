"""Native reader for versioned pyPhotometry ``.ppd`` binary files."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from fiberphotometry.io.acquisition import (
    AcquisitionField,
    AcquisitionInspection,
    file_sha256,
    validate_acquisition_input,
)
from fiberphotometry.model import make_recording
from fiberphotometry.pipeline import RecordingInput


@dataclass(frozen=True)
class PyPhotometryChannel:
    """Explicit analog-input mapping for one anatomical signal channel."""

    name: str
    signal_analog: int
    reference_analog: int | None = None


@dataclass(frozen=True)
class PyPhotometryDigitalEvents:
    """Expose rising edges on one pyPhotometry digital input as events."""

    digital_input: int
    name: str


@dataclass(frozen=True)
class PyPhotometrySchema:
    """Scientific mapping kept separate from the binary acquisition header."""

    channels: tuple[PyPhotometryChannel, ...]
    digital_events: tuple[PyPhotometryDigitalEvents, ...] = ()
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class _PPDData:
    header: dict[str, Any]
    analog: tuple[np.ndarray, ...]
    digital: tuple[np.ndarray, ...]
    led_on: tuple[np.ndarray, ...] | None
    baseline: tuple[np.ndarray, ...] | None
    clipping: tuple[np.ndarray, ...] | None
    sampling_rate: float


def inspect_pyphotometry(path: str | Path) -> AcquisitionInspection:
    """Inventory analog and digital inputs without assigning biological roles."""
    source = Path(path)
    parsed = _read_ppd(source)
    fields = tuple(
        AcquisitionField(
            f"analog_{index}", len(values), str(values.dtype), "signal", "V"
        )
        for index, values in enumerate(parsed.analog, start=1)
    ) + tuple(
        AcquisitionField(
            f"digital_{index}", len(values), str(values.dtype), "digital", None
        )
        for index, values in enumerate(parsed.digital, start=1)
    )
    metadata = tuple(
        (
            key,
            json.dumps(value, sort_keys=True) if not isinstance(value, str) else value,
        )
        for key, value in sorted(parsed.header.items())
    )
    return AcquisitionInspection(
        "pyphotometry", source.name, file_sha256(source), fields, metadata
    )


def load_pyphotometry_input(
    path: str | Path,
    schema: PyPhotometrySchema,
    *,
    subject: str,
    session: str,
) -> RecordingInput:
    """Load raw pyPhotometry signals and digital rising edges without filtering."""
    _validate_schema(schema)
    if not subject.strip() or not session.strip():
        raise ValueError("subject and session identifiers must be non-empty")
    source = Path(path)
    parsed = _read_ppd(source)
    _validate_indices(schema, len(parsed.analog), len(parsed.digital))
    signals = np.column_stack(
        [parsed.analog[channel.signal_analog - 1] for channel in schema.channels]
    )
    reference_arrays: list[np.ndarray] = []
    if schema.channels[0].reference_analog is not None:
        for channel in schema.channels:
            reference_index = channel.reference_analog
            if reference_index is None:  # guarded by schema validation
                raise AssertionError("validated reference mapping became incomplete")
            reference_arrays.append(parsed.analog[reference_index - 1])
    references = np.column_stack(reference_arrays) if reference_arrays else None
    sample_count = signals.shape[0]
    time = np.arange(sample_count, dtype=float) / parsed.sampling_rate
    recording = make_recording(
        time=time,
        signal=signals,
        reference=references,
        channel_names=[channel.name for channel in schema.channels],
        subject=subject,
        session=session,
        attrs={
            "source_format": "pyPhotometry_ppd",
            "source_name": source.name,
            "source_sha256": file_sha256(source),
            "source_fingerprint_scope": "file_content",
            "pyphotometry_schema": schema.to_json(),
            "pyphotometry_header": json.dumps(parsed.header, sort_keys=True),
            "pyphotometry_version": str(parsed.header.get("version", "unknown")),
            "sampling_rate_hz": parsed.sampling_rate,
        },
    )
    recording = _attach_acquisition_evidence(recording, parsed, schema)
    event_rows: list[tuple[float, str, str, int]] = []
    for event_spec in schema.digital_events:
        state = parsed.digital[event_spec.digital_input - 1]
        for event_index, sample_index in enumerate(
            1 + np.flatnonzero(np.diff(state.astype(np.int8)) == 1), start=1
        ):
            event_rows.append(
                (
                    float(sample_index / parsed.sampling_rate),
                    f"{session}:digital_{event_spec.digital_input}:{event_index}",
                    event_spec.name,
                    event_spec.digital_input,
                )
            )
    event_rows.sort(key=lambda row: (row[0], row[3], row[1]))
    loaded = RecordingInput(
        recording,
        tuple(row[0] for row in event_rows),
        tuple(row[1] for row in event_rows),
        {
            "event": tuple(row[2] for row in event_rows),
            "digital_input": tuple(row[3] for row in event_rows),
        },
    )
    return validate_acquisition_input(loaded)


def _read_ppd(path: Path) -> _PPDData:
    if path.suffix.lower() != ".ppd":
        raise ValueError("pyPhotometry input must use the .ppd extension")
    with path.open("rb") as stream:
        size_bytes = stream.read(2)
        if len(size_bytes) != 2:
            raise ValueError("pyPhotometry file is missing its two-byte header length")
        header_size = int.from_bytes(size_bytes, "little")
        header_bytes = stream.read(header_size)
        if len(header_bytes) != header_size:
            raise ValueError("pyPhotometry JSON header is truncated")
        payload = stream.read()
    try:
        header = json.loads(header_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("pyPhotometry JSON header is invalid") from error
    try:
        sampling_rate = float(header["sampling_rate"])
        volts_per_division = float(header["volts_per_division"][0])
        mode = str(header["mode"]).lower()
        version = _version_tuple(str(header["version"]))
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise ValueError(
            "pyPhotometry header lacks required acquisition metadata"
        ) from error
    if not np.isfinite(sampling_rate) or sampling_rate <= 0:
        raise ValueError("pyPhotometry sampling_rate must be positive")
    if version < (1, 0):
        n_analog = 2
        n_digital = 2
        pulsed = "time div" in mode
    else:
        try:
            n_analog = int(header["n_analog_signals"])
            n_digital = int(header["n_digital_signals"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("pyPhotometry header lacks channel counts") from error
        pulsed = "pulsed" in mode
    if n_analog < 1 or n_digital < 0 or n_digital > n_analog:
        raise ValueError("pyPhotometry channel counts are invalid")
    if len(payload) % 2:
        raise ValueError("pyPhotometry binary payload has an incomplete word")
    words = np.frombuffer(payload, dtype="<u2")
    has_baselines = version >= (1, 1) and pulsed
    stride = (2 if has_baselines else 1) * n_analog
    if not len(words) or len(words) % stride:
        raise ValueError("pyPhotometry payload does not contain complete sample frames")
    analog_words = words >> 1
    digital_words = (words & 1).astype(bool)
    clipping: tuple[np.ndarray, ...] | None
    if has_baselines:
        led_on = tuple(
            analog_words[2 * index :: stride].astype(float) * volts_per_division
            for index in range(n_analog)
        )
        baseline = tuple(
            analog_words[2 * index + 1 :: stride].astype(float) * volts_per_division
            for index in range(n_analog)
        )
        analog = tuple(on - off for on, off in zip(led_on, baseline, strict=True))
        try:
            adc_max = float(header["ADC_max_value"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "pyPhotometry v1.1 pulsed header lacks ADC_max_value"
            ) from error
        threshold = 0.98 * adc_max * volts_per_division
        clipping = tuple(
            np.maximum(on, off) > threshold
            for on, off in zip(led_on, baseline, strict=True)
        )
        digital = tuple(
            digital_words[2 * index :: stride] for index in range(n_digital)
        )
    else:
        led_on = None
        baseline = None
        analog = tuple(
            analog_words[index::stride].astype(float) * volts_per_division
            for index in range(n_analog)
        )
        digital = tuple(digital_words[index::stride] for index in range(n_digital))
        threshold = 0.98 * (1 << 15) * volts_per_division
        clipping = None if pulsed else tuple(values > threshold for values in analog)
    return _PPDData(header, analog, digital, led_on, baseline, clipping, sampling_rate)


def _attach_acquisition_evidence(
    recording: xr.Dataset, parsed: _PPDData, schema: PyPhotometrySchema
) -> xr.Dataset:
    signal_indices = [channel.signal_analog - 1 for channel in schema.channels]
    reference_indices = [
        int(channel.reference_analog) - 1
        for channel in schema.channels
        if channel.reference_analog is not None
    ]
    if parsed.clipping is not None:
        recording["signal_clipping"] = (
            ("time", "channel"),
            np.column_stack([parsed.clipping[index] for index in signal_indices]),
        )
        if reference_indices:
            recording["reference_clipping"] = (
                ("time", "channel"),
                np.column_stack(
                    [parsed.clipping[index] for index in reference_indices]
                ),
            )
    if parsed.led_on is not None and parsed.baseline is not None:
        recording["signal_raw_led_on"] = (
            ("time", "channel"),
            np.column_stack([parsed.led_on[index] for index in signal_indices]),
        )
        recording["signal_raw_baseline"] = (
            ("time", "channel"),
            np.column_stack([parsed.baseline[index] for index in signal_indices]),
        )
    if parsed.digital:
        recording["digital_state"] = (
            ("time", "digital_input"),
            np.column_stack(parsed.digital),
        )
        recording = recording.assign_coords(
            digital_input=[
                f"digital_{index}" for index in range(1, len(parsed.digital) + 1)
            ]
        )
    return recording


def _validate_schema(schema: PyPhotometrySchema) -> None:
    if schema.schema_version != "1" or not schema.channels:
        raise ValueError("pyPhotometry schema version 1 requires at least one channel")
    names = [channel.name for channel in schema.channels]
    if any(not name.strip() for name in names) or len(names) != len(set(names)):
        raise ValueError("pyPhotometry channel names must be non-empty and unique")
    references = [channel.reference_analog is not None for channel in schema.channels]
    if len(set(references)) > 1:
        raise ValueError(
            "pyPhotometry references must be declared for every channel or none"
        )
    event_names = [event.name for event in schema.digital_events]
    if any(not name.strip() for name in event_names) or len(event_names) != len(
        set(event_names)
    ):
        raise ValueError(
            "pyPhotometry digital event names must be non-empty and unique"
        )


def _validate_indices(
    schema: PyPhotometrySchema, n_analog: int, n_digital: int
) -> None:
    analog_indices = [
        index
        for channel in schema.channels
        for index in (channel.signal_analog, channel.reference_analog)
        if index is not None
    ]
    if any(index < 1 or index > n_analog for index in analog_indices):
        raise ValueError(f"pyPhotometry analog mappings must be within 1..{n_analog}")
    digital_indices = [event.digital_input for event in schema.digital_events]
    if any(index < 1 or index > n_digital for index in digital_indices):
        raise ValueError(f"pyPhotometry digital mappings must be within 1..{n_digital}")


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = tuple(int(part) for part in re.findall(r"\d+", value))
    return numbers or (0,)
