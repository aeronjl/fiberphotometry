"""Conservative scalar inference driven by explicit experimental designs."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise, product
from statistics import NormalDist
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from fiberphotometry.design import ObservationTable, StudyDesign, validate_design


@dataclass(frozen=True)
class Contrast:
    factor: str
    numerator: str
    denominator: str


@dataclass(frozen=True)
class Estimand:
    outcome: str
    contrast: Contrast
    aggregation_unit: str


@dataclass(frozen=True)
class ResamplingPlan:
    resample_units: tuple[str, ...]


@dataclass(frozen=True)
class PermutationPlan:
    mode: Literal["sign_flip", "shuffle"]
    exchangeability_unit: str
    within: tuple[str, ...] = ()


@dataclass(frozen=True)
class BootstrapResult:
    estimate: float
    confidence_interval: tuple[float, float]
    distribution: NDArray[np.float64]
    seed: int
    interval_method: str


@dataclass(frozen=True)
class PermutationResult:
    estimate: float
    p_value: float
    null_distribution: NDArray[np.float64]
    seed: int


def hierarchical_bootstrap(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    plan: ResamplingPlan,
    *,
    interval_method: Literal["percentile", "basic", "bca"],
    draws: int = 2000,
    seed: int = 0,
) -> BootstrapResult:
    """Bootstrap a two-level contrast through a declared nested unit path."""
    report = validate_design(table, design)
    report.raise_for_errors()
    unit_columns = _validate_estimand_and_units(
        table, design, estimand, plan.resample_units
    )
    rng = np.random.default_rng(seed)
    aggregation_column = _unit_column(design, estimand.aggregation_unit)
    sampled = [
        _resample_rows(table, unit_columns, aggregation_column, rng)
        for _ in range(draws)
    ]
    distribution = np.asarray(
        [_estimate(table, design, estimand, rows, groups) for rows, groups in sampled]
    )
    estimate = _estimate(table, design, estimand, np.arange(len(table)))
    interval = _bootstrap_interval(
        table, design, estimand, distribution, estimate, interval_method
    )
    return BootstrapResult(
        estimate,
        (float(interval[0]), float(interval[1])),
        distribution,
        seed,
        interval_method,
    )


def exact_sign_flip_test(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    *,
    exchangeability_unit: str,
) -> PermutationResult:
    """Enumerate the exact paired sign-flip null distribution (at most 20 units)."""
    validate_design(table, design).raise_for_errors()
    unit = _unit_column(design, exchangeability_unit)
    differences = _unit_differences(table, design, estimand, unit)
    if len(differences) > 20:
        raise ValueError("exact sign-flip enumeration is limited to 20 units")
    signs = np.asarray(list(product([-1, 1], repeat=len(differences))))
    null = np.mean(signs * differences, axis=1)
    observed = float(np.mean(differences))
    p_value = float(np.mean(np.abs(null) >= abs(observed)))
    return PermutationResult(observed, p_value, null, seed=0)


def permutation_test(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    plan: PermutationPlan,
    *,
    permutations: int = 2000,
    seed: int = 0,
) -> PermutationResult:
    """Test a contrast with explicit sign-flip or blocked-label exchangeability."""
    validate_design(table, design).raise_for_errors()
    rng = np.random.default_rng(seed)
    observed = _estimate(table, design, estimand, np.arange(len(table)))
    if plan.mode == "sign_flip":
        unit = _unit_column(design, plan.exchangeability_unit)
        differences = _unit_differences(table, design, estimand, unit)
        null = np.asarray(
            [
                np.mean(differences * rng.choice([-1, 1], size=len(differences)))
                for _ in range(permutations)
            ]
        )
    else:
        assignment_unit = _factor_assignment_unit(design, estimand.contrast.factor)
        if assignment_unit != plan.exchangeability_unit:
            raise ValueError(
                "shuffle exchangeability_unit must equal the factor assignment unit"
            )
        null = np.asarray(
            [
                _shuffled_estimate(table, design, estimand, plan, rng)
                for _ in range(permutations)
            ]
        )
    p_value = float((1 + np.sum(np.abs(null) >= abs(observed))) / (permutations + 1))
    return PermutationResult(observed, p_value, null, seed)


def _validate_estimand_and_units(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    units: tuple[str, ...],
) -> tuple[str, ...]:
    if not units:
        raise ValueError("resample_units cannot be empty")
    columns = tuple(_unit_column(design, unit) for unit in units)
    declared = {unit.name: unit for unit in design.units}
    for parent, child in pairwise(units):
        if declared[child].nested_within != parent:
            raise ValueError("resample_units must follow a directly nested path")
    if estimand.aggregation_unit not in units:
        raise ValueError("aggregation_unit must occur in resample_units")
    table.values(estimand.outcome)
    _factor_column(design, estimand.contrast.factor)
    factor = next(
        factor for factor in design.factors if factor.name == estimand.contrast.factor
    )
    if factor.kind != "categorical":
        raise ValueError("two-level contrasts require a categorical factor")
    return columns


def _resample_rows(
    table: ObservationTable,
    unit_columns: tuple[str, ...],
    aggregation_column: str,
    rng: np.random.Generator,
    rows: NDArray[np.int_] | None = None,
    level: int = 0,
    aggregation_group: int = -1,
    counter: list[int] | None = None,
) -> tuple[NDArray[np.int_], NDArray[np.int_]]:
    if counter is None:
        counter = [0]
    available = np.arange(len(table)) if rows is None else rows
    identifiers = table.values(unit_columns[level])[available]
    unique = np.asarray(list(dict.fromkeys(identifiers.tolist())), dtype=object)
    sampled = rng.choice(unique, size=len(unique), replace=True)
    output = []
    groups = []
    for identifier in sampled:
        selected = available[identifiers == identifier]
        group = aggregation_group
        if unit_columns[level] == aggregation_column:
            group = counter[0]
            counter[0] += 1
        if level == len(unit_columns) - 1:
            output.append(selected)
            groups.append(np.full(len(selected), group))
        else:
            child_rows, child_groups = _resample_rows(
                table,
                unit_columns,
                aggregation_column,
                rng,
                selected,
                level + 1,
                group,
                counter,
            )
            output.append(child_rows)
            groups.append(child_groups)
    return np.concatenate(output).astype(int), np.concatenate(groups).astype(int)


def _estimate(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    rows: NDArray[np.int_],
    aggregation_groups: NDArray[np.int_] | None = None,
) -> float:
    factor = table.values(_factor_column(design, estimand.contrast.factor))[rows]
    outcome = np.asarray(table.values(estimand.outcome)[rows], dtype=float)
    units = (
        table.values(_unit_column(design, estimand.aggregation_unit))[rows]
        if aggregation_groups is None
        else aggregation_groups
    )
    numerator = _unit_level_means(outcome, factor, units, estimand.contrast.numerator)
    denominator = _unit_level_means(
        outcome, factor, units, estimand.contrast.denominator
    )
    if not len(numerator) or not len(denominator):
        return float("nan")
    return float(np.mean(numerator) - np.mean(denominator))


def _unit_level_means(
    outcome: NDArray[np.float64],
    factor: np.ndarray,
    units: np.ndarray,
    level: str,
) -> NDArray[np.float64]:
    means = []
    for unit in dict.fromkeys(units[factor == level].tolist()):
        selected = (units == unit) & (factor == level) & np.isfinite(outcome)
        if selected.any():
            means.append(float(np.mean(outcome[selected])))
    return np.asarray(means)


def _unit_differences(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    unit_column: str,
) -> NDArray[np.float64]:
    units = table.values(unit_column)
    differences = []
    incomplete = []
    for unit in dict.fromkeys(units.tolist()):
        rows = np.flatnonzero(units == unit)
        value = _estimate(table, design, estimand, rows)
        if np.isfinite(value):
            differences.append(value)
        else:
            incomplete.append(unit)
    if incomplete:
        raise ValueError(
            "paired inference requires both contrast levels for every unit; "
            f"incomplete units: {incomplete!r}"
        )
    if len(differences) < 2:
        raise ValueError("sign-flip inference requires at least two complete units")
    return np.asarray(differences)


def _bootstrap_interval(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    distribution: NDArray[np.float64],
    estimate: float,
    method: str,
) -> NDArray[np.float64]:
    finite = distribution[np.isfinite(distribution)]
    if method == "percentile":
        return np.asarray(np.quantile(finite, [0.025, 0.975]), dtype=np.float64)
    quantiles = np.quantile(finite, [0.025, 0.975])
    if method == "basic":
        return np.asarray([2 * estimate - quantiles[1], 2 * estimate - quantiles[0]])
    if method != "bca":
        raise ValueError("interval_method must be 'percentile', 'basic', or 'bca'")
    unit_column = _unit_column(design, estimand.aggregation_unit)
    units = table.values(unit_column)
    jackknife = []
    for unit in dict.fromkeys(units.tolist()):
        rows = np.flatnonzero(units != unit)
        jackknife.append(_estimate(table, design, estimand, rows))
    jackknife_values = np.asarray(jackknife)
    mean = float(np.nanmean(jackknife_values))
    centered = mean - jackknife_values
    denominator = 6 * float(np.nansum(centered**2)) ** 1.5
    acceleration = float(np.nansum(centered**3) / denominator) if denominator else 0.0
    proportion = float(np.clip(np.mean(finite < estimate), 1e-6, 1 - 1e-6))
    normal = NormalDist()
    bias = normal.inv_cdf(proportion)
    adjusted = []
    for probability in (0.025, 0.975):
        z = normal.inv_cdf(probability)
        adjusted.append(normal.cdf(bias + (bias + z) / (1 - acceleration * (bias + z))))
    return np.asarray(np.quantile(finite, adjusted), dtype=np.float64)


def _shuffled_estimate(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    plan: PermutationPlan,
    rng: np.random.Generator,
) -> float:
    factor_column = _factor_column(design, estimand.contrast.factor)
    labels = table.values(factor_column).copy()
    exchangeability_column = _unit_column(design, plan.exchangeability_unit)
    exchangeability_ids = table.values(exchangeability_column)
    block_columns = tuple(_unit_column(design, name) for name in plan.within)
    blocks = [
        tuple(table.values(column)[row] for column in block_columns)
        for row in range(len(table))
    ]
    for block in dict.fromkeys(blocks):
        rows = np.asarray(
            [index for index, value in enumerate(blocks) if value == block]
        )
        units = list(dict.fromkeys(exchangeability_ids[rows].tolist()))
        unit_labels = np.asarray(
            [labels[rows[exchangeability_ids[rows] == unit][0]] for unit in units],
            dtype=object,
        )
        shuffled = rng.permutation(unit_labels)
        for unit, label in zip(units, shuffled, strict=True):
            labels[rows[exchangeability_ids[rows] == unit]] = label
    columns = dict(table.columns)
    columns[factor_column] = tuple(labels.tolist())
    return _estimate(ObservationTable(columns), design, estimand, np.arange(len(table)))


def _unit_column(design: StudyDesign, name: str) -> str:
    try:
        return next(unit.column for unit in design.units if unit.name == name)
    except StopIteration as error:
        raise ValueError(f"unknown unit {name!r}") from error


def _factor_column(design: StudyDesign, name: str) -> str:
    try:
        return next(factor.column for factor in design.factors if factor.name == name)
    except StopIteration as error:
        raise ValueError(f"unknown factor {name!r}") from error


def _factor_assignment_unit(design: StudyDesign, name: str) -> str:
    try:
        return next(
            factor.assignment_unit for factor in design.factors if factor.name == name
        )
    except StopIteration as error:
        raise ValueError(f"unknown factor {name!r}") from error
