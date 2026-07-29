"""Animal-level peri-event contrasts with pointwise and simultaneous bands."""

from __future__ import annotations

import json
import warnings
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from fipha.population import (
    PopulationContrastResult,
    PopulationContrastSpec,
    PopulationGroupAssignment,
    PopulationInteractionResult,
    PopulationInteractionSpec,
    PopulationUnitEstimate,
    infer_population_contrast,
    infer_population_interaction,
)


@dataclass(frozen=True)
class PeriEventInferenceSpec:
    """Declared alignment, population design, and uncertainty choices."""

    window: tuple[float, float] = (-1.0, 2.0)
    rate_hz: float = 20.0
    confidence: float = 0.95
    draws: int = 2000
    seed: int = 0
    within_animal: str = "equal_session_means"
    design: Literal["paired", "independent"] = "paired"

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
        if self.design not in {"paired", "independent"}:
            raise ValueError("time-course design must be 'paired' or 'independent'")


@dataclass(frozen=True)
class PeriEventSessionEstimate:
    """One session-condition curve before equal-session animal aggregation."""

    subject: str
    session: str
    level: str
    estimate: tuple[float, ...]
    events_per_time: tuple[int, ...]
    event_count: int


@dataclass(frozen=True)
class PeriEventInferenceResult:
    """A contrast curve plus its complete session-to-population evidence chain."""

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
    session_estimates: tuple[PeriEventSessionEstimate, ...]
    population: PopulationContrastResult
    schema_version: str = "2"

    def to_json(self) -> str:
        """Serialize arrays, unit ledgers, and inferential semantics."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class PeriEventInteractionResult:
    """A peri-event group-by-condition interaction with complete unit evidence."""

    relative_time: tuple[float, ...]
    session_estimates: tuple[PeriEventSessionEstimate, ...]
    interaction: PopulationInteractionResult
    schema_version: str = "1"

    @property
    def estimate(self) -> tuple[float, ...]:
        """Return the group difference between within-animal condition curves."""
        return self.interaction.population.estimate

    def to_json(self) -> str:
        """Serialize the complete event-to-interaction evidence chain."""
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
    design: Literal["paired", "independent"] = "paired",
    confidence: float = 0.95,
    draws: int = 2000,
    seed: int = 0,
) -> PeriEventInferenceResult:
    """Infer a curve after equal-session aggregation within each animal.

    ``values`` is event by relative-time. Events are never treated as independent
    inferential units. Paired designs contrast levels within animals; independent
    designs compare two disjoint groups of animal estimates.
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

    session_estimates, animal_estimates = _materialize_estimates(
        matrix,
        animals,
        sessions,
        conditions,
        numerator,
        denominator,
    )
    try:
        population = infer_population_contrast(
            animal_estimates,
            PopulationContrastSpec(
                numerator=numerator,
                denominator=denominator,
                design=design,
                confidence=confidence,
                draws=draws,
                seed=seed,
            ),
        )
    except ValueError as error:
        message = str(error).replace("population inference", "time-course inference")
        message = message.replace("units", "animals")
        raise ValueError(message) from error
    result_warnings = tuple(
        warning.replace("unit", "animal") for warning in population.warnings
    )
    return PeriEventInferenceResult(
        relative_time=tuple(time.tolist()),
        estimate=population.estimate,
        standard_error=population.standard_error,
        pointwise_lower=population.pointwise_lower,
        pointwise_upper=population.pointwise_upper,
        simultaneous_lower=population.simultaneous_lower,
        simultaneous_upper=population.simultaneous_upper,
        animals_per_time=population.contrast_units_per_point,
        animal_count=len(population.included_units),
        confidence=confidence,
        draws=draws,
        seed=seed,
        simultaneous_critical_value=population.simultaneous_critical_value,
        method="animal_bootstrap_" + population.method,
        warnings=result_warnings,
        session_estimates=session_estimates,
        population=population,
    )


