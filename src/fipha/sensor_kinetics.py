"""Gap-bounded sensor forward models and guarded regularized deconvolution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import optimize, signal, sparse
from scipy.sparse import linalg as sparse_linalg

from fipha.spectral import (
    ContinuityEvidence,
    GapHandlingSpec,
    _prepare_runs,
)

CoefficientSource: TypeAlias = Literal["independently_calibrated", "user_declared"]
KernelNormalization: TypeAlias = Literal["unit_area", "as_supplied"]
IdentifiabilitySeverity: TypeAlias = Literal["warning", "error"]
IdentifiabilityStatus: TypeAlias = Literal["pass", "warning", "fail"]
SmoothnessOrder: TypeAlias = Literal[0, 1, 2]


@dataclass(frozen=True)
class KineticModelIdentity:
    """Versioned scientific identity and unit contract for one response model."""

    model_id: str
    model_version: str
    sensor_profile_id: str
    sensor_profile_version: str
    input_quantity: str
    input_unit: str
    output_unit: str
    measurement_context: str
    evidence_source: str
    coefficient_source: CoefficientSource
    calibration_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "model_id",
            "model_version",
            "sensor_profile_id",
            "sensor_profile_version",
            "input_quantity",
            "input_unit",
            "output_unit",
            "measurement_context",
            "evidence_source",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must be non-empty")
            object.__setattr__(self, name, value)
        if self.coefficient_source not in {
            "independently_calibrated",
            "user_declared",
        }:
            raise ValueError("unsupported kinetic coefficient source")
        if self.coefficient_source == "independently_calibrated":
            if self.calibration_id is None or not self.calibration_id.strip():
                raise ValueError(
                    "independently calibrated models require a calibration_id"
                )
        elif self.calibration_id is not None:
            raise ValueError(
                "calibration_id is reserved for independently calibrated models"
            )


@dataclass(frozen=True)
class DifferenceOfExponentialsModel:
    """Causal unit-area rise/decay response with a declared steady-state gain."""

    identity: KineticModelIdentity
    rise_time_constant_s: float
    decay_time_constant_s: float
    gain: float = 1.0
    latency_s: float = 0.0
    tail_fraction: float = 1e-4

    def __post_init__(self) -> None:
        if not np.isfinite(self.rise_time_constant_s) or self.rise_time_constant_s <= 0:
            raise ValueError("rise_time_constant_s must be finite and positive")
        if (
            not np.isfinite(self.decay_time_constant_s)
            or self.decay_time_constant_s <= self.rise_time_constant_s
        ):
            raise ValueError("decay_time_constant_s must exceed rise_time_constant_s")
        if not np.isfinite(self.gain) or self.gain == 0:
            raise ValueError("kinetic model gain must be finite and non-zero")
        if not np.isfinite(self.latency_s) or self.latency_s < 0:
            raise ValueError("kinetic model latency must be finite and non-negative")
        if not 0 < self.tail_fraction < 0.1:
            raise ValueError("tail_fraction must lie between zero and 0.1")


@dataclass(frozen=True)
class SampledImpulseResponseModel:
    """Causal sampled response density for empirical or external model families."""

    identity: KineticModelIdentity
    sample_interval_s: float
    response_density: tuple[float, ...]
    normalization: KernelNormalization = "as_supplied"
    gain: float = 1.0

    def __post_init__(self) -> None:
        if not np.isfinite(self.sample_interval_s) or self.sample_interval_s <= 0:
            raise ValueError("sampled response interval must be finite and positive")
        values = np.asarray(self.response_density, dtype=float)
        if len(values) < 2 or not np.all(np.isfinite(values)):
            raise ValueError(
                "sampled response requires two or more finite density values"
            )
        if np.max(np.abs(values)) <= np.finfo(float).eps:
            raise ValueError("sampled response cannot be identically zero")
        if self.normalization not in {"unit_area", "as_supplied"}:
            raise ValueError("unsupported sampled response normalization")
        area = float(np.sum(values) * self.sample_interval_s)
        if self.normalization == "unit_area" and abs(area) <= np.finfo(float).eps:
            raise ValueError("unit-area sampled response requires non-zero area")
        if not np.isfinite(self.gain) or self.gain == 0:
            raise ValueError("sampled response gain must be finite and non-zero")
        object.__setattr__(self, "response_density", tuple(float(x) for x in values))


KineticForwardModel: TypeAlias = (
    DifferenceOfExponentialsModel | SampledImpulseResponseModel
)


@dataclass(frozen=True)
class KineticKernel:
    """Executable discrete kernel and its continuous-time interpretation."""

    sample_interval_s: float
    times_s: tuple[float, ...]
    response_density: tuple[float, ...]
    convolution_weights: tuple[float, ...]
    integral: float
    absolute_integral: float
    peak_time_s: float
    support_s: float
    source_family: str


@dataclass(frozen=True)
class KineticForwardSpec:
    """Declare gap and initial-state policy for forward prediction."""

    gap: GapHandlingSpec = field(default_factory=GapHandlingSpec)
    initial_state: Literal["zero_at_each_run"] = "zero_at_each_run"

    def __post_init__(self) -> None:
        if self.initial_state != "zero_at_each_run":
            raise ValueError("unsupported kinetic initial-state policy")


@dataclass(frozen=True)
class KineticForwardRun:
    """One continuity run predicted without carrying state across its boundary."""

    run_id: int
    start_s: float
    stop_s: float
    sample_count: int
    kernel_sample_count: int
    boundary_affected_sample_count: int


@dataclass(frozen=True)
class KineticForwardResult:
    """Predicted sensor output plus model, continuity, and boundary evidence."""

    time_s: tuple[float, ...]
    predicted_output: tuple[float, ...]
    valid: tuple[bool, ...]
    model: KineticForwardModel
    spec: KineticForwardSpec
    kernel: KineticKernel
    continuity: ContinuityEvidence
    runs: tuple[KineticForwardRun, ...]
    evidence_fingerprint: str
    interpretation: str
    method: str = "gap_bounded_causal_sensor_forward_convolution"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize output, model identity, continuity, and provenance."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class KineticDeconvolutionSpec:
    """Declare regularization and pre-outcome identifiability gates."""

    regularization_strength: float
    regularization_source: str
    smoothness_order: SmoothnessOrder = 1
    nonnegative: bool = False
    fit_run_baseline: bool = True
    minimum_samples_per_rise: float = 3.0
    minimum_run_to_kernel_ratio: float = 2.0
    maximum_regularized_condition_number: float = 1e8
    minimum_transfer_fraction: float = 0.05
    require_independent_calibration: bool = False
    maximum_iterations: int = 1_000
    gap: GapHandlingSpec = field(default_factory=GapHandlingSpec)

    def __post_init__(self) -> None:
        if (
            not np.isfinite(self.regularization_strength)
            or self.regularization_strength <= 0
        ):
            raise ValueError(
                "deconvolution regularization_strength must be finite and positive"
            )
        if not self.regularization_source.strip():
            raise ValueError("regularization_source must be non-empty")
        if self.smoothness_order not in {0, 1, 2}:
            raise ValueError("smoothness_order must be zero, one, or two")
        for name in (
            "minimum_samples_per_rise",
            "minimum_run_to_kernel_ratio",
            "maximum_regularized_condition_number",
        ):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not 0 < self.minimum_transfer_fraction < 1:
            raise ValueError("minimum_transfer_fraction must lie between zero and one")
        if self.maximum_iterations < 1:
            raise ValueError("maximum_iterations must be positive")


@dataclass(frozen=True)
class KineticIdentifiabilityIssue:
    """One actionable reason to warn about or refuse sensor inversion."""

    severity: IdentifiabilitySeverity
    code: str
    message: str
    run_id: int | None = None


@dataclass(frozen=True)
class KineticRunIdentifiability:
    """Pre-outcome sampling and duration evidence for one continuity run."""

    run_id: int
    start_s: float
    stop_s: float
    sample_count: int
    duration_s: float
    run_to_kernel_ratio: float
    eligible: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class KineticIdentifiabilityAssessment:
    """Outcome-blind model, sampling, transfer, and regularization assessment."""

    status: IdentifiabilityStatus
    model: KineticForwardModel
    spec: KineticDeconvolutionSpec
    kernel: KineticKernel
    continuity: ContinuityEvidence
    samples_per_rise: float | None
    nyquist_hz: float
    recoverable_bandwidth_hz: float
    unregularized_condition_number: float
    regularized_condition_number: float
    maximum_regularized_inverse_gain: float
    runs: tuple[KineticRunIdentifiability, ...]
    issues: tuple[KineticIdentifiabilityIssue, ...]
    interpretation: str

    def require_ready(self, *, allow_warnings: bool = True) -> None:
        """Raise when the assessment cannot support the requested inversion."""
        if self.status == "fail":
            raise ValueError("kinetic deconvolution identifiability assessment failed")
        if self.status == "warning" and not allow_warnings:
            raise ValueError("kinetic deconvolution has unresolved warnings")

    def to_json(self) -> str:
        """Serialize the complete prospective identifiability assessment."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class KineticDeconvolutionRun:
    """One solved run's reconstruction and optimization diagnostics."""

    run_id: int
    start_s: float
    stop_s: float
    sample_count: int
    boundary_affected_sample_count: int
    baseline: float
    reconstruction_rmse: float
    reconstruction_r_squared: float
    reconstruction_correlation: float | None
    latent_roughness: float
    active_lower_bound_fraction: float
    solver_iterations: int


