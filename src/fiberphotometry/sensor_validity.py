"""Extensible sensor profiles and isosbestic-aware validity diagnostics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import signal as scipy_signal

from fiberphotometry.multisignal import (
    AlignmentPolicy,
    ChannelIdentity,
    _cross_correlation,
    _prepare_pair,
)
from fiberphotometry.spectral import GapHandlingSpec

ValiditySeverity: TypeAlias = Literal["warning", "error"]
ValidityStatus: TypeAlias = Literal["pass", "warning", "fail"]


@dataclass(frozen=True)
class WavelengthRange:
    """Inclusive wavelength range in nanometres."""

    minimum_nm: float
    maximum_nm: float

    def __post_init__(self) -> None:
        if not (
            np.isfinite(self.minimum_nm)
            and np.isfinite(self.maximum_nm)
            and 0 < self.minimum_nm <= self.maximum_nm
        ):
            raise ValueError(
                "wavelength range must be finite, positive, and increasing"
            )

    def contains(self, wavelength_nm: float) -> bool:
        """Return whether a wavelength lies inside the inclusive range."""
        return self.minimum_nm <= wavelength_nm <= self.maximum_nm


@dataclass(frozen=True)
class SensorKinetics:
    """Context-specific kinetic evidence retained for interpretation constraints."""

    rise_time_s: float
    decay_time_s: float
    measurement_context: str
    evidence_source: str

    def __post_init__(self) -> None:
        if not np.isfinite(self.rise_time_s) or self.rise_time_s <= 0:
            raise ValueError("rise_time_s must be finite and positive")
        if not np.isfinite(self.decay_time_s) or self.decay_time_s <= 0:
            raise ValueError("decay_time_s must be finite and positive")
        if not self.measurement_context.strip() or not self.evidence_source.strip():
            raise ValueError("kinetic context and evidence source must be non-empty")


@dataclass(frozen=True)
class SensorProfile:
    """Versioned, user-extensible optical and interpretation contract for a sensor."""

    profile_id: str
    sensor_name: str
    profile_version: str
    signal_excitation_nm: WavelengthRange
    emission_nm: WavelengthRange | None
    isosbestic_excitation_nm: WavelengthRange | None
    interpretation: str
    evidence_source: str
    kinetics: SensorKinetics | None = None
    linear_response_range: tuple[float, float] | None = None
    linear_response_unit: str | None = None
    constraints: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "profile_id",
            "sensor_name",
            "profile_version",
            "interpretation",
            "evidence_source",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        if (self.linear_response_range is None) != (self.linear_response_unit is None):
            raise ValueError(
                "linear_response_range and linear_response_unit must be supplied "
                "together"
            )
        if self.linear_response_range is not None:
            low, high = self.linear_response_range
            if not np.isfinite(low) or not np.isfinite(high) or low >= high:
                raise ValueError("linear_response_range must be finite and increasing")
            assert self.linear_response_unit is not None
            if not self.linear_response_unit.strip():
                raise ValueError("linear_response_unit must be non-empty")
        cleaned_constraints = tuple(str(value).strip() for value in self.constraints)
        if any(not value for value in cleaned_constraints):
            raise ValueError("sensor constraints must be non-empty")
        object.__setattr__(self, "constraints", cleaned_constraints)
        cleaned_metadata = tuple(
            (str(key).strip(), str(value).strip()) for key, value in self.metadata
        )
        if any(not key or not value for key, value in cleaned_metadata):
            raise ValueError("sensor metadata keys and values must be non-empty")
        if len({key for key, _ in cleaned_metadata}) != len(cleaned_metadata):
            raise ValueError("sensor metadata keys must be unique")
        object.__setattr__(self, "metadata", cleaned_metadata)


@dataclass(frozen=True)
class SensorRegistry:
    """Immutable collection of versioned profiles without a closed sensor enum."""

    profiles: tuple[SensorProfile, ...] = ()

    def __post_init__(self) -> None:
        keys = [(item.profile_id, item.profile_version) for item in self.profiles]
        if len(set(keys)) != len(keys):
            raise ValueError("sensor registry profile ID/version pairs must be unique")

    def with_profile(self, profile: SensorProfile) -> SensorRegistry:
        """Return a new registry containing one additional profile."""
        return SensorRegistry((*self.profiles, profile))

    def resolve(
        self, profile_id: str, profile_version: str | None = None
    ) -> SensorProfile:
        """Resolve one profile, refusing an ambiguous version."""
        matches = [item for item in self.profiles if item.profile_id == profile_id]
        if profile_version is not None:
            matches = [
                item for item in matches if item.profile_version == profile_version
            ]
        if not matches:
            raise KeyError("sensor profile was not found")
        if len(matches) > 1:
            raise KeyError(
                "sensor profile version is ambiguous; specify profile_version"
            )
        return matches[0]

    def to_json(self) -> str:
        """Serialize registry content without requiring package-owned profiles."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class SensorChannelAssignment:
    """Attach session identity and optional reference pairing to a sensor channel."""

    subject: str
    session: str
    signal: ChannelIdentity
    reference: ChannelIdentity | None
    clock_id: str
    alignment_policy: AlignmentPolicy
    preprocessing_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "subject",
            "session",
            "clock_id",
            "preprocessing_fingerprint",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        if self.reference is not None and (
            self.reference.channel_id == self.signal.channel_id
        ):
            raise ValueError("sensor signal and reference channel IDs must differ")
        if self.alignment_policy not in {
            "native_shared_clock",
            "explicitly_resampled",
        }:
            raise ValueError("unsupported sensor alignment policy")


