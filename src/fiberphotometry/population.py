"""Reusable population contrasts over auditable experimental-unit estimates."""

from __future__ import annotations

import json
import warnings
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from scipy.stats import t as student_t


@dataclass(frozen=True)
class PopulationUnitEstimate:
    """One condition estimate for one independent population unit.

    ``source_units`` and ``observation_count`` retain how the estimate was formed;
    ``support`` records the number of finite source-unit estimates at each point.
    Scalar outcomes use one-element tuples, so the same contract can serve curves,
    spectra, transient summaries, and other derived outcomes.
    """

    unit_id: str
    level: str
    estimate: tuple[float, ...]
    support: tuple[int, ...]
    source_units: tuple[str, ...]
    observation_count: int

    def __post_init__(self) -> None:
        if not self.unit_id or not self.level:
            raise ValueError("population unit_id and level cannot be empty")
        if not self.estimate or len(self.estimate) != len(self.support):
            raise ValueError("population estimate and support must share a shape")
        if any(value < 0 for value in self.support):
            raise ValueError("population support cannot be negative")
        if not self.source_units or self.observation_count < 1:
            raise ValueError(
                "population estimates require source units and observations"
            )


@dataclass(frozen=True)
class PopulationInfluence:
    """Change in the population estimate after omitting one unit."""

    unit_id: str
    level: str
    estimate_without_unit: tuple[float, ...]
    maximum_absolute_change: float


@dataclass(frozen=True)
class PopulationContrastSpec:
    """Versioned choices for a two-level population contrast."""

    numerator: str
    denominator: str
    design: Literal["paired", "independent"]
    confidence: float = 0.95
    draws: int = 2000
    seed: int = 0
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.numerator or not self.denominator:
            raise ValueError("population contrast levels cannot be empty")
        if self.numerator == self.denominator:
            raise ValueError("population contrast levels must differ")
        if self.design not in {"paired", "independent"}:
            raise ValueError("population design must be 'paired' or 'independent'")
        if not 0 < self.confidence < 1:
            raise ValueError("confidence must lie between zero and one")
        if self.draws < 100:
            raise ValueError("population inference requires at least 100 draws")
        if self.schema_version != "1":
            raise ValueError("unsupported population-contrast schema version")