@dataclass(frozen=True)
class KineticDeconvolutionResult:
    """Conditional latent-input estimate with reconstruction and refusal evidence."""

    time_s: tuple[float, ...]
    latent_input: tuple[float, ...]
    reconstructed_output: tuple[float, ...]
    solved: tuple[bool, ...]
    model: KineticForwardModel
    spec: KineticDeconvolutionSpec
    assessment: KineticIdentifiabilityAssessment
    runs: tuple[KineticDeconvolutionRun, ...]
    evidence_fingerprint: str
    input_quantity: str
    input_unit: str
    output_unit: str
    interpretation: str
    method: str = "gap_bounded_regularized_linear_sensor_deconvolution"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize estimates, diagnostics, model assumptions, and provenance."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def kinetic_kernel(
    model: KineticForwardModel, sample_interval_s: float
) -> KineticKernel:
    """Materialize one causal model on a declared regular sampling interval."""
    if not np.isfinite(sample_interval_s) or sample_interval_s <= 0:
        raise ValueError("kernel sample interval must be finite and positive")
    if isinstance(model, DifferenceOfExponentialsModel):
        support = model.latency_s - model.decay_time_constant_s * np.log(
            model.tail_fraction
        )
        times = np.arange(0, support + sample_interval_s / 2, sample_interval_s)
        active = np.maximum(times - model.latency_s, 0)
        density = np.where(
            times >= model.latency_s,
            np.exp(-active / model.decay_time_constant_s)
            - np.exp(-active / model.rise_time_constant_s),
            0.0,
        )
        area = float(np.sum(density) * sample_interval_s)
        if area <= np.finfo(float).eps:
            raise ValueError(
                "sampling interval is too coarse to represent the kinetic kernel"
            )
        density = model.gain * density / area
        family = "difference_of_exponentials"
    else:
        source = np.asarray(model.response_density, dtype=float)
        source_times = np.arange(len(source), dtype=float) * model.sample_interval_s
        support = float(source_times[-1])
        times = np.arange(0, support + sample_interval_s / 2, sample_interval_s)
        density = np.interp(times, source_times, source)
        if model.normalization == "unit_area":
            area = float(np.sum(density) * sample_interval_s)
            if abs(area) <= np.finfo(float).eps:
                raise ValueError(
                    "resampled unit-area response has numerically zero integral"
                )
            density = density / area
        density = model.gain * density
        family = "sampled_impulse_response"
    weights = density * sample_interval_s
    integral = float(np.sum(weights))
    absolute_integral = float(np.sum(np.abs(weights)))
    peak_index = int(np.argmax(np.abs(density)))
    return KineticKernel(
        sample_interval_s=sample_interval_s,
        times_s=tuple(float(x) for x in times),
        response_density=tuple(float(x) for x in density),
        convolution_weights=tuple(float(x) for x in weights),
        integral=integral,
        absolute_integral=absolute_integral,
        peak_time_s=float(times[peak_index]),
        support_s=float(times[-1]),
        source_family=family,
    )


