"""Explicit adapter from official TDT Python SDK structures."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import numpy as np

from fiberphotometry.model import make_recording
from fiberphotometry.pipeline import RecordingInput


@dataclass(frozen=True)
class TDTStreamChannel:
    """Map TDT stream stores and one-indexed SDK channels to one location."""

    name: str
    signal_store: str
    signal_channel: int = 1
    reference_store: str | None = None
    reference_channel: int | None = None


@dataclass(frozen=True)
class TDTEpocValue:
    """Assign scientific meaning to one numeric TDT epoc code."""

    value: float
    label: str


@dataclass(frozen=True)
class TDTEpocEvents:
    """Map one TDT epoc store to the categorical analysis factor."""

    store: str
    factor_name: str
    values: tuple[TDTEpocValue, ...]


@dataclass(frozen=True)
class TDTBlockSchema:
    """Versioned scientific mapping for a TDT block."""

    channels: tuple[TDTStreamChannel, ...]
    events: TDTEpocEvents
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def load_tdt_input(
    block_path: str | Path,
    schema: TDTBlockSchema,
    *,
    subject: str,
    session: str,
    reader: Callable[..., Any] | None = None,
) -> RecordingInput:
    """Read one TDT block into the canonical recording and event boundary."""
    _validate_schema(schema)
    if not subject.strip() or not session.strip():
        raise ValueError("subject and session identifiers must be non-empty")
    block = Path(block_path)
    if not block.is_dir():
        raise ValueError(f"TDT block directory does not exist: {block}")
    selected_reader = reader or _official_reader()
    stores = sorted(
        {
            store
            for channel in schema.channels
            for store in (channel.signal_store, channel.reference_store)
            if store is not None
        }
        | {schema.events.store}
    )
    data = selected_reader(
        str(block), evtype=["streams", "epocs"], store=stores, verbose=0
    )
    stream_container = _field(data, "streams", "TDT block")
    signals: list[np.ndarray] = []
    references: list[np.ndarray] = []
    sampling_rates: list[float] = []
    start_times: list[float] = []
    sample_counts: list[int] = []
    structure_stores = []
    for channel in schema.channels:
        signal_stream = _field(
            stream_container,
            _sdk_field_name(channel.signal_store),
            "TDT stream stores",
        )
        signal, signal_fs, signal_start = _stream_channel(
            signal_stream, channel.signal_channel, store=channel.signal_store
        )
        signals.append(signal)
        sampling_rates.append(signal_fs)
        start_times.append(signal_start)
        sample_counts.append(len(signal))
        structure_stores.append(
            _store_structure(
                channel.signal_store,
                channel.signal_channel,
                signal_fs,
                signal_start,
                len(signal),
            )
        )
        if channel.reference_store is not None:
            reference_channel = channel.reference_channel
            if reference_channel is None:
                raise ValueError("TDT reference channel is missing")
            reference_stream = _field(
                stream_container,
                _sdk_field_name(channel.reference_store),
                "TDT stream stores",
            )
            reference, reference_fs, reference_start = _stream_channel(
                reference_stream,
                reference_channel,
                store=channel.reference_store,
            )
            references.append(reference)
            sampling_rates.append(reference_fs)
            start_times.append(reference_start)
            sample_counts.append(len(reference))
            structure_stores.append(
                _store_structure(
                    channel.reference_store,
                    reference_channel,
                    reference_fs,
                    reference_start,
                    len(reference),
                )
            )
    _require_aligned_streams(sampling_rates, start_times, sample_counts)
    sampling_rate = sampling_rates[0]
    start_time = start_times[0]
    sample_count = sample_counts[0]
    time = start_time + np.arange(sample_count, dtype=float) / sampling_rate

    epoc_container = _field(data, "epocs", "TDT block")
    epoc = _field(
        epoc_container, _sdk_field_name(schema.events.store), "TDT epoc stores"
    )
    onsets = _one_dimensional(epoc, "onset", schema.events.store)
    offsets = _one_dimensional(epoc, "offset", schema.events.store)
    values = _one_dimensional(epoc, "data", schema.events.store)
    if not (len(onsets) == len(offsets) == len(values)):
        raise ValueError("TDT epoc onset, offset, and data arrays must align")
    if not len(onsets):
        raise ValueError("TDT epoc store contains no events")
    if not np.all(np.isfinite(onsets)):
        raise ValueError("TDT epoc onset times must be finite")
    if np.any(np.isnan(offsets)) or np.any(np.isneginf(offsets)):
        raise ValueError("TDT epoc offsets cannot contain NaN or negative infinity")
    if np.any(offsets[np.isfinite(offsets)] < onsets[np.isfinite(offsets)]):
        raise ValueError("TDT epoc offsets cannot precede onsets")
    labels = _event_labels(values, schema.events.values)
    structure = {
        "schema": json.loads(schema.to_json()),
        "stores": structure_stores,
        "epoc": {"store": schema.events.store, "count": len(onsets)},
    }
    fingerprint = sha256(
        json.dumps(structure, sort_keys=True, separators=(",", ":")).encode()
    )
    for selected in (*signals, *references, onsets, offsets, values):
        fingerprint.update(np.asarray(selected, dtype="<f8").tobytes(order="C"))
    content_sha256 = fingerprint.hexdigest()
    recording = make_recording(
        time=time,
        signal=np.column_stack(signals),
        reference=np.column_stack(references) if references else None,
        channel_names=[channel.name for channel in schema.channels],
        subject=subject,
        session=session,
        attrs={
            "source_format": "TDT_block",
            "source_name": block.name,
            "source_sha256": content_sha256,
            "source_fingerprint_scope": "declared_stream_channels_and_epoc_content",
            "tdt_schema": schema.to_json(),
            "tdt_sdk_version": _tdt_version(),
            "tdt_stream_start_time_s": start_time,
            "tdt_sampling_rate_hz": sampling_rate,
            "event_source_name": f"{block.name}:{schema.events.store}",
            "event_source_sha256": content_sha256,
        },
    )
    event_ids = tuple(
        f"{session}:{schema.events.store}:{index + 1}" for index in range(len(onsets))
    )
    return RecordingInput(
        recording,
        tuple(float(value) for value in onsets),
        event_ids,
        {
            schema.events.factor_name: labels,
            "tdt_epoc_value": tuple(float(value) for value in values),
            "tdt_epoc_offset": tuple(float(value) for value in offsets),
        },
    )


def _validate_schema(schema: TDTBlockSchema) -> None:
    if schema.schema_version != "1":
        raise ValueError("unsupported TDT block schema version")
    if not schema.channels:
        raise ValueError("TDT schema requires at least one stream channel")
    names = [channel.name for channel in schema.channels]
    if any(not name.strip() for name in names) or len(names) != len(set(names)):
        raise ValueError("TDT channel names must be non-empty and unique")
    for channel in schema.channels:
        if not channel.signal_store.strip() or channel.signal_channel < 1:
            raise ValueError("TDT signal stores and channels must be explicit")
        reference_fields = (
            channel.reference_store is not None,
            channel.reference_channel is not None,
        )
        if len(set(reference_fields)) != 1:
            raise ValueError(
                "TDT reference store and channel must be declared together"
            )
        if channel.reference_store is not None:
            reference_channel = channel.reference_channel
            if (
                reference_channel is None
                or not channel.reference_store.strip()
                or reference_channel < 1
            ):
                raise ValueError("TDT reference stores and channels must be explicit")
    reference_presence = {
        channel.reference_store is not None for channel in schema.channels
    }
    if len(reference_presence) != 1:
        raise ValueError("TDT references must be mapped for every channel or none")
    if not schema.events.store.strip() or not schema.events.factor_name.strip():
        raise ValueError("TDT event store and factor name must be non-empty")
    if schema.events.factor_name in {"tdt_epoc_value", "tdt_epoc_offset"}:
        raise ValueError("TDT event factor name collides with retained provenance")
    if not schema.events.values:
        raise ValueError("TDT epoc values require explicit categorical labels")
    values = [item.value for item in schema.events.values]
    labels = [item.label for item in schema.events.values]
    if len(values) != len(set(values)) or len(labels) != len(set(labels)):
        raise ValueError("TDT epoc values and labels must be unique")
    if any(not label.strip() for label in labels):
        raise ValueError("TDT epoc labels must be non-empty")


def _sdk_field_name(store: str) -> str:
    """Mirror the official SDK's conversion from StoreID to Python field name."""
    candidate = store
    if not (candidate[0].isalnum() or candidate[0] == "_"):
        candidate = f"x{candidate}"
    return re.sub(r"\W|^(?=\d)", "_", candidate)