@dataclass(frozen=True)
class SensorValiditySpec:
    """Operational thresholds for metadata, channel, and reference review."""

    minimum_finite_fraction_warning: float = 0.95
    minimum_finite_fraction_error: float = 0.80
    maximum_repeated_extreme_fraction_warning: float = 0.01
    maximum_repeated_extreme_fraction_error: float = 0.05
    maximum_flat_step_fraction_warning: float = 0.01
    maximum_flat_step_fraction_error: float = 0.10
    maximum_saturation_fraction_warning: float = 0.001
    maximum_saturation_fraction_error: float = 0.01
    maximum_out_of_profile_fraction_warning: float = 0.001
    maximum_out_of_profile_fraction_error: float = 0.01
    minimum_reference_sd_ratio: float = 0.01
    maximum_reference_sd_ratio: float = 100.0
    weak_reference_correlation: float = 0.10
    maximum_reference_lag_s: float = 0.10
    minimum_lag_improvement: float = 0.05
    maximum_reference_event_effect_sd: float = 0.50
    event_baseline: tuple[float, float] = (-0.5, 0.0)
    event_response: tuple[float, float] = (0.0, 0.5)
    detector_floor: float | None = None
    detector_ceiling: float | None = None
    saturation_tolerance: float = 0.0
    require_wavelength_metadata: bool = True
    require_isosbestic: bool = False
    gap: GapHandlingSpec = field(default_factory=GapHandlingSpec)

    def __post_init__(self) -> None:
        _validate_nested_minimum(
            self.minimum_finite_fraction_error,
            self.minimum_finite_fraction_warning,
            "finite fraction",
        )
        for warning, error, name in (
            (
                self.maximum_repeated_extreme_fraction_warning,
                self.maximum_repeated_extreme_fraction_error,
                "repeated extreme fraction",
            ),
            (
                self.maximum_flat_step_fraction_warning,
                self.maximum_flat_step_fraction_error,
                "flat step fraction",
            ),
            (
                self.maximum_saturation_fraction_warning,
                self.maximum_saturation_fraction_error,
                "saturation fraction",
            ),
            (
                self.maximum_out_of_profile_fraction_warning,
                self.maximum_out_of_profile_fraction_error,
                "out-of-profile fraction",
            ),
        ):
            _validate_nested_maximum(warning, error, name)
        if not 0 <= self.weak_reference_correlation <= 1:
            raise ValueError("weak_reference_correlation must lie between zero and one")
        for name in (
            "minimum_reference_sd_ratio",
            "maximum_reference_sd_ratio",
            "maximum_reference_lag_s",
            "minimum_lag_improvement",
            "maximum_reference_event_effect_sd",
        ):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.minimum_reference_sd_ratio >= self.maximum_reference_sd_ratio:
            raise ValueError("reference SD ratio thresholds must be increasing")
        if self.event_baseline[0] >= self.event_baseline[1]:
            raise ValueError("event_baseline must be increasing")
        if self.event_response[0] >= self.event_response[1]:
            raise ValueError("event_response must be increasing")
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
class ChannelValidityMetrics:
    """Observable validity metrics for one optical channel."""

    channel_id: str
    sample_count: int
    finite_fraction: float
    standard_deviation: float
    repeated_extreme_fraction: float
    flat_step_fraction: float
    saturation_fraction: float | None
    outside_profile_fraction: float | None