def predict_sensor_response(
    time: ArrayLike,
    latent_input: ArrayLike,
    model: KineticForwardModel,
    spec: KineticForwardSpec | None = None,
    *,
    valid: ArrayLike | None = None,
) -> KineticForwardResult:
    """Apply a causal sensor model separately inside every valid continuity run."""
    spec = spec or KineticForwardSpec()
    prepared = _prepare_runs(time, latent_input, valid, spec.gap)
    kernel = kinetic_kernel(model, prepared.evidence.sampling_interval_s)
    predicted = np.full(len(prepared.time), np.nan)
    output_valid: NDArray[np.bool_] = np.zeros(len(prepared.time), dtype=bool)
    runs = []
    weights = np.asarray(kernel.convolution_weights)
    for run, indices in zip(prepared.evidence.runs, prepared.indices, strict=True):
        values = prepared.values[indices]
        prediction = signal.fftconvolve(values, weights, mode="full")[: len(values)]
        predicted[indices] = prediction
        output_valid[indices] = True
        runs.append(
            KineticForwardRun(
                run_id=run.run_id,
                start_s=run.start_s,
                stop_s=run.stop_s,
                sample_count=run.sample_count,
                kernel_sample_count=len(weights),
                boundary_affected_sample_count=min(len(weights) - 1, len(values)),
            )
        )
    fingerprint = _fingerprint(
        prepared.time,
        prepared.values,
        output_valid,
        model,
        spec,
        "forward",
    )
    return KineticForwardResult(
        time_s=tuple(float(x) for x in prepared.time),
        predicted_output=tuple(float(x) for x in predicted),
        valid=tuple(bool(x) for x in output_valid),
        model=model,
        spec=spec,
        kernel=kernel,
        continuity=prepared.evidence,
        runs=tuple(runs),
        evidence_fingerprint=fingerprint,
        interpretation=(
            "Predicted output is conditional on the declared linear time-invariant "
            "model and a zero initial state at every continuity-run boundary."
        ),
    )


