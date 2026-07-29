"""Versioned project configuration binding tabular sources to an analysis."""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias, cast

from fipha.config import EventAnalysisConfig
from fipha.io.tabular import (
    TabularChannel,
    TabularEventColumn,
    TabularEventSchema,
    TabularInputInspection,
    TabularRecordingSchema,
    inspect_loaded_tabular_input,
    load_tabular_input,
)
from fipha.io.tdt import (
    TDTBlockSchema,
    TDTEpocEvents,
    TDTEpocValue,
    TDTStreamChannel,
    load_tdt_input,
)
from fipha.multiverse import (
    ChoiceRef,
    CompatibilityRule,
    DecisionAlternative,
    DecisionNode,
    MultiverseSpec,
    PreprocessingOutcomeSpec,
)
from fipha.pipeline import (
    BaselineDFFOperation,
    LowpassFilterOperation,
    PipelineSpec,
    RecordingInput,
    ReferenceDFFOperation,
    ResampleOperation,
)
from fipha.workflow import EventAnalysis, EventSession


@dataclass(frozen=True)
class TabularSessionSource:
    subject: str
    session: str
    recording: Path
    events: Path
    session_start_time: datetime | None = None


@dataclass(frozen=True)
class TDTSessionSource:
    subject: str
    session: str
    block: Path
    session_start_time: datetime | None = None


SessionSource: TypeAlias = TabularSessionSource | TDTSessionSource


@dataclass(frozen=True)
class NWBExportConfig:
    """Metadata required to create valid per-session NWB files."""

    session_description: str
    identifier_prefix: str = "fipha"


@dataclass(frozen=True)
class MultiversePreprocessingAlternative:
    """One named, justified preprocessing recipe with explicit output units."""

    name: str
    rationale: str
    kind: str
    method: str
    normalization: str = "divide"
    lowpass_hz: float | None = None
    rolling_window_s: float = 60.0
    min_tau_s: float = 5.0
    asls_smoothness: float = 1e8
    asls_asymmetry: float = 0.01
    max_iterations: int = 20
    asls_reference_rate_hz: float = 20.0
    rolling_gap_factor: float = 1.5
    resample_rate_hz: float | str | None = None
    resample_max_gap_factor: float | None = None

    @property
    def output_variable(self) -> str:
        return (
            "baseline_subtracted"
            if self.kind == "signal_only" and self.normalization == "subtract"
            else "dff"
        )

    @property
    def units(self) -> str:
        return (
            "acquired fluorescence"
            if self.output_variable == "baseline_subtracted"
            else "ΔF/F"
        )

    def operations(self) -> tuple[Any, ...]:
        operations: list[Any] = []
        if self.resample_rate_hz is not None:
            operations.append(
                ResampleOperation(
                    rate_hz=cast(Any, self.resample_rate_hz),
                    max_gap_factor=self.resample_max_gap_factor,
                )
            )
        if self.lowpass_hz is not None:
            variables = (
                ("signal", "reference") if self.kind == "reference" else ("signal",)
            )
            operations.append(
                LowpassFilterOperation(self.lowpass_hz, variables=variables)
            )
        if self.kind == "reference":
            operations.append(ReferenceDFFOperation(method=cast(Any, self.method)))
        else:
            operations.append(
                BaselineDFFOperation(
                    method=cast(Any, self.method),
                    normalization=cast(Any, self.normalization),
                    min_tau_s=self.min_tau_s,
                    asls_smoothness=self.asls_smoothness,
                    asls_asymmetry=self.asls_asymmetry,
                    max_iterations=self.max_iterations,
                    asls_reference_rate_hz=self.asls_reference_rate_hz,
                    rolling_window_s=self.rolling_window_s,
                    rolling_gap_factor=self.rolling_gap_factor,
                )
            )
        return tuple(operations)


@dataclass(frozen=True)
class MultiverseWindowAlternative:
    """One named, justified response-window definition."""

    name: str
    rationale: str
    response: tuple[float, float]


