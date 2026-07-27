"""Guarded paired-signal metadata, association, and crosstalk diagnostics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import signal

from fiberphotometry.spectral import (
    ContinuityEvidence,
    GapHandlingSpec,
    _prepare_runs,
)

ChannelRole: TypeAlias = Literal[
    "sensor", "reference", "control", "isosbestic", "unclassified"
]
AlignmentPolicy: TypeAlias = Literal["native_shared_clock", "explicitly_resampled"]
Detrend: TypeAlias = Literal["none", "constant", "linear"]
CrosstalkStatus: TypeAlias = Literal["no_flag", "review"]


@dataclass(frozen=True)
class SpatialCoordinate:
    """Optional physical or atlas coordinate for one optical site."""

    x: float
    y: float
    z: float
    unit: str = "um"
    space: str = "device"

    def __post_init__(self) -> None:
        if any(not np.isfinite(value) for value in (self.x, self.y, self.z)):
            raise ValueError("spatial coordinates must be finite")
        if not self.unit.strip() or not self.space.strip():
            raise ValueError("coordinate unit and space must be non-empty")


@dataclass(frozen=True)
class ChannelIdentity:
    """Declared biological and optical identity of one analyzed signal."""

    channel_id: str
    site: str
    sensor: str
    role: ChannelRole
    unit: str
    excitation_wavelength_nm: float | None = None
    emission_wavelength_nm: float | None = None
    detector_id: str | None = None
    fiber_id: str | None = None
    coordinate: SpatialCoordinate | None = None

    def __post_init__(self) -> None:
        for name in ("channel_id", "site", "sensor", "unit"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        if self.role not in {
            "sensor",
            "reference",
            "control",
            "isosbestic",
            "unclassified",
        }:
            raise ValueError("unsupported channel role")
        for name in ("excitation_wavelength_nm", "emission_wavelength_nm"):
            value = getattr(self, name)
            if value is not None and (not np.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive when supplied")
        for name in ("detector_id", "fiber_id"):
            value = getattr(self, name)
            if value is not None:
                cleaned = str(value).strip()
                if not cleaned:
                    raise ValueError(f"{name} must be non-empty when supplied")
                object.__setattr__(self, name, cleaned)


@dataclass(frozen=True)
class SignalPairMetadata:
    """Identity and alignment provenance for one ordered signal pair."""

    subject: str
    session: str
    pair_id: str
    first: ChannelIdentity
    second: ChannelIdentity
    clock_id: str
    alignment_policy: AlignmentPolicy
    preprocessing_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "subject",
            "session",
            "pair_id",
            "clock_id",
            "preprocessing_fingerprint",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        if self.first.channel_id == self.second.channel_id:
            raise ValueError("a signal pair requires two distinct channel IDs")
        if self.alignment_policy not in {
            "native_shared_clock",
            "explicitly_resampled",
        }:
            raise ValueError("unsupported alignment policy")


@dataclass(frozen=True)
class JointContinuityEvidence:
    """Joint validity and continuity evidence for two aligned signals."""

    continuity: ContinuityEvidence
    total_sample_count: int
    first_invalid_sample_count: int
    second_invalid_sample_count: int
    jointly_invalid_sample_count: int
    joint_valid_sample_count: int
    covariate_invalid_sample_count: int


@dataclass(frozen=True)
class ResidualizationSpec:
    """Declare within-run regression of shared event or behavior covariates."""

    ridge_alpha: float = 0.0
    standardize_covariates: bool = True

    def __post_init__(self) -> None:
        if not np.isfinite(self.ridge_alpha) or self.ridge_alpha < 0:
            raise ValueError("ridge_alpha must be finite and non-negative")


@dataclass(frozen=True)
class RunResidualization:
    """One run's shared-covariate regression evidence."""

    run_id: int
    sample_count: int
    design_rank: int
    active_covariates: tuple[str, ...]
    first_coefficients: tuple[float, ...]
    second_coefficients: tuple[float, ...]
    first_r_squared: float
    second_r_squared: float