def assess_kinetic_identifiability(
    time: ArrayLike,
    model: KineticForwardModel,
    spec: KineticDeconvolutionSpec,
    *,
    valid: ArrayLike | None = None,
) -> KineticIdentifiabilityAssessment:
    """Assess sampling, duration, calibration, and regularized transfer pre-outcome."""
    time_values = np.asarray(time, dtype=float)
    dummy: NDArray[np.float64] = np.zeros(len(time_values), dtype=float)
    prepared = _prepare_runs(time_values, dummy, valid, spec.gap)
    interval = prepared.evidence.sampling_interval_s
    kernel = kinetic_kernel(model, interval)
    identity = model.identity
    issues: list[KineticIdentifiabilityIssue] = []
    if identity.coefficient_source == "user_declared":
        severity: IdentifiabilitySeverity = (
            "error" if spec.require_independent_calibration else "warning"
        )
        issues.append(
            KineticIdentifiabilityIssue(
                severity,
                "kinetic_model_not_independently_calibrated",
                "Model coefficients are user-declared sensitivity assumptions.",
            )
        )
    samples_per_rise = None
    if isinstance(model, DifferenceOfExponentialsModel):
        samples_per_rise = model.rise_time_constant_s / interval
        if samples_per_rise < spec.minimum_samples_per_rise:
            issues.append(
                KineticIdentifiabilityIssue(
                    "error",
                    "rise_dynamics_under_sampled",
                    f"{samples_per_rise:.3g} samples per rise time constant is below "
                    f"the declared minimum {spec.minimum_samples_per_rise:g}.",
                )
            )
    transfer = np.abs(
        np.fft.rfft(
            np.asarray(kernel.convolution_weights),
            n=_next_power_of_two(max(256, 2 * len(kernel.convolution_weights))),
        )
    )
    frequencies = np.fft.rfftfreq(2 * (len(transfer) - 1), interval)
    maximum_transfer = float(np.max(transfer))
    positive = transfer[transfer > np.finfo(float).eps * maximum_transfer]
    unregularized_condition = (
        float(maximum_transfer / np.min(positive)) if len(positive) else float("inf")
    )
    penalty = _frequency_penalty(len(transfer), spec.smoothness_order)
    denominator = transfer**2 + spec.regularization_strength * penalty
    unresolved = denominator <= np.finfo(float).eps
    if np.any(unresolved):
        issues.append(
            KineticIdentifiabilityIssue(
                "error",
                "regularization_leaves_transfer_nullspace",
                "The model and selected penalty leave at least one frequency "
                "unidentified.",
            )
        )
    positive_denominator = denominator[denominator > np.finfo(float).eps]
    regularized_condition = float(
        np.max(positive_denominator) / np.min(positive_denominator)
    )
    inverse_gain = np.divide(
        transfer,
        denominator,
        out=np.zeros_like(transfer),
        where=~unresolved,
    )
    maximum_inverse_gain = float(np.max(inverse_gain))
    if regularized_condition > spec.maximum_regularized_condition_number:
        issues.append(
            KineticIdentifiabilityIssue(
                "error",
                "regularized_system_ill_conditioned",
                f"Regularized transfer condition {regularized_condition:.3g} "
                "exceeds the declared maximum.",
            )
        )
    retained = frequencies[
        transfer >= spec.minimum_transfer_fraction * maximum_transfer
    ]
    recoverable_bandwidth = float(retained[-1]) if len(retained) else 0.0
    if recoverable_bandwidth < 1 / max(kernel.support_s, interval):
        issues.append(
            KineticIdentifiabilityIssue(
                "warning",
                "narrow_model_transfer_bandwidth",
                "The declared response strongly attenuates most measured frequencies.",
            )
        )
    run_results = []
    for run in prepared.evidence.runs:
        ratio = run.exposure_s / max(kernel.support_s, interval)
        enough_for_penalty = run.sample_count > spec.smoothness_order
        eligible = ratio >= spec.minimum_run_to_kernel_ratio and enough_for_penalty
        if eligible:
            reason = None
        elif not enough_for_penalty:
            reason = "fewer_samples_than_regularization_requires"
        else:
            reason = "run_shorter_than_kernel_ratio_gate"
        run_results.append(
            KineticRunIdentifiability(
                run.run_id,
                run.start_s,
                run.stop_s,
                run.sample_count,
                run.exposure_s,
                ratio,
                eligible,
                reason,
            )
        )
        if not eligible:
            message = (
                "Run has too few samples for the selected regularization order."
                if not enough_for_penalty
                else "Run is excluded because it is too short relative to "
                "kernel support."
            )
            issues.append(
                KineticIdentifiabilityIssue(
                    "warning",
                    "continuity_run_too_short",
                    message,
                    run.run_id,
                )
            )
    if not any(run.eligible for run in run_results):
        issues.append(
            KineticIdentifiabilityIssue(
                "error",
                "no_eligible_continuity_run",
                "No run satisfies the declared duration-to-kernel gate.",
            )
        )
    status: IdentifiabilityStatus
    if any(issue.severity == "error" for issue in issues):
        status = "fail"
    elif issues:
        status = "warning"
    else:
        status = "pass"
    return KineticIdentifiabilityAssessment(
        status=status,
        model=model,
        spec=spec,
        kernel=kernel,
        continuity=prepared.evidence,
        samples_per_rise=samples_per_rise,
        nyquist_hz=0.5 / interval,
        recoverable_bandwidth_hz=recoverable_bandwidth,
        unregularized_condition_number=unregularized_condition,
        regularized_condition_number=regularized_condition,
        maximum_regularized_inverse_gain=maximum_inverse_gain,
        runs=tuple(run_results),
        issues=tuple(issues),
        interpretation=(
            "Identifiability describes the declared linear model, sampling, run "
            "duration, and regularization; it does not validate the model in vivo."
        ),
    )


