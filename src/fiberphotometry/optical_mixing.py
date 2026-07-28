"""Identifiability-first wavelength-aware optical source separation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray

from fiberphotometry.multisignal import ChannelIdentity

OpticalComponentRole: TypeAlias = Literal[
    "sensor",
    "hemodynamic",
    "autofluorescence",
    "background",
    "other",
]
MixingCoefficientSource: TypeAlias = Literal["externally_calibrated", "user_declared"]
MixingSeverity: TypeAlias = Literal["warning", "error"]
MixingStatus: TypeAlias = Literal["pass", "warning", "error"]


@dataclass(frozen=True)
class OpticalComponent:
    """One declared latent contribution and its interpretation boundary."""

    component_id: str
    role: OpticalComponentRole
    unit: str
    description: str = ""

    def __post_init__(self) -> None:
        for name in ("component_id", "unit"):
            cleaned = str(getattr(self, name)).strip()
            if not cleaned:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, cleaned)
        if self.role not in {
            "sensor",
            "hemodynamic",
            "autofluorescence",
            "background",
            "other",
        }:
            raise ValueError("unsupported optical component role")
        object.__setattr__(self, "description", self.description.strip())


@dataclass(frozen=True)
class OpticalMixingChannel:
    """One measured channel, calibrated component loadings, and offset."""

    channel: ChannelIdentity
    coefficients: tuple[float, ...]
    offset: float = 0.0

    def __post_init__(self) -> None:
        if not self.coefficients:
            raise ValueError("optical mixing coefficients must be non-empty")
        if any(not np.isfinite(value) for value in self.coefficients):
            raise ValueError("optical mixing coefficients must be finite")
        if not np.isfinite(self.offset):
            raise ValueError("optical mixing offset must be finite")


@dataclass(frozen=True)
class OpticalMixingDesign:
    """Externally identified linear map from components to measurements."""

    components: tuple[OpticalComponent, ...]
    channels: tuple[OpticalMixingChannel, ...]
    coefficient_source: MixingCoefficientSource
    calibration_id: str
    design_version: str = "1"

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError("optical mixing design requires components")
        if not self.channels:
            raise ValueError("optical mixing design requires measured channels")
        component_ids = [item.component_id for item in self.components]
        channel_ids = [item.channel.channel_id for item in self.channels]
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("optical component IDs must be unique")
        if len(set(channel_ids)) != len(channel_ids):
            raise ValueError("optical mixing channel IDs must be unique")
        if any(
            len(item.coefficients) != len(self.components) for item in self.channels
        ):
            raise ValueError("every optical mixing row must match the component count")
        if self.coefficient_source not in {
            "externally_calibrated",
            "user_declared",
        }:
            raise ValueError("unsupported optical mixing coefficient source")
        for name in ("calibration_id", "design_version"):
            cleaned = str(getattr(self, name)).strip()
            if not cleaned:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, cleaned)


@dataclass(frozen=True)
class OpticalUnmixingSpec:
    """Declare identifiability, wavelength, missingness, and QC gates."""

    maximum_condition_number: float = 1_000.0
    require_wavelength_metadata: bool = True
    require_leave_one_channel_out: bool = False
    minimum_holdout_samples: int = 20
    gap_factor: float = 3.0

    def __post_init__(self) -> None:
        if (
            not np.isfinite(self.maximum_condition_number)
            or self.maximum_condition_number < 1
        ):
            raise ValueError("maximum_condition_number must be finite and at least one")
        if self.minimum_holdout_samples < 3:
            raise ValueError("minimum_holdout_samples must be at least three")
        if not np.isfinite(self.gap_factor) or self.gap_factor <= 1:
            raise ValueError("gap_factor must be finite and greater than one")


@dataclass(frozen=True)
class OpticalMixingCalibrationSpec:
    """Declare fitting gates for an independent known-component calibration."""

    fit_intercept: bool = True
    minimum_samples: int = 20
    maximum_component_design_condition: float = 1_000.0
    maximum_mixing_condition_number: float = 1_000.0
    require_wavelength_metadata: bool = True

    def __post_init__(self) -> None:
        if self.minimum_samples < 3:
            raise ValueError("calibration minimum_samples must be at least three")
        for name in (
            "maximum_component_design_condition",
            "maximum_mixing_condition_number",
        ):
            value = getattr(self, name)
            if not np.isfinite(value) or value < 1:
                raise ValueError(f"{name} must be finite and at least one")


@dataclass(frozen=True)
class OpticalMixingIssue:
    """One machine-readable design or validation concern."""

    severity: MixingSeverity
    code: str
    message: str
    channel_id: str | None = None


@dataclass(frozen=True)
class OpticalMixingDesignAssessment:
    """Rank, conditioning, metadata, and holdout-identifiability evidence."""

    status: MixingStatus
    channel_count: int
    component_count: int
    rank: int
    condition_number: float
    overdetermined: bool
    leave_one_channel_out_identifiable: bool
    issues: tuple[OpticalMixingIssue, ...]

    def to_json(self) -> str:
        """Serialize design evidence before any signal outcome is accessed."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class OpticalCalibrationChannelDiagnostic:
    """In-sample fit evidence for one independently calibrated channel row."""

    channel_id: str
    sample_count: int
    component_design_rank: int
    component_design_condition_number: float
    root_mean_square_error: float
    r_squared: float | None