@dataclass(frozen=True)
class IsosbesticValidityMetrics:
    """Pairwise timing and event diagnostics for a declared reference channel."""

    paired_sample_count: int
    signal_reference_correlation: float
    reference_to_signal_sd_ratio: float
    derivative_zero_lag_correlation: float
    derivative_best_lag_correlation: float
    derivative_best_lag_s: float
    derivative_lag_improvement: float
    valid_event_count: int
    reference_event_effect_sd: float | None


@dataclass(frozen=True)
class SensorValidityIssue:
    """One actionable metadata or observed-signal validity concern."""

    severity: ValiditySeverity
    code: str
    channel_id: str
    message: str
    value: float | str | None = None


@dataclass(frozen=True)
class SensorValidityAssessment:
    """Versioned sensor profile, metrics, issues, and interpretation boundary."""

    profile: SensorProfile
    assignment: SensorChannelAssignment
    spec: SensorValiditySpec
    signal_metrics: ChannelValidityMetrics
    reference_metrics: ChannelValidityMetrics | None
    isosbestic_metrics: IsosbesticValidityMetrics | None
    issues: tuple[SensorValidityIssue, ...]
    status: ValidityStatus
    interpretation_constraints: tuple[str, ...]
    interpretation: str = (
        "metadata_and_diagnostics_cannot_prove_biological_inertness_or_concentration"
    )
    schema_version: str = "1"

    def require_ready(self, *, allow_warnings: bool = True) -> None:
        """Refuse failed evidence and optionally warning-bearing evidence."""
        if self.status == "fail":
            raise ValueError("sensor validity assessment failed")
        if self.status == "warning" and not allow_warnings:
            raise ValueError("sensor validity assessment contains warnings")

    def to_json(self) -> str:
        """Serialize profile, diagnostics, and explicit interpretation limits."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def assess_sensor_validity(
    time: ArrayLike,
    signal_values: ArrayLike,
    assignment: SensorChannelAssignment,
    profile: SensorProfile,
    spec: SensorValiditySpec | None = None,
    *,
    reference_values: ArrayLike | None = None,
    signal_valid: ArrayLike | None = None,
    reference_valid: ArrayLike | None = None,
    event_times: ArrayLike | None = None,
) -> SensorValidityAssessment:
    """Assess declared sensor/reference semantics and observable validity evidence."""
    spec = spec or SensorValiditySpec()
    time_values = _validate_time(time)
    signal_array = _validate_values(signal_values, len(time_values), "signal_values")
    signal_mask = _valid_mask(signal_valid, len(time_values))
    if (assignment.reference is None) != (reference_values is None):
        raise ValueError(
            "reference metadata and reference_values must either both be supplied "
            "or absent"
        )
    reference_array: NDArray[np.float64] | None = None
    reference_mask: NDArray[np.bool_] | None = None
    if reference_values is not None:
        reference_array = _validate_values(
            reference_values, len(time_values), "reference_values"
        )
        reference_mask = _valid_mask(reference_valid, len(time_values))
    elif reference_valid is not None:
        raise ValueError("reference_valid requires reference_values")
    events = _validate_events(event_times)

    issues: list[SensorValidityIssue] = []
    _assess_profile_metadata(assignment, profile, spec, issues)
    signal_metrics = _channel_metrics(
        signal_array,
        signal_mask,
        assignment.signal,
        profile,
        spec,
    )
    _metric_issues(signal_metrics, spec, issues)
    reference_metrics: ChannelValidityMetrics | None = None
    isosbestic_metrics: IsosbesticValidityMetrics | None = None
    if reference_array is not None and reference_mask is not None:
        assert assignment.reference is not None
        reference_metrics = _channel_metrics(
            reference_array,
            reference_mask,
            assignment.reference,
            None,
            spec,
        )
        _metric_issues(reference_metrics, spec, issues)
        isosbestic_metrics = _isosbestic_metrics(
            time_values,
            signal_array,
            reference_array,
            signal_mask,
            reference_mask,
            events,
            spec,
        )
        _isosbestic_issues(
            isosbestic_metrics, assignment.reference.channel_id, spec, issues
        )
    elif profile.isosbestic_excitation_nm is not None:
        severity: ValiditySeverity = "error" if spec.require_isosbestic else "warning"
        issues.append(
            SensorValidityIssue(
                severity,
                "isosbestic_channel_absent",
                assignment.signal.channel_id,
                "the profile declares an isosbestic range but no paired channel "
                "was supplied",
            )
        )
    status: ValidityStatus = (
        "fail"
        if any(item.severity == "error" for item in issues)
        else "warning"
        if issues
        else "pass"
    )
    constraints = tuple(
        item
        for item in (
            profile.interpretation,
            *profile.constraints,
            (
                f"kinetics measured in {profile.kinetics.measurement_context}: "
                f"rise={profile.kinetics.rise_time_s:g}s, "
                f"decay={profile.kinetics.decay_time_s:g}s"
                if profile.kinetics is not None
                else ""
            ),
        )
        if item
    )
    return SensorValidityAssessment(
        profile,
        assignment,
        spec,
        signal_metrics,
        reference_metrics,
        isosbestic_metrics,
        tuple(issues),
        status,
        constraints,
    )


def _assess_profile_metadata(
    assignment: SensorChannelAssignment,
    profile: SensorProfile,
    spec: SensorValiditySpec,
    issues: list[SensorValidityIssue],
) -> None:
    signal_channel = assignment.signal
    if signal_channel.role != "sensor":
        issues.append(
            SensorValidityIssue(
                "error",
                "signal_role_not_sensor",
                signal_channel.channel_id,
                "the analyzed signal channel is not declared with role='sensor'",
                signal_channel.role,
            )
        )
    if signal_channel.sensor.casefold() != profile.sensor_name.casefold():
        issues.append(
            SensorValidityIssue(
                "error",
                "sensor_profile_mismatch",
                signal_channel.channel_id,
                "channel sensor name does not match the selected profile",
                signal_channel.sensor,
            )
        )
    _check_wavelength(
        signal_channel,
        signal_channel.excitation_wavelength_nm,
        profile.signal_excitation_nm,
        "signal_excitation",
        spec,
        issues,
    )
    if profile.emission_nm is not None:
        _check_wavelength(
            signal_channel,
            signal_channel.emission_wavelength_nm,
            profile.emission_nm,
            "signal_emission",
            spec,
            issues,
        )
    if (
        profile.linear_response_range is not None
        and signal_channel.unit != profile.linear_response_unit
    ):
        issues.append(
            SensorValidityIssue(
                "warning",
                "linear_range_unit_mismatch",
                signal_channel.channel_id,
                "profile linear range cannot be assessed in the channel's unit",
                f"{signal_channel.unit} != {profile.linear_response_unit}",
            )
        )
    reference = assignment.reference
    if reference is None:
        return
    if reference.role not in {"isosbestic", "reference", "control"}:
        issues.append(
            SensorValidityIssue(
                "error",
                "invalid_reference_role",
                reference.channel_id,
                "paired reference must be declared as isosbestic, reference, or "
                "control",
                reference.role,
            )
        )
    if profile.isosbestic_excitation_nm is not None:
        if reference.role != "isosbestic":
            issues.append(
                SensorValidityIssue(
                    "warning",
                    "reference_not_declared_isosbestic",
                    reference.channel_id,
                    "profile has an isosbestic range but the channel role is not "
                    "isosbestic",
                    reference.role,
                )
            )
        if (
            reference.role == "isosbestic"
            and reference.sensor.casefold() != profile.sensor_name.casefold()
        ):
            issues.append(
                SensorValidityIssue(
                    "error",
                    "isosbestic_sensor_profile_mismatch",
                    reference.channel_id,
                    "isosbestic channel sensor does not match the selected profile",
                    reference.sensor,
                )
            )
        _check_wavelength(
            reference,
            reference.excitation_wavelength_nm,
            profile.isosbestic_excitation_nm,
            "isosbestic_excitation",
            spec,
            issues,
        )
    elif reference.role == "isosbestic":
        issues.append(
            SensorValidityIssue(
                "warning",
                "profile_has_no_isosbestic_range",
                reference.channel_id,
                "channel is called isosbestic but the selected profile declares "
                "no range",
            )
        )
    if reference.site != signal_channel.site:
        issues.append(
            SensorValidityIssue(
                "warning",
                "reference_site_mismatch",
                reference.channel_id,
                "signal and reference have different declared sites",
                f"{signal_channel.site} != {reference.site}",
            )
        )
    if (
        reference.fiber_id is not None
        and signal_channel.fiber_id is not None
        and reference.fiber_id != signal_channel.fiber_id
    ):
        issues.append(
            SensorValidityIssue(
                "error",
                "reference_fiber_mismatch",
                reference.channel_id,
                "signal and reference have different declared fibers",
                f"{signal_channel.fiber_id} != {reference.fiber_id}",
            )
        )


def _check_wavelength(
    channel: ChannelIdentity,
    wavelength: float | None,
    expected: WavelengthRange,
    prefix: str,
    spec: SensorValiditySpec,
    issues: list[SensorValidityIssue],
) -> None:
    if wavelength is None:
        issues.append(
            SensorValidityIssue(
                "error" if spec.require_wavelength_metadata else "warning",
                f"{prefix}_wavelength_missing",
                channel.channel_id,
                "required wavelength metadata is absent",
            )
        )
    elif not expected.contains(wavelength):
        issues.append(
            SensorValidityIssue(
                "error",
                f"{prefix}_outside_profile",
                channel.channel_id,
                "declared wavelength lies outside the selected sensor profile",
                wavelength,
            )
        )


def _channel_metrics(
    values: NDArray[np.float64],
    valid: NDArray[np.bool_],
    channel: ChannelIdentity,
    profile: SensorProfile | None,
    spec: SensorValiditySpec,
) -> ChannelValidityMetrics:
    finite = valid & np.isfinite(values)
    selected = values[finite]
    outside_profile: float | None = None
    if profile is not None and profile.linear_response_range is not None:
        assert profile.linear_response_unit is not None
        if channel.unit == profile.linear_response_unit and len(selected):
            low, high = profile.linear_response_range
            outside_profile = float(np.mean((selected < low) | (selected > high)))
    return ChannelValidityMetrics(
        channel.channel_id,
        len(values),
        float(np.mean(finite)),
        float(np.std(selected)) if len(selected) else float("nan"),
        _extreme_repeat_fraction(selected),
        _flat_step_fraction(selected),
        _saturation_fraction(selected, spec),
        outside_profile,
    )


def _metric_issues(
    metrics: ChannelValidityMetrics,
    spec: SensorValiditySpec,
    issues: list[SensorValidityIssue],
) -> None:
    _minimum_issue(
        metrics.finite_fraction,
        spec.minimum_finite_fraction_warning,
        spec.minimum_finite_fraction_error,
        "finite_fraction",
        metrics.channel_id,
        issues,
    )
    _maximum_issue(
        metrics.repeated_extreme_fraction,
        spec.maximum_repeated_extreme_fraction_warning,
        spec.maximum_repeated_extreme_fraction_error,
        "repeated_extreme_fraction",
        metrics.channel_id,
        issues,
    )
    _maximum_issue(
        metrics.flat_step_fraction,
        spec.maximum_flat_step_fraction_warning,
        spec.maximum_flat_step_fraction_error,
        "flat_step_fraction",
        metrics.channel_id,
        issues,
    )
    if metrics.saturation_fraction is not None:
        _maximum_issue(
            metrics.saturation_fraction,
            spec.maximum_saturation_fraction_warning,
            spec.maximum_saturation_fraction_error,
            "detector_saturation_fraction",
            metrics.channel_id,
            issues,
        )
    if metrics.outside_profile_fraction is not None:
        _maximum_issue(
            metrics.outside_profile_fraction,
            spec.maximum_out_of_profile_fraction_warning,
            spec.maximum_out_of_profile_fraction_error,
            "outside_sensor_linear_range_fraction",
            metrics.channel_id,
            issues,
        )


def _isosbestic_metrics(
    time: NDArray[np.float64],
    signal_values: NDArray[np.float64],
    reference_values: NDArray[np.float64],
    signal_valid: NDArray[np.bool_],
    reference_valid: NDArray[np.bool_],
    events: NDArray[np.float64] | None,
    spec: SensorValiditySpec,
) -> IsosbesticValidityMetrics:
    prepared = _prepare_pair(
        time,
        signal_values,
        reference_values,
        signal_valid,
        reference_valid,
        spec.gap,
    )
    signal_runs = []
    reference_runs = []
    derivative_signal_runs = []
    derivative_reference_runs = []
    for indices in prepared.indices:
        signal_run = scipy_signal.detrend(prepared.first[indices], type="constant")
        reference_run = scipy_signal.detrend(prepared.second[indices], type="constant")
        signal_runs.append(np.asarray(signal_run, dtype=float))
        reference_runs.append(np.asarray(reference_run, dtype=float))
        if len(indices) >= 3:
            derivative_signal_runs.append(np.diff(signal_run))
            derivative_reference_runs.append(np.diff(reference_run))
    zero, _ = _cross_correlation(
        signal_runs, reference_runs, np.asarray([0], dtype=np.int64)
    )
    max_lag = max(
        1,
        round(
            spec.maximum_reference_lag_s
            / prepared.evidence.continuity.sampling_interval_s
        ),
    )
    lags = np.arange(-max_lag, max_lag + 1, dtype=np.int64)
    derivative, _ = _cross_correlation(
        derivative_signal_runs, derivative_reference_runs, lags
    )
    zero_index = max_lag
    finite_derivative = np.isfinite(derivative)
    if np.any(finite_derivative):
        comparable = np.where(finite_derivative, np.abs(derivative), -np.inf)
        best_index = int(np.argmax(comparable))
        best_correlation = float(derivative[best_index])
        best_lag_s = float(
            lags[best_index] * prepared.evidence.continuity.sampling_interval_s
        )
        zero_correlation = float(derivative[zero_index])
        lag_improvement = float(abs(best_correlation) - abs(zero_correlation))
    else:
        best_correlation = float("nan")
        best_lag_s = 0.0
        zero_correlation = float("nan")
        lag_improvement = float("nan")
    signal_selected = np.concatenate(signal_runs)
    reference_selected = np.concatenate(reference_runs)
    signal_sd = float(np.std(signal_selected))
    reference_sd = float(np.std(reference_selected))
    effect, event_count = _reference_event_effect(
        time,
        reference_values,
        signal_valid & reference_valid,
        events,
        spec,
    )
    return IsosbesticValidityMetrics(
        prepared.evidence.joint_valid_sample_count,
        float(zero[0]),
        reference_sd / max(signal_sd, np.finfo(float).eps),
        zero_correlation,
        best_correlation,
        best_lag_s,
        lag_improvement,
        event_count,
        effect,
    )


def _isosbestic_issues(
    metrics: IsosbesticValidityMetrics,
    channel_id: str,
    spec: SensorValiditySpec,
    issues: list[SensorValidityIssue],
) -> None:
    if abs(metrics.signal_reference_correlation) < spec.weak_reference_correlation:
        issues.append(
            SensorValidityIssue(
                "warning",
                "weak_signal_reference_correlation",
                channel_id,
                "reference has weak zero-lag association with the signal",
                metrics.signal_reference_correlation,
            )
        )
    if metrics.reference_to_signal_sd_ratio < spec.minimum_reference_sd_ratio:
        issues.append(
            SensorValidityIssue(
                "error",
                "reference_variance_too_low",
                channel_id,
                "reference variability is too small relative to the signal",
                metrics.reference_to_signal_sd_ratio,
            )
        )
    elif metrics.reference_to_signal_sd_ratio > spec.maximum_reference_sd_ratio:
        issues.append(
            SensorValidityIssue(
                "warning",
                "reference_variance_too_high",
                channel_id,
                "reference variability is unusually large relative to the signal",
                metrics.reference_to_signal_sd_ratio,
            )
        )
    if (
        abs(metrics.derivative_best_lag_s) >= spec.maximum_reference_lag_s
        and metrics.derivative_lag_improvement >= spec.minimum_lag_improvement
    ):
        issues.append(
            SensorValidityIssue(
                "warning",
                "signal_reference_timing_lag",
                channel_id,
                "derivative coupling improves materially away from zero lag",
                metrics.derivative_best_lag_s,
            )
        )
    if (
        metrics.reference_event_effect_sd is not None
        and abs(metrics.reference_event_effect_sd)
        >= spec.maximum_reference_event_effect_sd
    ):
        issues.append(
            SensorValidityIssue(
                "warning",
                "event_correlated_isosbestic_response",
                channel_id,
                "reference shows a large median event response",
                metrics.reference_event_effect_sd,
            )
        )


def _reference_event_effect(
    time: NDArray[np.float64],
    reference: NDArray[np.float64],
    valid: NDArray[np.bool_],
    events: NDArray[np.float64] | None,
    spec: SensorValiditySpec,
) -> tuple[float | None, int]:
    if events is None:
        return None, 0
    deltas = []
    for event in events:
        baseline = (
            (time >= event + spec.event_baseline[0])
            & (time < event + spec.event_baseline[1])
            & valid
        )
        response = (
            (time >= event + spec.event_response[0])
            & (time < event + spec.event_response[1])
            & valid
        )
        if baseline.any() and response.any():
            deltas.append(np.mean(reference[response]) - np.mean(reference[baseline]))
    finite = reference[valid & np.isfinite(reference)]
    scale = float(np.std(finite)) if len(finite) else float("nan")
    effect = (
        float(np.median(deltas) / max(scale, np.finfo(float).eps))
        if deltas
        else float("nan")
    )
    return effect, len(deltas)


def _minimum_issue(
    value: float,
    warning: float,
    error: float,
    code: str,
    channel_id: str,
    issues: list[SensorValidityIssue],
) -> None:
    if value < error:
        severity: ValiditySeverity = "error"
    elif value < warning:
        severity = "warning"
    else:
        return
    issues.append(
        SensorValidityIssue(
            severity,
            code,
            channel_id,
            f"{code.replace('_', ' ')} crosses the {severity} threshold",
            value,
        )
    )


def _maximum_issue(
    value: float,
    warning: float,
    error: float,
    code: str,
    channel_id: str,
    issues: list[SensorValidityIssue],
) -> None:
    if not np.isfinite(value):
        return
    if value > error:
        severity: ValiditySeverity = "error"
    elif value > warning:
        severity = "warning"
    else:
        return
    issues.append(
        SensorValidityIssue(
            severity,
            code,
            channel_id,
            f"{code.replace('_', ' ')} crosses the {severity} threshold",
            value,
        )
    )


def _extreme_repeat_fraction(values: NDArray[np.float64]) -> float:
    if not len(values):
        return float("nan")
    minimum_count = int(np.sum(values == np.min(values)))
    maximum_count = int(np.sum(values == np.max(values)))
    repeated = max(minimum_count - 1, 0) + max(maximum_count - 1, 0)
    return float(repeated / len(values))


def _flat_step_fraction(values: NDArray[np.float64]) -> float:
    if len(values) < 2:
        return float("nan")
    scale = max(float(np.std(values)), np.finfo(float).eps)
    return float(np.mean(np.abs(np.diff(values)) <= scale * 1e-12))


def _saturation_fraction(
    values: NDArray[np.float64], spec: SensorValiditySpec
) -> float | None:
    if spec.detector_floor is None or spec.detector_ceiling is None:
        return None
    saturated = (values <= spec.detector_floor + spec.saturation_tolerance) | (
        values >= spec.detector_ceiling - spec.saturation_tolerance
    )
    return float(np.mean(saturated)) if len(values) else float("nan")


def _validate_nested_minimum(error: float, warning: float, name: str) -> None:
    if not 0 <= error <= warning <= 1:
        raise ValueError(f"{name} thresholds must satisfy 0 <= error <= warning <= 1")


def _validate_nested_maximum(warning: float, error: float, name: str) -> None:
    if not 0 <= warning <= error <= 1:
        raise ValueError(f"{name} thresholds must satisfy 0 <= warning <= error <= 1")


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
        raise ValueError("validity masks must be one-dimensional and match time")
    return mask


def _validate_events(events: ArrayLike | None) -> NDArray[np.float64] | None:
    if events is None:
        return None
    values = np.asarray(events, dtype=float)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("event_times must be a finite one-dimensional array")
    return values