def deconvolve_sensor_response(
    time: ArrayLike,
    observed_output: ArrayLike,
    model: KineticForwardModel,
    spec: KineticDeconvolutionSpec,
    *,
    valid: ArrayLike | None = None,
) -> KineticDeconvolutionResult:
    """Estimate conditional latent input after prospective identifiability gates."""
    time_values = np.asarray(time, dtype=float)
    observed_values = np.asarray(observed_output, dtype=float)
    if observed_values.shape != time_values.shape or observed_values.ndim != 1:
        raise ValueError("observed kinetic output must match one-dimensional time")
    combined_valid: NDArray[np.bool_] = np.isfinite(observed_values)
    if valid is not None:
        declared_valid = np.asarray(valid, dtype=bool)
        if declared_valid.shape != time_values.shape:
            raise ValueError("kinetic validity must match time")
        combined_valid &= declared_valid
    assessment = assess_kinetic_identifiability(
        time_values, model, spec, valid=combined_valid
    )
    assessment.require_ready()
    prepared = _prepare_runs(time_values, observed_values, combined_valid, spec.gap)
    eligible = {run.run_id for run in assessment.runs if run.eligible}
    latent = np.full(len(prepared.time), np.nan)
    reconstructed = np.full(len(prepared.time), np.nan)
    solved: NDArray[np.bool_] = np.zeros(len(prepared.time), dtype=bool)
    run_results = []
    weights = np.asarray(assessment.kernel.convolution_weights)
    for run, indices in zip(prepared.evidence.runs, prepared.indices, strict=True):
        if run.run_id not in eligible:
            continue
        values = prepared.values[indices]
        estimate, prediction, baseline, iterations = _solve_run(values, weights, spec)
        latent[indices] = estimate
        reconstructed[indices] = prediction
        solved[indices] = True
        residual = values - prediction
        variance = float(np.sum((values - np.mean(values)) ** 2))
        r_squared = (
            float(1 - np.sum(residual**2) / variance) if variance > 0 else float("nan")
        )
        correlation = _safe_correlation(values, prediction)
        difference_order = min(spec.smoothness_order, max(len(estimate) - 1, 0))
        roughness = float(
            np.sqrt(np.mean(np.diff(estimate, n=difference_order) ** 2))
            if difference_order > 0
            else np.sqrt(np.mean(estimate**2))
        )
        run_results.append(
            KineticDeconvolutionRun(
                run_id=run.run_id,
                start_s=run.start_s,
                stop_s=run.stop_s,
                sample_count=run.sample_count,
                boundary_affected_sample_count=min(len(weights) - 1, run.sample_count),
                baseline=baseline,
                reconstruction_rmse=float(np.sqrt(np.mean(residual**2))),
                reconstruction_r_squared=r_squared,
                reconstruction_correlation=correlation,
                latent_roughness=roughness,
                active_lower_bound_fraction=(
                    float(np.mean(estimate <= 1e-10)) if spec.nonnegative else 0.0
                ),
                solver_iterations=iterations,
            )
        )
    if not np.any(solved):
        raise ValueError("no continuity run was eligible for kinetic deconvolution")
    fingerprint = _fingerprint(
        prepared.time,
        prepared.values,
        solved,
        model,
        spec,
        "deconvolution",
    )
    identity = model.identity
    return KineticDeconvolutionResult(
        time_s=tuple(float(x) for x in prepared.time),
        latent_input=tuple(float(x) for x in latent),
        reconstructed_output=tuple(float(x) for x in reconstructed),
        solved=tuple(bool(x) for x in solved),
        model=model,
        spec=spec,
        assessment=assessment,
        runs=tuple(run_results),
        evidence_fingerprint=fingerprint,
        input_quantity=identity.input_quantity,
        input_unit=identity.input_unit,
        output_unit=identity.output_unit,
        interpretation=(
            "Latent input is a regularized estimate conditional on the declared "
            "linear response, calibration source, baseline policy, and zero state "
            "at each gap. It is not ground-truth analyte concentration."
        ),
    )


