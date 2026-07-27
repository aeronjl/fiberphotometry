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
        )
        _validate_session(result)
        return result


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

    def __post_init__(self) -> None:
        names = [item.name for item in self.event_kernels]
        all_names = names + list(self.continuous_covariates)
        if not all_names:
            raise ValueError("encoding model requires at least one predictor")
        if len(all_names) != len(set(all_names)):
            raise ValueError("encoding predictor names must be unique")
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
class ContinuousCoefficient:
    """Coefficient for a one-standard-deviation continuous-covariate change."""

    name: str
    coefficient: float
    training_mean: float
    training_standard_deviation: float


@dataclass(frozen=True)
class EventKernelInterval:
    """Pointwise grouped-jackknife uncertainty for one event kernel."""

    name: str
    lag_s: tuple[float, ...]
    full_coefficient: tuple[float, ...]
    jackknife_estimate: tuple[float, ...]
    standard_error: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]


@dataclass(frozen=True)
class GroupedKernelUncertainty:
    """Delete-one-group sensitivity intervals conditional on one ridge penalty."""

    method: Literal["delete_one_group_jackknife"]
    confidence_level: float
    conditional_on_selected_alpha: float
    groups: int
    omitted_groups: tuple[str, ...]
    event_kernels: tuple[EventKernelInterval, ...]
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
    schema_version: str = "6"

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
    _validate_event_lag_support(design)
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
    for layout in design.event_slices:
        basis_coefficients = coefficients[layout.columns]
        reconstructed = layout.basis @ basis_coefficients
        kernels.append(
            EventKernelResult(
                name=layout.spec.name,
                source_event=_source_event(layout.spec),
                modulation=layout.spec.modulation,
                lag_s=tuple(float(value) for value in layout.lags),
                coefficient=tuple(float(value) for value in reconstructed),
                basis=EventKernelBasisResult(
                    family=layout.spec.basis.family,
                    component_label=layout.component_labels,
                    coefficient=tuple(float(value) for value in basis_coefficients),
                    function_by_lag=tuple(
                        tuple(float(value) for value in component)
                        for component in layout.basis.T
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
        design, coefficients, selected.alpha, confidence_level=0.95
    )
    diagnostics = _residual_diagnostics(design, folds, selected.alpha, spec.group_by)
    return EncodingModelResult(
        sample_interval_s=design.sample_interval,
        selected_alpha=selected.alpha,
        intercept=intercept,
        event_kernels=tuple(kernels),
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


def _validate_event_lag_support(design: _Design) -> None:
    unsupported: list[str] = []
    for layout in design.event_slices:
        for offset, label in enumerate(layout.component_labels):
            column = layout.columns.start + offset
            if design.values[:, column].nnz == 0:
                unsupported.append(f"{layout.spec.name}@{label}")
    if unsupported:
        raise ValueError(
            "encoding event lags have no retained observations: "
            + ", ".join(unsupported)
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
    for kernel in spec.event_kernels:
        start = int(np.ceil(kernel.window_s[0] / interval - 1e-12))
        stop = int(np.floor(kernel.window_s[1] / interval + 1e-12))
        offsets = np.arange(start, stop + 1, dtype=int)
        if not len(offsets):
            raise ValueError(f"event-kernel window {kernel.name!r} contains no samples")
        lags = offsets.astype(float) * interval
        basis, component_labels = _event_basis(kernel, lags)
        columns = slice(column, column + basis.shape[1])
        event_layout.append(
            _EventLayout(kernel, columns, lags, basis, component_labels)
        )
        column += basis.shape[1]
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
    for session in sessions:
        matrix = lil_matrix((len(session.time), width), dtype=float)
        for layout in event_layout:
            kernel = layout.spec
            source_event = _source_event(kernel)
            try:
                event_times = session.events[source_event]
            except KeyError as error:
                raise ValueError(
                    f"encoding session {session.session!r} lacks event "
                    f"{source_event!r} for kernel {kernel.name!r}"
                ) from error
            event_weights = _event_weights(session, kernel, event_times)
            offsets = np.rint(layout.lags / interval).astype(int)
            for event_time, event_weight in zip(
                event_times, event_weights, strict=True
            ):
                event_counts[kernel.name] += 1
                event_index = int(np.argmin(np.abs(session.time - event_time)))
                mismatch = abs(float(session.time[event_index]) - event_time)
                if mismatch > interval / 2 + spec.sampling_tolerance * interval:
                    raise ValueError(
                        f"event {kernel.name!r} does not align to session sampling grid"
                    )
                rows = event_index + offsets
                valid = (rows >= 0) & (rows < len(session.time))
                for lag_index, row in zip(
                    np.flatnonzero(valid), rows[valid], strict=True
                ):
                    for component, value in enumerate(layout.basis[lag_index]):
                        weighted_value = event_weight * value
                        if weighted_value != 0:
                            matrix[int(row), layout.columns.start + component] += (
                                weighted_value
                            )
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
        values,
        response,
        np.asarray(groups, dtype=str),
        np.asarray(session_labels, dtype=str),
        np.asarray(residual_segment_ids, dtype=str),
        tuple(event_layout),
        continuous_layout,
        interval,
        validity,
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
    *,
    confidence_level: float,
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
    critical = float(student_t.ppf(0.5 + confidence_level / 2, df=max(1, count - 1)))
    kernels = []
    for layout in design.event_slices:
        full_curve = layout.basis @ full_coefficients[layout.columns]
        replicate_curves = replicate_values[:, layout.columns] @ layout.basis.T
        replicate_mean = np.mean(replicate_curves, axis=0)
        jackknife_estimate = count * full_curve - (count - 1) * replicate_mean
        standard_error = np.sqrt(
            (count - 1)
            / count
            * np.sum((replicate_curves - replicate_mean) ** 2, axis=0)
        )
        lower = jackknife_estimate - critical * standard_error
        upper = jackknife_estimate + critical * standard_error
        kernels.append(
            EventKernelInterval(
                layout.spec.name,
                tuple(float(value) for value in layout.lags),
                tuple(float(value) for value in full_curve),
                tuple(float(value) for value in jackknife_estimate),
                tuple(float(value) for value in standard_error),
                tuple(float(value) for value in lower),
                tuple(float(value) for value in upper),
            )
        )
    return GroupedKernelUncertainty(
        "delete_one_group_jackknife",
        confidence_level,
        alpha,
        count,
        groups,
        tuple(kernels),
    )


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