def _stream_channel(
    stream: Any, channel: int, *, store: str
) -> tuple[np.ndarray, float, float]:
    values = np.asarray(_field(stream, "data", f"TDT stream {store!r}"), dtype=float)
    if values.ndim == 1:
        if channel != 1:
            raise ValueError(
                f"TDT stream {store!r} is one-dimensional; channel must be 1"
            )
        selected = values
    elif values.ndim == 2:
        if channel > values.shape[0]:
            raise ValueError(
                f"TDT stream {store!r} has {values.shape[0]} channels, not {channel}"
            )
        selected = values[channel - 1]
    else:
        raise ValueError(f"TDT stream {store!r} data must be one- or two-dimensional")
    fs = float(_field(stream, "fs", f"TDT stream {store!r}"))
    start = float(_field(stream, "start_time", f"TDT stream {store!r}"))
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError(f"TDT stream {store!r} sampling rate must be positive")
    if not np.isfinite(start):
        raise ValueError(f"TDT stream {store!r} start_time must be finite")
    if len(selected) < 2:
        raise ValueError(f"TDT stream {store!r} requires at least two samples")
    return np.asarray(selected, dtype=float), fs, start


def _require_aligned_streams(
    sampling_rates: list[float], start_times: list[float], sample_counts: list[int]
) -> None:
    if not all(
        np.isclose(value, sampling_rates[0], rtol=1e-9, atol=0)
        for value in sampling_rates
    ):
        raise ValueError("TDT mapped streams have different sampling rates")
    if not all(
        np.isclose(value, start_times[0], rtol=0, atol=1e-9) for value in start_times
    ):
        raise ValueError("TDT mapped streams have different start times")
    if len(set(sample_counts)) != 1:
        raise ValueError("TDT mapped streams have different sample counts")