@dataclass(frozen=True)
class ResidualizationEvidence:
    """Complete evidence for optional paired-signal residualization."""

    covariate_names: tuple[str, ...]
    spec: ResidualizationSpec
    runs: tuple[RunResidualization, ...]
    coefficient_scale: str = "intercept_then_within_run_standardized_covariates"


@dataclass(frozen=True)
class BlockPermutationSpec:
    """Within-session null that re-pairs complete temporal blocks."""

    block_duration_s: float = 20.0
    resamples: int = 1000
    seed: int = 0

    def __post_init__(self) -> None:
        if not np.isfinite(self.block_duration_s) or self.block_duration_s <= 0:
            raise ValueError("block_duration_s must be finite and positive")
        if self.resamples < 100:
            raise ValueError("blocked association requires at least 100 resamples")


@dataclass(frozen=True)
class LaggedAssociationSpec:
    """Declare lag, detrending, missingness, and optional blocked-null choices."""

    maximum_lag_s: float = 5.0
    detrend: Detrend = "constant"
    minimum_pairs_per_lag: int = 10
    gap: GapHandlingSpec = field(default_factory=GapHandlingSpec)
    residualization: ResidualizationSpec = ResidualizationSpec()
    blocked_permutation: BlockPermutationSpec | None = None

    def __post_init__(self) -> None:
        if not np.isfinite(self.maximum_lag_s) or self.maximum_lag_s <= 0:
            raise ValueError("maximum_lag_s must be finite and positive")
        if self.detrend not in {"none", "constant", "linear"}:
            raise ValueError("unsupported detrend policy")
        if self.minimum_pairs_per_lag < 2:
            raise ValueError("minimum_pairs_per_lag must be at least two")
        if (
            self.blocked_permutation is not None
            and self.blocked_permutation.block_duration_s <= 2 * self.maximum_lag_s
        ):
            raise ValueError(
                "block_duration_s must exceed twice maximum_lag_s so null blocks "
                "retain every requested lag"
            )


@dataclass(frozen=True)
class BlockPermutationResult:
    """Blocked null evidence for zero-lag and maximum-lag association."""

    block_duration_s: float
    block_sample_count: int
    complete_block_count: int
    resamples: int
    seed: int
    zero_lag_pvalue: float
    maximum_absolute_pvalue: float


@dataclass(frozen=True)
class LaggedAssociationResult:
    """Gap-separated, optionally residualized association across physical lags."""

    pair: SignalPairMetadata
    spec: LaggedAssociationSpec
    lags_s: tuple[float, ...]
    correlation: tuple[float, ...]
    pairs_per_lag: tuple[int, ...]
    zero_lag_correlation: float
    peak_lag_s: float
    peak_correlation: float
    evidence: JointContinuityEvidence
    residualization: ResidualizationEvidence | None
    blocked_permutation: BlockPermutationResult | None
    lag_convention: str = "positive_lag_means_second_signal_occurs_later"
    method: str = "gap_separated_energy_normalized_cross_correlation"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize association values, metadata, and support evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class CrosstalkDiagnosticSpec:
    """Operational flags that prompt review but do not prove contamination."""

    maximum_lag_s: float = 1.0
    high_absolute_correlation: float = 0.8
    near_zero_peak_s: float = 0.1
    minimum_excitation_separation_nm: float = 20.0
    minimum_emission_separation_nm: float = 20.0
    high_control_loading: float = 0.6
    gap: GapHandlingSpec = field(default_factory=GapHandlingSpec)

    def __post_init__(self) -> None:
        if self.maximum_lag_s <= 0 or self.near_zero_peak_s < 0:
            raise ValueError("crosstalk lag thresholds must be non-negative")
        if not 0 < self.high_absolute_correlation <= 1:
            raise ValueError("high_absolute_correlation must lie in (0, 1]")
        if not 0 < self.high_control_loading <= 1:
            raise ValueError("high_control_loading must lie in (0, 1]")
        if (
            self.minimum_excitation_separation_nm < 0
            or self.minimum_emission_separation_nm < 0
        ):
            raise ValueError("wavelength separation thresholds cannot be negative")