@dataclass(frozen=True)
class MultiverseEffectThreshold:
    """A practical-effect threshold scoped to one measurement unit lane."""

    units: str
    smallest_effect: float
    direction: str = "either"


@dataclass(frozen=True)
class ProjectMultiverseConfig:
    """Project-file decisions that materialize a typed robustness multiverse."""

    preprocessing: tuple[MultiversePreprocessingAlternative, ...]
    response_windows: tuple[MultiverseWindowAlternative, ...]
    reference_preprocessing: str | None
    reference_response_window: str | None
    intent: str
    smallest_effect: float | None = None
    direction: str = "either"
    leave_one_animal_out: bool = False
    effect_thresholds: tuple[MultiverseEffectThreshold, ...] = ()
    compatibility_rules: tuple[CompatibilityRule, ...] = ()
    schema_version: str = "1"

    def build(self, base: PipelineSpec) -> MultiverseSpec:
        """Bind declared alternatives to the already-validated primary pipeline."""
        nodes = []
        references = []
        if self.preprocessing:
            nodes.append(
                DecisionNode(
                    "preprocessing",
                    "preprocessing_outcome",
                    tuple(
                        DecisionAlternative(
                            item.name,
                            item.rationale,
                            PreprocessingOutcomeSpec(
                                item.operations(),
                                replace(
                                    base.event_summary,
                                    variable=item.output_variable,
                                ),
                            ),
                        )
                        for item in self.preprocessing
                    ),
                )
            )
            references.append(
                ChoiceRef("preprocessing", cast(str, self.reference_preprocessing))
            )
        if self.response_windows:
            nodes.append(
                DecisionNode(
                    "response_window",
                    "event_summary",
                    tuple(
                        DecisionAlternative(
                            item.name,
                            item.rationale,
                            replace(base.event_summary, response=item.response),
                        )
                        for item in self.response_windows
                    ),
                )
            )
            references.append(
                ChoiceRef("response_window", cast(str, self.reference_response_window))
            )
        # Event-window choices update the base summary first; the coupled
        # preprocessing choice then fixes the output variable and units last.
        ordered_nodes = tuple(
            sorted(nodes, key=lambda node: node.target == "preprocessing_outcome")
        )
        return MultiverseSpec(
            base,
            ordered_nodes,
            self.compatibility_rules,
            tuple(references),
            cast(Any, self.intent),
            smallest_effect=self.smallest_effect,
            direction=cast(Any, self.direction),
            leave_one_unit_out=self.leave_one_animal_out,
        )

    def preprocessing_unit_groups(self) -> dict[str, tuple[str, ...]]:
        """Return alternative labels partitioned by scientifically compatible units."""
        groups: dict[str, list[str]] = {}
        for alternative in self.preprocessing:
            groups.setdefault(alternative.units, []).append(alternative.name)
        return {units: tuple(names) for units, names in groups.items()}

    def effect_threshold(self, units: str) -> MultiverseEffectThreshold | None:
        """Return the declared practical-effect policy for one unit lane."""
        return next(
            (item for item in self.effect_thresholds if item.units == units), None
        )


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
    metadata: dict[str, Any] = field(default_factory=dict)
    nwb: NWBExportConfig | None = None
    multiverse: ProjectMultiverseConfig | None = None
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
                "input_format",
                "output_directory",
                "sessions",
                "recording",
                "events",
                "analysis",
                "metadata",
                "nwb",
                "multiverse",
            },
            "project root",
        )
        if payload.get("schema_version") != "1":
            raise ValueError("unsupported tabular project schema_version")
        if payload.get("input_format", "tabular") != "tabular":
            raise ValueError("tabular project input_format must be 'tabular'")
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
            metadata=_metadata(payload.get("metadata")),
            nwb=nwb,
            multiverse=_multiverse_config(payload.get("multiverse"), analysis),
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
            inputs.append(
                _project_recording_input(item, source.subject, source.session)
            )
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
            "metadata": self.metadata,
            "nwb": asdict(self.nwb) if self.nwb is not None else None,
            "multiverse": asdict(self.multiverse)
            if self.multiverse is not None
            else None,
        }
        return json.dumps(payload, indent=2, sort_keys=True)


