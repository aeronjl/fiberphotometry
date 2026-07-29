"""Versioned, auditable analysis plans built from explicit design assumptions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from typing import Literal

from scipy.stats import nct, t

from fipha.design import ObservationTable, StudyDesign
from fipha.inference import (
    Contrast,
    Estimand,
    PermutationPlan,
    exact_sign_flip_test,
    permutation_test,
    recommend_inference,
    unit_t_interval,
)


@dataclass(frozen=True)
class AnalysisPlan:
    estimand: Estimand
    method: str
    required_assumptions: tuple[str, ...]
    acknowledged_assumptions: tuple[str, ...]
    executable: bool
    intent: Literal["confirmatory", "exploratory", "descriptive"]
    seed: int | None = None
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> AnalysisPlan:
        payload = json.loads(value)
        if payload.get("schema_version") != "1":
            raise ValueError("unsupported analysis-plan schema version")
        payload["estimand"]["contrast"] = Contrast(**payload["estimand"]["contrast"])
        payload["estimand"] = Estimand(**payload["estimand"])
        payload["required_assumptions"] = tuple(payload["required_assumptions"])
        payload["acknowledged_assumptions"] = tuple(payload["acknowledged_assumptions"])
        return cls(**payload)


@dataclass(frozen=True)
class AnalysisResult:
    plan: AnalysisPlan
    estimate: float
    confidence_interval: tuple[float, float] | None
    p_value: float
    engine: str
    package_version: str
    executed_at_utc: str
    input_fingerprint: str
    random_seed: int | None
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class PowerSensitivity:
    animals_per_condition: int
    minimum_power: float
    maximum_power: float
    effect_range: tuple[float, float]
    animal_sd_range: tuple[float, float]


def create_analysis_plan(
    table: ObservationTable,
    design: StudyDesign,
    estimand: Estimand,
    *,
    randomized: bool | None,
    intent: Literal["confirmatory", "exploratory", "descriptive"],
    acknowledged_assumptions: tuple[str, ...] = (),
    seed: int | None = None,
) -> AnalysisPlan:
    """Create a non-executable plan until every method assumption is acknowledged."""
    recommendation = recommend_inference(table, design, estimand, randomized=randomized)
    required = _assumptions(recommendation.primary)
    acknowledged = tuple(sorted(set(acknowledged_assumptions)))
    return AnalysisPlan(
        estimand=estimand,
        method=recommendation.primary,
        required_assumptions=required,
        acknowledged_assumptions=acknowledged,
        executable=set(required) <= set(acknowledged),
        intent=intent,
        seed=seed,
    )


def execute_analysis_plan(
    plan: AnalysisPlan, table: ObservationTable, design: StudyDesign
) -> AnalysisResult:
    """Execute only acknowledged, currently supported scalar plans."""
    if not plan.executable:
        raise ValueError("analysis plan is not executable; acknowledge all assumptions")
    provenance = (
        version("fipha"),
        datetime.now(UTC).isoformat(),
        _fingerprint(table, design),
        plan.seed,
    )
    if plan.method in {"welch_t", "paired_t"}:
        result = unit_t_interval(
            table,
            design,
            plan.estimand,
            mode="welch" if plan.method == "welch_t" else "paired",
        )
        return AnalysisResult(
            plan,
            result.estimate,
            result.confidence_interval,
            result.p_value,
            "scipy",
            *provenance,
        )
    if plan.method == "exact_sign_flip":
        exact_result = exact_sign_flip_test(
            table,
            design,
            plan.estimand,
            exchangeability_unit=plan.estimand.aggregation_unit,
        )
        return AnalysisResult(
            plan,
            exact_result.estimate,
            None,
            exact_result.p_value,
            "exact",
            *provenance,
        )
    if plan.method in {"monte_carlo_sign_flip", "assignment_unit_permutation"}:
        if plan.seed is None:
            raise ValueError("Monte Carlo execution requires a recorded seed")
        assignment = next(
            factor.assignment_unit
            for factor in design.factors
            if factor.name == plan.estimand.contrast.factor
        )
        permutation = permutation_test(
            table,
            design,
            plan.estimand,
            PermutationPlan(
                "sign_flip" if plan.method == "monte_carlo_sign_flip" else "shuffle",
                plan.estimand.aggregation_unit
                if plan.method == "monte_carlo_sign_flip"
                else assignment,
            ),
            seed=plan.seed,
        )
        return AnalysisResult(
            plan,
            permutation.estimate,
            None,
            permutation.p_value,
            "numpy-monte-carlo",
            *provenance,
        )
    raise ValueError(f"execution is not implemented for method {plan.method!r}")


def welch_power_sensitivity(
    *,
    animals_per_condition: int,
    effect_range: tuple[float, float],
    animal_sd_range: tuple[float, float],
    alpha: float = 0.05,
) -> PowerSensitivity:
    """Bound Gaussian Welch power over user-supplied effect and SD ranges."""
    if animals_per_condition < 2 or effect_range[0] < 0 or animal_sd_range[0] <= 0:
        raise ValueError(
            "power inputs require n >= 2, nonnegative effects, and positive SDs"
        )
    degrees = 2 * animals_per_condition - 2
    critical = float(t.ppf(1 - alpha / 2, degrees))

    def power(effect: float, standard_deviation: float) -> float:
        noncentrality = effect / (
            standard_deviation * (2 / animals_per_condition) ** 0.5
        )
        return float(
            nct.cdf(-critical, degrees, noncentrality)
            + nct.sf(critical, degrees, noncentrality)
        )

    values = [
        power(effect, standard_deviation)
        for effect in effect_range
        for standard_deviation in animal_sd_range
    ]
    return PowerSensitivity(
        animals_per_condition,
        min(values),
        max(values),
        effect_range,
        animal_sd_range,
    )


def _assumptions(method: str) -> tuple[str, ...]:
    common = ("independent_aggregation_units", "estimand_matches_question")
    if method in {
        "exact_sign_flip",
        "monte_carlo_sign_flip",
        "assignment_unit_permutation",
    }:
        return (
            *common,
            "exchangeability_under_null",
            "randomization_mechanism_correct",
        )
    if method == "welch_t":
        return (*common, "approximately_gaussian_unit_means")
    if method == "paired_t":
        return (*common, "approximately_gaussian_unit_differences", "complete_pairs")
    return (*common, "bootstrap_scheme_matches_sampling_process")


def _fingerprint(table: ObservationTable, design: StudyDesign) -> str:
    payload = json.dumps(
        {"columns": table.columns, "design": json.loads(design.to_json())},
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode()).hexdigest()
