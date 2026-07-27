"""Typed boundaries for external pose and behavior-analysis tools."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray


def _readonly_float(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    array = np.array(values, dtype=float, copy=True)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    array.setflags(write=False)
    return array


def _time_from_fps(
    length: int,
    *,
    time_s: ArrayLike | None,
    fps: float | None,
) -> NDArray[np.float64]:
    if (time_s is None) == (fps is None):
        raise ValueError("provide exactly one of time_s or fps")
    if fps is not None:
        if not np.isfinite(fps) or fps <= 0:
            raise ValueError("fps must be finite and positive")
        return _readonly_float(np.arange(length, dtype=float) / fps, name="time_s")
    assert time_s is not None
    result = _readonly_float(time_s, name="time_s")
    if len(result) != length:
        raise ValueError("time_s length must match the source frames")
    return result


def _validate_time(time_s: NDArray[np.float64]) -> None:
    if len(time_s) == 0:
        raise ValueError("time_s must contain at least one sample")
    if not np.all(np.isfinite(time_s)):
        raise ValueError("time_s must contain only finite values")
    if len(time_s) > 1 and np.any(np.diff(time_s) <= 0):
        raise ValueError("time_s must be strictly increasing")


@dataclass(frozen=True)
class ClockPulseMatches:
    """Explicit one-to-one synchronization pulses observed on two clocks."""

    source_clock_id: str
    target_clock_id: str
    source_time_s: tuple[float, ...]
    target_time_s: tuple[float, ...]
    match_labels: tuple[str, ...] = ()

    @classmethod
    def from_arrays(
        cls,
        *,
        source_clock_id: str,
        target_clock_id: str,
        source_time_s: ArrayLike,
        target_time_s: ArrayLike,
        match_labels: Sequence[str] | None = None,
    ) -> ClockPulseMatches:
        """Create declared pulse pairs without attempting automatic matching."""

        source = _readonly_float(source_time_s, name="source_time_s")
        target = _readonly_float(target_time_s, name="target_time_s")
        return cls(
            source_clock_id=str(source_clock_id),
            target_clock_id=str(target_clock_id),
            source_time_s=tuple(float(value) for value in source),
            target_time_s=tuple(float(value) for value in target),
            match_labels=tuple(str(value) for value in (match_labels or ())),
        )

    def __post_init__(self) -> None:
        if not self.source_clock_id.strip() or not self.target_clock_id.strip():
            raise ValueError("clock IDs must be non-empty")
        if self.source_clock_id == self.target_clock_id:
            raise ValueError("source and target clock IDs must differ")
        source = tuple(float(value) for value in self.source_time_s)
        target = tuple(float(value) for value in self.target_time_s)
        if len(source) != len(target):
            raise ValueError("source and target pulse counts must match")
        if any(not np.isfinite(value) for value in (*source, *target)):
            raise ValueError("pulse times must be finite")
        if any(right <= left for left, right in pairwise(source)):
            raise ValueError("source pulse times must be strictly increasing")
        if any(right <= left for left, right in pairwise(target)):
            raise ValueError("target pulse times must be strictly increasing")
        labels = tuple(str(value) for value in self.match_labels)
        if labels and len(labels) != len(source):
            raise ValueError("match_labels must be empty or match the pulse count")
        if any(not value.strip() for value in labels):
            raise ValueError("match labels must be non-empty")
        if labels and len(labels) != len(set(labels)):
            raise ValueError("match labels must be unique")
        object.__setattr__(self, "source_time_s", source)
        object.__setattr__(self, "target_time_s", target)
        object.__setattr__(self, "match_labels", labels)


@dataclass(frozen=True)
class ClockSynchronizationSpec:
    """Prospective acceptance thresholds for an affine clock mapping."""

    maximum_absolute_residual_s: float
    maximum_drift_ppm: float
    minimum_matches: int = 3
    minimum_source_span_s: float = 1.0
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if (
            not np.isfinite(self.maximum_absolute_residual_s)
            or self.maximum_absolute_residual_s <= 0
        ):
            raise ValueError("maximum_absolute_residual_s must be finite and positive")
        if not np.isfinite(self.maximum_drift_ppm) or self.maximum_drift_ppm < 0:
            raise ValueError("maximum_drift_ppm must be finite and non-negative")
        if self.minimum_matches < 3:
            raise ValueError("minimum_matches must be at least three")
        if (
            not np.isfinite(self.minimum_source_span_s)
            or self.minimum_source_span_s <= 0
        ):
            raise ValueError("minimum_source_span_s must be finite and positive")


@dataclass(frozen=True)
class ClockSynchronization:
    """Accepted affine mapping and complete pulse-level diagnostic evidence."""

    source_clock_id: str
    target_clock_id: str
    intercept_s: float
    scale: float
    drift_ppm: float
    source_start_s: float
    source_stop_s: float
    source_span_s: float
    matched_pulses: int
    source_pulse_time_s: tuple[float, ...]
    target_pulse_time_s: tuple[float, ...]
    match_labels: tuple[str, ...]
    fitted_target_time_s: tuple[float, ...]
    residual_s: tuple[float, ...]
    root_mean_square_residual_s: float
    median_absolute_residual_s: float
    maximum_absolute_residual_s: float
    allowed_maximum_absolute_residual_s: float
    allowed_maximum_drift_ppm: float
    minimum_matches: int
    minimum_source_span_s: float
    synchronization_id: str
    method: Literal["affine_matched_pulses"] = "affine_matched_pulses"
    artifact_type: Literal["clock_synchronization"] = "clock_synchronization"
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.source_clock_id.strip() or not self.target_clock_id.strip():
            raise ValueError("clock IDs must be non-empty")
        if self.source_clock_id == self.target_clock_id:
            raise ValueError("source and target clock IDs must differ")
        if not np.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("clock synchronization scale must be finite and positive")
        scalars = (
            self.intercept_s,
            self.drift_ppm,
            self.source_start_s,
            self.source_stop_s,
            self.source_span_s,
            self.root_mean_square_residual_s,
            self.median_absolute_residual_s,
            self.maximum_absolute_residual_s,
            self.allowed_maximum_absolute_residual_s,
            self.allowed_maximum_drift_ppm,
            self.minimum_source_span_s,
        )
        if any(not np.isfinite(value) for value in scalars):
            raise ValueError("clock synchronization diagnostics must be finite")
        if self.matched_pulses < 3 or self.minimum_matches < 3:
            raise ValueError("clock synchronization requires at least three pulses")
        evidence_lengths = {
            len(self.source_pulse_time_s),
            len(self.target_pulse_time_s),
            len(self.fitted_target_time_s),
            len(self.residual_s),
        }
        if evidence_lengths != {self.matched_pulses}:
            raise ValueError("clock pulse evidence must match matched_pulses")
        if self.match_labels and len(self.match_labels) != self.matched_pulses:
            raise ValueError("clock match labels must match matched_pulses")
        if self.source_stop_s <= self.source_start_s or self.source_span_s <= 0:
            raise ValueError("clock synchronization source span must be positive")
        if self.maximum_absolute_residual_s < 0:
            raise ValueError("clock synchronization residual must be non-negative")
        if (
            self.maximum_absolute_residual_s
            > self.allowed_maximum_absolute_residual_s + 1e-12
        ):
            raise ValueError("clock synchronization exceeds its residual threshold")
        if abs(self.drift_ppm) > self.allowed_maximum_drift_ppm + 1e-12:
            raise ValueError("clock synchronization exceeds its drift threshold")
        if not self.synchronization_id.strip():
            raise ValueError("synchronization_id must be non-empty")

    def to_json(self) -> str:
        """Serialize the accepted mapping and all matched-pulse evidence."""

        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def transform_time(
        self,
        source_time_s: ArrayLike,
        *,
        maximum_extrapolation_s: float = 0.0,
    ) -> NDArray[np.float64]:
        """Map source times, refusing extrapolation beyond a declared allowance."""

        source = _readonly_float(source_time_s, name="source_time_s")
        if not len(source):
            return source
        _validate_time(source)
        self._validate_extrapolation(source, maximum_extrapolation_s)
        return _readonly_float(
            self.intercept_s + self.scale * source,
            name="target_time_s",
        )

    def synchronize_covariate(
        self,
        covariate: BehaviorCovariate,
        *,
        maximum_extrapolation_s: float = 0.0,
    ) -> BehaviorCovariate:
        """Transform covariate timestamps and append synchronization provenance."""

        self._require_source_clock(covariate.clock_id)
        return BehaviorCovariate(
            subject=covariate.subject,
            session=covariate.session,
            name=covariate.name,
            time_s=self.transform_time(
                covariate.time_s,
                maximum_extrapolation_s=maximum_extrapolation_s,
            ),
            values=covariate.values,
            valid=covariate.valid,
            unit=covariate.unit,
            source=covariate.source,
            clock_id=self.target_clock_id,
            source_version=covariate.source_version,
            source_artifact=covariate.source_artifact,
            clock_synchronization_ids=(
                *covariate.clock_synchronization_ids,
                self.synchronization_id,
            ),
        )

    def synchronize_pose(
        self,
        pose: PoseTrajectory,
        *,
        maximum_extrapolation_s: float = 0.0,
    ) -> PoseTrajectory:
        """Transform pose timestamps without changing coordinates or confidence."""

        self._require_source_clock(pose.clock_id)
        return PoseTrajectory(
            subject=pose.subject,
            session=pose.session,
            keypoint=pose.keypoint,
            time_s=self.transform_time(
                pose.time_s,
                maximum_extrapolation_s=maximum_extrapolation_s,
            ),
            x=pose.x,
            y=pose.y,
            confidence=pose.confidence,
            coordinate_unit=pose.coordinate_unit,
            source=pose.source,
            clock_id=self.target_clock_id,
            individual=pose.individual,
            source_version=pose.source_version,
            source_artifact=pose.source_artifact,
            clock_synchronization_ids=(
                *pose.clock_synchronization_ids,
                self.synchronization_id,
            ),
        )

    def synchronize_annotations(
        self,
        annotations: BehaviorAnnotations,
        *,
        maximum_extrapolation_s: float = 0.0,
    ) -> BehaviorAnnotations:
        """Transform point and interval times while retaining their semantics."""

        self._require_source_clock(annotations.clock_id)
        points = {
            label: tuple(
                float(value)
                for value in self.transform_time(
                    times,
                    maximum_extrapolation_s=maximum_extrapolation_s,
                )
            )
            for label, times in annotations.point_events.items()
        }
        intervals = tuple(
            BehaviorInterval(
                label=item.label,
                start_s=float(
                    self.transform_time(
                        [item.start_s],
                        maximum_extrapolation_s=maximum_extrapolation_s,
                    )[0]
                ),
                stop_s=float(
                    self.transform_time(
                        [item.stop_s],
                        maximum_extrapolation_s=maximum_extrapolation_s,
                    )[0]
                ),
                confidence=item.confidence,
            )
            for item in annotations.intervals
        )
        return BehaviorAnnotations(
            subject=annotations.subject,
            session=annotations.session,
            point_events=points,
            intervals=intervals,
            source=annotations.source,
            clock_id=self.target_clock_id,
            source_version=annotations.source_version,
            source_artifact=annotations.source_artifact,
            clock_synchronization_ids=(
                *annotations.clock_synchronization_ids,
                self.synchronization_id,
            ),
        )

    def _require_source_clock(self, clock_id: str) -> None:
        if clock_id != self.source_clock_id:
            raise ValueError(
                f"clock synchronization expects {self.source_clock_id!r}, "
                f"received {clock_id!r}"
            )

    def _validate_extrapolation(
        self,
        source_time_s: NDArray[np.float64],
        maximum_extrapolation_s: float,
    ) -> None:
        if not np.isfinite(maximum_extrapolation_s) or maximum_extrapolation_s < 0:
            raise ValueError("maximum_extrapolation_s must be finite and non-negative")
        before = max(0.0, self.source_start_s - float(source_time_s[0]))
        after = max(0.0, float(source_time_s[-1]) - self.source_stop_s)
        required = max(before, after)
        if required > maximum_extrapolation_s + 1e-12:
            raise ValueError(
                f"clock transform requires {required:g}s extrapolation; allowed "
                f"maximum is {maximum_extrapolation_s:g}s"
            )


def fit_clock_synchronization(
    matches: ClockPulseMatches,
    spec: ClockSynchronizationSpec,
) -> ClockSynchronization:
    """Fit and validate ``target_time = intercept + scale * source_time``."""

    source = np.asarray(matches.source_time_s, dtype=float)
    target = np.asarray(matches.target_time_s, dtype=float)
    if len(source) < spec.minimum_matches:
        raise ValueError(
            f"clock synchronization has {len(source)} matches; minimum is "
            f"{spec.minimum_matches}"
        )
    source_span = float(source[-1] - source[0])
    if source_span < spec.minimum_source_span_s:
        raise ValueError(
            f"clock synchronization spans {source_span:g}s; minimum is "
            f"{spec.minimum_source_span_s:g}s"
        )
    centered_source = source - np.mean(source)
    centered_target = target - np.mean(target)
    denominator = float(centered_source @ centered_source)
    scale = float(centered_source @ centered_target / denominator)
    intercept = float(np.mean(target) - scale * np.mean(source))
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("clock synchronization must produce a positive finite scale")
    fitted = intercept + scale * source
    residual = target - fitted
    drift_ppm = (scale - 1.0) * 1e6
    maximum_residual = float(np.max(np.abs(residual)))
    if abs(drift_ppm) > spec.maximum_drift_ppm:
        raise ValueError(
            f"clock drift is {drift_ppm:g} ppm; allowed magnitude is "
            f"{spec.maximum_drift_ppm:g} ppm"
        )
    if maximum_residual > spec.maximum_absolute_residual_s:
        raise ValueError(
            f"clock maximum absolute residual is {maximum_residual:g}s; allowed "
            f"maximum is {spec.maximum_absolute_residual_s:g}s"
        )
    evidence = {
        "source_clock_id": matches.source_clock_id,
        "target_clock_id": matches.target_clock_id,
        "source_time_s": matches.source_time_s,
        "target_time_s": matches.target_time_s,
        "match_labels": matches.match_labels,
        "spec": asdict(spec),
        "intercept_s": intercept,
        "scale": scale,
    }
    digest = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ClockSynchronization(
        source_clock_id=matches.source_clock_id,
        target_clock_id=matches.target_clock_id,
        intercept_s=intercept,
        scale=scale,
        drift_ppm=drift_ppm,
        source_start_s=float(source[0]),
        source_stop_s=float(source[-1]),
        source_span_s=source_span,
        matched_pulses=len(source),
        source_pulse_time_s=matches.source_time_s,
        target_pulse_time_s=matches.target_time_s,
        match_labels=matches.match_labels,
        fitted_target_time_s=tuple(float(value) for value in fitted),
        residual_s=tuple(float(value) for value in residual),
        root_mean_square_residual_s=float(np.sqrt(np.mean(residual**2))),
        median_absolute_residual_s=float(np.median(np.abs(residual))),
        maximum_absolute_residual_s=maximum_residual,
        allowed_maximum_absolute_residual_s=spec.maximum_absolute_residual_s,
        allowed_maximum_drift_ppm=spec.maximum_drift_ppm,
        minimum_matches=spec.minimum_matches,
        minimum_source_span_s=spec.minimum_source_span_s,
        synchronization_id=f"clock-sync-{digest}",
    )


@dataclass(frozen=True)
class BehaviorCovariate:
    """One timestamped external covariate with an explicit validity mask."""

    subject: str
    session: str
    name: str
    time_s: NDArray[np.float64]
    values: NDArray[np.float64]
    valid: NDArray[np.bool_]
    unit: str
    source: str
    clock_id: str
    source_version: str | None = None
    source_artifact: str | None = None
    clock_synchronization_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        time_s = _readonly_float(self.time_s, name="time_s")
        values = _readonly_float(self.values, name="values")
        valid = np.array(self.valid, dtype=bool, copy=True)
        if valid.ndim != 1:
            raise ValueError("valid must be one-dimensional")
        if len(time_s) != len(values) or len(time_s) != len(valid):
            raise ValueError("time_s, values, and valid must have equal length")
        _validate_time(time_s)
        if not self.name.strip() or not self.unit.strip():
            raise ValueError("covariate name and unit must be non-empty")
        if not self.source.strip() or not self.clock_id.strip():
            raise ValueError("covariate source and clock_id must be non-empty")
        synchronization_ids = tuple(
            str(value) for value in self.clock_synchronization_ids
        )
        if any(not value.strip() for value in synchronization_ids):
            raise ValueError("clock synchronization IDs must be non-empty")
        valid &= np.isfinite(values)
        valid.setflags(write=False)
        object.__setattr__(self, "time_s", time_s)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "clock_synchronization_ids", synchronization_ids)

    def align_to(
        self,
        target_time_s: ArrayLike,
        *,
        target_clock_id: str,
        max_gap_s: float,
    ) -> NDArray[np.float64]:
        """Return aligned values; use :meth:`aligned_to` to retain the mask."""

        return self.aligned_to(
            target_time_s,
            target_clock_id=target_clock_id,
            max_gap_s=max_gap_s,
        ).values

    def aligned_to(
        self,
        target_time_s: ArrayLike,
        *,
        target_clock_id: str,
        max_gap_s: float,
    ) -> BehaviorCovariate:
        """Interpolate within valid runs and retain the aligned validity mask."""

        if target_clock_id != self.clock_id:
            raise ValueError(
                "clock mismatch; synchronize externally and declare a shared clock_id"
            )
        target = _readonly_float(target_time_s, name="target_time_s")
        _validate_time(target)
        if not np.isfinite(max_gap_s) or max_gap_s <= 0:
            raise ValueError("max_gap_s must be finite and positive")

        aligned = np.full(len(target), np.nan, dtype=float)
        indices = np.flatnonzero(self.valid)
        if not len(indices):
            return self._aligned_covariate(target, aligned)

        split_after = np.flatnonzero(
            (np.diff(indices) != 1) | (np.diff(self.time_s[indices]) > max_gap_s)
        )
        runs = np.split(indices, split_after + 1)
        for run in runs:
            run_time = self.time_s[run]
            run_values = self.values[run]
            if len(run) == 1:
                matches = np.isclose(target, run_time[0], rtol=0.0, atol=1e-12)
                aligned[matches] = run_values[0]
                continue
            inside = (target >= run_time[0]) & (target <= run_time[-1])
            aligned[inside] = np.interp(target[inside], run_time, run_values)
        return self._aligned_covariate(target, aligned)

    def _aligned_covariate(
        self,
        target_time_s: NDArray[np.float64],
        values: NDArray[np.float64],
    ) -> BehaviorCovariate:
        return BehaviorCovariate(
            subject=self.subject,
            session=self.session,
            name=self.name,
            time_s=target_time_s,
            values=values,
            valid=np.isfinite(values),
            unit=self.unit,
            source=self.source,
            clock_id=self.clock_id,
            source_version=self.source_version,
            source_artifact=self.source_artifact,
            clock_synchronization_ids=self.clock_synchronization_ids,
        )


@dataclass(frozen=True)
class PoseTrajectory:
    """One tracked keypoint from DeepLabCut or SLEAP."""

    subject: str
    session: str
    keypoint: str
    time_s: NDArray[np.float64]
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    confidence: NDArray[np.float64]
    coordinate_unit: str
    source: Literal["deeplabcut", "sleap"]
    clock_id: str
    individual: str | None = None
    source_version: str | None = None
    source_artifact: str | None = None
    clock_synchronization_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        time_s = _readonly_float(self.time_s, name="time_s")
        x = _readonly_float(self.x, name="x")
        y = _readonly_float(self.y, name="y")
        confidence = _readonly_float(self.confidence, name="confidence")
        if len({len(time_s), len(x), len(y), len(confidence)}) != 1:
            raise ValueError("pose arrays must have equal length")
        _validate_time(time_s)
        if not self.keypoint.strip() or not self.coordinate_unit.strip():
            raise ValueError("keypoint and coordinate_unit must be non-empty")
        if not self.clock_id.strip():
            raise ValueError("clock_id must be non-empty")
        synchronization_ids = tuple(
            str(value) for value in self.clock_synchronization_ids
        )
        if any(not value.strip() for value in synchronization_ids):
            raise ValueError("clock synchronization IDs must be non-empty")
        finite_confidence = confidence[np.isfinite(confidence)]
        if np.any(finite_confidence < 0):
            raise ValueError("confidence-like scores must be non-negative")
        object.__setattr__(self, "time_s", time_s)
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "clock_synchronization_ids", synchronization_ids)

    def speed(
        self,
        *,
        minimum_confidence: float,
        coordinate_scale: float = 1.0,
        output_unit: str | None = None,
        name: str | None = None,
    ) -> BehaviorCovariate:
        """Calculate pairwise speed while retaining confidence-derived missingness."""

        if not np.isfinite(minimum_confidence) or minimum_confidence < 0:
            raise ValueError("minimum_confidence must be finite and non-negative")
        if not np.isfinite(coordinate_scale) or coordinate_scale <= 0:
            raise ValueError("coordinate_scale must be finite and positive")
        valid_pose = (
            np.isfinite(self.x)
            & np.isfinite(self.y)
            & np.isfinite(self.confidence)
            & (self.confidence >= minimum_confidence)
        )
        values = np.full(len(self.time_s), np.nan, dtype=float)
        valid = np.zeros(len(self.time_s), dtype=bool)
        if len(self.time_s) > 1:
            delta = np.hypot(np.diff(self.x), np.diff(self.y)) * coordinate_scale
            values[1:] = delta / np.diff(self.time_s)
            valid[1:] = valid_pose[1:] & valid_pose[:-1] & np.isfinite(values[1:])
        unit = output_unit or f"{self.coordinate_unit}/s"
        return BehaviorCovariate(
            subject=self.subject,
            session=self.session,
            name=name or f"{self.keypoint}_speed",
            time_s=self.time_s,
            values=values,
            valid=valid,
            unit=unit,
            source=self.source,
            clock_id=self.clock_id,
            source_version=self.source_version,
            source_artifact=self.source_artifact,
            clock_synchronization_ids=self.clock_synchronization_ids,
        )


@dataclass(frozen=True)
class BehaviorInterval:
    """One externally identified behavioral state or bout."""

    label: str
    start_s: float
    stop_s: float
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("interval label must be non-empty")
        if not np.isfinite(self.start_s) or not np.isfinite(self.stop_s):
            raise ValueError("interval bounds must be finite")
        if self.stop_s <= self.start_s:
            raise ValueError("interval stop_s must be greater than start_s")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("interval confidence must lie between zero and one")


@dataclass(frozen=True)
class IntervalEncodingInputs:
    """Aligned interval edges, durations and physical bounds for encoding models."""

    events: Mapping[str, tuple[float, ...]]
    event_values: Mapping[str, Mapping[str, tuple[float, ...]]]
    intervals: Mapping[str, tuple[tuple[float, float], ...]]
    edge: Literal["onset", "offset"]
    schema_version: str = "1"


@dataclass(frozen=True)
class BehaviorAnnotations:
    """Point events and intervals discovered by an external behavior tool."""

    subject: str
    session: str
    point_events: Mapping[str, tuple[float, ...]]
    intervals: tuple[BehaviorInterval, ...]
    source: str
    clock_id: str
    source_version: str | None = None
    source_artifact: str | None = None
    clock_synchronization_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.clock_id.strip():
            raise ValueError("annotation source and clock_id must be non-empty")
        synchronization_ids = tuple(
            str(value) for value in self.clock_synchronization_ids
        )
        if any(not value.strip() for value in synchronization_ids):
            raise ValueError("clock synchronization IDs must be non-empty")
        normalized: dict[str, tuple[float, ...]] = {}
        for label, times in self.point_events.items():
            if not label.strip():
                raise ValueError("point-event labels must be non-empty")
            values = tuple(float(value) for value in times)
            if any(not np.isfinite(value) for value in values):
                raise ValueError("point-event times must be finite")
            normalized[label] = tuple(sorted(values))
        object.__setattr__(self, "point_events", normalized)
        object.__setattr__(
            self,
            "intervals",
            tuple(sorted(self.intervals, key=lambda item: (item.start_s, item.stop_s))),
        )
        object.__setattr__(self, "clock_synchronization_ids", synchronization_ids)

    def event_times(
        self,
        *,
        edge: Literal["onset", "offset"] = "onset",
        include_points: bool = True,
    ) -> Mapping[str, tuple[float, ...]]:
        """Return event-kernel-ready times without discarding interval identity."""

        collected = {label: list(times) for label, times in self.point_events.items()}
        if not include_points:
            collected = {}
        attribute = "start_s" if edge == "onset" else "stop_s"
        for interval in self.intervals:
            collected.setdefault(interval.label, []).append(
                getattr(interval, attribute)
            )
        return {
            label: tuple(sorted(times)) for label, times in sorted(collected.items())
        }

    def normalized_progress(
        self,
        time_s: ArrayLike,
        *,
        label: str,
    ) -> BehaviorCovariate:
        """Map samples inside non-overlapping bouts to progress in ``[0, 1]``."""

        time = _readonly_float(time_s, name="time_s")
        _validate_time(time)
        selected = [interval for interval in self.intervals if interval.label == label]
        values = np.full(len(time), np.nan, dtype=float)
        valid = np.zeros(len(time), dtype=bool)
        for interval in selected:
            inside = (time >= interval.start_s) & (time <= interval.stop_s)
            if np.any(valid & inside):
                raise ValueError(
                    f"overlapping {label!r} intervals make progress ambiguous"
                )
            values[inside] = (time[inside] - interval.start_s) / (
                interval.stop_s - interval.start_s
            )
            valid[inside] = True
        return BehaviorCovariate(
            subject=self.subject,
            session=self.session,
            name=f"{label}_progress",
            time_s=time,
            values=values,
            valid=valid,
            unit="proportion",
            source=self.source,
            clock_id=self.clock_id,
            source_version=self.source_version,
            source_artifact=self.source_artifact,
            clock_synchronization_ids=self.clock_synchronization_ids,
        )

    def interval_encoding_inputs(
        self,
        *,
        edge: Literal["onset", "offset"] = "onset",
    ) -> IntervalEncodingInputs:
        """Return aligned interval edges, duration values and physical bounds."""

        if edge not in {"onset", "offset"}:
            raise ValueError("interval encoding edge must be 'onset' or 'offset'")
        labels = sorted({interval.label for interval in self.intervals})
        events: dict[str, tuple[float, ...]] = {}
        event_values: dict[str, Mapping[str, tuple[float, ...]]] = {}
        intervals: dict[str, tuple[tuple[float, float], ...]] = {}
        for label in labels:
            selected = [item for item in self.intervals if item.label == label]
            by_edge = sorted(
                selected,
                key=(
                    (lambda item: (item.start_s, item.stop_s))
                    if edge == "onset"
                    else (lambda item: (item.stop_s, item.start_s))
                ),
            )
            events[label] = tuple(
                item.start_s if edge == "onset" else item.stop_s for item in by_edge
            )
            event_values[label] = {
                "duration_s": tuple(item.stop_s - item.start_s for item in by_edge)
            }
            intervals[label] = tuple(
                (item.start_s, item.stop_s)
                for item in sorted(
                    selected,
                    key=lambda item: (item.start_s, item.stop_s),
                )
            )
        return IntervalEncodingInputs(events, event_values, intervals, edge)


def pose_from_deeplabcut(
    frame: Any,
    *,
    subject: str,
    session: str,
    keypoint: str,
    time_s: ArrayLike | None = None,
    fps: float | None = None,
    scorer: str | None = None,
    individual: str | None = None,
    coordinate_unit: str = "px",
    clock_id: str = "video",
    source_version: str | None = None,
    source_artifact: str | None = None,
) -> PoseTrajectory:
    """Read one keypoint from a DeepLabCut MultiIndex-like result table."""

    if not hasattr(frame, "columns") or not hasattr(frame, "__getitem__"):
        raise TypeError("frame must provide dataframe-like columns and column access")
    columns = [
        tuple(column) if isinstance(column, tuple) else (column,)
        for column in frame.columns
    ]
    matches: dict[str, list[tuple[Any, ...]]] = {"x": [], "y": [], "likelihood": []}
    for column in columns:
        if len(column) < 3 or str(column[-2]) != keypoint:
            continue
        coordinate = str(column[-1]).lower()
        if coordinate not in matches:
            continue
        if scorer is not None and str(column[0]) != scorer:
            continue
        if individual is not None and (
            len(column) < 4 or str(column[-3]) != individual
        ):
            continue
        matches[coordinate].append(column)
    ambiguous = {name: values for name, values in matches.items() if len(values) != 1}
    if ambiguous:
        counts = {name: len(values) for name, values in ambiguous.items()}
        raise ValueError(
            "DeepLabCut keypoint columns are missing or ambiguous; "
            f"observed matches {counts}. Declare scorer/individual explicitly."
        )
    x = np.asarray(frame[matches["x"][0]], dtype=float)
    y = np.asarray(frame[matches["y"][0]], dtype=float)
    confidence = np.asarray(frame[matches["likelihood"][0]], dtype=float)
    finite_likelihood = confidence[np.isfinite(confidence)]
    if np.any((finite_likelihood < 0) | (finite_likelihood > 1)):
        raise ValueError("DeepLabCut likelihood must lie between zero and one")
    time = _time_from_fps(len(x), time_s=time_s, fps=fps)
    return PoseTrajectory(
        subject=subject,
        session=session,
        keypoint=keypoint,
        time_s=time,
        x=x,
        y=y,
        confidence=confidence,
        coordinate_unit=coordinate_unit,
        source="deeplabcut",
        clock_id=clock_id,
        individual=individual,
        source_version=source_version,
        source_artifact=source_artifact,
    )


def pose_from_deeplabcut_file(
    path: str | Path,
    *,
    subject: str,
    session: str,
    keypoint: str,
    time_s: ArrayLike | None = None,
    fps: float | None = None,
    scorer: str | None = None,
    individual: str | None = None,
    csv_header_rows: Literal[3, 4] = 3,
    coordinate_unit: str = "px",
    clock_id: str = "video",
    source_version: str | None = None,
) -> PoseTrajectory:
    """Read one keypoint from a DeepLabCut prediction HDF5 or CSV file."""

    try:
        import pandas as pd  # type: ignore[import-untyped]
    except ImportError as error:  # pragma: no cover - depends on optional install
        raise ImportError(
            "DeepLabCut file input requires the 'behavior' optional dependency"
        ) from error
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".h5", ".hdf5"}:
        frame = pd.read_hdf(source)
    elif suffix == ".csv":
        frame = pd.read_csv(
            source,
            header=list(range(csv_header_rows)),
            index_col=0,
        )
    else:
        raise ValueError("DeepLabCut file must have .h5, .hdf5, or .csv suffix")
    return pose_from_deeplabcut(
        frame,
        subject=subject,
        session=session,
        keypoint=keypoint,
        time_s=time_s,
        fps=fps,
        scorer=scorer,
        individual=individual,
        coordinate_unit=coordinate_unit,
        clock_id=clock_id,
        source_version=source_version,
        source_artifact=str(source),
    )


def pose_from_sleap(
    tracks: ArrayLike,
    *,
    subject: str,
    session: str,
    node_names: Sequence[str],
    node: str,
    dims: tuple[str, str, str, str],
    time_s: ArrayLike | None = None,
    fps: float | None = None,
    track: int = 0,
    point_scores: ArrayLike | None = None,
    score_dims: tuple[str, str, str] | None = None,
    coordinate_unit: str = "px",
    clock_id: str = "video",
    source_version: str | None = None,
    source_artifact: str | None = None,
) -> PoseTrajectory:
    """Read one node from a SLEAP Analysis HDF5-shaped array."""

    expected = {"frame", "track", "node", "xy"}
    if set(dims) != expected or len(set(dims)) != 4:
        raise ValueError(f"dims must contain exactly {sorted(expected)}")
    values = np.asarray(tracks, dtype=float)
    if values.ndim != 4:
        raise ValueError("tracks must be four-dimensional")
    canonical = np.moveaxis(
        values,
        [dims.index(name) for name in ("frame", "track", "node", "xy")],
        range(4),
    )
    if canonical.shape[3] != 2:
        raise ValueError("the SLEAP xy dimension must have length two")
    if len(node_names) != canonical.shape[2] or node not in node_names:
        raise ValueError("node_names must match the node dimension and include node")
    if not 0 <= track < canonical.shape[1]:
        raise ValueError("track index is out of range")
    node_index = list(node_names).index(node)
    selected = canonical[:, track, node_index, :]

    if point_scores is None:
        confidence = np.ones(canonical.shape[0], dtype=float)
    else:
        score_values = np.asarray(point_scores, dtype=float)
        score_order = score_dims or tuple(name for name in dims if name != "xy")
        if set(score_order) != {"frame", "track", "node"}:
            raise ValueError("score_dims must contain frame, track, and node")
        if score_values.ndim != 3:
            raise ValueError("point_scores must be three-dimensional")
        canonical_scores = np.moveaxis(
            score_values,
            [score_order.index(name) for name in ("frame", "track", "node")],
            range(3),
        )
        if canonical_scores.shape != canonical.shape[:3]:
            raise ValueError("point_scores dimensions must match tracks")
        confidence = canonical_scores[:, track, node_index]
    time = _time_from_fps(canonical.shape[0], time_s=time_s, fps=fps)
    return PoseTrajectory(
        subject=subject,
        session=session,
        keypoint=node,
        time_s=time,
        x=selected[:, 0],
        y=selected[:, 1],
        confidence=confidence,
        coordinate_unit=coordinate_unit,
        source="sleap",
        clock_id=clock_id,
        individual=str(track),
        source_version=source_version,
        source_artifact=source_artifact,
    )


def pose_from_sleap_analysis_h5(
    path: str | Path,
    *,
    subject: str,
    session: str,
    node: str,
    time_s: ArrayLike | None = None,
    fps: float | None = None,
    track: int = 0,
    dims: tuple[str, str, str, str] | None = None,
    score_dims: tuple[str, str, str] | None = None,
    coordinate_unit: str = "px",
    clock_id: str = "video",
    source_version: str | None = None,
) -> PoseTrajectory:
    """Read one node from a SLEAP Analysis HDF5 file."""

    try:
        import h5py  # type: ignore[import-untyped]
    except ImportError as error:  # pragma: no cover - depends on optional install
        raise ImportError(
            "SLEAP file input requires the 'behavior' optional dependency"
        ) from error
    source = Path(path)
    with h5py.File(source, "r") as file:
        tracks = file["tracks"][:]
        node_names = [_decode_text(value) for value in file["node_names"][:]]
        point_scores = file["point_scores"][:] if "point_scores" in file else None
        stored_dims = _hdf5_dims(file["tracks"].attrs.get("dims"))
        stored_score_dims = (
            _hdf5_dims(file["point_scores"].attrs.get("dims"))
            if "point_scores" in file
            else None
        )
    selected_dims = dims or stored_dims
    if selected_dims is None or len(selected_dims) != 4:
        raise ValueError(
            "SLEAP file has no usable tracks dimension metadata; declare dims"
        )
    selected_score_dims = score_dims or stored_score_dims
    return pose_from_sleap(
        tracks,
        subject=subject,
        session=session,
        node_names=node_names,
        node=node,
        dims=(
            selected_dims[0],
            selected_dims[1],
            selected_dims[2],
            selected_dims[3],
        ),
        time_s=time_s,
        fps=fps,
        track=track,
        point_scores=point_scores,
        score_dims=(
            (
                selected_score_dims[0],
                selected_score_dims[1],
                selected_score_dims[2],
            )
            if selected_score_dims is not None
            else None
        ),
        coordinate_unit=coordinate_unit,
        clock_id=clock_id,
        source_version=source_version,
        source_artifact=str(source),
    )


def _decode_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _hdf5_dims(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, (np.ndarray, list, tuple)):
        items = value.tolist() if isinstance(value, np.ndarray) else value
        return tuple(_decode_text(item) for item in items)
    decoded = _decode_text(value)
    if decoded.startswith("["):
        import json

        loaded = json.loads(decoded)
        if not isinstance(loaded, list) or not all(
            isinstance(item, str) for item in loaded
        ):
            raise ValueError("HDF5 dims attribute must be a JSON string list")
        return tuple(loaded)
    raise ValueError("HDF5 dims attribute has an unsupported representation")


def annotations_from_moseq(
    syllable: Sequence[int],
    *,
    subject: str,
    session: str,
    fps: float,
    labels: Mapping[int, str] | None = None,
    clock_id: str = "video",
    source_version: str | None = None,
    source_artifact: str | None = None,
) -> BehaviorAnnotations:
    """Run-length encode a Keypoint-MoSeq syllable sequence as bouts."""

    states = np.asarray(syllable)
    if states.ndim != 1 or len(states) == 0:
        raise ValueError("syllable must be a non-empty one-dimensional sequence")
    if states.dtype.kind not in "iu":
        raise TypeError("syllable must contain integer state labels")
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be finite and positive")
    changes = np.flatnonzero(np.diff(states) != 0) + 1
    starts = np.concatenate(([0], changes))
    stops = np.concatenate((changes, [len(states)]))
    intervals = tuple(
        BehaviorInterval(
            label=(labels or {}).get(
                int(states[start]), f"syllable_{int(states[start])}"
            ),
            start_s=float(start / fps),
            stop_s=float(stop / fps),
        )
        for start, stop in zip(starts, stops, strict=True)
    )
    return BehaviorAnnotations(
        subject=subject,
        session=session,
        point_events={},
        intervals=intervals,
        source="keypoint-moseq",
        clock_id=clock_id,
        source_version=source_version,
        source_artifact=source_artifact,
    )


def annotations_from_moseq_results_h5(
    path: str | Path,
    *,
    recording: str,
    subject: str,
    session: str,
    fps: float,
    labels: Mapping[int, str] | None = None,
    clock_id: str = "video",
    source_version: str | None = None,
) -> BehaviorAnnotations:
    """Read a recording's syllable sequence from Keypoint-MoSeq results HDF5."""

    try:
        import h5py
    except ImportError as error:  # pragma: no cover - depends on optional install
        raise ImportError(
            "Keypoint-MoSeq file input requires the 'behavior' optional dependency"
        ) from error
    source = Path(path)
    with h5py.File(source, "r") as file:
        dataset = f"{recording}/syllable"
        if dataset not in file:
            raise ValueError(
                f"Keypoint-MoSeq results have no syllable dataset {dataset!r}"
            )
        syllable = file[dataset][:]
    return annotations_from_moseq(
        syllable,
        subject=subject,
        session=session,
        fps=fps,
        labels=labels,
        clock_id=clock_id,
        source_version=source_version,
        source_artifact=str(source),
    )