@dataclass(frozen=True)
class TDTProjectConfig:
    """Complete project contract for explicitly mapped TDT blocks."""

    source_path: Path
    source_sha256: str
    output_directory: Path
    sources: tuple[TDTSessionSource, ...]
    tdt_schema: TDTBlockSchema
    analysis: EventAnalysisConfig
    metadata: dict[str, Any] = field(default_factory=dict)
    nwb: NWBExportConfig | None = None
    multiverse: ProjectMultiverseConfig | None = None
    schema_version: str = "1"

    @classmethod
    def from_toml(cls, path: str | Path) -> TDTProjectConfig:
        source = Path(path).resolve()
        if not source.is_file():
            raise ValueError(f"project configuration does not exist: {source}")
        raw = source.read_bytes()
        payload = tomllib.loads(raw.decode("utf-8"))
        _reject_unknown(
            payload,
            {
                "schema_version",
                "input_format",
                "output_directory",
                "sessions",
                "tdt",
                "analysis",
                "metadata",
                "nwb",
                "multiverse",
            },
            "project root",
        )
        if payload.get("schema_version") != "1":
            raise ValueError("unsupported TDT project schema_version")
        if payload.get("input_format") != "tdt":
            raise ValueError("TDT project input_format must be 'tdt'")
        base = source.parent
        sources = _tdt_session_sources(payload.get("sessions"), base)
        analysis = EventAnalysisConfig.from_mapping(_table(payload, "analysis"))
        output_raw = payload.get("output_directory", "artifacts")
        if not isinstance(output_raw, str) or not output_raw.strip():
            raise ValueError("output_directory must be a non-empty path string")
        return cls(
            source_path=source,
            source_sha256=hashlib.sha256(raw).hexdigest(),
            output_directory=(base / output_raw).resolve(),
            sources=sources,
            tdt_schema=_tdt_schema(_table(payload, "tdt")),
            analysis=analysis,
            metadata=_metadata(payload.get("metadata")),
            nwb=_nwb_config(payload.get("nwb"), sources),
            multiverse=_multiverse_config(payload.get("multiverse"), analysis),
        )

    @property
    def fingerprint(self) -> str:
        return self.source_sha256

    def load(self, *, reader: Any | None = None) -> LoadedTabularProject:
        sessions = []
        inspections = []
        inputs = []
        factor = self.analysis.factor_name
        for source in self.sources:
            item = load_tdt_input(
                source.block,
                self.tdt_schema,
                subject=source.subject,
                session=source.session,
                reader=reader,
            )
            if factor not in item.columns:
                raise ValueError(
                    f"TDT event mapping does not provide analysis factor {factor!r}"
                )
            sessions.append(
                EventSession.from_arrays(
                    item.recording,
                    item.event_times,
                    tuple(str(value) for value in item.columns[factor]),
                    event_ids=item.event_ids,
                )
            )
            inspections.append(inspect_loaded_tabular_input(item))
            inputs.append(
                _project_recording_input(item, source.subject, source.session)
            )
        return LoadedTabularProject(tuple(sessions), tuple(inspections), tuple(inputs))

    def build_analysis(self, sessions: tuple[EventSession, ...]) -> EventAnalysis:
        return replace(
            self.analysis.build(sessions),
            configuration_fingerprint=self.fingerprint,
        )

    def normalized_json(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "input_format": "tdt",
            "project_sha256": self.fingerprint,
            "output_directory": self.output_directory.name,
            "sessions": [
                {
                    "subject": source.subject,
                    "session": source.session,
                    "block": source.block.name,
                    "session_start_time": (
                        source.session_start_time.isoformat()
                        if source.session_start_time is not None
                        else None
                    ),
                }
                for source in self.sources
            ],
            "tdt": asdict(self.tdt_schema),
            "analysis": json.loads(self.analysis.to_json()),
            "metadata": self.metadata,
            "nwb": asdict(self.nwb) if self.nwb is not None else None,
            "multiverse": asdict(self.multiverse)
            if self.multiverse is not None
            else None,
        }
        return json.dumps(payload, indent=2, sort_keys=True)