@dataclass(frozen=True)
class PopulationContrastResult:
    """A paired or independent contrast over population-unit estimates."""

    spec: PopulationContrastSpec
    design: Literal["paired", "independent"]
    numerator: str
    denominator: str
    estimate: tuple[float, ...]
    standard_error: tuple[float, ...]
    standardized_effect: tuple[float, ...]
    pointwise_lower: tuple[float, ...]
    pointwise_upper: tuple[float, ...]
    simultaneous_lower: tuple[float, ...]
    simultaneous_upper: tuple[float, ...]
    numerator_units_per_point: tuple[int, ...]
    denominator_units_per_point: tuple[int, ...]
    contrast_units_per_point: tuple[int, ...]
    included_units: tuple[str, ...]
    excluded_units: tuple[str, ...]
    unit_estimates: tuple[PopulationUnitEstimate, ...]
    influence: tuple[PopulationInfluence, ...]
    confidence: float
    draws: int
    seed: int
    simultaneous_critical_value: float
    effect_size_method: str
    method: str
    warnings: tuple[str, ...]
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize the estimand, unit ledger, and uncertainty choices."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def infer_population_contrast(
    estimates: tuple[PopulationUnitEstimate, ...],
    spec: PopulationContrastSpec,
) -> PopulationContrastResult:
    """Contrast already-materialized unit estimates without pseudo-replication."""
    numerator = spec.numerator
    denominator = spec.denominator
    design = spec.design
    confidence = spec.confidence
    draws = spec.draws
    seed = spec.seed
    selected = tuple(
        item for item in estimates if item.level in {numerator, denominator}
    )
    if not selected:
        raise ValueError("no unit estimates match the requested contrast")
    width = len(selected[0].estimate)
    if width == 0:
        raise ValueError("population unit estimates cannot be empty")
    if any(
        len(item.estimate) != width or len(item.support) != width for item in selected
    ):
        raise ValueError("population unit estimates must share one outcome shape")
    keys = [(item.unit_id, item.level) for item in selected]
    if len(set(keys)) != len(keys):
        raise ValueError("population estimates require unique unit-level rows")

    numerator_items = tuple(item for item in selected if item.level == numerator)
    denominator_items = tuple(item for item in selected if item.level == denominator)
    numerator_ids = {item.unit_id for item in numerator_items}
    denominator_ids = {item.unit_id for item in denominator_items}
    all_ids = numerator_ids | denominator_ids

    if design == "paired":
        included = tuple(sorted(numerator_ids & denominator_ids))
        excluded = tuple(sorted(all_ids - set(included)))
        if len(included) < 2:
            raise ValueError("paired population inference requires two complete units")
    else:
        overlap = numerator_ids & denominator_ids
        if overlap:
            raise ValueError(
                "independent population groups cannot share units: "
                + ", ".join(sorted(overlap))
            )
        if len(numerator_ids) < 2 or len(denominator_ids) < 2:
            raise ValueError(
                "independent population inference requires two units per level"
            )
        included = tuple(sorted(all_ids))
        excluded = ()

    numerator_matrix, numerator_names = _matrix(numerator_items, included, design)
    denominator_matrix, denominator_names = _matrix(denominator_items, included, design)
    numerator_support = np.sum(np.isfinite(numerator_matrix), axis=0)
    denominator_support = np.sum(np.isfinite(denominator_matrix), axis=0)

    if design == "paired":
        contrasts = numerator_matrix - denominator_matrix
        contrast_support = np.sum(np.isfinite(contrasts), axis=0)
        estimate, standard_error = _paired_summary(contrasts)
        degrees = contrast_support.astype(float) - 1
        standardized, effect_method = _paired_effect(contrasts)
    else:
        contrast_support = numerator_support + denominator_support
        estimate, standard_error, degrees = _independent_summary(
            numerator_matrix, denominator_matrix
        )
        standardized, effect_method = _independent_effect(
            numerator_matrix, denominator_matrix
        )

    valid = (
        (numerator_support >= 2)
        & (denominator_support >= 2)
        & np.isfinite(estimate)
        & np.isfinite(standard_error)
    )
    if design == "paired":
        valid &= contrast_support >= 2
    if not valid.any():
        raise ValueError("no outcome point has sufficient population-unit support")
    for array in (estimate, standard_error, standardized):
        array[~valid] = np.nan

    rng = np.random.default_rng(seed)
    distribution = _bootstrap_distribution(
        numerator_matrix,
        denominator_matrix,
        design=design,
        draws=draws,
        rng=rng,
    )
    alpha = 1 - confidence
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        pointwise_lower = np.nanquantile(distribution, alpha / 2, axis=0)
        pointwise_upper = np.nanquantile(distribution, 1 - alpha / 2, axis=0)
        studentized = np.abs((distribution - estimate) / standard_error)
    usable = valid & (standard_error > 0)
    maxima = np.nanmax(np.where(usable, studentized, np.nan), axis=1)
    finite_maxima = maxima[np.isfinite(maxima)]
    bootstrap_critical = (
        float(np.quantile(finite_maxima, confidence))
        if len(finite_maxima)
        else float("nan")
    )
    finite_degrees = degrees[usable & np.isfinite(degrees) & (degrees > 0)]
    t_floor = (
        float(student_t.ppf(0.5 + confidence / 2, np.min(finite_degrees)))
        if len(finite_degrees)
        else float("nan")
    )
    critical_candidates = [
        value for value in (bootstrap_critical, t_floor) if np.isfinite(value)
    ]
    critical = max(critical_candidates) if critical_candidates else float("nan")
    simultaneous_lower = estimate - critical * standard_error
    simultaneous_upper = estimate + critical * standard_error
    for array in (
        pointwise_lower,
        pointwise_upper,
        simultaneous_lower,
        simultaneous_upper,
    ):
        array[~valid] = np.nan

    influence = _influence(
        numerator_matrix,
        numerator_names,
        denominator_matrix,
        denominator_names,
        design,
        estimate,
    )
    result_warnings: list[str] = []
    if excluded:
        result_warnings.append("incomplete_paired_units_excluded")
    if (
        len(set(numerator_support[valid].tolist())) > 1
        or len(set(denominator_support[valid].tolist())) > 1
    ):
        result_warnings.append("unit_support_varies_across_outcome")
    if not np.all(valid):
        result_warnings.append("insufficient_units_at_some_outcome_points")
    if not usable.all():
        result_warnings.append("simultaneous_band_undefined_at_zero_variance_points")

    return PopulationContrastResult(
        spec=spec,
        design=design,
        numerator=numerator,
        denominator=denominator,
        estimate=_tuple(estimate),
        standard_error=_tuple(standard_error),
        standardized_effect=_tuple(standardized),
        pointwise_lower=_tuple(pointwise_lower),
        pointwise_upper=_tuple(pointwise_upper),
        simultaneous_lower=_tuple(simultaneous_lower),
        simultaneous_upper=_tuple(simultaneous_upper),
        numerator_units_per_point=_integer_tuple(numerator_support),
        denominator_units_per_point=_integer_tuple(denominator_support),
        contrast_units_per_point=_integer_tuple(contrast_support),
        included_units=included,
        excluded_units=excluded,
        unit_estimates=selected,
        influence=influence,
        confidence=confidence,
        draws=draws,
        seed=seed,
        simultaneous_critical_value=critical,
        effect_size_method=effect_method,
        method=(
            "paired_unit_bootstrap_percentile_and_max_t"
            if design == "paired"
            else "independent_group_bootstrap_percentile_and_welch_max_t"
        ),
        warnings=tuple(result_warnings),
    )


