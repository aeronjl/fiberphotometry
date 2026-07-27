"""Prospective optogenetic artifact masks and observed recovery diagnostics."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class StimulationPulse:
    """One declared stimulation interval in the photometry signal clock."""

    pulse_id: str
    onset_s: float
    offset_s: float
    site: str
    wavelength_nm: float | None = None
    power_mw: float | None = None

    def __post_init__(self) -> None:
        for name in ("pulse_id", "site"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        if not np.isfinite(self.onset_s) or not np.isfinite(self.offset_s):
            raise ValueError("stimulation pulse times must be finite")
        if self.offset_s < self.onset_s:
            raise ValueError("stimulation pulse offset cannot precede onset")
        for name in ("wavelength_nm", "power_mw"):
            value = getattr(self, name)
            if value is not None and (not np.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive when supplied")


@dataclass(frozen=True)
class OptogeneticMaskSpec:
    """Prospective time-only exclusion policy around stimulation intervals."""

    pre_pulse_s: float = 0.01
    post_pulse_s: float = 0.20

    def __post_init__(self) -> None:
        if not np.isfinite(self.pre_pulse_s) or self.pre_pulse_s < 0:
            raise ValueError("pre_pulse_s must be finite and non-negative")
        if not np.isfinite(self.post_pulse_s) or self.post_pulse_s < 0:
            raise ValueError("post_pulse_s must be finite and non-negative")


@dataclass(frozen=True)
class OptogeneticMaskedInterval:
    """One merged exclusion interval and the pulses that generated it."""

    start_s: float
    stop_s: float
    pulse_ids: tuple[str, ...]
    sample_count: int
    clipped_at_recording_start: bool
    clipped_at_recording_stop: bool


@dataclass(frozen=True)
class OptogeneticArtifactMask:
    """A reusable boolean validity mask with complete pulse-time provenance."""

    spec: OptogeneticMaskSpec
    pulses: tuple[StimulationPulse, ...]
    artifact_mask: tuple[bool, ...]
    valid_mask: tuple[bool, ...]
    intervals: tuple[OptogeneticMaskedInterval, ...]
    total_sample_count: int
    originally_invalid_sample_count: int
    artifact_sample_count: int
    newly_invalid_sample_count: int
    retained_sample_count: int
    retained_fraction: float
    mask_fingerprint: str
    method: str = "prospective_pulse_interval_expansion"
    schema_version: str = "1"

    @property
    def valid_array(self) -> NDArray[np.bool_]:
        """Return a copy suitable for downstream ``valid`` arguments."""
        return np.asarray(self.valid_mask, dtype=bool)

    @property
    def artifact_array(self) -> NDArray[np.bool_]:
        """Return a copy marking stimulation-artifact samples."""
        return np.asarray(self.artifact_mask, dtype=bool)

    def to_json(self) -> str:
        """Serialize the mask, pulse ledger, and effective denominator."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class OptogeneticRecoverySpec:
    """Observed artifact and recovery measurements that never alter the mask."""

    baseline_duration_s: float = 0.5
    baseline_guard_s: float = 0.02
    assessment_duration_s: float = 1.0
    recovery_threshold_sd: float = 3.0
    stable_duration_s: float = 0.05
    minimum_baseline_samples: int = 10
    control_artifact_threshold_sd: float = 5.0
    detector_floor: float | None = None
    detector_ceiling: float | None = None
    saturation_tolerance: float = 0.0

    def __post_init__(self) -> None:
        positives = (
            ("baseline_duration_s", self.baseline_duration_s),
            ("assessment_duration_s", self.assessment_duration_s),
            ("recovery_threshold_sd", self.recovery_threshold_sd),
            ("stable_duration_s", self.stable_duration_s),
            ("control_artifact_threshold_sd", self.control_artifact_threshold_sd),
        )
        for name, value in positives:
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not np.isfinite(self.baseline_guard_s) or self.baseline_guard_s < 0:
            raise ValueError("baseline_guard_s must be finite and non-negative")
        if self.minimum_baseline_samples < 3:
            raise ValueError("minimum_baseline_samples must be at least three")
        if (self.detector_floor is None) != (self.detector_ceiling is None):
            raise ValueError(
                "detector_floor and detector_ceiling must be supplied together"
            )
        if self.detector_floor is not None:
            assert self.detector_ceiling is not None
            if not (
                np.isfinite(self.detector_floor)
                and np.isfinite(self.detector_ceiling)
                and self.detector_floor < self.detector_ceiling
            ):
                raise ValueError("detector bounds must be finite and increasing")
        if not np.isfinite(self.saturation_tolerance) or self.saturation_tolerance < 0:
            raise ValueError("saturation_tolerance must be finite and non-negative")