ProjectConfig: TypeAlias = TabularProjectConfig | TDTProjectConfig


def load_project_config(path: str | Path) -> ProjectConfig:
    """Dispatch a project file while retaining tabular v0.1 compatibility."""
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"project configuration does not exist: {source.resolve()}")
    payload = tomllib.loads(source.read_text(encoding="utf-8"))
    if payload.get("input_format", "tabular") == "tdt":
        return TDTProjectConfig.from_toml(source)
    return TabularProjectConfig.from_toml(source)


def _project_recording_input(
    item: RecordingInput, subject: str, session: str
) -> RecordingInput:
    """Attach declared design units while preserving arbitrary imported event fields."""
    count = len(item.event_times)
    return RecordingInput(
        item.recording,
        item.event_times,
        item.event_ids,
        {
            **item.columns,
            "animal": (subject,) * count,
            "session": (session,) * count,
        },
    )


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


def _tdt_session_sources(value: object, base: Path) -> tuple[TDTSessionSource, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("sessions must be a non-empty TOML array of tables")
    sources = []
    identities = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError("every sessions entry must be a TOML table")
        _reject_unknown(
            item,
            {"subject", "session", "block", "session_start_time"},
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
            TDTSessionSource(
                subject,
                session,
                (
                    base / _nonempty_string(item, "block", f"sessions[{index}]")
                ).resolve(),
                start_time,
            )
        )
    return tuple(sources)


def _multiverse_config(
    value: object, analysis: EventAnalysisConfig
) -> ProjectMultiverseConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("multiverse must be a TOML table")
    _reject_unknown(
        value,
        {
            "schema_version",
            "intent",
            "direction",
            "smallest_effect",
            "effect_thresholds",
            "leave_one_animal_out",
            "reference_preprocessing",
            "reference_response_window",
            "preprocessing",
            "response_windows",
            "compatibility_rules",
        },
        "multiverse",
    )
    if value.get("schema_version") != "1":
        raise ValueError("unsupported multiverse schema_version")
    preprocessing = _multiverse_preprocessing(value.get("preprocessing", []), analysis)
    windows = _multiverse_windows(value.get("response_windows", []))
    if not preprocessing and not windows:
        raise ValueError("multiverse requires preprocessing or response_windows")
    reference_preprocessing = _multiverse_reference(
        value, "reference_preprocessing", preprocessing
    )
    reference_window = _multiverse_reference(
        value, "reference_response_window", windows
    )
    compatibility_rules = _multiverse_compatibility_rules(
        value.get("compatibility_rules", []), preprocessing, windows
    )
    intent = value.get("intent", analysis.intent)
    if intent not in {"confirmatory", "exploratory", "descriptive"}:
        raise ValueError("multiverse.intent is invalid")
    direction = value.get("direction", "either")
    if direction not in {"positive", "negative", "either"}:
        raise ValueError("multiverse.direction is invalid")
    smallest_raw = value.get("smallest_effect")
    smallest_effect = None
    if smallest_raw is not None:
        if (
            not isinstance(smallest_raw, int | float)
            or isinstance(smallest_raw, bool)
            or not math.isfinite(float(smallest_raw))
            or float(smallest_raw) < 0
        ):
            raise ValueError(
                "multiverse.smallest_effect must be finite and nonnegative"
            )
        smallest_effect = float(smallest_raw)
    if smallest_effect is not None and len({item.units for item in preprocessing}) > 1:
        raise ValueError(
            "multiverse.smallest_effect cannot span preprocessing output units"
        )
    effect_thresholds = _multiverse_effect_thresholds(
        value.get("effect_thresholds", []),
        preprocessing,
        analysis,
        str(direction),
    )
    if smallest_effect is not None and effect_thresholds:
        raise ValueError(
            "multiverse.smallest_effect and effect_thresholds are mutually exclusive"
        )
    leave_one_out = value.get("leave_one_animal_out", False)
    if not isinstance(leave_one_out, bool):
        raise ValueError("multiverse.leave_one_animal_out must be boolean")
    return ProjectMultiverseConfig(
        preprocessing=preprocessing,
        response_windows=windows,
        reference_preprocessing=reference_preprocessing,
        reference_response_window=reference_window,
        intent=str(intent),
        smallest_effect=smallest_effect,
        direction=str(direction),
        leave_one_animal_out=leave_one_out,
        effect_thresholds=effect_thresholds,
        compatibility_rules=compatibility_rules,
    )


def _multiverse_compatibility_rules(
    value: object,
    preprocessing: tuple[MultiversePreprocessingAlternative, ...],
    windows: tuple[MultiverseWindowAlternative, ...],
) -> tuple[CompatibilityRule, ...]:
    if not isinstance(value, list):
        raise ValueError("multiverse.compatibility_rules must be an array of tables")
    known = {
        "preprocessing": {item.name for item in preprocessing},
        "response_window": {item.name for item in windows},
    }
    output = []
    for index, item in enumerate(value):
        section = f"multiverse.compatibility_rules[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{section} must be a TOML table")
        _reject_unknown(item, {"reason", "when"}, section)
        when = item.get("when")
        if not isinstance(when, list) or not when:
            raise ValueError(f"{section}.when must be a non-empty array of tables")
        choices = []
        for choice_index, choice in enumerate(when):
            choice_section = f"{section}.when[{choice_index}]"
            if not isinstance(choice, dict):
                raise ValueError(f"{choice_section} must be a TOML inline table")
            _reject_unknown(choice, {"node", "alternative"}, choice_section)
            node = _nonempty_string(choice, "node", choice_section)
            alternative = _nonempty_string(choice, "alternative", choice_section)
            if node not in known or alternative not in known[node]:
                raise ValueError(f"{choice_section} names an unknown choice")
            choices.append(ChoiceRef(node, alternative))
        if len(choices) != len(set(choices)):
            raise ValueError(f"{section}.when cannot repeat a choice")
        output.append(
            CompatibilityRule(tuple(choices), _nonempty_string(item, "reason", section))
        )
    return tuple(output)