def annotations_from_boris(
    columns: Mapping[str, Sequence[Any]],
    *,
    subject: str,
    session: str,
    behavior_column: str,
    type_column: str,
    start_column: str,
    stop_column: str,
    clock_id: str = "video",
    source_version: str | None = None,
    source_artifact: str | None = None,
) -> BehaviorAnnotations:
    """Convert an aggregated BORIS export after explicit column selection."""

    required = (behavior_column, type_column, start_column, stop_column)
    missing = [name for name in required if name not in columns]
    if missing:
        raise ValueError(f"BORIS export is missing columns: {missing}")
    lengths = {len(columns[name]) for name in required}
    if len(lengths) != 1:
        raise ValueError("selected BORIS columns must have equal length")
    points: dict[str, list[float]] = {}
    intervals: list[BehaviorInterval] = []
    for index in range(next(iter(lengths))):
        label = str(columns[behavior_column][index]).strip()
        kind = str(columns[type_column][index]).strip().upper()
        start = float(columns[start_column][index])
        if kind == "POINT":
            points.setdefault(label, []).append(start)
        elif kind == "STATE":
            stop = float(columns[stop_column][index])
            intervals.append(BehaviorInterval(label, start, stop))
        else:
            raise ValueError(
                f"BORIS row {index} has unsupported behavior type {kind!r}"
            )
    return BehaviorAnnotations(
        subject=subject,
        session=session,
        point_events={label: tuple(times) for label, times in points.items()},
        intervals=tuple(intervals),
        source="boris",
        clock_id=clock_id,
        source_version=source_version,
        source_artifact=source_artifact,
    )