@dataclass(frozen=True)
class CrosstalkFlag:
    """One reason to review optical or shared-driver contamination."""

    code: str
    message: str
    value: float | str | None = None


@dataclass(frozen=True)
class CrosstalkDiagnosticResult:
    """Metadata and association diagnostics without automatic correction."""

    pair: SignalPairMetadata
    spec: CrosstalkDiagnosticSpec
    status: CrosstalkStatus
    raw_zero_lag_correlation: float
    raw_peak_lag_s: float
    raw_peak_correlation: float
    control_name: str | None
    first_control_correlation: float | None
    second_control_correlation: float | None
    control_residualized_zero_lag_correlation: float | None
    excitation_separation_nm: float | None
    emission_separation_nm: float | None
    shared_detector: bool | None
    shared_fiber: bool | None
    same_site: bool
    flags: tuple[CrosstalkFlag, ...]
    evidence: JointContinuityEvidence
    interpretation: str = (
        "flags_prompt_review; correlation_cannot_establish_or_exclude_crosstalk"
    )
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize flags and the evidence used to compute them."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class _PreparedPair:
    time: NDArray[np.float64]
    first: NDArray[np.float64]
    second: NDArray[np.float64]
    covariates: NDArray[np.float64] | None
    indices: tuple[NDArray[np.int64], ...]
    evidence: JointContinuityEvidence


def lagged_association(
    time: ArrayLike,
    first: ArrayLike,
    second: ArrayLike,
    pair: SignalPairMetadata,
    spec: LaggedAssociationSpec | None = None,
    *,
    valid_first: ArrayLike | None = None,
    valid_second: ArrayLike | None = None,
    covariates: ArrayLike | None = None,
    covariate_names: tuple[str, ...] | list[str] | None = None,
) -> LaggedAssociationResult:
    """Estimate lagged association without crossing gaps or state boundaries.

    Optional covariates are regressed from both signals separately within each
    continuity run. Event designs and behavior traces therefore use one explicit
    boundary without being interpreted as causal adjustment.
    """
    spec = spec or LaggedAssociationSpec()
    prepared = _prepare_pair(
        time,
        first,
        second,
        valid_first,
        valid_second,
        spec.gap,
        covariates=covariates,
    )
    names = _validate_covariate_names(prepared.covariates, covariate_names)
    return _lagged_from_prepared(prepared, pair, spec, names)