def _multiverse_effect_thresholds(
    value: object,
    preprocessing: tuple[MultiversePreprocessingAlternative, ...],
    analysis: EventAnalysisConfig,
    default_direction: str,
) -> tuple[MultiverseEffectThreshold, ...]:
    if not isinstance(value, list):
        raise ValueError("multiverse.effect_thresholds must be an array of tables")
    output = []
    for index, item in enumerate(value):
        section = f"multiverse.effect_thresholds[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{section} must be a TOML table")
        _reject_unknown(item, {"units", "smallest_effect", "direction"}, section)
        direction = item.get("direction", default_direction)
        if direction not in {"positive", "negative", "either"}:
            raise ValueError(f"{section}.direction is invalid")
        output.append(
            MultiverseEffectThreshold(
                _nonempty_string(item, "units", section),
                _nonnegative_number(
                    item.get("smallest_effect"), f"{section}.smallest_effect"
                ),
                str(direction),
            )
        )
    units = [item.units for item in output]
    if len(units) != len(set(units)):
        raise ValueError("multiverse.effect_thresholds units must be unique")
    if output:
        declared_units = {item.units for item in preprocessing} or {
            _analysis_output_units(analysis)
        }
        if set(units) != declared_units:
            raise ValueError(
                "multiverse.effect_thresholds must cover every declared unit lane"
            )
    return tuple(output)