def annotations_from_boris_tabular_file(
    path: str | Path,
    *,
    subject: str,
    session: str,
    source_subject: str | None = None,
    clock_id: str = "video",
    source_version: str | None = None,
) -> BehaviorAnnotations:
    """Read BORIS tabular CSV, pairing START/STOP state-event rows."""

    source = Path(path)
    with source.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.reader(stream))
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if {"Time", "Subject", "Behavior", "Status"} <= set(row)
        ),
        None,
    )
    if header_index is None:
        raise ValueError("BORIS tabular CSV has no Time/Subject/Behavior/Status header")
    header = rows[header_index]
    records = [
        dict(zip(header, row, strict=False))
        for row in rows[header_index + 1 :]
        if any(value.strip() for value in row)
    ]
    observed_subjects = sorted(
        {record.get("Subject", "").strip() for record in records}
    )
    observed_subjects = [value for value in observed_subjects if value]
    selected_subject = source_subject
    if selected_subject is None:
        if len(observed_subjects) != 1:
            raise ValueError(
                "BORIS tabular CSV contains multiple subjects; declare source_subject"
            )
        selected_subject = observed_subjects[0]
    if selected_subject not in observed_subjects:
        raise ValueError(f"BORIS source_subject {selected_subject!r} was not found")

    points: dict[str, list[float]] = {}
    intervals: list[BehaviorInterval] = []
    open_states: dict[str, float] = {}
    for record in records:
        if record.get("Subject", "").strip() != selected_subject:
            continue
        label = record.get("Behavior", "").strip()
        status = record.get("Status", "").strip().upper()
        time = float(record.get("Time", "nan"))
        if not label or not np.isfinite(time):
            raise ValueError("BORIS event rows require finite time and behavior")
        if status == "START":
            if label in open_states:
                raise ValueError(f"BORIS state {label!r} has consecutive START rows")
            open_states[label] = time
        elif status == "STOP":
            try:
                start = open_states.pop(label)
            except KeyError:
                raise ValueError(
                    f"BORIS state {label!r} has STOP without START"
                ) from None
            intervals.append(BehaviorInterval(label, start, time))
        elif status in {"", "POINT"}:
            points.setdefault(label, []).append(time)
        else:
            raise ValueError(f"unsupported BORIS tabular status {status!r}")
    if open_states:
        raise ValueError(f"BORIS states have START without STOP: {sorted(open_states)}")
    return BehaviorAnnotations(
        subject=subject,
        session=session,
        point_events={label: tuple(times) for label, times in points.items()},
        intervals=tuple(intervals),
        source="boris",
        clock_id=clock_id,
        source_version=source_version,
        source_artifact=str(source),
    )
