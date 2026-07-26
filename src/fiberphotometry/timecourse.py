"""Animal-level peri-event contrasts with pointwise and simultaneous bands."""

from __future__ import annotations

import json
import warnings
from dataclasses import asdict, dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.stats import t as student_t


@dataclass(frozen=True)
class PeriEventInferenceSpec:
    """Declared alignment and uncertainty choices for a peri-event contrast."""

    window: tuple[float, float] = (-1.0, 2.0)
    rate_hz: float = 20.0
    confidence: float = 0.95
    draws: int = 2000
    seed: int = 0
    within_animal: str = "equal_session_means"

    def __post_init__(self) -> None:
        if self.window[0] >= self.window[1]:
            raise ValueError("time-course window start must be earlier than stop")
        if self.rate_hz <= 0:
            raise ValueError("time-course rate_hz must be positive")
        if not 0 < self.confidence < 1:
            raise ValueError("time-course confidence must lie between zero and one")
        if self.draws < 100:
            raise ValueError("time-course inference requires at least 100 draws")
        if self.within_animal != "equal_session_means":
            raise ValueError("unsupported within-animal aggregation policy")


@dataclass(frozen=True)
class PeriEventInferenceResult:
    """A contrast curve with distinct local and whole-window uncertainty."""

    relative_time: tuple[float, ...]
    estimate: tuple[float, ...]
    standard_error: tuple[float, ...]
    pointwise_lower: tuple[float, ...]
    pointwise_upper: tuple[float, ...]
    simultaneous_lower: tuple[float, ...]
    simultaneous_upper: tuple[float, ...]
    animals_per_time: tuple[int, ...]
    animal_count: int
    confidence: float
    draws: int
    seed: int
    simultaneous_critical_value: float
    method: str
    warnings: tuple[str, ...]
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize arrays and inferential semantics without hidden defaults."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def infer_peri_event_contrast(
    values: NDArray[np.float64],
    relative_time: NDArray[np.float64],
    *,
    animals: tuple[str, ...],
    sessions: tuple[str, ...],
    conditions: tuple[str, ...],
    numerator: str,
    denominator: str,
    confidence: float = 0.95,
    draws: int = 2000,
    seed: int = 0,
) -> PeriEventInferenceResult:
    """Infer a curve after equal-session aggregation within each animal.

    ``values`` is event by relative-time. Events are never treated as independent
    inferential units: session-condition means are formed first, followed by
    animal-condition means, and only animal contrast curves are resampled.
    """
    matrix = np.asarray(values, dtype=float)
    time = np.asarray(relative_time, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(time):
        raise ValueError("values must be event by relative_time")
    if len(time) < 2 or not np.all(np.diff(time) > 0):
        raise ValueError("relative_time must be strictly increasing")
    if not 0 < confidence < 1:
        raise ValueError("confidence must lie between zero and one")
    if draws < 100:
        raise ValueError("peri-event inference requires at least 100 draws")
    event_count = matrix.shape[0]
    if not (len(animals) == len(sessions) == len(conditions) == event_count):
        raise ValueError("event metadata must match the values rows")
    if numerator == denominator:
        raise ValueError("time-course contrast levels must differ")

    curves, names = _animal_contrasts(
        matrix,
        animals,
        sessions,
        conditions,
        numerator,
        denominator,
    )
    if len(curves) < 2:
        raise ValueError("time-course inference requires two complete animals")
    finite_counts = np.sum(np.isfinite(curves), axis=0)
    valid = finite_counts >= 2
    if not valid.any():
        raise ValueError("no time point has two finite animal contrasts")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        estimate = np.nanmean(curves, axis=0)
        standard_error = np.nanstd(curves, axis=0, ddof=1) / np.sqrt(finite_counts)
    estimate[~valid] = np.nan
    standard_error[~valid] = np.nan

    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(curves), size=(draws, len(curves)))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        distribution = np.nanmean(curves[sampled], axis=1)
    alpha = 1 - confidence
    pointwise_lower = np.nanquantile(distribution, alpha / 2, axis=0)
    pointwise_upper = np.nanquantile(distribution, 1 - alpha / 2, axis=0)
    studentized = np.abs((distribution - estimate) / standard_error)
    usable = valid & np.isfinite(standard_error) & (standard_error > 0)
    maxima = np.nanmax(np.where(usable, studentized, np.nan), axis=1)
    finite_maxima = maxima[np.isfinite(maxima)]
    bootstrap_critical = (
        float(np.quantile(finite_maxima, confidence))
        if len(finite_maxima)
        else float("nan")
    )
    t_floor = float(student_t.ppf(0.5 + confidence / 2, len(curves) - 1))
    critical = max(bootstrap_critical, t_floor)
    simultaneous_lower = estimate - critical * standard_error
    simultaneous_upper = estimate + critical * standard_error
    for array in (
        pointwise_lower,
        pointwise_upper,
        simultaneous_lower,
        simultaneous_upper,
    ):
        array[~valid] = np.nan

    result_warnings = []
    if len(set(finite_counts[valid].tolist())) > 1:
        result_warnings.append("animal_support_varies_across_time")
    if not np.all(valid):
        result_warnings.append("insufficient_animals_at_some_time_points")
    if not usable.all():
        result_warnings.append("simultaneous_band_undefined_at_zero_variance_points")
    return PeriEventInferenceResult(
        tuple(time.tolist()),
        _tuple(estimate),
        _tuple(standard_error),
        _tuple(pointwise_lower),
        _tuple(pointwise_upper),
        _tuple(simultaneous_lower),
        _tuple(simultaneous_upper),
        tuple(int(value) for value in finite_counts),
        len(names),
        confidence,
        draws,
        seed,
        critical,
        (
            "animal_bootstrap_percentile_pointwise_and_fixed_se_max_t_simultaneous_"
            "with_animal_t_floor"
        ),
        tuple(result_warnings),
    )


def _animal_contrasts(
    values: NDArray[np.float64],
    animals: tuple[str, ...],
    sessions: tuple[str, ...],
    conditions: tuple[str, ...],
    numerator: str,
    denominator: str,
) -> tuple[NDArray[np.float64], tuple[str, ...]]:
    output = []
    names = []
    animal_array = np.asarray(animals, dtype=str)
    session_array = np.asarray(sessions, dtype=str)
    condition_array = np.asarray(conditions, dtype=str)
    for animal in sorted(set(animals)):
        level_curves = []
        for level in (numerator, denominator):
            session_curves = []
            selected_animal = animal_array == animal
            for session in sorted(set(session_array[selected_animal].tolist())):
                selected = (
                    selected_animal
                    & (session_array == session)
                    & (condition_array == level)
                )
                if selected.any():
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        session_curves.append(np.nanmean(values[selected], axis=0))
            if not session_curves:
                break
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                level_curves.append(np.nanmean(session_curves, axis=0))
        if len(level_curves) == 2:
            output.append(level_curves[0] - level_curves[1])
            names.append(animal)
    return np.asarray(output, dtype=float), tuple(names)


def _tuple(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)
