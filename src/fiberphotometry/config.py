"""Versioned TOML configuration for scientist-facing event analyses."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from fiberphotometry.timecourse import PeriEventInferenceSpec
from fiberphotometry.workflow import (
    EventAnalysis,
    EventAnalysisResult,
    EventSession,
    Preprocessing,
)


@dataclass(frozen=True)
class EventAnalysisConfig:
    """Validated, serializable choices that can be applied to loaded sessions."""

    title: str
    numerator: str
    denominator: str
    factor_name: str
    channel: str
    preprocessing_kind: Literal["reference", "signal_only"]
    preprocessing_method: str
    normalization: Literal["divide", "subtract"] = "divide"
    rolling_window_s: float = 60.0
    resample_rate_hz: float | Literal["median"] | None = None
    resample_max_gap_factor: float | None = None
    baseline: tuple[float, float] = (-0.5, 0.0)
    response: tuple[float, float] = (0.0, 0.5)
    randomized: bool | None = False
    intent: Literal["confirmatory", "exploratory", "descriptive"] = "exploratory"
    acknowledged_assumptions: tuple[str, ...] = ()
    blocking_warnings: tuple[str, ...] = ()
    scalar_mixed_model: bool = False
    contrast_unit: Literal["session"] | None = None
    timecourse: PeriEventInferenceSpec | None = None
    schema_version: str = "1"

    @classmethod
    def from_toml(cls, source: str | bytes | Path) -> EventAnalysisConfig:
        """Load a strict configuration from TOML text, bytes, or a path."""
        if isinstance(source, Path):
            payload = tomllib.loads(source.read_text(encoding="utf-8"))
        elif isinstance(source, bytes):
            payload = tomllib.loads(source.decode())
        else:
            payload = tomllib.loads(source)
        return cls.from_mapping(payload)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> EventAnalysisConfig:
        """Build a strict configuration from an already parsed TOML table."""
        _reject_unknown(
            payload,
            {
                "schema_version",
                "title",
                "contrast",
                "channel",
                "preprocessing",
                "event_windows",
                "inference",
                "timecourse",
                "quality",
            },
            "root",
        )
        if payload.get("schema_version") != "1":
            raise ValueError("unsupported event-analysis config schema_version")
        contrast = _table(payload, "contrast")
        channel = _table(payload, "channel")
        preprocessing = _table(payload, "preprocessing")
        windows = _table(payload, "event_windows")
        inference = _table(payload, "inference")
        timecourse = _table(payload, "timecourse", required=False)
        quality = _table(payload, "quality", required=False)
        _reject_unknown(contrast, {"factor", "numerator", "denominator"}, "contrast")
        _reject_unknown(channel, {"name"}, "channel")
        _reject_unknown(
            preprocessing,
            {
                "kind",
                "method",
                "normalization",
                "rolling_window_s",
                "resample_rate_hz",
                "resample_max_gap_factor",
            },
            "preprocessing",
        )
        _reject_unknown(windows, {"baseline", "response"}, "event_windows")
        _reject_unknown(
            inference,
            {
                "intent",
                "randomized",
                "acknowledged_assumptions",
                "scalar_mixed_model",
                "contrast_unit",
            },
            "inference",
        )
        _reject_unknown(quality, {"blocking_warnings"}, "quality")
        _reject_unknown(
            timecourse,
            {"enabled", "window", "rate_hz", "confidence", "draws", "seed"},
            "timecourse",
        )
        kind = str(_required(preprocessing, "kind"))
        method = str(_required(preprocessing, "method"))
        normalization = str(preprocessing.get("normalization", "divide"))
        _validate_preprocessing(kind, method, normalization)
        resample_rate_raw = preprocessing.get("resample_rate_hz")
        if resample_rate_raw is None:
            resample_rate_hz: float | Literal["median"] | None = None
        elif resample_rate_raw == "median":
            resample_rate_hz = "median"
        elif isinstance(resample_rate_raw, int | float):
            resample_rate_hz = float(resample_rate_raw)
            if resample_rate_hz <= 0:
                raise ValueError("preprocessing.resample_rate_hz must be positive")
        else:
            raise ValueError(
                "preprocessing.resample_rate_hz must be positive or 'median'"
            )
        gap_factor_raw = preprocessing.get("resample_max_gap_factor")
        resample_max_gap_factor = (
            None if gap_factor_raw is None else float(gap_factor_raw)
        )
        if resample_max_gap_factor is not None and resample_max_gap_factor <= 1:
            raise ValueError(
                "preprocessing.resample_max_gap_factor must be greater than one"
            )
        if resample_rate_hz is None and resample_max_gap_factor is not None:
            raise ValueError(
                "preprocessing.resample_max_gap_factor requires resample_rate_hz"
            )
        intent = str(_required(inference, "intent"))
        if intent not in {"confirmatory", "exploratory", "descriptive"}:
            raise ValueError("inference.intent is invalid")
        randomized_raw = inference.get("randomized", False)
        randomized: bool | None
        if isinstance(randomized_raw, bool):
            randomized = randomized_raw
        elif randomized_raw == "unspecified":
            randomized = None
        else:
            raise ValueError("inference.randomized must be boolean or 'unspecified'")
        scalar_mixed_model = inference.get("scalar_mixed_model", False)
        if not isinstance(scalar_mixed_model, bool):
            raise ValueError("inference.scalar_mixed_model must be boolean")
        contrast_unit = inference.get("contrast_unit")
        if contrast_unit not in {None, "session"}:
            raise ValueError("inference.contrast_unit must be 'session' when supplied")
        timecourse_spec = _timecourse(timecourse)
        return cls(
            title=str(payload.get("title", "Fiber photometry event contrast")),
            numerator=str(_required(contrast, "numerator")),
            denominator=str(_required(contrast, "denominator")),
            factor_name=str(contrast.get("factor", "condition")),
            channel=str(_required(channel, "name")),
            preprocessing_kind=kind,  # type: ignore[arg-type]
            preprocessing_method=method,
            normalization=normalization,  # type: ignore[arg-type]
            rolling_window_s=float(preprocessing.get("rolling_window_s", 60.0)),
            resample_rate_hz=resample_rate_hz,
            resample_max_gap_factor=resample_max_gap_factor,
            baseline=_window(windows, "baseline"),
            response=_window(windows, "response"),
            randomized=randomized,
            intent=intent,  # type: ignore[arg-type]
            acknowledged_assumptions=_strings(
                inference.get("acknowledged_assumptions", ()),
                "inference.acknowledged_assumptions",
            ),
            blocking_warnings=_strings(
                quality.get("blocking_warnings", ()), "quality.blocking_warnings"
            ),
            scalar_mixed_model=scalar_mixed_model,
            contrast_unit=contrast_unit,
            timecourse=timecourse_spec,
        )

    @property
    def fingerprint(self) -> str:
        """Return a stable SHA-256 over normalized configuration choices."""
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def to_json(self) -> str:
        """Return the normalized configuration and its fingerprint."""
        return json.dumps(
            {**asdict(self), "configuration_sha256": self.fingerprint},
            indent=2,
            sort_keys=True,
        )

    def build(self, sessions: tuple[EventSession, ...]) -> EventAnalysis:
        """Apply configuration choices to already-loaded labelled sessions."""
        preprocessing = (
            Preprocessing.reference(method=self.preprocessing_method)  # type: ignore[arg-type]
            if self.preprocessing_kind == "reference"
            else Preprocessing.signal_only(
                method=self.preprocessing_method,  # type: ignore[arg-type]
                normalization=self.normalization,
                rolling_window_s=self.rolling_window_s,
                resample_rate_hz=self.resample_rate_hz,
                resample_max_gap_factor=self.resample_max_gap_factor,
            )
        )
        return EventAnalysis(
            sessions,
            self.numerator,
            self.denominator,
            self.channel,
            preprocessing,
            baseline=self.baseline,
            response=self.response,
            factor_name=self.factor_name,
            title=self.title,
            randomized=self.randomized,
            intent=self.intent,
            blocking_warnings=self.blocking_warnings,
            contrast_unit=self.contrast_unit,
            timecourse=self.timecourse,
            configuration_fingerprint=self.fingerprint,
        )

    def run(self, sessions: tuple[EventSession, ...]) -> EventAnalysisResult:
        """Build and execute using assumptions explicitly recorded in the file."""
        return self.build(sessions).run(
            acknowledged_assumptions=self.acknowledged_assumptions
        )


def _table(
    payload: dict[str, Any], name: str, *, required: bool = True
) -> dict[str, Any]:
    value = payload.get(name)
    if value is None and not required:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a TOML table")
    return value


def _required(payload: dict[str, Any], name: str) -> Any:
    if name not in payload:
        raise ValueError(f"missing required configuration key {name!r}")
    return payload[name]


def _reject_unknown(payload: dict[str, Any], allowed: set[str], section: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"unknown {section} configuration keys: {unknown}")


def _window(payload: dict[str, Any], name: str) -> tuple[float, float]:
    value = _required(payload, name)
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"event_windows.{name} must contain exactly two numbers")
    window = (float(value[0]), float(value[1]))
    if window[0] >= window[1]:
        raise ValueError(f"event_windows.{name} must be increasing")
    return window


def _timecourse(payload: dict[str, Any]) -> PeriEventInferenceSpec | None:
    if not payload or payload.get("enabled", True) is False:
        return None
    enabled = payload.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError("timecourse.enabled must be boolean")
    window_raw = payload.get("window", [-1.0, 2.0])
    if not isinstance(window_raw, list) or len(window_raw) != 2:
        raise ValueError("timecourse.window must contain exactly two numbers")
    return PeriEventInferenceSpec(
        window=(float(window_raw[0]), float(window_raw[1])),
        rate_hz=float(payload.get("rate_hz", 20.0)),
        confidence=float(payload.get("confidence", 0.95)),
        draws=int(payload.get("draws", 2000)),
        seed=int(payload.get("seed", 0)),
    )


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"{name} must be an array of strings")
    return tuple(value)


def _validate_preprocessing(kind: str, method: str, normalization: str) -> None:
    if kind == "reference":
        if method not in {"irls", "ols"}:
            raise ValueError("reference preprocessing method must be 'irls' or 'ols'")
        if normalization != "divide":
            raise ValueError("reference preprocessing normalization must be 'divide'")
        return
    if kind != "signal_only":
        raise ValueError("preprocessing.kind must be 'reference' or 'signal_only'")
    if method not in {"double_exponential", "asls", "rolling_mean"}:
        raise ValueError("invalid signal-only preprocessing method")
    if normalization not in {"divide", "subtract"}:
        raise ValueError("preprocessing.normalization must be 'divide' or 'subtract'")