def _analysis_output_units(analysis: EventAnalysisConfig) -> str:
    return (
        "acquired fluorescence"
        if analysis.preprocessing_kind == "signal_only"
        and analysis.normalization == "subtract"
        else "ΔF/F"
    )


def _multiverse_preprocessing(
    value: object, analysis: EventAnalysisConfig
) -> tuple[MultiversePreprocessingAlternative, ...]:
    if not isinstance(value, list):
        raise ValueError("multiverse.preprocessing must be an array of tables")
    output = []
    for index, item in enumerate(value):
        section = f"multiverse.preprocessing[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{section} must be a TOML table")
        _reject_unknown(
            item,
            {
                "name",
                "rationale",
                "kind",
                "method",
                "normalization",
                "lowpass_hz",
                "rolling_window_s",
                "min_tau_s",
                "asls_smoothness",
                "asls_asymmetry",
                "max_iterations",
                "asls_reference_rate_hz",
                "rolling_gap_factor",
                "resample_rate_hz",
                "resample_max_gap_factor",
            },
            section,
        )
        kind = item.get("kind", analysis.preprocessing_kind)
        if kind not in {"reference", "signal_only"}:
            raise ValueError(f"{section}.kind is invalid")
        if kind != analysis.preprocessing_kind:
            raise ValueError(
                f"{section}.kind must match primary analysis preprocessing kind"
            )
        method = _nonempty_string(item, "method", section)
        valid_methods = (
            {"irls", "ols"}
            if kind == "reference"
            else {"double_exponential", "asls", "rolling_mean"}
        )
        if method not in valid_methods:
            raise ValueError(f"{section}.method is invalid for {kind} preprocessing")
        normalization = item.get("normalization", analysis.normalization)
        if normalization not in {"divide", "subtract"}:
            raise ValueError(f"{section}.normalization is invalid")
        if kind == "reference" and "normalization" in item:
            raise ValueError(
                f"{section}.normalization is only valid for signal_only recipes"
            )
        _validate_method_parameters(item, section, str(kind), method)
        cutoff_raw = item.get("lowpass_hz")
        cutoff = _optional_positive_number(cutoff_raw, f"{section}.lowpass_hz")
        rolling_window = _positive_number(
            item.get("rolling_window_s", analysis.rolling_window_s),
            f"{section}.rolling_window_s",
        )
        resample_raw = item.get("resample_rate_hz")
        if resample_raw is None:
            resample_rate: float | str | None = None
        elif resample_raw == "median":
            resample_rate = "median"
        else:
            resample_rate = _positive_number(
                resample_raw, f"{section}.resample_rate_hz"
            )
        gap = _optional_positive_number(
            item.get("resample_max_gap_factor"),
            f"{section}.resample_max_gap_factor",
        )
        if gap is not None and gap <= 1:
            raise ValueError(
                f"{section}.resample_max_gap_factor must be greater than one"
            )
        if gap is not None and resample_rate is None:
            raise ValueError(
                f"{section}.resample_max_gap_factor requires resample_rate_hz"
            )
        min_tau = _positive_number(item.get("min_tau_s", 5.0), f"{section}.min_tau_s")
        asls_smoothness = _positive_number(
            item.get("asls_smoothness", 1e8), f"{section}.asls_smoothness"
        )
        asls_asymmetry = _open_unit_interval(
            item.get("asls_asymmetry", 0.01), f"{section}.asls_asymmetry"
        )
        max_iterations = _positive_integer(
            item.get("max_iterations", 20), f"{section}.max_iterations"
        )
        asls_reference_rate = _positive_number(
            item.get("asls_reference_rate_hz", 20.0),
            f"{section}.asls_reference_rate_hz",
        )
        rolling_gap = _positive_number(
            item.get("rolling_gap_factor", 1.5), f"{section}.rolling_gap_factor"
        )
        if rolling_gap <= 1:
            raise ValueError(f"{section}.rolling_gap_factor must be greater than one")
        output.append(
            MultiversePreprocessingAlternative(
                name=_nonempty_string(item, "name", section),
                rationale=_nonempty_string(item, "rationale", section),
                kind=str(kind),
                method=method,
                normalization=str(normalization),
                lowpass_hz=cutoff,
                rolling_window_s=rolling_window,
                min_tau_s=min_tau,
                asls_smoothness=asls_smoothness,
                asls_asymmetry=asls_asymmetry,
                max_iterations=max_iterations,
                asls_reference_rate_hz=asls_reference_rate,
                rolling_gap_factor=rolling_gap,
                resample_rate_hz=resample_rate,
                resample_max_gap_factor=gap,
            )
        )
    _validate_multiverse_alternatives(output, "multiverse.preprocessing")
    return tuple(output)