def _matrix(
    items: tuple[PopulationUnitEstimate, ...],
    included: tuple[str, ...],
    design: str,
) -> tuple[NDArray[np.float64], tuple[str, ...]]:
    lookup = {item.unit_id: item for item in items}
    names = included if design == "paired" else tuple(sorted(lookup))
    return (
        np.asarray([lookup[name].estimate for name in names], dtype=float),
        names,
    )


def _paired_summary(
    contrasts: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        estimate = np.nanmean(contrasts, axis=0)
        count = np.sum(np.isfinite(contrasts), axis=0)
        standard_error = np.nanstd(contrasts, axis=0, ddof=1) / np.sqrt(count)
    return estimate, standard_error


def _independent_summary(
    numerator: NDArray[np.float64], denominator: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        numerator_count = np.sum(np.isfinite(numerator), axis=0)
        denominator_count = np.sum(np.isfinite(denominator), axis=0)
        numerator_mean = np.nanmean(numerator, axis=0)
        denominator_mean = np.nanmean(denominator, axis=0)
        numerator_term = np.nanvar(numerator, axis=0, ddof=1) / numerator_count
        denominator_term = np.nanvar(denominator, axis=0, ddof=1) / denominator_count
        standard_error = np.sqrt(numerator_term + denominator_term)
        degrees = (numerator_term + denominator_term) ** 2 / (
            numerator_term**2 / (numerator_count - 1)
            + denominator_term**2 / (denominator_count - 1)
        )
    return numerator_mean - denominator_mean, standard_error, degrees


def _paired_effect(
    contrasts: NDArray[np.float64],
) -> tuple[NDArray[np.float64], str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        count = np.sum(np.isfinite(contrasts), axis=0)
        effect = np.nanmean(contrasts, axis=0) / np.nanstd(contrasts, axis=0, ddof=1)
    correction = 1 - 3 / (4 * count - 5)
    return effect * correction, "hedges_gz_paired"


def _independent_effect(
    numerator: NDArray[np.float64], denominator: NDArray[np.float64]
) -> tuple[NDArray[np.float64], str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        numerator_count = np.sum(np.isfinite(numerator), axis=0)
        denominator_count = np.sum(np.isfinite(denominator), axis=0)
        degrees = numerator_count + denominator_count - 2
        pooled = np.sqrt(
            (
                (numerator_count - 1) * np.nanvar(numerator, axis=0, ddof=1)
                + (denominator_count - 1) * np.nanvar(denominator, axis=0, ddof=1)
            )
            / degrees
        )
        effect = (
            np.nanmean(numerator, axis=0) - np.nanmean(denominator, axis=0)
        ) / pooled
    correction = 1 - 3 / (4 * degrees - 1)
    return effect * correction, "hedges_g_independent_pooled_sd"


def _bootstrap_distribution(
    numerator: NDArray[np.float64],
    denominator: NDArray[np.float64],
    *,
    design: str,
    draws: int,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    if design == "paired":
        contrasts = numerator - denominator
        indices = rng.integers(0, len(contrasts), size=(draws, len(contrasts)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            distribution = np.nanmean(contrasts[indices], axis=1)
        return np.asarray(distribution, dtype=float)
    numerator_indices = rng.integers(0, len(numerator), size=(draws, len(numerator)))
    denominator_indices = rng.integers(
        0, len(denominator), size=(draws, len(denominator))
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        distribution = np.nanmean(numerator[numerator_indices], axis=1) - np.nanmean(
            denominator[denominator_indices], axis=1
        )
    return np.asarray(distribution, dtype=float)


def _influence(
    numerator: NDArray[np.float64],
    numerator_names: tuple[str, ...],
    denominator: NDArray[np.float64],
    denominator_names: tuple[str, ...],
    design: str,
    full_estimate: NDArray[np.float64],
) -> tuple[PopulationInfluence, ...]:
    output = []
    names = sorted(set(numerator_names) | set(denominator_names))
    for name in names:
        numerator_keep = np.asarray([item != name for item in numerator_names])
        denominator_keep = np.asarray([item != name for item in denominator_names])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            if design == "paired":
                reduced = np.nanmean(
                    numerator[numerator_keep] - denominator[denominator_keep], axis=0
                )
                level = "paired"
            else:
                reduced = np.nanmean(numerator[numerator_keep], axis=0) - np.nanmean(
                    denominator[denominator_keep], axis=0
                )
                level = "numerator" if name in set(numerator_names) else "denominator"
            change = np.abs(reduced - full_estimate)
            maximum = (
                float(np.nanmax(change)) if np.isfinite(change).any() else float("nan")
            )
        output.append(PopulationInfluence(name, level, _tuple(reduced), maximum))
    return tuple(output)


def _tuple(values: NDArray[np.float64]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _integer_tuple(values: NDArray[np.integer]) -> tuple[int, ...]:
    return tuple(int(value) for value in values)
