"""Leakage-safe event-kernel encoding models for continuous photometry signals."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from itertools import pairwise
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse import csr_matrix, lil_matrix, vstack
from scipy.stats import norm
from scipy.stats import t as student_t


@dataclass(frozen=True)
class FIRBasisSpec:
    """One unconstrained coefficient per sampled event lag."""

    family: Literal["fir"] = "fir"
    schema_version: str = "1"


@dataclass(frozen=True)
class RaisedCosineBasisSpec:
    """A lower-dimensional linear raised-cosine basis over the lag window."""

    functions: int
    family: Literal["raised_cosine"] = "raised_cosine"
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if self.functions < 1:
            raise ValueError("raised-cosine basis functions must be positive")


EventKernelBasisSpec: TypeAlias = FIRBasisSpec | RaisedCosineBasisSpec


@dataclass(frozen=True)
class EventModulationSpec:
    """Multiply an event kernel by a declared current or lagged event value."""

    value: str
    lag_events: int = 0
    unavailable_value: float = 0.0
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("event-modulation value name must be non-empty")
        if isinstance(self.lag_events, bool) or not isinstance(self.lag_events, int):
            raise ValueError("event-modulation lag_events must be an integer")
        if self.lag_events < 0:
            raise ValueError("event-modulation lag_events must be nonnegative")
        if not np.isfinite(self.unavailable_value):
            raise ValueError("event-modulation unavailable_value must be finite")


@dataclass(frozen=True)
class EventKernelSpec:
    """One named event train, lag window and typed kernel basis."""

    name: str
    window_s: tuple[float, float]
    basis: EventKernelBasisSpec = field(default_factory=FIRBasisSpec)
    source_event: str | None = None
    modulation: EventModulationSpec | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("event-kernel name must be non-empty")
        if self.source_event is not None and not self.source_event.strip():
            raise ValueError("event-kernel source_event must be non-empty")
        if self.window_s[0] > self.window_s[1]:
            raise ValueError("event-kernel window start must not exceed stop")


@dataclass(frozen=True)
class LinearProgressBasisSpec:
    """Piecewise-linear basis over normalized interval progress in ``[0, 1]``."""

    functions: int = 5
    evaluation_points: int = 101
    family: Literal["linear_progress"] = "linear_progress"
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if isinstance(self.functions, bool) or not isinstance(self.functions, int):
            raise ValueError("progress-basis functions must be an integer")
        if self.functions < 1:
            raise ValueError("progress-basis functions must be positive")
        if isinstance(self.evaluation_points, bool) or not isinstance(
            self.evaluation_points, int
        ):
            raise ValueError("progress-basis evaluation_points must be an integer")
        if self.evaluation_points < 2:
            raise ValueError("progress-basis evaluation_points must be at least two")


@dataclass(frozen=True)
class ProgressKernelSpec:
    """One normalized-progress trajectory for a named interval family."""

    name: str
    source_interval: str | None = None
    basis: LinearProgressBasisSpec = field(default_factory=LinearProgressBasisSpec)
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("progress-kernel name must be non-empty")
        if self.source_interval is not None and not self.source_interval.strip():
            raise ValueError("progress-kernel source_interval must be non-empty")


@dataclass(frozen=True)
class EncodingSession:
    """One continuous response with aligned events and continuous covariates."""

    subject: str
    session: str
    time: NDArray[np.float64]
    response: NDArray[np.float64]
    events: Mapping[str, tuple[float, ...]]
    continuous_covariates: Mapping[str, NDArray[np.float64]]
    response_valid: NDArray[np.bool_] | None = None
    continuous_covariate_validity: Mapping[str, NDArray[np.bool_]] = field(
        default_factory=dict
    )
    event_values: Mapping[str, Mapping[str, tuple[float, ...]]] = field(
        default_factory=dict
    )
    intervals: Mapping[str, tuple[tuple[float, float], ...]] = field(
        default_factory=dict
    )

    @classmethod
    def from_arrays(
        cls,
        *,
        subject: str,
        session: str,
        time: ArrayLike,
        response: ArrayLike,
        events: Mapping[str, Sequence[float]],
        continuous_covariates: Mapping[str, ArrayLike] | None = None,
        response_valid: ArrayLike | None = None,
        continuous_covariate_validity: Mapping[str, ArrayLike] | None = None,
        event_values: Mapping[str, Mapping[str, Sequence[float]]] | None = None,
        intervals: Mapping[str, Sequence[tuple[float, float]]] | None = None,
    ) -> EncodingSession:
        """Create a validated session without joining signals across recordings."""
        time_values = np.asarray(time, dtype=float)
        response_values = np.asarray(response, dtype=float)
        covariates = {
            name: np.asarray(values, dtype=float)
            for name, values in (continuous_covariates or {}).items()
        }
        covariate_validity = {
            name: np.asarray(values, dtype=bool)
            for name, values in (continuous_covariate_validity or {}).items()
        }
        result = cls(
            subject=str(subject),
            session=str(session),
            time=time_values.copy(),
            response=response_values.copy(),
            events={
                name: tuple(float(value) for value in values)
                for name, values in events.items()
            },
            continuous_covariates={
                name: values.copy() for name, values in covariates.items()
            },
            response_valid=(
                np.asarray(response_valid, dtype=bool).copy()
                if response_valid is not None
                else None
            ),
            continuous_covariate_validity={
                name: values.copy() for name, values in covariate_validity.items()
            },
            event_values={
                event: {
                    name: tuple(float(value) for value in values)
                    for name, values in event_covariates.items()
                }
                for event, event_covariates in (event_values or {}).items()
            },
            intervals={
                name: tuple(
                    (float(start), float(stop)) for start, stop in interval_values
                )
                for name, interval_values in (intervals or {}).items()
            },
        )
        _validate_session(result)
        return result


@dataclass(frozen=True)
class KernelUncertaintySpec:
    """Default grouped pointwise sensitivity policy."""

    confidence_level: float = 0.95
    simultaneous_method: Literal["none"] = "none"
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("kernel confidence_level must lie in (0, 1)")


@dataclass(frozen=True)
class MultiplierSimultaneousBandSpec:
    """Explicit opt-in to the incompletely calibrated multiplier max-t band."""

    confidence_level: float = 0.95
    simultaneous_method: Literal["jackknife_gaussian_multiplier_max_t"] = (
        "jackknife_gaussian_multiplier_max_t"
    )
    simultaneous_draws: int = 2_000
    simultaneous_seed: int = 20_260_727
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("kernel confidence_level must lie in (0, 1)")
        if isinstance(self.simultaneous_draws, bool) or not isinstance(
            self.simultaneous_draws, int
        ):
            raise ValueError("kernel simultaneous_draws must be an integer")
        if self.simultaneous_draws < 100:
            raise ValueError("kernel simultaneous_draws must be at least 100")
        if isinstance(self.simultaneous_seed, bool) or not isinstance(
            self.simultaneous_seed, int
        ):
            raise ValueError("kernel simultaneous_seed must be an integer")
        if self.simultaneous_seed < 0:
            raise ValueError("kernel simultaneous_seed must be nonnegative")


@dataclass(frozen=True)
class EncodingModelSpec:
    """Declared predictors and grouped validation policy for one encoding model."""

    event_kernels: tuple[EventKernelSpec, ...]
    continuous_covariates: tuple[str, ...] = ()
    alpha_grid: tuple[float, ...] = (0.0, 0.1, 1.0, 10.0)
    group_by: Literal["animal", "session"] = "animal"
    folds: int = 5
    sampling_tolerance: float = 1e-3
    minimum_session_coverage: float = 0.5
    minimum_session_observations: int = 3
    schema_version: str = "1"
    progress_kernels: tuple[ProgressKernelSpec, ...] = ()
    uncertainty: KernelUncertaintySpec | MultiplierSimultaneousBandSpec = field(
        default_factory=KernelUncertaintySpec
    )

    def __post_init__(self) -> None:
        names = [item.name for item in self.event_kernels] + [
            item.name for item in self.progress_kernels
        ]
        all_names = names + list(self.continuous_covariates)
        if not all_names:
            raise ValueError("encoding model requires at least one predictor")
        if len(all_names) != len(set(all_names)):
            raise ValueError("encoding predictor names must be unique")
        if isinstance(self.uncertainty, MultiplierSimultaneousBandSpec) and not names:
            raise ValueError(
                "simultaneous kernel bands require an event or progress kernel"
            )
        if not self.alpha_grid or any(value < 0 for value in self.alpha_grid):
            raise ValueError("encoding alpha_grid must contain nonnegative values")
        if len(self.alpha_grid) != len(set(self.alpha_grid)):
            raise ValueError("encoding alpha_grid must not contain duplicates")
        if self.folds < 2:
            raise ValueError("encoding cross-validation requires at least two folds")
        if not 0 < self.sampling_tolerance < 0.1:
            raise ValueError("encoding sampling_tolerance must lie between 0 and 0.1")
        if not 0 < self.minimum_session_coverage <= 1:
            raise ValueError("minimum_session_coverage must lie in (0, 1]")
        if self.minimum_session_observations < 1:
            raise ValueError("minimum_session_observations must be positive")


@dataclass(frozen=True)
class EncodingFoldResult:
    """Held-out group identities and prediction score for one fold."""

    fold: int
    held_out_groups: tuple[str, ...]
    observations: int
    r_squared: float


@dataclass(frozen=True)
class EncodingAlphaResult:
    """Cross-validated performance for one ridge penalty."""

    alpha: float
    mean_r_squared: float
    folds: tuple[EncodingFoldResult, ...]


@dataclass(frozen=True)
class EventKernelResult:
    """Estimated response-unit change at each lag for one event type."""

    name: str
    source_event: str
    modulation: EventModulationSpec | None
    lag_s: tuple[float, ...]
    coefficient: tuple[float, ...]
    basis: EventKernelBasisResult


@dataclass(frozen=True)
class EventKernelBasisResult:
    """Basis weights and sampled functions used to reconstruct one kernel."""

    family: str
    component_label: tuple[str, ...]
    coefficient: tuple[float, ...]
    function_by_lag: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class ProgressKernelBasisResult:
    """Basis weights and functions used to reconstruct normalized progress."""

    family: str
    component_label: tuple[str, ...]
    coefficient: tuple[float, ...]
    function_by_progress: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class ProgressKernelResult:
    """Estimated response trajectory over normalized interval progress."""

    name: str
    source_interval: str
    intervals: int
    progress: tuple[float, ...]
    coefficient: tuple[float, ...]
    basis: ProgressKernelBasisResult


@dataclass(frozen=True)
class ContinuousCoefficient:
    """Coefficient for a one-standard-deviation continuous-covariate change."""

    name: str
    coefficient: float
    training_mean: float
    training_standard_deviation: float


@dataclass(frozen=True)
class EventKernelInterval:
    """Pointwise and optional simultaneous uncertainty for one event kernel."""

    name: str
    lag_s: tuple[float, ...]
    full_coefficient: tuple[float, ...]
    jackknife_estimate: tuple[float, ...]
    standard_error: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    simultaneous_lower: tuple[float, ...] | None
    simultaneous_upper: tuple[float, ...] | None


@dataclass(frozen=True)
class ProgressKernelInterval:
    """Pointwise and optional simultaneous uncertainty over progress."""

    name: str
    progress: tuple[float, ...]
    full_coefficient: tuple[float, ...]
    jackknife_estimate: tuple[float, ...]
    standard_error: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    simultaneous_lower: tuple[float, ...] | None
    simultaneous_upper: tuple[float, ...] | None


@dataclass(frozen=True)
class GroupedKernelUncertainty:
    """Delete-one-group sensitivity intervals conditional on one ridge penalty."""

    method: Literal["delete_one_group_jackknife"]
    confidence_level: float
    conditional_on_selected_alpha: float
    groups: int
    omitted_groups: tuple[str, ...]
    event_kernels: tuple[EventKernelInterval, ...]
    progress_kernels: tuple[ProgressKernelInterval, ...] = ()
    simultaneous_method: Literal["jackknife_gaussian_multiplier_max_t"] | None = None
    simultaneous_draws: int | None = None
    simultaneous_seed: int | None = None
    simultaneous_family_size: int | None = None
    pointwise_critical_value: float = 0.0
    simultaneous_critical_value: float | None = None
    simultaneous: bool = False


@dataclass(frozen=True)
class EncodingGroupDiagnostic:
    """Out-of-fold prediction and residual diagnostics for one complete group."""

    group: str
    sessions: int
    observations: int
    r_squared: float
    rmse: float
    mae: float
    residual_mean: float
    residual_standard_deviation: float
    lag1_autocorrelation: float | None
    durbin_watson: float | None


@dataclass(frozen=True)
class EncodingResidualDiagnostics:
    """Group-held-out diagnostics with lag calculations reset by session."""

    prediction_source: Literal["group_held_out"]
    group_by: str
    groups: tuple[EncodingGroupDiagnostic, ...]
    pooled_observations: int
    pooled_r_squared: float
    pooled_rmse: float
    pooled_mae: float
    pooled_residual_mean: float
    pooled_residual_standard_deviation: float
    pooled_lag1_autocorrelation: float | None
    pooled_durbin_watson: float | None


@dataclass(frozen=True)
class EncodingSessionCoverage:
    """Complete-case exclusions for one session before model fitting."""

    subject: str
    session: str
    total_observations: int
    retained_observations: int
    excluded_observations: int
    retained_fraction: float
    invalid_response: int
    invalid_by_covariate: Mapping[str, int]
    contiguous_retained_runs: int
    retained_index_fingerprint: str


@dataclass(frozen=True)
class EncodingValidityReport:
    """Declared mask policy and retained denominators for an encoding model."""

    policy: Literal["complete_case"]
    minimum_session_coverage: float
    minimum_session_observations: int
    total_observations: int
    retained_observations: int
    excluded_observations: int
    retained_fraction: float
    sessions: tuple[EncodingSessionCoverage, ...]


@dataclass(frozen=True)
class EncodingModelResult:
    """Fitted kernels plus group-held-out predictive validation evidence."""

    sample_interval_s: float
    selected_alpha: float
    intercept: float
    event_kernels: tuple[EventKernelResult, ...]
    progress_kernels: tuple[ProgressKernelResult, ...]
    continuous_coefficients: tuple[ContinuousCoefficient, ...]
    kernel_uncertainty: GroupedKernelUncertainty
    residual_diagnostics: EncodingResidualDiagnostics
    validity: EncodingValidityReport
    cross_validation: tuple[EncodingAlphaResult, ...]
    group_by: str
    groups: int
    sessions: int
    animals: int
    observations: int
    artifact_type: Literal["event_kernel_encoding_result"] = (
        "event_kernel_encoding_result"
    )
    schema_version: str = "8"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class _Design:
    values: csr_matrix
    response: NDArray[np.float64]
    groups: NDArray[np.str_]
    sessions: NDArray[np.str_]
    residual_segments: NDArray[np.str_]
    event_slices: tuple[_EventLayout, ...]
    progress_slices: tuple[_ProgressLayout, ...]
    progress_interval_counts: Mapping[str, int]
    continuous_indices: tuple[tuple[str, int], ...]
    sample_interval: float
    validity: EncodingValidityReport


@dataclass(frozen=True)
class _EventLayout:
    spec: EventKernelSpec
    columns: slice
    lags: NDArray[np.float64]
    basis: NDArray[np.float64]
    component_labels: tuple[str, ...]


@dataclass(frozen=True)
class _ProgressLayout:
    spec: ProgressKernelSpec
    columns: slice
    component_labels: tuple[str, ...]


@dataclass(frozen=True)
class _JackknifeCurve:
    full: NDArray[np.float64]
    estimate: NDArray[np.float64]
    standard_error: NDArray[np.float64]
    lower: NDArray[np.float64]
    upper: NDArray[np.float64]
    centered_pseudo_values: NDArray[np.float64]


def fit_event_kernel_model(
    sessions: Sequence[EncodingSession], spec: EncodingModelSpec
) -> EncodingModelResult:
    """Fit an FIR Gaussian ridge model using group-held-out alpha selection.

    Event kernels are constructed independently inside each session, so an event
    can never contribute predictors to a neighboring recording. Cross-validation
    holds out complete animals or sessions and applies continuous-covariate scaling
    learned from the training fold only.
    """
    if not sessions:
        raise ValueError("encoding model requires at least one session")
    design = _build_design(tuple(sessions), spec)
    _validate_kernel_support(design)
    unique_groups = sorted(set(design.groups.tolist()))
    if len(unique_groups) < 2:
        raise ValueError("encoding cross-validation requires at least two groups")
    folds = _group_folds(design.groups, min(spec.folds, len(unique_groups)))
    alpha_results = tuple(
        _cross_validate_alpha(design, folds, alpha) for alpha in spec.alpha_grid
    )
    selected = max(
        alpha_results,
        key=lambda item: (item.mean_r_squared, -item.alpha),
    )
    coefficients, intercept, means, scales = _fit(
        design.values, design.response, selected.alpha, design.continuous_indices
    )
    kernels = []
    for event_layout_item in design.event_slices:
        basis_coefficients = coefficients[event_layout_item.columns]
        reconstructed = event_layout_item.basis @ basis_coefficients
        kernels.append(
            EventKernelResult(
                name=event_layout_item.spec.name,
                source_event=_source_event(event_layout_item.spec),
                modulation=event_layout_item.spec.modulation,
                lag_s=tuple(float(value) for value in event_layout_item.lags),
                coefficient=tuple(float(value) for value in reconstructed),
                basis=EventKernelBasisResult(
                    family=event_layout_item.spec.basis.family,
                    component_label=event_layout_item.component_labels,
                    coefficient=tuple(float(value) for value in basis_coefficients),
                    function_by_lag=tuple(
                        tuple(float(value) for value in component)
                        for component in event_layout_item.basis.T
                    ),
                ),
            )
        )
    progress_kernels = []
    for progress_layout_item in design.progress_slices:
        progress: NDArray[np.float64] = np.linspace(
            0.0,
            1.0,
            progress_layout_item.spec.basis.evaluation_points,
            dtype=float,
        )
        basis, _ = _progress_basis(progress_layout_item.spec.basis, progress)
        basis_coefficients = coefficients[progress_layout_item.columns]
        reconstructed = basis @ basis_coefficients
        progress_kernels.append(
            ProgressKernelResult(
                name=progress_layout_item.spec.name,
                source_interval=_source_interval(progress_layout_item.spec),
                intervals=design.progress_interval_counts[
                    progress_layout_item.spec.name
                ],
                progress=tuple(float(value) for value in progress),
                coefficient=tuple(float(value) for value in reconstructed),
                basis=ProgressKernelBasisResult(
                    family=progress_layout_item.spec.basis.family,
                    component_label=progress_layout_item.component_labels,
                    coefficient=tuple(float(value) for value in basis_coefficients),
                    function_by_progress=tuple(
                        tuple(float(value) for value in component)
                        for component in basis.T
                    ),
                ),
            )
        )
    continuous = tuple(
        ContinuousCoefficient(
            name,
            float(coefficients[index]),
            float(means[index]),
            float(scales[index]),
        )
        for name, index in design.continuous_indices
    )
    uncertainty = _grouped_kernel_uncertainty(
        design, coefficients, selected.alpha, spec.uncertainty
    )
    diagnostics = _residual_diagnostics(design, folds, selected.alpha, spec.group_by)
    return EncodingModelResult(
        sample_interval_s=design.sample_interval,
        selected_alpha=selected.alpha,
        intercept=intercept,
        event_kernels=tuple(kernels),
        progress_kernels=tuple(progress_kernels),
        continuous_coefficients=continuous,
        kernel_uncertainty=uncertainty,
        residual_diagnostics=diagnostics,
        validity=design.validity,
        cross_validation=alpha_results,
        group_by=spec.group_by,
        groups=len(unique_groups),
        sessions=len({(item.subject, item.session) for item in sessions}),
        animals=len({item.subject for item in sessions}),
        observations=len(design.response),
    )


def _validate_kernel_support(design: _Design) -> None:
    unsupported_events: list[str] = []
    for event_layout_item in design.event_slices:
        for offset, label in enumerate(event_layout_item.component_labels):
            column = event_layout_item.columns.start + offset
            if design.values[:, column].nnz == 0:
                unsupported_events.append(f"{event_layout_item.spec.name}@{label}")
    if unsupported_events:
        raise ValueError(
            "encoding event lags have no retained observations: "
            + ", ".join(unsupported_events)
        )
    unsupported_progress: list[str] = []
    for progress_layout_item in design.progress_slices:
        for offset, label in enumerate(progress_layout_item.component_labels):
            column = progress_layout_item.columns.start + offset
            if design.values[:, column].nnz == 0:
                unsupported_progress.append(f"{progress_layout_item.spec.name}@{label}")
    if unsupported_progress:
        raise ValueError(
            "encoding progress components have no retained observations: "
            + ", ".join(unsupported_progress)
        )


def _build_design(
    sessions: tuple[EncodingSession, ...], spec: EncodingModelSpec
) -> _Design:
    for session in sessions:
        _validate_session(session)
    session_ids = [(item.subject, item.session) for item in sessions]
    if len(session_ids) != len(set(session_ids)):
        raise ValueError(
            "encoding session identifiers must be unique within each animal"
        )
    intervals = np.asarray([_sample_interval(item, spec) for item in sessions])
    interval = float(np.median(intervals))
    if np.max(np.abs(intervals - interval)) > spec.sampling_tolerance * interval:
        raise ValueError("encoding sessions must share one regular sampling interval")
    event_layout: list[_EventLayout] = []
    column = 0
    for event_kernel in spec.event_kernels:
        event_start_index = int(np.ceil(event_kernel.window_s[0] / interval - 1e-12))
        event_stop_index = int(np.floor(event_kernel.window_s[1] / interval + 1e-12))
        offsets = np.arange(event_start_index, event_stop_index + 1, dtype=int)
        if not len(offsets):
            raise ValueError(
                f"event-kernel window {event_kernel.name!r} contains no samples"
            )
        lags = offsets.astype(float) * interval
        basis, component_labels = _event_basis(event_kernel, lags)
        columns = slice(column, column + basis.shape[1])
        event_layout.append(
            _EventLayout(event_kernel, columns, lags, basis, component_labels)
        )
        column += basis.shape[1]
    progress_layout: list[_ProgressLayout] = []
    for progress_kernel in spec.progress_kernels:
        _, labels = _progress_basis(
            progress_kernel.basis, np.asarray([0.0], dtype=float)
        )
        columns = slice(column, column + progress_kernel.basis.functions)
        progress_layout.append(_ProgressLayout(progress_kernel, columns, labels))
        column += progress_kernel.basis.functions
    continuous_layout = tuple(
        (name, column + index) for index, name in enumerate(spec.continuous_covariates)
    )
    width = column + len(continuous_layout)
    matrices: list[csr_matrix] = []
    responses = []
    groups = []
    session_labels = []
    residual_segment_ids = []
    coverage_records = []
    event_counts = {kernel.name: 0 for kernel in spec.event_kernels}
    progress_interval_counts = {kernel.name: 0 for kernel in spec.progress_kernels}
    for session in sessions:
        matrix = lil_matrix((len(session.time), width), dtype=float)
        for event_layout_item in event_layout:
            event_kernel = event_layout_item.spec
            source_event = _source_event(event_kernel)
            try:
                event_times = session.events[source_event]
            except KeyError as error:
                raise ValueError(
                    f"encoding session {session.session!r} lacks event "
                    f"{source_event!r} for kernel {event_kernel.name!r}"
                ) from error
            event_weights = _event_weights(session, event_kernel, event_times)
            offsets = np.rint(event_layout_item.lags / interval).astype(int)
            for event_time, event_weight in zip(
                event_times, event_weights, strict=True
            ):
                event_counts[event_kernel.name] += 1
                event_index = int(np.argmin(np.abs(session.time - event_time)))
                mismatch = abs(float(session.time[event_index]) - event_time)
                if mismatch > interval / 2 + spec.sampling_tolerance * interval:
                    raise ValueError(
                        f"event {event_kernel.name!r} does not align to session "
                        "sampling grid"
                    )
                rows = event_index + offsets
                valid = (rows >= 0) & (rows < len(session.time))
                for lag_index, row in zip(
                    np.flatnonzero(valid), rows[valid], strict=True
                ):
                    for component, value in enumerate(
                        event_layout_item.basis[lag_index]
                    ):
                        weighted_value = event_weight * value
                        if weighted_value != 0:
                            matrix[
                                int(row), event_layout_item.columns.start + component
                            ] += weighted_value
        for progress_layout_item in progress_layout:
            source_interval = _source_interval(progress_layout_item.spec)
            try:
                interval_values = session.intervals[source_interval]
            except KeyError as error:
                raise ValueError(
                    f"encoding session {session.session!r} lacks interval "
                    f"{source_interval!r} for progress kernel "
                    f"{progress_layout_item.spec.name!r}"
                ) from error
            _validate_progress_intervals(
                session,
                source_interval,
                interval_values,
                tolerance=spec.sampling_tolerance * interval,
                sample_interval=interval,
            )
            progress_interval_counts[progress_layout_item.spec.name] += len(
                interval_values
            )
            assigned = np.zeros(len(session.time), dtype=bool)
            for interval_start, interval_stop in interval_values:
                inside = (session.time >= interval_start) & (
                    session.time < interval_stop
                )
                if np.any(assigned & inside):
                    raise ValueError(
                        f"overlapping interval {source_interval!r} makes normalized "
                        f"progress ambiguous in session {session.session!r}"
                    )
                rows = np.flatnonzero(inside)
                if not len(rows):
                    continue
                progress = (session.time[rows] - interval_start) / (
                    interval_stop - interval_start
                )
                basis, _ = _progress_basis(progress_layout_item.spec.basis, progress)
                for row, row_basis in zip(rows, basis, strict=True):
                    for component, value in enumerate(row_basis):
                        if value != 0:
                            matrix[
                                int(row), progress_layout_item.columns.start + component
                            ] += value
                assigned[rows] = True
        for name, index in continuous_layout:
            try:
                matrix[:, index] = session.continuous_covariates[name]
            except KeyError as error:
                raise ValueError(
                    f"encoding session {session.session!r} lacks covariate {name!r}"
                ) from error
        response_valid = np.isfinite(session.response)
        if session.response_valid is not None:
            response_valid &= session.response_valid
        retained = response_valid.copy()
        invalid_by_covariate: dict[str, int] = {}
        for name, _ in continuous_layout:
            covariate_valid = np.isfinite(session.continuous_covariates[name])
            if name in session.continuous_covariate_validity:
                covariate_valid &= session.continuous_covariate_validity[name]
            invalid_by_covariate[name] = int(np.sum(~covariate_valid))
            retained &= covariate_valid
        retained_count = int(np.sum(retained))
        retained_fraction = retained_count / len(session.time)
        segment = f"{session.subject}/{session.session}"
        run_ids, run_count = _retained_run_ids(retained, segment)
        coverage = EncodingSessionCoverage(
            subject=session.subject,
            session=session.session,
            total_observations=len(session.time),
            retained_observations=retained_count,
            excluded_observations=len(session.time) - retained_count,
            retained_fraction=retained_fraction,
            invalid_response=int(np.sum(~response_valid)),
            invalid_by_covariate=invalid_by_covariate,
            contiguous_retained_runs=run_count,
            retained_index_fingerprint=sha256(
                np.asarray(retained, dtype=np.uint8).tobytes()
            ).hexdigest(),
        )
        if retained_count < spec.minimum_session_observations:
            raise ValueError(
                f"encoding session {segment!r} retains {retained_count} observations; "
                f"minimum is {spec.minimum_session_observations}"
            )
        if retained_fraction < spec.minimum_session_coverage:
            raise ValueError(
                f"encoding session {segment!r} retains {retained_fraction:.1%}; "
                f"minimum coverage is {spec.minimum_session_coverage:.1%}"
            )
        coverage_records.append(coverage)
        matrices.append(matrix.tocsr()[retained])
        responses.append(session.response[retained])
        group = (
            session.subject
            if spec.group_by == "animal"
            else f"{session.subject}/{session.session}"
        )
        groups.extend([group] * retained_count)
        session_labels.extend([segment] * retained_count)
        residual_segment_ids.extend(run_ids)
    absent_events = [name for name, count in event_counts.items() if count == 0]
    if absent_events:
        raise ValueError(
            "encoding event predictors have no occurrences: "
            + ", ".join(sorted(absent_events))
        )
    absent_intervals = [
        name for name, count in progress_interval_counts.items() if count == 0
    ]
    if absent_intervals:
        raise ValueError(
            "encoding progress predictors have no intervals: "
            + ", ".join(sorted(absent_intervals))
        )
    values = vstack(matrices, format="csr")
    response = np.concatenate(responses)
    if len(response) <= width:
        raise ValueError("encoding model has too few finite observations")
    unsupported_events = [
        layout.spec.name
        for layout in event_layout
        if values[:, layout.columns].nnz == 0
    ]
    if unsupported_events:
        raise ValueError(
            "encoding event predictors have no retained support: "
            + ", ".join(sorted(unsupported_events))
        )
    unsupported_progress = [
        layout.spec.name
        for layout in progress_layout
        if values[:, layout.columns].nnz == 0
    ]
    if unsupported_progress:
        raise ValueError(
            "encoding progress predictors have no retained support: "
            + ", ".join(sorted(unsupported_progress))
        )
    total_observations = sum(item.total_observations for item in coverage_records)
    retained_observations = sum(item.retained_observations for item in coverage_records)
    validity = EncodingValidityReport(
        policy="complete_case",
        minimum_session_coverage=spec.minimum_session_coverage,
        minimum_session_observations=spec.minimum_session_observations,
        total_observations=total_observations,
        retained_observations=retained_observations,
        excluded_observations=total_observations - retained_observations,
        retained_fraction=retained_observations / total_observations,
        sessions=tuple(coverage_records),
    )
    return _Design(
        values=values,
        response=response,
        groups=np.asarray(groups, dtype=str),
        sessions=np.asarray(session_labels, dtype=str),
        residual_segments=np.asarray(residual_segment_ids, dtype=str),
        event_slices=tuple(event_layout),
        progress_slices=tuple(progress_layout),
        progress_interval_counts=progress_interval_counts,
        continuous_indices=continuous_layout,
        sample_interval=interval,
        validity=validity,
    )


def _event_basis(
    kernel: EventKernelSpec,
    lags: NDArray[np.float64],
) -> tuple[NDArray[np.float64], tuple[str, ...]]:
    if isinstance(kernel.basis, FIRBasisSpec):
        return np.eye(len(lags), dtype=float), tuple(f"{float(lag):g}s" for lag in lags)
    functions = kernel.basis.functions
    if functions > len(lags):
        raise ValueError(
            f"raised-cosine basis for {kernel.name!r} requests {functions} "
            f"functions for {len(lags)} sampled lags"
        )
    if functions == 1:
        basis = np.ones((len(lags), 1), dtype=float)
    else:
        centers = np.linspace(float(lags[0]), float(lags[-1]), functions)
        spacing = float(centers[1] - centers[0])
        distance = (lags[:, None] - centers[None, :]) / spacing
        basis = np.where(
            np.abs(distance) <= 1,
            0.5 * (np.cos(np.pi * distance) + 1),
            0.0,
        )
        basis /= np.sum(basis, axis=1, keepdims=True)
    if np.linalg.matrix_rank(basis) != functions:
        raise ValueError(f"raised-cosine basis for {kernel.name!r} is rank deficient")
    return basis, tuple(f"raised-cosine-{index}" for index in range(functions))


def _progress_basis(
    spec: LinearProgressBasisSpec,
    progress: NDArray[np.float64],
) -> tuple[NDArray[np.float64], tuple[str, ...]]:
    if np.any(~np.isfinite(progress)) or np.any((progress < 0) | (progress > 1)):
        raise ValueError("normalized progress must be finite and lie in [0, 1]")
    if spec.functions == 1:
        return np.ones((len(progress), 1), dtype=float), ("progress-constant",)
    centers = np.linspace(0.0, 1.0, spec.functions, dtype=float)
    spacing = float(centers[1] - centers[0])
    basis = np.maximum(
        1.0 - np.abs(progress[:, None] - centers[None, :]) / spacing,
        0.0,
    )
    basis /= np.sum(basis, axis=1, keepdims=True)
    return basis, tuple(f"progress-{float(value):g}" for value in centers)


def _source_interval(kernel: ProgressKernelSpec) -> str:
    return kernel.source_interval if kernel.source_interval is not None else kernel.name


def _validate_progress_intervals(
    session: EncodingSession,
    name: str,
    intervals: tuple[tuple[float, float], ...],
    *,
    tolerance: float,
    sample_interval: float,
) -> None:
    if any(current[0] <= previous[0] for previous, current in pairwise(intervals)):
        raise ValueError(
            f"interval {name!r} must be strictly ordered in session {session.session!r}"
        )
    if any(current[0] < previous[1] for previous, current in pairwise(intervals)):
        raise ValueError(
            f"overlapping interval {name!r} makes normalized progress ambiguous "
            f"in session {session.session!r}"
        )
    earliest = float(session.time[0]) - tolerance
    latest = float(session.time[-1]) + sample_interval + tolerance
    if any(start < earliest or stop > latest for start, stop in intervals):
        raise ValueError(
            f"interval {name!r} extends beyond session {session.session!r} support"
        )


def _source_event(kernel: EventKernelSpec) -> str:
    return kernel.source_event if kernel.source_event is not None else kernel.name


def _event_weights(
    session: EncodingSession,
    kernel: EventKernelSpec,
    event_times: tuple[float, ...],
) -> NDArray[np.float64]:
    modulation = kernel.modulation
    if modulation is None:
        return np.ones(len(event_times), dtype=float)
    source_event = _source_event(kernel)
    if modulation.lag_events and any(
        current >= following for current, following in pairwise(event_times)
    ):
        raise ValueError(
            f"history-modulated event {source_event!r} must be strictly increasing "
            f"within session {session.session!r}"
        )
    try:
        values = session.event_values[source_event][modulation.value]
    except KeyError as error:
        raise ValueError(
            f"encoding session {session.session!r} lacks event value "
            f"{modulation.value!r} for event {source_event!r}"
        ) from error
    weights = np.full(len(event_times), modulation.unavailable_value, dtype=float)
    if modulation.lag_events < len(event_times):
        stop = len(event_times) - modulation.lag_events
        weights[modulation.lag_events :] = values[:stop]
    return weights


def _retained_run_ids(
    retained: NDArray[np.bool_], session: str
) -> tuple[list[str], int]:
    indices = np.flatnonzero(retained)
    if not len(indices):
        return [], 0
    run = np.concatenate(([0], np.cumsum(np.diff(indices) != 1)))
    return [f"{session}#run-{int(value)}" for value in run], int(run[-1] + 1)


def _validate_session(session: EncodingSession) -> None:
    if not session.subject.strip() or not session.session.strip():
        raise ValueError("encoding sessions require subject and session identities")
    if session.time.ndim != 1 or session.response.ndim != 1:
        raise ValueError("encoding time and response must be one-dimensional")
    if len(session.time) != len(session.response) or len(session.time) < 3:
        raise ValueError("encoding time and response lengths are invalid")
    if not np.all(np.isfinite(session.time)) or not np.all(np.diff(session.time) > 0):
        raise ValueError("encoding time must be finite and strictly increasing")
    for name, event_times in session.events.items():
        if not name.strip() or not all(np.isfinite(event_times)):
            raise ValueError("encoding event names and times must be valid")
    unknown_event_values = set(session.event_values) - set(session.events)
    if unknown_event_values:
        raise ValueError(
            "encoding event values name unknown events: "
            + ", ".join(sorted(unknown_event_values))
        )
    for event, values_by_name in session.event_values.items():
        for name, values in values_by_name.items():
            if (
                not name.strip()
                or len(values) != len(session.events[event])
                or not all(np.isfinite(values))
            ):
                raise ValueError(
                    f"encoding event value {name!r} must be finite and match "
                    f"event {event!r} occurrences"
                )
    for name, intervals in session.intervals.items():
        if not name.strip():
            raise ValueError("encoding interval names must be non-empty")
        if any(
            not np.isfinite(start) or not np.isfinite(stop) or stop <= start
            for start, stop in intervals
        ):
            raise ValueError(
                f"encoding interval {name!r} bounds must be finite and positive"
            )
    for name, covariate_values in session.continuous_covariates.items():
        if (
            not name.strip()
            or covariate_values.ndim != 1
            or len(covariate_values) != len(session.time)
        ):
            raise ValueError("encoding continuous covariates must match session time")
    if session.response_valid is not None and (
        session.response_valid.ndim != 1
        or len(session.response_valid) != len(session.time)
        or session.response_valid.dtype.kind != "b"
    ):
        raise ValueError("encoding response validity must be a matching bool mask")
    unknown_masks = set(session.continuous_covariate_validity) - set(
        session.continuous_covariates
    )
    if unknown_masks:
        raise ValueError(
            "encoding validity masks name unknown covariates: "
            + ", ".join(sorted(unknown_masks))
        )
    for name, validity in session.continuous_covariate_validity.items():
        if (
            validity.ndim != 1
            or len(validity) != len(session.time)
            or validity.dtype.kind != "b"
        ):
            raise ValueError(
                f"encoding validity for covariate {name!r} must be a matching bool mask"
            )


def _sample_interval(session: EncodingSession, spec: EncodingModelSpec) -> float:
    differences = np.diff(session.time)
    interval = float(np.median(differences))
    if np.max(np.abs(differences - interval)) > spec.sampling_tolerance * interval:
        raise ValueError(
            "event-kernel encoding requires regular sampling; resample explicitly"
        )
    return interval


def _group_folds(groups: NDArray[np.str_], count: int) -> tuple[tuple[str, ...], ...]:
    sizes = {group: int(np.sum(groups == group)) for group in set(groups.tolist())}
    bins: list[list[str]] = [[] for _ in range(count)]
    loads = [0] * count
    for group in sorted(sizes, key=lambda item: (-sizes[item], item)):
        target = min(range(count), key=lambda index: (loads[index], index))
        bins[target].append(group)
        loads[target] += sizes[group]
    return tuple(tuple(sorted(values)) for values in bins)


def _cross_validate_alpha(
    design: _Design, folds: tuple[tuple[str, ...], ...], alpha: float
) -> EncodingAlphaResult:
    results = []
    for index, held_out in enumerate(folds):
        test = np.isin(design.groups, held_out)
        train = ~test
        coefficients, intercept, means, scales = _fit(
            design.values[train],
            design.response[train],
            alpha,
            design.continuous_indices,
        )
        prediction = _predict(
            design.values[test],
            coefficients,
            intercept,
            design.continuous_indices,
            means,
            scales,
        )
        group_scores = []
        for group in held_out:
            group_mask = design.groups[test] == group
            score = _r_squared(
                design.response[test][group_mask], prediction[group_mask]
            )
            if np.isfinite(score):
                group_scores.append(score)
        if not group_scores:
            raise ValueError(
                "encoding validation requires response variation in each held-out fold"
            )
        results.append(
            EncodingFoldResult(
                index,
                held_out,
                int(np.sum(test)),
                float(np.mean(group_scores)),
            )
        )
    return EncodingAlphaResult(
        alpha,
        float(np.mean([item.r_squared for item in results])),
        tuple(results),
    )


def _grouped_kernel_uncertainty(
    design: _Design,
    full_coefficients: NDArray[np.float64],
    alpha: float,
    spec: KernelUncertaintySpec | MultiplierSimultaneousBandSpec,
) -> GroupedKernelUncertainty:
    groups = tuple(sorted(set(design.groups.tolist())))
    replicates = []
    for group in groups:
        retained = design.groups != group
        coefficients, _, _, _ = _fit(
            design.values[retained],
            design.response[retained],
            alpha,
            design.continuous_indices,
        )
        replicates.append(coefficients)
    replicate_values = np.vstack(replicates)
    count = len(groups)
    pointwise_critical = float(
        student_t.ppf(0.5 + spec.confidence_level / 2, df=max(1, count - 1))
    )
    event_curves = []
    for event_layout_item in design.event_slices:
        full_curve = (
            event_layout_item.basis @ full_coefficients[event_layout_item.columns]
        )
        replicate_curves = (
            replicate_values[:, event_layout_item.columns] @ event_layout_item.basis.T
        )
        event_curves.append(
            _jackknife_curve(full_curve, replicate_curves, count, pointwise_critical)
        )
    progress_values = []
    progress_curves = []
    for progress_layout_item in design.progress_slices:
        progress: NDArray[np.float64] = np.linspace(
            0.0,
            1.0,
            progress_layout_item.spec.basis.evaluation_points,
            dtype=float,
        )
        basis, _ = _progress_basis(progress_layout_item.spec.basis, progress)
        full_curve = basis @ full_coefficients[progress_layout_item.columns]
        replicate_curves = replicate_values[:, progress_layout_item.columns] @ basis.T
        progress_values.append(progress)
        progress_curves.append(
            _jackknife_curve(full_curve, replicate_curves, count, pointwise_critical)
        )
    all_curves = tuple(event_curves) + tuple(progress_curves)
    simultaneous_spec = (
        spec if isinstance(spec, MultiplierSimultaneousBandSpec) else None
    )
    simultaneous_critical = (
        _simultaneous_critical_value(
            all_curves,
            groups=count,
            confidence_level=spec.confidence_level,
            draws=simultaneous_spec.simultaneous_draws,
            seed=simultaneous_spec.simultaneous_seed,
            minimum=pointwise_critical,
        )
        if simultaneous_spec is not None
        else None
    )
    kernels = []
    for event_layout_item, curve in zip(design.event_slices, event_curves, strict=True):
        kernels.append(
            EventKernelInterval(
                name=event_layout_item.spec.name,
                lag_s=tuple(float(value) for value in event_layout_item.lags),
                full_coefficient=_float_tuple(curve.full),
                jackknife_estimate=_float_tuple(curve.estimate),
                standard_error=_float_tuple(curve.standard_error),
                lower=_float_tuple(curve.lower),
                upper=_float_tuple(curve.upper),
                simultaneous_lower=(
                    _float_tuple(
                        curve.estimate - simultaneous_critical * curve.standard_error
                    )
                    if simultaneous_critical is not None
                    else None
                ),
                simultaneous_upper=(
                    _float_tuple(
                        curve.estimate + simultaneous_critical * curve.standard_error
                    )
                    if simultaneous_critical is not None
                    else None
                ),
            )
        )
    progress_kernels = []
    for progress_layout_item, progress, curve in zip(
        design.progress_slices, progress_values, progress_curves, strict=True
    ):
        progress_kernels.append(
            ProgressKernelInterval(
                name=progress_layout_item.spec.name,
                progress=_float_tuple(progress),
                full_coefficient=_float_tuple(curve.full),
                jackknife_estimate=_float_tuple(curve.estimate),
                standard_error=_float_tuple(curve.standard_error),
                lower=_float_tuple(curve.lower),
                upper=_float_tuple(curve.upper),
                simultaneous_lower=(
                    _float_tuple(
                        curve.estimate - simultaneous_critical * curve.standard_error
                    )
                    if simultaneous_critical is not None
                    else None
                ),
                simultaneous_upper=(
                    _float_tuple(
                        curve.estimate + simultaneous_critical * curve.standard_error
                    )
                    if simultaneous_critical is not None
                    else None
                ),
            )
        )
    return GroupedKernelUncertainty(
        method="delete_one_group_jackknife",
        confidence_level=spec.confidence_level,
        conditional_on_selected_alpha=alpha,
        groups=count,
        omitted_groups=groups,
        event_kernels=tuple(kernels),
        progress_kernels=tuple(progress_kernels),
        simultaneous_method=(
            simultaneous_spec.simultaneous_method
            if simultaneous_spec is not None
            else None
        ),
        simultaneous_draws=(
            simultaneous_spec.simultaneous_draws
            if simultaneous_spec is not None
            else None
        ),
        simultaneous_seed=(
            simultaneous_spec.simultaneous_seed
            if simultaneous_spec is not None
            else None
        ),
        simultaneous_family_size=(
            sum(len(item.full) for item in all_curves)
            if simultaneous_spec is not None
            else None
        ),
        pointwise_critical_value=pointwise_critical,
        simultaneous_critical_value=simultaneous_critical,
        simultaneous=simultaneous_spec is not None,
    )


def _jackknife_curve(
    full_curve: NDArray[np.float64],
    replicate_curves: NDArray[np.float64],
    groups: int,
    pointwise_critical: float,
) -> _JackknifeCurve:
    pseudo_values = groups * full_curve - (groups - 1) * replicate_curves
    estimate = np.mean(pseudo_values, axis=0)
    centered = pseudo_values - estimate
    standard_error = np.sqrt(np.sum(centered**2, axis=0) / (groups * (groups - 1)))
    return _JackknifeCurve(
        full=full_curve,
        estimate=estimate,
        standard_error=standard_error,
        lower=estimate - pointwise_critical * standard_error,
        upper=estimate + pointwise_critical * standard_error,
        centered_pseudo_values=centered,
    )


def _simultaneous_critical_value(
    curves: tuple[_JackknifeCurve, ...],
    *,
    groups: int,
    confidence_level: float,
    draws: int,
    seed: int,
    minimum: float,
) -> float:
    centered = np.concatenate([item.centered_pseudo_values for item in curves], axis=1)
    standard_error = np.concatenate([item.standard_error for item in curves])
    varying = standard_error > np.finfo(float).eps
    if not np.any(varying):
        return minimum
    multipliers = np.random.default_rng(seed).normal(size=(draws, groups))
    deviations = multipliers @ centered[:, varying]
    deviations /= np.sqrt(groups * (groups - 1))
    standardized = np.abs(deviations / standard_error[varying])
    maximum = np.max(standardized, axis=1)
    raw_critical = float(np.quantile(maximum, confidence_level, method="higher"))
    gaussian_critical = float(norm.ppf(0.5 + confidence_level / 2))
    small_sample_scale = minimum / gaussian_critical
    return max(minimum, raw_critical * small_sample_scale)


def _float_tuple(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _residual_diagnostics(
    design: _Design,
    folds: tuple[tuple[str, ...], ...],
    alpha: float,
    group_by: str,
) -> EncodingResidualDiagnostics:
    prediction = np.full(len(design.response), np.nan, dtype=float)
    for held_out in folds:
        test = np.isin(design.groups, held_out)
        train = ~test
        coefficients, intercept, means, scales = _fit(
            design.values[train],
            design.response[train],
            alpha,
            design.continuous_indices,
        )
        prediction[test] = _predict(
            design.values[test],
            coefficients,
            intercept,
            design.continuous_indices,
            means,
            scales,
        )
    if not np.all(np.isfinite(prediction)):
        raise RuntimeError("encoding diagnostics did not predict every observation")
    group_results = []
    for group in sorted(set(design.groups.tolist())):
        selected = design.groups == group
        metrics = _residual_metrics(
            design.response[selected],
            prediction[selected],
            design.residual_segments[selected],
        )
        group_results.append(
            EncodingGroupDiagnostic(
                group,
                len(set(design.sessions[selected].tolist())),
                int(np.sum(selected)),
                *metrics,
            )
        )
    pooled = _residual_metrics(design.response, prediction, design.residual_segments)
    return EncodingResidualDiagnostics(
        "group_held_out",
        group_by,
        tuple(group_results),
        len(design.response),
        *pooled,
    )


def _residual_metrics(
    observed: NDArray[np.float64],
    predicted: NDArray[np.float64],
    contiguous_segments: NDArray[np.str_],
) -> tuple[float, float, float, float, float, float | None, float | None]:
    residual = observed - predicted
    lag_numerator = 0.0
    lag_left = 0.0
    lag_right = 0.0
    difference_sum = 0.0
    for segment in sorted(set(contiguous_segments.tolist())):
        values = residual[contiguous_segments == segment]
        if len(values) < 2:
            continue
        centered = values - np.mean(values)
        lag_numerator += float(centered[:-1] @ centered[1:])
        lag_left += float(centered[:-1] @ centered[:-1])
        lag_right += float(centered[1:] @ centered[1:])
        difference_sum += float(np.sum(np.diff(values) ** 2))
    lag_denominator = float(np.sqrt(lag_left * lag_right))
    residual_sum = float(residual @ residual)
    lag1 = lag_numerator / lag_denominator if lag_denominator > 0 else None
    durbin_watson = difference_sum / residual_sum if residual_sum > 0 else None
    return (
        _r_squared(observed, predicted),
        float(np.sqrt(np.mean(residual**2))),
        float(np.mean(np.abs(residual))),
        float(np.mean(residual)),
        float(np.std(residual)),
        lag1,
        durbin_watson,
    )


def _fit(
    values: csr_matrix,
    response: NDArray[np.float64],
    alpha: float,
    continuous: tuple[tuple[str, int], ...],
) -> tuple[NDArray[np.float64], float, NDArray[np.float64], NDArray[np.float64]]:
    width = values.shape[1]
    means = np.zeros(width, dtype=float)
    scales = np.ones(width, dtype=float)
    column_sum = np.asarray(values.sum(axis=0), dtype=float).ravel()
    gram = np.asarray((values.T @ values).toarray(), dtype=float)
    cross = np.asarray(values.T @ response, dtype=float).ravel()
    response_sum = float(np.sum(response))
    count = len(response)
    for _, index in continuous:
        means[index] = column_sum[index] / count
        variance = gram[index, index] / count - means[index] ** 2
        scales[index] = float(np.sqrt(max(variance, 0.0)))
        if scales[index] <= np.finfo(float).eps:
            raise ValueError(
                "encoding continuous covariates must vary in training data"
            )
    multiplier = np.ones(width, dtype=float)
    shift = np.zeros(width, dtype=float)
    for _, index in continuous:
        multiplier[index] = 1 / scales[index]
        shift[index] = -means[index] / scales[index]
    scaled_sum = multiplier * column_sum
    transformed_sum = scaled_sum + count * shift
    transformed_gram = gram * np.outer(multiplier, multiplier)
    transformed_gram += np.outer(scaled_sum, shift)
    transformed_gram += np.outer(shift, scaled_sum)
    transformed_gram += count * np.outer(shift, shift)
    transformed_cross = multiplier * cross + shift * response_sum
    response_mean = response_sum / count
    centered_gram = (
        transformed_gram - np.outer(transformed_sum, transformed_sum) / count
    )
    centered_cross = transformed_cross - transformed_sum * response_mean
    penalty = alpha * np.eye(width)
    coefficients = np.linalg.pinv(centered_gram + penalty) @ centered_cross
    intercept = float(response_mean - transformed_sum @ coefficients / count)
    return coefficients, intercept, means, scales


def _predict(
    values: csr_matrix,
    coefficients: NDArray[np.float64],
    intercept: float,
    continuous: tuple[tuple[str, int], ...],
    means: NDArray[np.float64],
    scales: NDArray[np.float64],
) -> NDArray[np.float64]:
    raw_coefficients = coefficients.copy()
    adjusted_intercept = intercept
    for _, index in continuous:
        raw_coefficients[index] /= scales[index]
        adjusted_intercept -= means[index] * raw_coefficients[index]
    return np.asarray(adjusted_intercept + values @ raw_coefficients, dtype=float)


def _r_squared(observed: NDArray[np.float64], predicted: NDArray[np.float64]) -> float:
    residual = float(np.sum((observed - predicted) ** 2))
    total = float(np.sum((observed - np.mean(observed)) ** 2))
    return 1 - residual / total if total > 0 else float("nan")