@dataclass(frozen=True)
class PulseRecoveryDiagnostic:
    """Observed signal and optional negative-control behavior around one pulse."""

    pulse_id: str
    pulse_onset_s: float
    pulse_offset_s: float
    baseline_sample_count: int
    baseline_median: float
    baseline_robust_sd: float
    assessment_stop_s: float
    censored_by_next_pulse: bool
    peak_absolute_deviation_sd: float
    peak_time_from_onset_s: float
    recovered: bool
    recovery_time_from_offset_s: float | None
    stable_sample_count_required: int
    saturation_fraction: float | None
    control_peak_absolute_deviation_sd: float | None
    control_recovered: bool | None
    control_recovery_time_from_offset_s: float | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OptogeneticArtifactAssessment:
    """Pulse-level recovery evidence that remains separate from mask construction."""

    spec: OptogeneticRecoverySpec
    pulses: tuple[StimulationPulse, ...]
    diagnostics: tuple[PulseRecoveryDiagnostic, ...]
    negative_control_name: str | None
    valid_sample_count: int
    warnings: tuple[str, ...]
    interpretation: str = (
        "observed_recovery_is_diagnostic_only_and_does_not_modify_the_mask"
    )
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize pulse-level recovery and control evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_optogenetic_artifact_mask(
    time: ArrayLike,
    pulses: tuple[StimulationPulse, ...] | list[StimulationPulse],
    spec: OptogeneticMaskSpec | None = None,
    *,
    existing_valid: ArrayLike | None = None,
) -> OptogeneticArtifactMask:
    """Build a fixed mask from pulse timing without inspecting signal outcomes."""
    spec = spec or OptogeneticMaskSpec()
    time_values = _validate_time(time)
    ordered = _validate_pulses(pulses)
    original_valid = _valid_mask(existing_valid, len(time_values))
    expanded = [
        (pulse.onset_s - spec.pre_pulse_s, pulse.offset_s + spec.post_pulse_s, pulse)
        for pulse in ordered
    ]
    merged = _merge_expanded_intervals(expanded)
    artifact = np.zeros(len(time_values), dtype=bool)
    intervals = []
    for start, stop, pulse_ids in merged:
        selected = (time_values >= start) & (time_values <= stop)
        artifact |= selected
        intervals.append(
            OptogeneticMaskedInterval(
                start,
                stop,
                pulse_ids,
                int(np.count_nonzero(selected)),
                bool(start < time_values[0]),
                bool(stop > time_values[-1]),
            )
        )
    valid = original_valid & ~artifact
    fingerprint = _mask_fingerprint(
        time_values, ordered, spec, artifact, original_valid
    )
    return OptogeneticArtifactMask(
        spec,
        ordered,
        tuple(map(bool, artifact.tolist())),
        tuple(map(bool, valid.tolist())),
        tuple(intervals),
        len(time_values),
        int(np.count_nonzero(~original_valid)),
        int(np.count_nonzero(artifact)),
        int(np.count_nonzero(original_valid & artifact)),
        int(np.count_nonzero(valid)),
        float(np.mean(valid)),
        fingerprint,
    )