def infer_peri_event_interaction(
    values: NDArray[np.float64],
    relative_time: NDArray[np.float64],
    *,
    animals: tuple[str, ...],
    sessions: tuple[str, ...],
    groups: tuple[str, ...],
    conditions: tuple[str, ...],
    spec: PopulationInteractionSpec,
) -> PeriEventInteractionResult:
    """Infer a group contrast over within-animal peri-event condition contrasts."""
    matrix = np.asarray(values, dtype=float)
    time = np.asarray(relative_time, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != len(time):
        raise ValueError("values must be event by relative_time")
    if len(time) < 2 or not np.all(np.diff(time) > 0):
        raise ValueError("relative_time must be strictly increasing")
    event_count = matrix.shape[0]
    if not (
        len(animals) == len(sessions) == len(groups) == len(conditions) == event_count
    ):
        raise ValueError("event metadata must match the values rows")
    assignments = _group_assignments(animals, groups)
    session_estimates, animal_estimates = _materialize_estimates(
        matrix,
        animals,
        sessions,
        conditions,
        spec.condition_numerator,
        spec.condition_denominator,
    )
    interaction = infer_population_interaction(animal_estimates, assignments, spec)
    return PeriEventInteractionResult(
        relative_time=tuple(time.tolist()),
        session_estimates=session_estimates,
        interaction=interaction,
    )


def _materialize_estimates(
    values: NDArray[np.float64],
    animals: tuple[str, ...],
    sessions: tuple[str, ...],
    conditions: tuple[str, ...],
    numerator: str,
    denominator: str,
) -> tuple[tuple[PeriEventSessionEstimate, ...], tuple[PopulationUnitEstimate, ...]]:
    session_output: list[PeriEventSessionEstimate] = []
    animal_output: list[PopulationUnitEstimate] = []
    animal_array = np.asarray(animals, dtype=str)
    session_array = np.asarray(sessions, dtype=str)
    condition_array = np.asarray(conditions, dtype=str)
    for animal in sorted(set(animals)):
        selected_animal = animal_array == animal
        for level in (numerator, denominator):
            session_curves: list[NDArray[np.float64]] = []
            session_ids: list[str] = []
            event_count = 0
            for session in sorted(set(session_array[selected_animal].tolist())):
                selected = (
                    selected_animal
                    & (session_array == session)
                    & (condition_array == level)
                )
                if not selected.any():
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    curve = np.nanmean(values[selected], axis=0)
                events_per_time = np.sum(np.isfinite(values[selected]), axis=0)
                count = int(np.sum(selected))
                session_curves.append(curve)
                session_ids.append(session)
                event_count += count
                session_output.append(
                    PeriEventSessionEstimate(
                        subject=animal,
                        session=session,
                        level=level,
                        estimate=_tuple(curve),
                        events_per_time=_integer_tuple(events_per_time),
                        event_count=count,
                    )
                )
            if not session_curves:
                continue
            stack = np.asarray(session_curves, dtype=float)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                animal_curve = np.nanmean(stack, axis=0)
            animal_output.append(
                PopulationUnitEstimate(
                    unit_id=animal,
                    level=level,
                    estimate=_tuple(animal_curve),
                    support=_integer_tuple(np.sum(np.isfinite(stack), axis=0)),
                    source_units=tuple(session_ids),
                    observation_count=event_count,
                )
            )
    return tuple(session_output), tuple(animal_output)


def _group_assignments(
    animals: tuple[str, ...], groups: tuple[str, ...]
) -> tuple[PopulationGroupAssignment, ...]:
    assignments: list[PopulationGroupAssignment] = []
    animal_array = np.asarray(animals, dtype=str)
    group_array = np.asarray(groups, dtype=str)
    for animal in sorted(set(animals)):
        observed = sorted(set(group_array[animal_array == animal].tolist()))
        if len(observed) != 1:
            raise ValueError(
                f"animal {animal!r} must have exactly one population group"
            )
        assignments.append(PopulationGroupAssignment(animal, observed[0]))
    return tuple(assignments)


def _tuple(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _integer_tuple(values: NDArray[np.integer]) -> tuple[int, ...]:
    return tuple(int(value) for value in values)