def _solve_run(
    observed: NDArray[np.float64],
    weights: NDArray[np.float64],
    spec: KineticDeconvolutionSpec,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, int]:
    sample_count = len(observed)
    convolution = _convolution_matrix(weights, sample_count)
    penalty = _difference_matrix(sample_count, spec.smoothness_order)
    if spec.fit_run_baseline:
        design = sparse.hstack(
            (convolution, sparse.csr_matrix(np.ones((sample_count, 1)))),
            format="csr",
        )
        penalty_design = sparse.hstack(
            (penalty, sparse.csr_matrix((penalty.shape[0], 1))), format="csr"
        )
    else:
        design = convolution
        penalty_design = penalty
    augmented = sparse.vstack(
        (design, np.sqrt(spec.regularization_strength) * penalty_design),
        format="csr",
    )
    target = np.concatenate((observed, np.zeros(penalty.shape[0])))
    parameter_count = augmented.shape[1]
    if spec.nonnegative:
        initial = np.zeros(parameter_count)
        if spec.fit_run_baseline:
            initial[-1] = float(np.median(observed))
        bounds: list[tuple[float | None, float | None]] = [(0.0, None)] * sample_count
        if spec.fit_run_baseline:
            bounds.append((None, None))

        def objective(
            parameters: NDArray[np.float64],
        ) -> tuple[float, NDArray[np.float64]]:
            residual = np.asarray(augmented @ parameters).ravel() - target
            gradient = np.asarray(augmented.T @ residual).ravel()
            return 0.5 * float(residual @ residual), gradient

        constrained_result = optimize.minimize(
            objective,
            initial,
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={"maxiter": spec.maximum_iterations, "ftol": 1e-12},
        )
        if not constrained_result.success:
            raise ValueError(
                f"constrained kinetic solver failed: {constrained_result.message}"
            )
        parameters = np.asarray(constrained_result.x, dtype=float)
        iterations = int(constrained_result.nit)
    else:
        unconstrained_result = sparse_linalg.lsmr(
            augmented,
            target,
            atol=1e-10,
            btol=1e-10,
            maxiter=spec.maximum_iterations,
        )
        if unconstrained_result[1] == 7:
            raise ValueError("kinetic solver reached maximum iterations")
        parameters = np.asarray(unconstrained_result[0], dtype=float)
        iterations = int(unconstrained_result[2])
    if spec.fit_run_baseline:
        estimate = parameters[:-1]
        baseline = float(parameters[-1])
    else:
        estimate = parameters
        baseline = 0.0
    prediction = np.asarray(convolution @ estimate).ravel() + baseline
    return estimate, prediction, baseline, iterations