def _event_labels(
    values: np.ndarray, declared: tuple[TDTEpocValue, ...]
) -> tuple[str, ...]:
    labels = {item.value: item.label for item in declared}
    unknown = sorted({float(value) for value in values if float(value) not in labels})
    if unknown:
        raise ValueError(f"TDT epoc store contains unmapped values: {unknown}")
    return tuple(labels[float(value)] for value in values)


def _one_dimensional(container: Any, name: str, store: str) -> np.ndarray:
    values = np.asarray(_field(container, name, f"TDT epoc {store!r}"), dtype=float)
    if values.ndim != 1:
        raise ValueError(f"TDT epoc {store!r} {name} must be one-dimensional")
    return values


def _field(container: Any, name: str, context: str) -> Any:
    if isinstance(container, Mapping) and name in container:
        return container[name]
    try:
        return getattr(container, name)
    except AttributeError as error:
        raise ValueError(f"{context} is missing {name!r}") from error


def _store_structure(
    store: str, channel: int, fs: float, start: float, samples: int
) -> dict[str, str | int | float]:
    return {
        "store": store,
        "channel": channel,
        "sampling_rate_hz": fs,
        "start_time_s": start,
        "samples": samples,
    }


def _official_reader() -> Callable[..., Any]:
    try:
        from tdt import read_block  # type: ignore[import-untyped]
    except ImportError as error:
        raise ValueError(
            "TDT import requires the optional 'tdt' dependencies"
        ) from error
    return cast(Callable[..., Any], read_block)


def _tdt_version() -> str:
    try:
        return version("tdt")
    except PackageNotFoundError:
        return "reader-injected"
