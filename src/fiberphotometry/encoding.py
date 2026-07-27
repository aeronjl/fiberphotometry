"""Leakage-safe event-kernel encoding models for continuous photometry signals."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.sparse import csr_matrix, lil_matrix, vstack


@dataclass(frozen=True)
class EventKernelSpec:
    """One named event train and its finite impulse-response lag window."""

    name: str
    window_s: tuple[float, float]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("event-kernel name must be non-empty")
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
    ) -> EncodingSession:
        """Create a validated session without joining signals across recordings."""
        time_values = np.asarray(time, dtype=float)
        response_values = np.asarray(response, dtype=float)
        covariates = {
            name: np.asarray(values, dtype=float)
            for name, values in (continuous_covariates or {}).items()
        }
        result = cls(
            str(subject),
            str(session),
            time_values.copy(),
            response_values.copy(),
            {
                name: tuple(float(value) for value in values)
                for name, values in events.items()
            },
            {name: values.copy() for name, values in covariates.items()},
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
    lag_s: tuple[float, ...]
    coefficient: tuple[float, ...]


@dataclass(frozen=True)
class ContinuousCoefficient:
    """Coefficient for a one-standard-deviation continuous-covariate change."""

    name: str
    coefficient: float
    training_mean: float
    training_standard_deviation: float


@dataclass(frozen=True)
class EncodingModelResult:
    """Fitted kernels plus group-held-out predictive validation evidence."""

    sample_interval_s: float
    selected_alpha: float
    intercept: float
    event_kernels: tuple[EventKernelResult, ...]
    continuous_coefficients: tuple[ContinuousCoefficient, ...]
    cross_validation: tuple[EncodingAlphaResult, ...]
    group_by: str
    groups: int
    sessions: int
    animals: int
    observations: int
    artifact_type: Literal["event_kernel_encoding_result"] = (
        "event_kernel_encoding_result"
    )
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class _Design:
    values: csr_matrix
    response: NDArray[np.float64]
    groups: NDArray[np.str_]
    event_slices: tuple[tuple[EventKernelSpec, slice, NDArray[np.float64]], ...]
    continuous_indices: tuple[tuple[str, int], ...]
    sample_interval: float


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
    kernels = tuple(
        EventKernelResult(
            kernel.name,
            tuple(float(value) for value in lags),
            tuple(float(value) for value in coefficients[columns]),
        )
        for kernel, columns, lags in design.event_slices
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
    return EncodingModelResult(
        design.sample_interval,
        selected.alpha,
        intercept,
        kernels,
        continuous,
        alpha_results,
        spec.group_by,
        len(unique_groups),
        len({(item.subject, item.session) for item in sessions}),
        len({item.subject for item in sessions}),
        len(design.response),
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
    event_layout: list[tuple[EventKernelSpec, slice, NDArray[np.float64]]] = []
    column = 0
    for kernel in spec.event_kernels:
        start = int(np.ceil(kernel.window_s[0] / interval - 1e-12))
        stop = int(np.floor(kernel.window_s[1] / interval + 1e-12))
        offsets = np.arange(start, stop + 1, dtype=int)
        if not len(offsets):
            raise ValueError(f"event-kernel window {kernel.name!r} contains no samples")
        columns = slice(column, column + len(offsets))
        event_layout.append((kernel, columns, offsets.astype(float) * interval))
        column += len(offsets)
    continuous_layout = tuple(
        (name, column + index) for index, name in enumerate(spec.continuous_covariates)
    )
    width = column + len(continuous_layout)
    matrices: list[csr_matrix] = []
    responses = []
    groups = []
    event_counts = {kernel.name: 0 for kernel in spec.event_kernels}
    for session in sessions:
        matrix = lil_matrix((len(session.time), width), dtype=float)
        for kernel, columns, lags in event_layout:
            try:
                event_times = session.events[kernel.name]
            except KeyError as error:
                raise ValueError(
                    f"encoding session {session.session!r} lacks event {kernel.name!r}"
                ) from error
            offsets = np.rint(lags / interval).astype(int)
            for event_time in event_times:
                event_counts[kernel.name] += 1
                event_index = int(np.argmin(np.abs(session.time - event_time)))
                mismatch = abs(float(session.time[event_index]) - event_time)
                if mismatch > interval / 2 + spec.sampling_tolerance * interval:
                    raise ValueError(
                        f"event {kernel.name!r} does not align to session sampling grid"
                    )
                rows = event_index + offsets
                valid = (rows >= 0) & (rows < len(session.time))
                event_columns = np.arange(columns.start, columns.stop)[valid]
                for row, event_column in zip(rows[valid], event_columns, strict=True):
                    matrix[int(row), int(event_column)] += 1
        for name, index in continuous_layout:
            try:
                matrix[:, index] = session.continuous_covariates[name]
            except KeyError as error:
                raise ValueError(
                    f"encoding session {session.session!r} lacks covariate {name!r}"
                ) from error
        finite = np.isfinite(session.response)
        for name, _ in continuous_layout:
            finite &= np.isfinite(session.continuous_covariates[name])
        matrices.append(matrix.tocsr()[finite])
        responses.append(session.response[finite])
        group = (
            session.subject
            if spec.group_by == "animal"
            else f"{session.subject}/{session.session}"
        )
        groups.extend([group] * int(np.sum(finite)))
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
    return _Design(
        values,
        response,
        np.asarray(groups, dtype=str),
        tuple(event_layout),
        continuous_layout,
        interval,
    )


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
    for name, covariate_values in session.continuous_covariates.items():
        if (
            not name.strip()
            or covariate_values.ndim != 1
            or len(covariate_values) != len(session.time)
        ):
            raise ValueError("encoding continuous covariates must match session time")


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