@dataclass(frozen=True)
class OpticalMixingCalibrationResult:
    """Fitted external calibration matrix and descriptive fit diagnostics."""

    design: OpticalMixingDesign
    spec: OpticalMixingCalibrationSpec
    assessment: OpticalMixingDesignAssessment
    channel_diagnostics: tuple[OpticalCalibrationChannelDiagnostic, ...]
    input_sample_count: int
    evidence_fingerprint: str
    method: str = "known_component_multichannel_linear_calibration"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize calibration coefficients, diagnostics, and provenance."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class OpticalAvailabilityPattern:
    """Identifiability evidence for one observed channel subset."""

    pattern_id: str
    available_channel_ids: tuple[str, ...]
    sample_count: int
    rank: int
    condition_number: float | None
    solved: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class OpticalChannelHoldoutDiagnostic:
    """Reconstruction of one channel from all other simultaneously observed rows."""

    channel_id: str
    identifiable_without_channel: bool
    sample_count: int
    rank: int
    condition_number: float | None
    root_mean_square_error: float | None
    normalized_root_mean_square_error: float | None
    r_squared: float | None
    exclusion_reason: str | None


@dataclass(frozen=True)
class OpticalUnmixingResult:
    """Unmixed sources, channel reconstructions, residuals, and complete evidence."""

    design: OpticalMixingDesign
    spec: OpticalUnmixingSpec
    assessment: OpticalMixingDesignAssessment
    time_s: tuple[float, ...]
    component_values: tuple[tuple[float, ...], ...]
    reconstructed_channel_values: tuple[tuple[float, ...], ...]
    residual_channel_values: tuple[tuple[float, ...], ...]
    observation_valid: tuple[tuple[bool, ...], ...]
    component_valid: tuple[bool, ...]
    availability_patterns: tuple[OpticalAvailabilityPattern, ...]
    holdout_diagnostics: tuple[OpticalChannelHoldoutDiagnostic, ...]
    input_sample_count: int
    solved_sample_count: int
    unsolved_sample_count: int
    nominal_interval_s: float
    gap_count: int
    evidence_fingerprint: str
    method: str = "externally_identified_pointwise_linear_optical_unmixing"
    schema_version: str = "1"

    def component(self, component_id: str) -> tuple[float, ...]:
        """Return one component series by declared identity."""
        identifiers = [item.component_id for item in self.design.components]
        try:
            index = identifiers.index(component_id)
        except ValueError as error:
            raise KeyError(f"unknown optical component {component_id!r}") from error
        return tuple(row[index] for row in self.component_values)

    def to_json(self) -> str:
        """Serialize sources, predictions, residuals, and evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True, allow_nan=True)


@dataclass(frozen=True)
class UnmixedOpticalComponentSeries:
    """One extracted source series with identity and provenance attached."""

    component: OpticalComponent
    time_s: tuple[float, ...]
    values: tuple[float, ...]
    valid: tuple[bool, ...]
    evidence_fingerprint: str
    mixing_calibration_id: str
    mixing_design_version: str


def assess_optical_mixing_design(
    design: OpticalMixingDesign,
    spec: OpticalUnmixingSpec | None = None,
) -> OpticalMixingDesignAssessment:
    """Assess identifiability without accessing recorded signal outcomes."""
    spec = spec or OpticalUnmixingSpec()
    matrix = _mixing_matrix(design)
    rank = int(np.linalg.matrix_rank(matrix))
    condition = _condition_number(matrix, rank, len(design.components))
    issues: list[OpticalMixingIssue] = []
    if len(design.channels) < len(design.components):
        issues.append(
            OpticalMixingIssue(
                "error",
                "fewer_channels_than_components",
                "the declared system has fewer measurements than latent components",
            )
        )
    if rank < len(design.components):
        issues.append(
            OpticalMixingIssue(
                "error",
                "rank_deficient_mixing_matrix",
                "the declared coefficient matrix does not identify every component",
            )
        )
    elif condition > spec.maximum_condition_number:
        issues.append(
            OpticalMixingIssue(
                "error",
                "ill_conditioned_mixing_matrix",
                "the declared coefficient matrix exceeds the condition-number gate",
            )
        )
    if design.coefficient_source == "user_declared":
        issues.append(
            OpticalMixingIssue(
                "warning",
                "coefficients_not_externally_calibrated",
                "coefficients are user-declared rather than externally calibrated",
            )
        )
    for row in design.channels:
        channel = row.channel
        if channel.role == "unclassified":
            issues.append(
                OpticalMixingIssue(
                    "error",
                    "unclassified_channel_role",
                    "mixing channels require an explicit optical role",
                    channel.channel_id,
                )
            )
        if spec.require_wavelength_metadata:
            for field, value in (
                ("excitation", channel.excitation_wavelength_nm),
                ("emission", channel.emission_wavelength_nm),
            ):
                if value is None:
                    issues.append(
                        OpticalMixingIssue(
                            "error",
                            f"missing_{field}_wavelength",
                            f"{field} wavelength metadata is required",
                            channel.channel_id,
                        )
                    )
    leave_one_out = _all_holdout_designs_identifiable(matrix, spec)
    if not leave_one_out:
        severity: MixingSeverity = (
            "error" if spec.require_leave_one_channel_out else "warning"
        )
        issues.append(
            OpticalMixingIssue(
                severity,
                "leave_one_channel_out_not_identifiable",
                "at least one held-out channel leaves an underidentified submatrix",
            )
        )
    status: MixingStatus = (
        "error"
        if any(item.severity == "error" for item in issues)
        else "warning"
        if issues
        else "pass"
    )
    return OpticalMixingDesignAssessment(
        status=status,
        channel_count=len(design.channels),
        component_count=len(design.components),
        rank=rank,
        condition_number=float(condition),
        overdetermined=len(design.channels) > len(design.components),
        leave_one_channel_out_identifiable=leave_one_out,
        issues=tuple(issues),
    )


def calibrate_optical_mixing(
    known_component_values: ArrayLike,
    measured_channel_values: ArrayLike,
    components: tuple[OpticalComponent, ...],
    channels: tuple[ChannelIdentity, ...],
    calibration_id: str,
    spec: OpticalMixingCalibrationSpec | None = None,
    *,
    valid_components: ArrayLike | None = None,
    valid_channels: ArrayLike | None = None,
    design_version: str = "1",
) -> OpticalMixingCalibrationResult:
    """Fit mixing rows only when calibration component values are already known."""
    spec = spec or OpticalMixingCalibrationSpec()
    if not components or not channels:
        raise ValueError("optical calibration requires components and channels")
    if not calibration_id.strip() or not design_version.strip():
        raise ValueError("calibration_id and design_version must be non-empty")
    component_ids = [item.component_id for item in components]
    channel_ids = [item.channel_id for item in channels]
    if len(set(component_ids)) != len(component_ids):
        raise ValueError("optical calibration component IDs must be unique")
    if len(set(channel_ids)) != len(channel_ids):
        raise ValueError("optical calibration channel IDs must be unique")
    component_values = np.asarray(known_component_values, dtype=float)
    channel_values = np.asarray(measured_channel_values, dtype=float)
    if component_values.ndim != 2 or component_values.shape[1] != len(components):
        raise ValueError("known_component_values must be sample by declared component")
    if channel_values.shape != (len(component_values), len(channels)):
        raise ValueError("measured_channel_values must be sample by declared channel")
    component_valid = _valid_matrix(valid_components, component_values)
    channel_valid = _valid_matrix(valid_channels, channel_values)
    shared_component_valid = np.all(component_valid, axis=1)
    rows: list[OpticalMixingChannel] = []
    diagnostics: list[OpticalCalibrationChannelDiagnostic] = []
    for channel_index, channel in enumerate(channels):
        selected = shared_component_valid & channel_valid[:, channel_index]
        sample_count = int(np.count_nonzero(selected))
        if sample_count < spec.minimum_samples:
            raise ValueError(
                f"calibration channel {channel.channel_id!r} has fewer than "
                "minimum_samples"
            )
        predictors = component_values[selected]
        design_matrix = (
            np.column_stack((np.ones(sample_count), predictors))
            if spec.fit_intercept
            else predictors
        )
        expected_rank = len(components) + int(spec.fit_intercept)
        rank = int(np.linalg.matrix_rank(design_matrix))
        condition = _condition_number(design_matrix, rank, expected_rank)
        if rank < expected_rank:
            raise ValueError(
                f"calibration channel {channel.channel_id!r} component design "
                "is rank deficient"
            )
        if condition > spec.maximum_component_design_condition:
            raise ValueError(
                f"calibration channel {channel.channel_id!r} component design "
                "exceeds the condition-number gate"
            )
        response = channel_values[selected, channel_index]
        beta = np.linalg.lstsq(design_matrix, response, rcond=None)[0]
        offset = float(beta[0]) if spec.fit_intercept else 0.0
        coefficients = beta[1:] if spec.fit_intercept else beta
        fitted = design_matrix @ beta
        residual = response - fitted
        rmse = float(np.sqrt(np.mean(np.square(residual))))
        centered = response - np.mean(response)
        total = float(np.dot(centered, centered))
        r_squared = (
            1 - float(np.dot(residual, residual)) / total
            if total > np.finfo(float).eps
            else None
        )
        rows.append(
            OpticalMixingChannel(
                channel=channel,
                coefficients=_float_tuple(np.asarray(coefficients, dtype=float)),
                offset=offset,
            )
        )
        diagnostics.append(
            OpticalCalibrationChannelDiagnostic(
                channel_id=channel.channel_id,
                sample_count=sample_count,
                component_design_rank=rank,
                component_design_condition_number=float(condition),
                root_mean_square_error=rmse,
                r_squared=r_squared,
            )
        )
    design = OpticalMixingDesign(
        components=components,
        channels=tuple(rows),
        coefficient_source="externally_calibrated",
        calibration_id=calibration_id,
        design_version=design_version,
    )
    unmixing_spec = OpticalUnmixingSpec(
        maximum_condition_number=spec.maximum_mixing_condition_number,
        require_wavelength_metadata=spec.require_wavelength_metadata,
    )
    assessment = assess_optical_mixing_design(design, unmixing_spec)
    if assessment.status == "error":
        codes = ", ".join(
            issue.code for issue in assessment.issues if issue.severity == "error"
        )
        raise ValueError(f"calibrated optical mixing design failed: {codes}")
    fingerprint = _calibration_fingerprint(
        component_values,
        channel_values,
        component_valid,
        channel_valid,
        components,
        channels,
        calibration_id,
        design_version,
        spec,
    )
    return OpticalMixingCalibrationResult(
        design=design,
        spec=spec,
        assessment=assessment,
        channel_diagnostics=tuple(diagnostics),
        input_sample_count=len(component_values),
        evidence_fingerprint=fingerprint,
    )


def unmix_optical_signals(
    time: ArrayLike,
    values: ArrayLike,
    design: OpticalMixingDesign,
    spec: OpticalUnmixingSpec | None = None,
    *,
    valid: ArrayLike | None = None,
) -> OpticalUnmixingResult:
    """Apply a declared mixing matrix without estimating it from the outcomes."""
    spec = spec or OpticalUnmixingSpec()
    assessment = assess_optical_mixing_design(design, spec)
    if assessment.status == "error":
        codes = ", ".join(
            issue.code for issue in assessment.issues if issue.severity == "error"
        )
        raise ValueError(f"optical mixing design failed: {codes}")
    time_values, observations, observation_valid = _validate_observations(
        time, values, valid, len(design.channels)
    )
    matrix = _mixing_matrix(design)
    offsets = np.asarray([item.offset for item in design.channels], dtype=float)
    components = np.full((len(time_values), len(design.components)), np.nan)
    reconstructed = np.full_like(observations, np.nan)
    residuals = np.full_like(observations, np.nan)
    patterns: list[OpticalAvailabilityPattern] = []
    for pattern_values in sorted({tuple(row) for row in observation_valid.tolist()}):
        pattern = np.asarray(pattern_values, dtype=bool)
        selected_samples = np.all(observation_valid == pattern, axis=1)
        selected_channels = np.flatnonzero(pattern)
        submatrix = matrix[selected_channels]
        rank = int(np.linalg.matrix_rank(submatrix)) if len(submatrix) else 0
        condition = (
            _condition_number(submatrix, rank, len(design.components))
            if len(submatrix)
            else float("inf")
        )
        reason: str | None = None
        if len(selected_channels) < len(design.components):
            reason = "fewer_available_channels_than_components"
        elif rank < len(design.components):
            reason = "rank_deficient_available_submatrix"
        elif condition > spec.maximum_condition_number:
            reason = "ill_conditioned_available_submatrix"
        solved = reason is None
        channel_ids = tuple(
            design.channels[index].channel.channel_id for index in selected_channels
        )
        pattern_id = "".join("1" if value else "0" for value in pattern_values)
        patterns.append(
            OpticalAvailabilityPattern(
                pattern_id=pattern_id,
                available_channel_ids=channel_ids,
                sample_count=int(np.count_nonzero(selected_samples)),
                rank=rank,
                condition_number=float(condition) if np.isfinite(condition) else None,
                solved=solved,
                exclusion_reason=reason,
            )
        )
        if not solved:
            continue
        centered = observations[np.ix_(selected_samples, selected_channels)]
        centered = centered - offsets[selected_channels]
        source_values = np.linalg.lstsq(submatrix, centered.T, rcond=None)[0].T
        components[selected_samples] = source_values
        reconstructed[selected_samples] = source_values @ matrix.T + offsets
        observed_cells = observation_valid & selected_samples[:, np.newaxis]
        residuals[observed_cells] = (
            observations[observed_cells] - reconstructed[observed_cells]
        )
    component_valid = np.all(np.isfinite(components), axis=1)
    holdouts = _holdout_diagnostics(
        observations, observation_valid, matrix, offsets, design, spec
    )
    if spec.require_leave_one_channel_out:
        insufficient = [
            item.channel_id
            for item in holdouts
            if item.sample_count < spec.minimum_holdout_samples
        ]
        if insufficient:
            raise ValueError(
                "leave-one-channel-out validation has insufficient complete samples: "
                + ", ".join(insufficient)
            )
    differences = np.diff(time_values)
    nominal_interval = float(np.median(differences))
    gap_count = int(np.count_nonzero(differences > spec.gap_factor * nominal_interval))
    fingerprint = _fingerprint(
        time_values, observations, observation_valid, design, spec
    )
    return OpticalUnmixingResult(
        design=design,
        spec=spec,
        assessment=assessment,
        time_s=_float_tuple(time_values),
        component_values=_float_matrix(components),
        reconstructed_channel_values=_float_matrix(reconstructed),
        residual_channel_values=_float_matrix(residuals),
        observation_valid=_bool_matrix(observation_valid),
        component_valid=tuple(bool(value) for value in component_valid),
        availability_patterns=tuple(patterns),
        holdout_diagnostics=tuple(holdouts),
        input_sample_count=len(time_values),
        solved_sample_count=int(np.count_nonzero(component_valid)),
        unsolved_sample_count=int(len(time_values) - np.count_nonzero(component_valid)),
        nominal_interval_s=nominal_interval,
        gap_count=gap_count,
        evidence_fingerprint=fingerprint,
    )


def extract_unmixed_component(
    result: OpticalUnmixingResult, component_id: str
) -> UnmixedOpticalComponentSeries:
    """Extract one source without discarding identity or mixing provenance."""
    identifiers = [item.component_id for item in result.design.components]
    try:
        index = identifiers.index(component_id)
    except ValueError as error:
        raise KeyError(f"unknown optical component {component_id!r}") from error
    component = result.design.components[index]
    values = tuple(row[index] for row in result.component_values)
    return UnmixedOpticalComponentSeries(
        component=component,
        time_s=result.time_s,
        values=values,
        valid=result.component_valid,
        evidence_fingerprint=result.evidence_fingerprint,
        mixing_calibration_id=result.design.calibration_id,
        mixing_design_version=result.design.design_version,
    )


def _validate_observations(
    time: ArrayLike,
    values: ArrayLike,
    valid: ArrayLike | None,
    channel_count: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    time_values = np.asarray(time, dtype=float)
    observations = np.asarray(values, dtype=float)
    if time_values.ndim != 1 or len(time_values) < 3:
        raise ValueError("optical time must contain three or more samples")
    if not np.all(np.isfinite(time_values)) or not np.all(np.diff(time_values) > 0):
        raise ValueError("optical time must be finite and strictly increasing")
    if observations.shape != (len(time_values), channel_count):
        raise ValueError("optical values must be time by declared mixing channel")
    if valid is None:
        observation_valid = np.ones(observations.shape, dtype=bool)
    else:
        observation_valid = np.asarray(valid, dtype=bool)
        if observation_valid.shape != observations.shape:
            raise ValueError("optical valid mask must match the values matrix")
    observation_valid &= np.isfinite(observations)
    return time_values, observations, observation_valid


def _valid_matrix(
    supplied: ArrayLike | None, values: NDArray[np.float64]
) -> NDArray[np.bool_]:
    if supplied is None:
        valid: NDArray[np.bool_] = np.ones(values.shape, dtype=bool)
    else:
        valid = np.asarray(supplied, dtype=bool)
        if valid.shape != values.shape:
            raise ValueError("calibration validity mask must match its values")
    finite: NDArray[np.bool_] = np.asarray(np.isfinite(values), dtype=np.bool_)
    return np.asarray(valid & finite, dtype=np.bool_)


def _mixing_matrix(design: OpticalMixingDesign) -> NDArray[np.float64]:
    return np.asarray([item.coefficients for item in design.channels], dtype=float)


def _condition_number(
    matrix: NDArray[np.float64], rank: int, component_count: int
) -> float:
    if rank < component_count:
        return float("inf")
    return float(np.linalg.cond(matrix))


def _all_holdout_designs_identifiable(
    matrix: NDArray[np.float64], spec: OpticalUnmixingSpec
) -> bool:
    if len(matrix) <= matrix.shape[1]:
        return False
    for channel_index in range(len(matrix)):
        submatrix = np.delete(matrix, channel_index, axis=0)
        rank = int(np.linalg.matrix_rank(submatrix))
        if rank < matrix.shape[1]:
            return False
        if np.linalg.cond(submatrix) > spec.maximum_condition_number:
            return False
    return True


def _holdout_diagnostics(
    observations: NDArray[np.float64],
    observation_valid: NDArray[np.bool_],
    matrix: NDArray[np.float64],
    offsets: NDArray[np.float64],
    design: OpticalMixingDesign,
    spec: OpticalUnmixingSpec,
) -> list[OpticalChannelHoldoutDiagnostic]:
    complete = np.all(observation_valid, axis=1)
    output = []
    for held_index, row in enumerate(design.channels):
        retained = np.arange(len(design.channels)) != held_index
        submatrix = matrix[retained]
        rank = int(np.linalg.matrix_rank(submatrix))
        condition = _condition_number(submatrix, rank, len(design.components))
        reason: str | None = None
        if rank < len(design.components):
            reason = "heldout_submatrix_rank_deficient"
        elif condition > spec.maximum_condition_number:
            reason = "heldout_submatrix_ill_conditioned"
        sample_count = int(np.count_nonzero(complete))
        if reason is None and sample_count < spec.minimum_holdout_samples:
            reason = "fewer_than_minimum_holdout_samples"
        rmse: float | None = None
        normalized: float | None = None
        r_squared: float | None = None
        if reason is None:
            centered = observations[np.ix_(complete, retained)] - offsets[retained]
            sources = np.linalg.lstsq(submatrix, centered.T, rcond=None)[0].T
            predicted = sources @ matrix[held_index] + offsets[held_index]
            observed = observations[complete, held_index]
            residual = observed - predicted
            rmse = float(np.sqrt(np.mean(np.square(residual))))
            standard_deviation = float(np.std(observed, ddof=1))
            if standard_deviation > np.finfo(float).eps:
                normalized = rmse / standard_deviation
            centered_observed = observed - np.mean(observed)
            total = float(np.dot(centered_observed, centered_observed))
            if total > np.finfo(float).eps:
                r_squared = 1 - float(np.dot(residual, residual)) / total
        output.append(
            OpticalChannelHoldoutDiagnostic(
                channel_id=row.channel.channel_id,
                identifiable_without_channel=rank == len(design.components)
                and condition <= spec.maximum_condition_number,
                sample_count=sample_count,
                rank=rank,
                condition_number=float(condition) if np.isfinite(condition) else None,
                root_mean_square_error=rmse,
                normalized_root_mean_square_error=normalized,
                r_squared=r_squared,
                exclusion_reason=reason,
            )
        )
    return output


def _fingerprint(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    valid: NDArray[np.bool_],
    design: OpticalMixingDesign,
    spec: OpticalUnmixingSpec,
) -> str:
    digest = hashlib.sha256()
    for array in (time.astype("<f8"), values.astype("<f8"), valid.astype("u1")):
        digest.update(array.tobytes())
    digest.update(
        json.dumps(
            {"design": asdict(design), "spec": asdict(spec)},
            sort_keys=True,
        ).encode()
    )
    return f"sha256:{digest.hexdigest()}"


def _calibration_fingerprint(
    component_values: NDArray[np.float64],
    channel_values: NDArray[np.float64],
    component_valid: NDArray[np.bool_],
    channel_valid: NDArray[np.bool_],
    components: tuple[OpticalComponent, ...],
    channels: tuple[ChannelIdentity, ...],
    calibration_id: str,
    design_version: str,
    spec: OpticalMixingCalibrationSpec,
) -> str:
    digest = hashlib.sha256()
    for array in (
        component_values.astype("<f8"),
        channel_values.astype("<f8"),
        component_valid.astype("u1"),
        channel_valid.astype("u1"),
    ):
        digest.update(array.tobytes())
    digest.update(
        json.dumps(
            {
                "components": [asdict(item) for item in components],
                "channels": [asdict(item) for item in channels],
                "calibration_id": calibration_id,
                "design_version": design_version,
                "spec": asdict(spec),
            },
            sort_keys=True,
        ).encode()
    )
    return f"sha256:{digest.hexdigest()}"


def _float_tuple(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _float_matrix(
    values: NDArray[np.float64],
) -> tuple[tuple[float, ...], ...]:
    return tuple(_float_tuple(row) for row in values)


def _bool_matrix(values: NDArray[np.bool_]) -> tuple[tuple[bool, ...], ...]:
    return tuple(tuple(bool(value) for value in row) for row in values)