def _multiverse_windows(value: object) -> tuple[MultiverseWindowAlternative, ...]:
    if not isinstance(value, list):
        raise ValueError("multiverse.response_windows must be an array of tables")
    output = []
    for index, item in enumerate(value):
        section = f"multiverse.response_windows[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{section} must be a TOML table")
        _reject_unknown(item, {"name", "rationale", "response"}, section)
        response = item.get("response")
        if (
            not isinstance(response, list)
            or len(response) != 2
            or any(
                not isinstance(point, int | float) or isinstance(point, bool)
                for point in response
            )
        ):
            raise ValueError(f"{section}.response must contain two numbers")
        parsed = (float(response[0]), float(response[1]))
        if not all(math.isfinite(point) for point in parsed) or parsed[0] >= parsed[1]:
            raise ValueError(f"{section}.response must be finite and increasing")
        output.append(
            MultiverseWindowAlternative(
                _nonempty_string(item, "name", section),
                _nonempty_string(item, "rationale", section),
                parsed,
            )
        )
    _validate_multiverse_alternatives(output, "multiverse.response_windows")
    return tuple(output)


def _validate_multiverse_alternatives(value: list[Any], section: str) -> None:
    if value and len(value) < 2:
        raise ValueError(f"{section} requires at least two alternatives")
    names = [item.name for item in value]
    if len(names) != len(set(names)):
        raise ValueError(f"{section} names must be unique")


def _validate_method_parameters(
    item: dict[str, Any], section: str, kind: str, method: str
) -> None:
    method_parameters = {
        "min_tau_s",
        "asls_smoothness",
        "asls_asymmetry",
        "max_iterations",
        "asls_reference_rate_hz",
        "rolling_window_s",
        "rolling_gap_factor",
    }
    allowed = {
        "double_exponential": {"min_tau_s"},
        "asls": {
            "asls_smoothness",
            "asls_asymmetry",
            "max_iterations",
            "asls_reference_rate_hz",
        },
        "rolling_mean": {"rolling_window_s", "rolling_gap_factor"},
    }.get(method, set())
    invalid = sorted((set(item) & method_parameters) - allowed)
    if invalid:
        family = method if kind == "signal_only" else "reference correction"
        raise ValueError(f"{section} parameters are invalid for {family}: {invalid}")


def _positive_number(value: object, name: str) -> float:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) <= 0
    ):
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


def _nonnegative_number(value: object, name: str) -> float:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise ValueError(f"{name} must be finite and nonnegative")
    return float(value)


def _open_unit_interval(value: object, name: str) -> float:
    parsed = _positive_number(value, name)
    if parsed >= 1:
        raise ValueError(f"{name} must lie between zero and one")
    return parsed


def _optional_positive_number(value: object, name: str) -> float | None:
    return None if value is None else _positive_number(value, name)


def _multiverse_reference(
    payload: dict[str, Any], key: str, alternatives: tuple[Any, ...]
) -> str | None:
    if not alternatives:
        if key in payload:
            raise ValueError(f"multiverse.{key} requires matching alternatives")
        return None
    reference = _nonempty_string(payload, key, "multiverse")
    if reference not in {item.name for item in alternatives}:
        raise ValueError(f"multiverse.{key} names an unknown alternative")
    return reference