def assess_optogenetic_artifacts(
    time: ArrayLike,
    signal_values: ArrayLike,
    pulses: tuple[StimulationPulse, ...] | list[StimulationPulse],
    spec: OptogeneticRecoverySpec | None = None,
    *,
    valid: ArrayLike | None = None,
    negative_control: ArrayLike | None = None,
    negative_control_name: str | None = None,
) -> OptogeneticArtifactAssessment:
    """Measure pulse artifacts, recovery, saturation, and negative-control behavior."""
    spec = spec or OptogeneticRecoverySpec()
    time_values = _validate_time(time)
    values = _validate_values(signal_values, len(time_values), "signal_values")
    ordered = _validate_pulses(pulses)
    sample_valid = _valid_mask(valid, len(time_values)) & np.isfinite(values)
    control: NDArray[np.float64] | None = None
    if negative_control is not None:
        control = _validate_values(
            negative_control, len(time_values), "negative_control"
        )
        sample_valid &= np.isfinite(control)
        negative_control_name = str(negative_control_name or "negative_control").strip()
        if not negative_control_name:
            raise ValueError("negative_control_name must be non-empty")
    elif negative_control_name is not None:
        raise ValueError("negative_control_name requires negative_control values")
    interval = float(np.median(np.diff(time_values)))
    stable_samples = max(1, round(spec.stable_duration_s / interval))
    diagnostics = []
    for index, pulse in enumerate(ordered):
        previous_offset = ordered[index - 1].offset_s if index > 0 else None
        next_onset = ordered[index + 1].onset_s if index + 1 < len(ordered) else None
        assessment_stop = pulse.offset_s + spec.assessment_duration_s
        censored = next_onset is not None and next_onset < assessment_stop
        if censored:
            assert next_onset is not None
            assessment_stop = next_onset
        diagnostic = _assess_pulse(
            time_values,
            values,
            control,
            sample_valid,
            pulse,
            previous_offset,
            assessment_stop,
            censored,
            stable_samples,
            spec,
        )
        diagnostics.append(diagnostic)
    warnings = tuple(
        sorted({warning for item in diagnostics for warning in item.warnings})
    )
    return OptogeneticArtifactAssessment(
        spec,
        ordered,
        tuple(diagnostics),
        negative_control_name,
        int(np.count_nonzero(sample_valid)),
        warnings,
    )


def _assess_pulse(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    control: NDArray[np.float64] | None,
    valid: NDArray[np.bool_],
    pulse: StimulationPulse,
    previous_offset_s: float | None,
    assessment_stop: float,
    censored: bool,
    stable_samples: int,
    spec: OptogeneticRecoverySpec,
) -> PulseRecoveryDiagnostic:
    baseline_selected = (
        (time >= pulse.onset_s - spec.baseline_duration_s)
        & (time < pulse.onset_s - spec.baseline_guard_s)
        & valid
    )
    baseline = values[baseline_selected]
    warnings = []
    if (
        previous_offset_s is not None
        and previous_offset_s > pulse.onset_s - spec.baseline_duration_s
    ):
        warnings.append("baseline_overlaps_previous_pulse")
    if len(baseline) < spec.minimum_baseline_samples:
        warnings.append("insufficient_pre_pulse_baseline")
        return PulseRecoveryDiagnostic(
            pulse.pulse_id,
            pulse.onset_s,
            pulse.offset_s,
            len(baseline),
            float("nan"),
            float("nan"),
            assessment_stop,
            censored,
            float("nan"),
            float("nan"),
            False,
            None,
            stable_samples,
            None,
            None,
            None,
            None,
            tuple(warnings),
        )
    baseline_median, baseline_scale = _robust_location_scale(baseline)
    before_stop = time < assessment_stop if censored else time <= assessment_stop
    assessment_selected = (time >= pulse.onset_s) & before_stop & valid
    assessment_indices = np.flatnonzero(assessment_selected)
    assessment = values[assessment_indices]
    standardized = np.abs(assessment - baseline_median) / baseline_scale
    if len(standardized):
        peak_index = int(np.argmax(standardized))
        peak = float(standardized[peak_index])
        peak_time = float(time[assessment_indices[peak_index]] - pulse.onset_s)
    else:
        peak = peak_time = float("nan")
    recovery_selected = (time >= pulse.offset_s) & before_stop & valid
    recovery_indices = np.flatnonzero(recovery_selected)
    recovery = _recovery_time(
        time[recovery_indices],
        values[recovery_indices],
        baseline_median,
        baseline_scale,
        pulse.offset_s,
        spec.recovery_threshold_sd,
        stable_samples,
    )
    if recovery is None:
        warnings.append(
            "recovery_censored_by_next_pulse" if censored else "not_recovered_in_window"
        )
    saturation = _saturation_fraction(assessment, spec)
    if saturation is not None and saturation > 0:
        warnings.append("detector_saturation_during_assessment")

    control_peak: float | None = None
    control_recovery: float | None = None
    control_recovered: bool | None = None
    if control is not None:
        control_baseline = control[baseline_selected]
        control_median, control_scale = _robust_location_scale(control_baseline)
        control_assessment = control[assessment_indices]
        control_peak = (
            float(np.max(np.abs(control_assessment - control_median) / control_scale))
            if len(control_assessment)
            else float("nan")
        )
        control_recovery = _recovery_time(
            time[recovery_indices],
            control[recovery_indices],
            control_median,
            control_scale,
            pulse.offset_s,
            spec.recovery_threshold_sd,
            stable_samples,
        )
        control_recovered = control_recovery is not None
        if (
            np.isfinite(control_peak)
            and control_peak >= spec.control_artifact_threshold_sd
        ):
            warnings.append("large_negative_control_artifact")
    return PulseRecoveryDiagnostic(
        pulse.pulse_id,
        pulse.onset_s,
        pulse.offset_s,
        len(baseline),
        baseline_median,
        baseline_scale,
        assessment_stop,
        censored,
        peak,
        peak_time,
        recovery is not None,
        recovery,
        stable_samples,
        saturation,
        control_peak,
        control_recovered,
        control_recovery,
        tuple(warnings),
    )