def assess_crosstalk(
    time: ArrayLike,
    first: ArrayLike,
    second: ArrayLike,
    pair: SignalPairMetadata,
    spec: CrosstalkDiagnosticSpec | None = None,
    *,
    valid_first: ArrayLike | None = None,
    valid_second: ArrayLike | None = None,
    shared_control: ArrayLike | None = None,
    control_name: str | None = None,
) -> CrosstalkDiagnosticResult:
    """Combine optical metadata and signal diagnostics without claiming causality."""
    spec = spec or CrosstalkDiagnosticSpec()
    lag_spec = LaggedAssociationSpec(
        maximum_lag_s=spec.maximum_lag_s,
        detrend="constant",
        gap=spec.gap,
    )
    raw = lagged_association(
        time,
        first,
        second,
        pair,
        lag_spec,
        valid_first=valid_first,
        valid_second=valid_second,
    )
    first_control: float | None = None
    second_control: float | None = None
    residualized: float | None = None
    if shared_control is not None:
        cleaned_name = str(control_name or "shared_control").strip()
        if not cleaned_name:
            raise ValueError("control_name must be non-empty")
        control_name = cleaned_name
        control = np.asarray(shared_control, dtype=float)
        first_control = _zero_lag_with_control(
            time, first, control, pair, lag_spec, valid_first
        )
        second_control = _zero_lag_with_control(
            time, second, control, pair, lag_spec, valid_second
        )
        residualized_result = lagged_association(
            time,
            first,
            second,
            pair,
            lag_spec,
            valid_first=valid_first,
            valid_second=valid_second,
            covariates=control[:, np.newaxis],
            covariate_names=(control_name,),
        )
        residualized = residualized_result.zero_lag_correlation
    elif control_name is not None:
        raise ValueError("control_name requires shared_control values")

    excitation_separation = _separation(
        pair.first.excitation_wavelength_nm,
        pair.second.excitation_wavelength_nm,
    )
    emission_separation = _separation(
        pair.first.emission_wavelength_nm,
        pair.second.emission_wavelength_nm,
    )
    shared_detector = _shared_identifier(
        pair.first.detector_id, pair.second.detector_id
    )
    shared_fiber = _shared_identifier(pair.first.fiber_id, pair.second.fiber_id)
    flags: list[CrosstalkFlag] = []
    if shared_detector:
        flags.append(
            CrosstalkFlag(
                "shared_detector",
                "both signals use the same declared detector",
                pair.first.detector_id,
            )
        )
    if shared_fiber:
        flags.append(
            CrosstalkFlag(
                "shared_fiber",
                "both signals use the same declared optical fiber",
                pair.first.fiber_id,
            )
        )
    if (
        excitation_separation is not None
        and excitation_separation < spec.minimum_excitation_separation_nm
    ):
        flags.append(
            CrosstalkFlag(
                "close_excitation_wavelengths",
                "declared excitation wavelengths are closer than the review threshold",
                excitation_separation,
            )
        )
    if (
        emission_separation is not None
        and emission_separation < spec.minimum_emission_separation_nm
    ):
        flags.append(
            CrosstalkFlag(
                "close_emission_wavelengths",
                "declared emission wavelengths are closer than the review threshold",
                emission_separation,
            )
        )
    if abs(raw.zero_lag_correlation) >= spec.high_absolute_correlation:
        flags.append(
            CrosstalkFlag(
                "high_zero_lag_association",
                "zero-lag association exceeds the review threshold",
                raw.zero_lag_correlation,
            )
        )
    if abs(raw.peak_lag_s) <= spec.near_zero_peak_s:
        flags.append(
            CrosstalkFlag(
                "near_zero_lag_peak",
                "the strongest tested association occurs near zero lag",
                raw.peak_lag_s,
            )
        )
    if (
        first_control is not None
        and second_control is not None
        and (
            abs(first_control) >= spec.high_control_loading
            and abs(second_control) >= spec.high_control_loading
        )
    ):
        flags.append(
            CrosstalkFlag(
                "shared_control_loading",
                "both signals load strongly on the supplied shared control",
                min(abs(first_control), abs(second_control)),
            )
        )
    return CrosstalkDiagnosticResult(
        pair,
        spec,
        "review" if flags else "no_flag",
        raw.zero_lag_correlation,
        raw.peak_lag_s,
        raw.peak_correlation,
        control_name,
        first_control,
        second_control,
        residualized,
        excitation_separation,
        emission_separation,
        shared_detector,
        shared_fiber,
        pair.first.site == pair.second.site,
        tuple(flags),
        raw.evidence,
    )


