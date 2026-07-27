"""Shared guarantees for native acquisition-system adapters."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, TypeAlias

import numpy as np

from fiberphotometry.model import validate_recording
from fiberphotometry.pipeline import RecordingInput

AcquisitionFormat: TypeAlias = Literal[
    "doric",
    "neurophotometrics",
    "pyphotometry",
    "tabular",
    "tdt",
    "unknown",
]
FieldRole: TypeAlias = Literal["signal", "time", "digital", "metadata", "unknown"]


@dataclass(frozen=True)
class AcquisitionField:
    """One discoverable field in an acquisition source."""

    key: str
    sample_count: int
    dtype: str
    role: FieldRole = "unknown"
    units: str | None = None


@dataclass(frozen=True)
class AcquisitionInspection:
    """Dependency-light inventory returned before scientific channel mapping."""

    source_format: AcquisitionFormat
    source_name: str
    source_sha256: str
    fields: tuple[AcquisitionField, ...]
    metadata: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def detect_acquisition_format(path: str | Path) -> AcquisitionFormat:
    """Conservatively detect native formats without guessing channel identity."""
    source = Path(path)
    if source.is_dir():
        names = {item.suffix.lower() for item in source.iterdir() if item.is_file()}
        return "tdt" if names & {".tev", ".tsq", ".tnt", ".tbk"} else "unknown"
    suffix = source.suffix.lower()
    if suffix == ".doric":
        return "doric"
    if suffix == ".ppd":
        return "pyphotometry"
    if suffix in {".pqt", ".parquet"}:
        return (
            "neurophotometrics"
            if "neurophotometrics" in source.name.lower()
            or "fpdata" in source.name.lower()
            else "unknown"
        )
    if suffix not in {".csv", ".tsv", ".txt"}:
        return "unknown"
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            first = stream.readline()
        delimiter = "\t" if suffix == ".tsv" else csv.Sniffer().sniff(first).delimiter
        headings = {
            heading.strip()
            for heading in next(csv.reader([first], delimiter=delimiter))
        }
    except (OSError, csv.Error, StopIteration):
        return "unknown"
    timestamp = bool(headings & {"Timestamp", "SystemTimestamp"})
    led_state = bool(headings & {"LedState", "Flags"})
    roi = any(heading.startswith("Region") for heading in headings)
    return "neurophotometrics" if timestamp and led_state and roi else "tabular"


def validate_acquisition_input(value: RecordingInput) -> RecordingInput:
    """Validate guarantees every native reader must satisfy."""
    validate_recording(value.recording)
    event_times = np.asarray(value.event_times, dtype=float)
    if event_times.ndim != 1 or not np.all(np.isfinite(event_times)):
        raise ValueError(
            "acquisition event times must be a finite one-dimensional sequence"
        )
    if len(value.event_times) != len(value.event_ids):
        raise ValueError("acquisition event times and identifiers must align")
    identifiers = tuple(str(identifier) for identifier in value.event_ids)
    if any(not identifier.strip() for identifier in identifiers):
        raise ValueError("acquisition event identifiers must be non-empty")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("acquisition event identifiers must be unique")
    for name, column in value.columns.items():
        if len(column) != len(event_times):
            raise ValueError(f"acquisition event column {name!r} does not align")
    required_attrs = {"source_format", "source_name", "source_sha256"}
    missing = required_attrs - value.recording.attrs.keys()
    if missing:
        raise ValueError(f"native acquisition provenance is missing: {sorted(missing)}")
    return value


def file_sha256(path: str | Path) -> str:
    """Hash complete file content in bounded chunks."""
    digest = sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