def _recovery_time(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    baseline: float,
    scale: float,
    offset_s: float,
    threshold_sd: float,
    stable_samples: int,
) -> float | None:
    within = np.abs(values - baseline) <= threshold_sd * scale
    if len(within) < stable_samples:
        return None
    convolution = np.convolve(
        within.astype(int), np.ones(stable_samples, dtype=int), mode="valid"
    )
    candidates = np.flatnonzero(convolution == stable_samples)
    return float(time[candidates[0]] - offset_s) if len(candidates) else None


def _robust_location_scale(values: NDArray[np.float64]) -> tuple[float, float]:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    scale = max(1.4826 * mad, float(np.std(values)), np.finfo(float).eps)
    return median, scale


def _saturation_fraction(
    values: NDArray[np.float64], spec: OptogeneticRecoverySpec
) -> float | None:
    if spec.detector_floor is None or spec.detector_ceiling is None:
        return None
    saturated = (values <= spec.detector_floor + spec.saturation_tolerance) | (
        values >= spec.detector_ceiling - spec.saturation_tolerance
    )
    return float(np.mean(saturated)) if len(values) else float("nan")


def _merge_expanded_intervals(
    expanded: list[tuple[float, float, StimulationPulse]],
) -> list[tuple[float, float, tuple[str, ...]]]:
    if not expanded:
        return []
    output: list[tuple[float, float, tuple[str, ...]]] = []
    start, stop, first = expanded[0]
    identifiers = [first.pulse_id]
    for next_start, next_stop, pulse in expanded[1:]:
        if next_start <= stop:
            stop = max(stop, next_stop)
            identifiers.append(pulse.pulse_id)
        else:
            output.append((start, stop, tuple(identifiers)))
            start, stop, identifiers = next_start, next_stop, [pulse.pulse_id]
    output.append((start, stop, tuple(identifiers)))
    return output


def _mask_fingerprint(
    time: NDArray[np.float64],
    pulses: tuple[StimulationPulse, ...],
    spec: OptogeneticMaskSpec,
    artifact: NDArray[np.bool_],
    original_valid: NDArray[np.bool_],
) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(time, dtype="<f8").tobytes())
    digest.update(np.asarray(artifact, dtype=np.uint8).tobytes())
    digest.update(np.asarray(original_valid, dtype=np.uint8).tobytes())
    digest.update(
        json.dumps(
            {"pulses": [asdict(item) for item in pulses], "spec": asdict(spec)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    return digest.hexdigest()


def _validate_time(time: ArrayLike) -> NDArray[np.float64]:
    values = np.asarray(time, dtype=float)
    if values.ndim != 1 or len(values) < 3:
        raise ValueError("time must contain three or more samples")
    if not np.all(np.isfinite(values)) or not np.all(np.diff(values) > 0):
        raise ValueError("time must be finite and strictly increasing")
    return values


def _validate_values(values: ArrayLike, length: int, name: str) -> NDArray[np.float64]:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) != length:
        raise ValueError(f"{name} must be one-dimensional and match time")
    return array


def _valid_mask(valid: ArrayLike | None, length: int) -> NDArray[np.bool_]:
    if valid is None:
        return np.ones(length, dtype=bool)
    mask = np.asarray(valid, dtype=bool)
    if mask.ndim != 1 or len(mask) != length:
        raise ValueError("existing validity must be one-dimensional and match time")
    return mask


def _validate_pulses(
    pulses: tuple[StimulationPulse, ...] | list[StimulationPulse],
) -> tuple[StimulationPulse, ...]:
    if not pulses:
        raise ValueError("optogenetic artifact handling requires at least one pulse")
    ordered = tuple(sorted(pulses, key=lambda item: (item.onset_s, item.offset_s)))
    identifiers = [item.pulse_id for item in ordered]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("stimulation pulse IDs must be unique")
    return ordered