def _prepare_pair(
    time: ArrayLike,
    first: ArrayLike,
    second: ArrayLike,
    valid_first: ArrayLike | None,
    valid_second: ArrayLike | None,
    gap: GapHandlingSpec,
    *,
    covariates: ArrayLike | None = None,
    partition: NDArray[np.int64] | None = None,
) -> _PreparedPair:
    time_values = np.asarray(time, dtype=float)
    first_values = np.asarray(first, dtype=float)
    second_values = np.asarray(second, dtype=float)
    if time_values.ndim != 1 or first_values.ndim != 1 or second_values.ndim != 1:
        raise ValueError("paired time and signal values must be one-dimensional")
    if not (len(time_values) == len(first_values) == len(second_values)):
        raise ValueError("paired time and signal values must align sample for sample")
    first_valid = _valid_mask(first_values, valid_first, "valid_first")
    second_valid = _valid_mask(second_values, valid_second, "valid_second")
    covariate_values: NDArray[np.float64] | None = None
    covariate_valid = np.ones(len(time_values), dtype=bool)
    if covariates is not None:
        covariate_values = np.asarray(covariates, dtype=float)
        if covariate_values.ndim == 1:
            covariate_values = covariate_values[:, np.newaxis]
        if covariate_values.ndim != 2 or covariate_values.shape[0] != len(time_values):
            raise ValueError("covariates must be sample by covariate")
        covariate_valid = np.all(np.isfinite(covariate_values), axis=1)
    joint_valid = first_valid & second_valid & covariate_valid
    selected = (
        np.ones(len(time_values), dtype=bool)
        if partition is None
        else np.asarray(partition >= 0, dtype=bool)
    )
    effective_joint_valid = joint_valid & selected
    prepared = _prepare_runs(
        time_values,
        first_values,
        effective_joint_valid,
        gap,
        partition=partition,
    )
    evidence = JointContinuityEvidence(
        prepared.evidence,
        int(np.count_nonzero(selected)),
        int(np.count_nonzero(selected & ~first_valid)),
        int(np.count_nonzero(selected & ~second_valid)),
        int(np.count_nonzero(selected & ~(first_valid & second_valid))),
        int(np.count_nonzero(effective_joint_valid)),
        int(np.count_nonzero(selected & ~covariate_valid)),
    )
    return _PreparedPair(
        prepared.time,
        prepared.values,
        second_values,
        covariate_values,
        prepared.indices,
        evidence,
    )


def _lagged_from_prepared(
    prepared: _PreparedPair,
    pair: SignalPairMetadata,
    spec: LaggedAssociationSpec,
    covariate_names: tuple[str, ...],
) -> LaggedAssociationResult:
    first_runs: list[NDArray[np.float64]] = []
    second_runs: list[NDArray[np.float64]] = []
    residual_runs: list[RunResidualization] = []
    for run_id, indices in enumerate(prepared.indices):
        first_values = prepared.first[indices]
        second_values = prepared.second[indices]
        if prepared.covariates is not None:
            first_values, second_values, evidence = _residualize_run(
                first_values,
                second_values,
                prepared.covariates[indices],
                covariate_names,
                spec.residualization,
                run_id,
            )
            residual_runs.append(evidence)
        if spec.detrend != "none":
            first_values = signal.detrend(first_values, type=spec.detrend)
            second_values = signal.detrend(second_values, type=spec.detrend)
        first_runs.append(np.asarray(first_values, dtype=float))
        second_runs.append(np.asarray(second_values, dtype=float))
    max_lag = round(spec.maximum_lag_s * prepared.evidence.continuity.sampling_rate_hz)
    max_lag = min(max_lag, max(len(run) for run in first_runs) - 1)
    lag_samples = np.arange(-max_lag, max_lag + 1)
    correlation, pairs = _cross_correlation(first_runs, second_runs, lag_samples)
    correlation[pairs < spec.minimum_pairs_per_lag] = np.nan
    lags = lag_samples * prepared.evidence.continuity.sampling_interval_s
    zero_index = max_lag
    usable = np.isfinite(correlation)
    if not usable.any():
        raise ValueError("no lag has the declared minimum paired support")
    peak_index = int(np.nanargmax(np.abs(correlation)))
    blocked = _blocked_permutation(
        first_runs,
        second_runs,
        lag_samples,
        correlation[zero_index],
        correlation[peak_index],
        prepared.evidence.continuity.sampling_rate_hz,
        spec.blocked_permutation,
        spec.minimum_pairs_per_lag,
    )
    residualization = (
        ResidualizationEvidence(
            covariate_names,
            spec.residualization,
            tuple(residual_runs),
        )
        if prepared.covariates is not None
        else None
    )
    return LaggedAssociationResult(
        pair,
        spec,
        _float_tuple(lags),
        _float_tuple(correlation),
        tuple(int(value) for value in pairs),
        float(correlation[zero_index]),
        float(lags[peak_index]),
        float(correlation[peak_index]),
        prepared.evidence,
        residualization,
        blocked,
    )