def _convolution_matrix(
    weights: NDArray[np.float64], sample_count: int
) -> sparse.csr_matrix:
    width = min(len(weights), sample_count)
    diagonals = [np.full(sample_count - lag, weights[lag]) for lag in range(width)]
    return sparse.diags(
        diagonals,
        offsets=-np.arange(width),
        shape=(sample_count, sample_count),
        format="csr",
    )


def _difference_matrix(sample_count: int, order: SmoothnessOrder) -> sparse.csr_matrix:
    if order == 0:
        return sparse.eye(sample_count, format="csr")
    if order == 1:
        return sparse.diags(
            (-np.ones(sample_count - 1), np.ones(sample_count - 1)),
            (0, 1),
            shape=(sample_count - 1, sample_count),
            format="csr",
        )
    if sample_count < 3:
        raise ValueError("second-order regularization requires at least three samples")
    return sparse.diags(
        (
            np.ones(sample_count - 2),
            -2 * np.ones(sample_count - 2),
            np.ones(sample_count - 2),
        ),
        (0, 1, 2),
        shape=(sample_count - 2, sample_count),
        format="csr",
    )


def _frequency_penalty(length: int, order: SmoothnessOrder) -> NDArray[np.float64]:
    frequency = np.linspace(0, np.pi, length)
    if order == 0:
        return np.ones(length)
    return (2 - 2 * np.cos(frequency)) ** order


def _next_power_of_two(value: int) -> int:
    return 1 << (value - 1).bit_length()


def _safe_correlation(
    first: NDArray[np.float64], second: NDArray[np.float64]
) -> float | None:
    if np.std(first) <= np.finfo(float).eps or np.std(second) <= np.finfo(float).eps:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def _fingerprint(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    valid: NDArray[np.bool_],
    model: KineticForwardModel,
    spec: KineticForwardSpec | KineticDeconvolutionSpec,
    operation: str,
) -> str:
    digest = hashlib.sha256()
    for array in (time.astype("<f8"), values.astype("<f8"), valid.astype("u1")):
        digest.update(array.tobytes())
    digest.update(
        json.dumps(
            {
                "operation": operation,
                "model": asdict(model),
                "spec": asdict(spec),
            },
            sort_keys=True,
        ).encode()
    )
    return f"sha256:{digest.hexdigest()}"
