"""Small, serializable experimental-design declarations for valid inference."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np

Scalar = str | int | float | bool | None


@dataclass(frozen=True)
class ObservationTable:
    """Open metadata columns with equal length and no imposed scientific ontology."""

    columns: Mapping[str, tuple[Scalar, ...]]

    def __post_init__(self) -> None:
        lengths = {len(values) for values in self.columns.values()}
        if not self.columns or len(lengths) != 1:
            raise ValueError("observation columns must be non-empty and equal length")

    @classmethod
    def from_columns(cls, columns: Mapping[str, Sequence[Scalar]]) -> ObservationTable:
        normalized = {name: tuple(values) for name, values in columns.items()}
        return cls(columns=normalized)

    def __len__(self) -> int:
        return len(next(iter(self.columns.values())))

    def values(self, column: str) -> np.ndarray:
        try:
            return np.asarray(self.columns[column], dtype=object)
        except KeyError as error:
            raise ValueError(f"observation table has no column {column!r}") from error


@dataclass(frozen=True)
class Unit:
    """An identified sampling unit, optionally nested within another unit."""

    name: str
    column: str
    nested_within: str | None = None


@dataclass(frozen=True)
class Factor:
    """An inferential factor and the unit at which its labels are assigned."""

    name: str
    column: str
    kind: Literal["categorical", "continuous"]
    assignment_unit: str


@dataclass(frozen=True)
class StudyDesign:
    """Versioned declaration of units and factors, separate from observations."""

    observation_id: str
    units: tuple[Unit, ...]
    factors: tuple[Factor, ...] = ()
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> StudyDesign:
        payload = json.loads(value)
        if payload.get("schema_version") != "1":
            raise ValueError("unsupported study-design schema version")
        return cls(
            observation_id=payload["observation_id"],
            units=tuple(Unit(**unit) for unit in payload["units"]),
            factors=tuple(Factor(**factor) for factor in payload.get("factors", [])),
            schema_version=payload["schema_version"],
        )


@dataclass(frozen=True)
class DesignIssue:
    severity: Literal["error", "warning"]
    code: str
    message: str


@dataclass(frozen=True)
class DesignReport:
    observations: int
    unit_counts: Mapping[str, int]
    factor_levels: Mapping[str, int]
    issues: tuple[DesignIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def raise_for_errors(self) -> None:
        errors = [issue.message for issue in self.issues if issue.severity == "error"]
        if errors:
            raise ValueError("invalid study design: " + "; ".join(errors))


def validate_design(table: ObservationTable, design: StudyDesign) -> DesignReport:
    """Compare a declaration with observed relationships and assignment levels."""
    issues: list[DesignIssue] = []
    required = {design.observation_id}
    required.update(unit.column for unit in design.units)
    required.update(factor.column for factor in design.factors)
    for column in sorted(required - table.columns.keys()):
        issues.append(
            DesignIssue("error", "missing_column", f"missing column {column!r}")
        )
    unit_names = [unit.name for unit in design.units]
    if len(unit_names) != len(set(unit_names)):
        issues.append(
            DesignIssue("error", "duplicate_unit", "unit names must be unique")
        )
    factor_names = [factor.name for factor in design.factors]
    if len(factor_names) != len(set(factor_names)):
        issues.append(
            DesignIssue("error", "duplicate_factor", "factor names must be unique")
        )
    if design.observation_id in table.columns:
        identifiers = table.values(design.observation_id)
        if len(set(identifiers.tolist())) != len(identifiers):
            issues.append(
                DesignIssue(
                    "error", "duplicate_observation", "observation IDs must be unique"
                )
            )
    units_by_name = {unit.name: unit for unit in design.units}
    for unit in design.units:
        if unit.nested_within is not None and unit.nested_within not in units_by_name:
            issues.append(
                DesignIssue(
                    "error",
                    "unknown_parent",
                    f"unit {unit.name!r} has an unknown parent",
                )
            )
        elif unit.column in table.columns and unit.nested_within is not None:
            parent = units_by_name[unit.nested_within]
            if parent.column in table.columns and not _functionally_depends(
                table.values(unit.column), table.values(parent.column)
            ):
                issues.append(
                    DesignIssue(
                        "error",
                        "crossed_nesting",
                        f"{unit.name!r} occurs under multiple {parent.name!r} units",
                    )
                )
    for factor in design.factors:
        if factor.assignment_unit not in units_by_name:
            issues.append(
                DesignIssue(
                    "error",
                    "unknown_assignment_unit",
                    f"factor {factor.name!r} has an unknown assignment unit",
                )
            )
            continue
        unit = units_by_name[factor.assignment_unit]
        if (
            factor.column in table.columns
            and unit.column in table.columns
            and not _functionally_depends(
                table.values(unit.column), table.values(factor.column)
            )
        ):
            issues.append(
                DesignIssue(
                    "error",
                    "factor_varies_within_assignment_unit",
                    f"factor {factor.name!r} changes within {unit.name!r}",
                )
            )
        if factor.kind == "categorical" and factor.column in table.columns:
            levels, counts = np.unique(table.values(factor.column), return_counts=True)
            if len(levels) < 2:
                issues.append(
                    DesignIssue(
                        "warning",
                        "single_factor_level",
                        f"factor {factor.name!r} has one observed level",
                    )
                )
            elif counts.min() / counts.max() < 0.25:
                issues.append(
                    DesignIssue(
                        "warning",
                        "factor_imbalance",
                        f"factor {factor.name!r} is strongly imbalanced",
                    )
                )
    return DesignReport(
        observations=len(table),
        unit_counts={
            unit.name: len(set(table.values(unit.column).tolist()))
            for unit in design.units
            if unit.column in table.columns
        },
        factor_levels={
            factor.name: len(set(table.values(factor.column).tolist()))
            for factor in design.factors
            if factor.column in table.columns
        },
        issues=tuple(issues),
    )


def _functionally_depends(keys: np.ndarray, values: np.ndarray) -> bool:
    mapping: dict[Scalar, Scalar] = {}
    for key, value in zip(keys.tolist(), values.tolist(), strict=True):
        if key in mapping and mapping[key] != value:
            return False
        mapping[key] = value
    return True