def _residualize_run(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    covariates: NDArray[np.float64],
    names: tuple[str, ...],
    spec: ResidualizationSpec,
    run_id: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64], RunResidualization]:
    active = np.std(covariates, axis=0) > np.finfo(float).eps
    selected = covariates[:, active]
    active_names = tuple(name for name, keep in zip(names, active, strict=True) if keep)
    if spec.standardize_covariates and selected.shape[1]:
        selected = (selected - np.mean(selected, axis=0)) / np.std(selected, axis=0)
    design = np.column_stack((np.ones(len(first)), selected))
    rank = int(np.linalg.matrix_rank(design))
    first_coefficients = _regression_coefficients(design, first, spec.ridge_alpha)
    second_coefficients = _regression_coefficients(design, second, spec.ridge_alpha)
    first_fitted = design @ first_coefficients
    second_fitted = design @ second_coefficients
    first_residual = first - first_fitted
    second_residual = second - second_fitted
    evidence = RunResidualization(
        run_id,
        len(first),
        rank,
        active_names,
        _float_tuple(first_coefficients),
        _float_tuple(second_coefficients),
        _r_squared(first, first_residual),
        _r_squared(second, second_residual),
    )
    return first_residual, second_residual, evidence


def _regression_coefficients(
    design: NDArray[np.float64], values: NDArray[np.float64], ridge_alpha: float
) -> NDArray[np.float64]:
    if ridge_alpha == 0:
        coefficients, _, _, _ = np.linalg.lstsq(design, values, rcond=None)
        return np.asarray(coefficients, dtype=float)
    penalty = np.eye(design.shape[1]) * ridge_alpha
    penalty[0, 0] = 0
    return np.asarray(
        np.linalg.solve(design.T @ design + penalty, design.T @ values),
        dtype=float,
    )


def _r_squared(values: NDArray[np.float64], residuals: NDArray[np.float64]) -> float:
    total = float(np.sum((values - np.mean(values)) ** 2))
    return float(1 - np.sum(residuals**2) / total) if total > 0 else float("nan")


def _cross_correlation(
    first_runs: list[NDArray[np.float64]],
    second_runs: list[NDArray[np.float64]],
    lag_samples: NDArray[np.int64],
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    numerator = np.zeros(len(lag_samples))
    first_power = np.zeros(len(lag_samples))
    second_power = np.zeros(len(lag_samples))
    pairs = np.zeros(len(lag_samples), dtype=np.int64)
    for first, second in zip(first_runs, second_runs, strict=True):
        for index, lag in enumerate(lag_samples):
            if lag > 0:
                left = first[:-lag]
                right = second[lag:]
            elif lag < 0:
                left = first[-lag:]
                right = second[:lag]
            else:
                left = first
                right = second
            if not len(left):
                continue
            numerator[index] += np.dot(left, right)
            first_power[index] += np.dot(left, left)
            second_power[index] += np.dot(right, right)
            pairs[index] += len(left)
    denominator = np.sqrt(first_power * second_power)
    correlation = np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, np.nan),
        where=denominator > 0,
    )
    return correlation, pairs


