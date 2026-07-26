"""Versioned project configuration binding tabular sources to an analysis."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from fiberphotometry.config import EventAnalysisConfig
from fiberphotometry.io.tabular import (
    TabularChannel,
    TabularEventColumn,
    TabularEventSchema,
    TabularInputInspection,
    TabularRecordingSchema,
    inspect_loaded_tabular_input,
    load_tabular_input,
)
from fiberphotometry.pipeline import RecordingInput
from fiberphotometry.workflow import EventAnalysis, EventSession


@dataclass(frozen=True)
class TabularSessionSource:
    subject: str
    session: str
    recording: Path
    events: Path
    session_start_time: datetime | None = None


@dataclass(frozen=True)
class NWBExportConfig:
    """Metadata required to create valid per-session NWB files."""

    session_description: str
    identifier_prefix: str = "fiberphotometry"


@dataclass(frozen=True)
class LoadedTabularProject:
    sessions: tuple[EventSession, ...]
    inspections: tuple[TabularInputInspection, ...]
    inputs: tuple[RecordingInput, ...]


@dataclass(frozen=True)
class TabularProjectConfig:
    """Complete, fingerprinted input and analysis contract for the CLI."""

    source_path: Path
    source_sha256: str
    output_directory: Path
    sources: tuple[TabularSessionSource, ...]
    recording_schema: TabularRecordingSchema
    event_schema: TabularEventSchema
    analysis: EventAnalysisConfig
    nwb: NWBExportConfig | None = None
    schema_version: str = "1"

    @classmethod
    def from_toml(cls, path: str | Path) -> TabularProjectConfig:
        """Load a project file and resolve data paths relative to that file."""
        source = Path(path).resolve()
        if not source.is_file():
            raise ValueError(f"project configuration does not exist: {source}")
        raw = source.read_bytes()
        payload = tomllib.loads(raw.decode("utf-8"))
        _reject_unknown(
            payload,
            {
                "schema_version",
                "output_directory",
                "sessions",
                "recording",
                "events",
                "analysis",
                "nwb",
            },
            "project root",
        )
        if payload.get("schema_version") != "1":
            raise ValueError("unsupported tabular project schema_version")
        base = source.parent
        sources = _session_sources(payload.get("sessions"), base)
        recording_schema = _recording_schema(_table(payload, "recording"))
        event_schema = _event_schema(_table(payload, "events"))
        analysis = EventAnalysisConfig.from_mapping(_table(payload, "analysis"))
        nwb = _nwb_config(payload.get("nwb"), sources)
        output_raw = payload.get("output_directory", "artifacts")
        if not isinstance(output_raw, str) or not output_raw.strip():
            raise ValueError("output_directory must be a non-empty path string")
        return cls(
            source_path=source,
            source_sha256=hashlib.sha256(raw).hexdigest(),
            output_directory=(base / output_raw).resolve(),
            sources=sources,
            recording_schema=recording_schema,
            event_schema=event_schema,
            analysis=analysis,
            nwb=nwb,
        )

    @property
    def fingerprint(self) -> str:
        return self.source_sha256

    def load(self) -> LoadedTabularProject:
        """Load every source and retain its preflight diagnostics."""
        sessions = []
        inspections = []
        inputs = []
        factor = self.analysis.factor_name
        for source in self.sources:
            item = load_tabular_input(
                source.recording,
                self.recording_schema,
                source.events,
                self.event_schema,
                subject=source.subject,
                session=source.session,
            )
            if factor not in item.columns:
                raise ValueError(
                    f"event mapping does not provide analysis factor {factor!r}"
                )
            conditions = tuple(str(value) for value in item.columns[factor])
            sessions.append(
                EventSession.from_arrays(
                    item.recording,
                    item.event_times,
                    conditions,
                    event_ids=item.event_ids,
                )
            )
            inspections.append(inspect_loaded_tabular_input(item))
            inputs.append(item)
        return LoadedTabularProject(tuple(sessions), tuple(inspections), tuple(inputs))

    def build_analysis(self, sessions: tuple[EventSession, ...]) -> EventAnalysis:
        """Build an analysis carrying the full project-file fingerprint."""
        return replace(
            self.analysis.build(sessions),
            configuration_fingerprint=self.fingerprint,
        )

    def normalized_json(self) -> str:
        """Describe resolved project choices without serializing private paths."""
        payload = {
            "schema_version": self.schema_version,
            "project_sha256": self.fingerprint,
            "output_directory": self.output_directory.name,
            "sessions": [
                {
                    "subject": source.subject,
                    "session": source.session,
                    "recording": source.recording.name,
                    "events": source.events.name,
                    "session_start_time": (
                        source.session_start_time.isoformat()
                        if source.session_start_time is not None
                        else None
                    ),
                }
                for source in self.sources
            ],
            "recording": asdict(self.recording_schema),
            "events": asdict(self.event_schema),
            "analysis": json.loads(self.analysis.to_json()),
            "nwb": asdict(self.nwb) if self.nwb is not None else None,
        }
        return json.dumps(payload, indent=2, sort_keys=True)


def _session_sources(value: object, base: Path) -> tuple[TabularSessionSource, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("sessions must be a non-empty TOML array of tables")
    sources = []
    identities = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError("every sessions entry must be a TOML table")
        _reject_unknown(
            item,
            {"subject", "session", "recording", "events", "session_start_time"},
            f"sessions[{index}]",
        )
        subject = _nonempty_string(item, "subject", f"sessions[{index}]")
        session = _nonempty_string(item, "session", f"sessions[{index}]")
        identity = (subject, session)
        if identity in identities:
            raise ValueError("subject/session pairs must be unique")
        identities.add(identity)
        start_time = item.get("session_start_time")
        if start_time is not None and not isinstance(start_time, datetime):
            raise ValueError(
                f"sessions[{index}].session_start_time must be a TOML datetime"
            )
        sources.append(
            TabularSessionSource(
                subject,
                session,
                (
                    base / _nonempty_string(item, "recording", f"sessions[{index}]")
                ).resolve(),
                (
                    base / _nonempty_string(item, "events", f"sessions[{index}]")
                ).resolve(),
                start_time,
            )
        )
    return tuple(sources)


def _nwb_config(
    value: object, sources: tuple[TabularSessionSource, ...]
) -> NWBExportConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("nwb must be a TOML table")
    _reject_unknown(value, {"session_description", "identifier_prefix"}, "nwb")
    for index, source in enumerate(sources):
        start = source.session_start_time
        if start is None:
            raise ValueError(
                f"sessions[{index}].session_start_time is required for NWB export"
            )
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("NWB session_start_time must include a timezone offset")
    identifier_prefix = value.get("identifier_prefix", "fiberphotometry")
    if not isinstance(identifier_prefix, str) or not identifier_prefix.strip():
        raise ValueError("nwb.identifier_prefix must be a non-empty string")
    return NWBExportConfig(
        session_description=_nonempty_string(value, "session_description", "nwb"),
        identifier_prefix=identifier_prefix,
    )


def _recording_schema(payload: dict[str, Any]) -> TabularRecordingSchema:
    _reject_unknown(
        payload, {"time_column", "time_unit", "delimiter", "channels"}, "recording"
    )
    channels_raw = payload.get("channels")
    if not isinstance(channels_raw, list) or not channels_raw:
        raise ValueError("recording.channels must be a non-empty array of tables")
    channels = []
    for index, item in enumerate(channels_raw):
        if not isinstance(item, dict):
            raise ValueError("every recording.channels entry must be a TOML table")
        _reject_unknown(
            item,
            {"name", "signal_column", "reference_column"},
            f"recording.channels[{index}]",
        )
        reference = item.get("reference_column")
        if reference is not None and not isinstance(reference, str):
            raise ValueError("reference_column must be a string when supplied")
        channels.append(
            TabularChannel(
                _nonempty_string(item, "name", f"recording.channels[{index}]"),
                _nonempty_string(item, "signal_column", f"recording.channels[{index}]"),
                reference,
            )
        )
    return TabularRecordingSchema(
        time_column=_nonempty_string(payload, "time_column", "recording"),
        channels=tuple(channels),
        time_unit=str(payload.get("time_unit", "seconds")),  # type: ignore[arg-type]
        delimiter=_optional_delimiter(payload.get("delimiter"), "recording"),
    )


def _event_schema(payload: dict[str, Any]) -> TabularEventSchema:
    _reject_unknown(
        payload,
        {"time_column", "event_id_column", "time_unit", "delimiter", "columns"},
        "events",
    )
    columns_raw = payload.get("columns", [])
    if not isinstance(columns_raw, list):
        raise ValueError("events.columns must be an array of tables")
    columns = []
    for index, item in enumerate(columns_raw):
        if not isinstance(item, dict):
            raise ValueError("every events.columns entry must be a TOML table")
        _reject_unknown(item, {"source", "name", "kind"}, f"events.columns[{index}]")
        name = item.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError("event column name must be a string when supplied")
        columns.append(
            TabularEventColumn(
                source=_nonempty_string(item, "source", f"events.columns[{index}]"),
                name=name,
                kind=str(item.get("kind", "string")),  # type: ignore[arg-type]
            )
        )
    return TabularEventSchema(
        time_column=_nonempty_string(payload, "time_column", "events"),
        event_id_column=_nonempty_string(payload, "event_id_column", "events"),
        columns=tuple(columns),
        time_unit=str(payload.get("time_unit", "seconds")),  # type: ignore[arg-type]
        delimiter=_optional_delimiter(payload.get("delimiter"), "events"),
    )


def _table(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a TOML table")
    return value


def _nonempty_string(payload: dict[str, Any], key: str, section: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{section}.{key} must be a non-empty string")
    return value


def _optional_delimiter(value: object, section: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 1:
        raise ValueError(f"{section}.delimiter must be exactly one character")
    return value


def _reject_unknown(payload: dict[str, Any], allowed: set[str], section: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"unknown {section} configuration keys: {unknown}")