def _tdt_schema(payload: dict[str, Any]) -> TDTBlockSchema:
    _reject_unknown(payload, {"channels", "events"}, "tdt")
    channels_raw = payload.get("channels")
    if not isinstance(channels_raw, list) or not channels_raw:
        raise ValueError("tdt.channels must be a non-empty array of tables")
    channels = []
    for index, item in enumerate(channels_raw):
        if not isinstance(item, dict):
            raise ValueError("every tdt.channels entry must be a TOML table")
        _reject_unknown(
            item,
            {
                "name",
                "signal_store",
                "signal_channel",
                "reference_store",
                "reference_channel",
            },
            f"tdt.channels[{index}]",
        )
        channels.append(
            TDTStreamChannel(
                name=_nonempty_string(item, "name", f"tdt.channels[{index}]"),
                signal_store=_nonempty_string(
                    item, "signal_store", f"tdt.channels[{index}]"
                ),
                signal_channel=_positive_integer(
                    item.get("signal_channel", 1),
                    f"tdt.channels[{index}].signal_channel",
                ),
                reference_store=_optional_string(
                    item.get("reference_store"),
                    f"tdt.channels[{index}].reference_store",
                ),
                reference_channel=(
                    _positive_integer(
                        item["reference_channel"],
                        f"tdt.channels[{index}].reference_channel",
                    )
                    if "reference_channel" in item
                    else None
                ),
            )
        )
    events = _table(payload, "events")
    _reject_unknown(events, {"store", "factor_name", "values"}, "tdt.events")
    values_raw = events.get("values")
    if not isinstance(values_raw, list) or not values_raw:
        raise ValueError("tdt.events.values must be a non-empty array of tables")
    values = []
    for index, item in enumerate(values_raw):
        if not isinstance(item, dict):
            raise ValueError("every tdt.events.values entry must be a TOML table")
        _reject_unknown(item, {"value", "label"}, f"tdt.events.values[{index}]")
        raw_value = item.get("value")
        if not isinstance(raw_value, int | float):
            raise ValueError(f"tdt.events.values[{index}].value must be numeric")
        values.append(
            TDTEpocValue(
                float(raw_value),
                _nonempty_string(item, "label", f"tdt.events.values[{index}]"),
            )
        )
    return TDTBlockSchema(
        channels=tuple(channels),
        events=TDTEpocEvents(
            store=_nonempty_string(events, "store", "tdt.events"),
            factor_name=_nonempty_string(events, "factor_name", "tdt.events"),
            values=tuple(values),
        ),
    )


def _nwb_config(
    value: object,
    sources: tuple[TabularSessionSource, ...] | tuple[TDTSessionSource, ...],
) -> NWBExportConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("nwb must be a TOML table")
    _reject_unknown(value, {"session_description", "identifier_prefix"}, "nwb")
    for index, source in enumerate(cast(tuple[SessionSource, ...], sources)):
        start = source.session_start_time
        if start is None:
            raise ValueError(
                f"sessions[{index}].session_start_time is required for NWB export"
            )
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("NWB session_start_time must include a timezone offset")
    identifier_prefix = value.get("identifier_prefix", "fipha")
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


def _metadata(value: object) -> dict[str, Any]:
    """Retain open, TOML-native metadata for evolving scientific conventions."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("metadata must be a TOML table")
    _validate_metadata_value(value, "metadata")
    return value


def _validate_metadata_value(value: object, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{path} keys must be non-empty strings")
            _validate_metadata_value(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_metadata_value(child, f"{path}[{index}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} must be finite")
    if not isinstance(value, str | int | float | bool):
        raise ValueError(
            f"{path} must contain only TOML scalar, array, or table values"
        )


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


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string when supplied")
    return value


def _positive_integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _reject_unknown(payload: dict[str, Any], allowed: set[str], section: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"unknown {section} configuration keys: {unknown}")