def _blocked_permutation(
    first_runs: list[NDArray[np.float64]],
    second_runs: list[NDArray[np.float64]],
    lag_samples: NDArray[np.int64],
    observed_zero: float,
    observed_peak: float,
    sampling_rate_hz: float,
    spec: BlockPermutationSpec | None,
    minimum_pairs: int,
) -> BlockPermutationResult | None:
    if spec is None:
        return None
    block_samples = round(spec.block_duration_s * sampling_rate_hz)
    first_blocks: list[NDArray[np.float64]] = []
    second_blocks: list[NDArray[np.float64]] = []
    for first, second in zip(first_runs, second_runs, strict=True):
        for start in range(0, len(first) - block_samples + 1, block_samples):
            first_blocks.append(first[start : start + block_samples])
            second_blocks.append(second[start : start + block_samples])
    if len(first_blocks) < 3:
        raise ValueError("blocked association requires at least three complete blocks")
    rng = np.random.default_rng(spec.seed)
    zero_null = np.empty(spec.resamples)
    peak_null = np.empty(spec.resamples)
    zero_index = int(np.flatnonzero(lag_samples == 0)[0])
    for draw in range(spec.resamples):
        permutation = rng.permutation(len(second_blocks))
        permuted = [second_blocks[index] for index in permutation]
        correlation, pairs = _cross_correlation(first_blocks, permuted, lag_samples)
        correlation[pairs < minimum_pairs] = np.nan
        zero_null[draw] = correlation[zero_index]
        peak_null[draw] = np.nanmax(np.abs(correlation))
    zero_pvalue = float(
        (1 + np.count_nonzero(np.abs(zero_null) >= abs(observed_zero)))
        / (spec.resamples + 1)
    )
    peak_pvalue = float(
        (1 + np.count_nonzero(peak_null >= abs(observed_peak))) / (spec.resamples + 1)
    )
    return BlockPermutationResult(
        spec.block_duration_s,
        block_samples,
        len(first_blocks),
        spec.resamples,
        spec.seed,
        zero_pvalue,
        peak_pvalue,
    )


def _zero_lag_with_control(
    time: ArrayLike,
    values: ArrayLike,
    control: NDArray[np.float64],
    pair: SignalPairMetadata,
    spec: LaggedAssociationSpec,
    valid: ArrayLike | None,
) -> float:
    control_identity = ChannelIdentity(
        "shared-control",
        "shared",
        "control",
        "control",
        pair.first.unit,
    )
    control_pair = SignalPairMetadata(
        pair.subject,
        pair.session,
        f"{pair.pair_id}:control",
        pair.first,
        control_identity,
        pair.clock_id,
        pair.alignment_policy,
        pair.preprocessing_fingerprint,
    )
    return lagged_association(
        time,
        values,
        control,
        control_pair,
        spec,
        valid_first=valid,
    ).zero_lag_correlation


def _valid_mask(
    values: NDArray[np.float64], valid: ArrayLike | None, name: str
) -> NDArray[np.bool_]:
    if valid is None:
        mask = np.ones(len(values), dtype=bool)
    else:
        mask = np.asarray(valid, dtype=bool)
        if mask.shape != values.shape:
            raise ValueError(f"{name} must match its signal samples")
    return np.asarray(mask & np.isfinite(values), dtype=bool)


def _validate_covariate_names(
    covariates: NDArray[np.float64] | None,
    names: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    if covariates is None:
        if names:
            raise ValueError("covariate_names require covariate values")
        return ()
    if names is None:
        raise ValueError("covariate_names are required with covariate values")
    cleaned = tuple(str(name).strip() for name in names)
    if len(cleaned) != covariates.shape[1]:
        raise ValueError("covariate_names must match covariate columns")
    if any(not name for name in cleaned) or len(set(cleaned)) != len(cleaned):
        raise ValueError("covariate_names must be non-empty and unique")
    return cleaned


def _separation(first: float | None, second: float | None) -> float | None:
    return abs(first - second) if first is not None and second is not None else None


def _shared_identifier(first: str | None, second: str | None) -> bool | None:
    return first == second if first is not None and second is not None else None


def _float_tuple(values: ArrayLike) -> tuple[float, ...]:
    return tuple(float(value) for value in np.asarray(values, dtype=float))
