"""Paired held-out predictor-family comparisons for encoding multiverses."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from math import sqrt
from statistics import mean, stdev
from typing import Literal

from scipy.stats import t as student_t

from fiberphotometry.encoding import EncodingModelSpec
from fiberphotometry.encoding_multiverse import (
    EncodingMultiverseResult,
    EncodingUniverseResult,
    _observation_evidence,
    _score,
)

PredictorFamilyComparisonStatus = Literal[
    "paired_predictive_comparison",
    "descriptive_only",
    "failed",
]


@dataclass(frozen=True)
class PredictorFamilyDropSpec:
    """One explicitly declared family and its literal reduced model."""

    family: str
    reduced_model: str
    removed_predictors: tuple[str, ...]
    rationale: str
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.family.strip():
            raise ValueError("predictor family name must be non-empty")
        if not self.reduced_model.strip():
            raise ValueError("reduced model name must be non-empty")
        if not self.removed_predictors or any(
            not name.strip() for name in self.removed_predictors
        ):
            raise ValueError("removed predictors must contain non-empty names")
        if len(self.removed_predictors) != len(set(self.removed_predictors)):
            raise ValueError("removed predictor names must be unique")
        if not self.rationale.strip():
            raise ValueError("predictor family rationale must be non-empty")


@dataclass(frozen=True)
class PredictorFamilyContributionSpec:
    """Full model and prespecified leave-family-out comparisons."""

    full_model: str
    families: tuple[PredictorFamilyDropSpec, ...]
    confidence_level: float = 0.95
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.full_model.strip():
            raise ValueError("full model name must be non-empty")
        if not self.families:
            raise ValueError("contribution analysis requires at least one family")
        family_names = [item.family for item in self.families]
        reduced_names = [item.reduced_model for item in self.families]
        if len(family_names) != len(set(family_names)):
            raise ValueError("predictor family names must be unique")
        if len(reduced_names) != len(set(reduced_names)):
            raise ValueError("reduced model names must be unique")
        if self.full_model in reduced_names:
            raise ValueError("a reduced model cannot be the full model")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must lie in (0, 1)")


@dataclass(frozen=True)
class PredictorFamilyGroupDelta:
    """Paired out-of-fold score difference for one independent group."""

    group: str
    observations: int
    full_r_squared: float
    reduced_r_squared: float
    delta_r_squared: float


@dataclass(frozen=True)
class PredictorFamilyDeltaDispersion:
    """Spread of paired group deltas; not a calibrated confidence interval.

    Held-out groups share overlapping training sets, so their delta scores are
    positively dependent. The Student-*t* arithmetic below therefore understates
    the variance of the mean delta, and no unbiased estimator of k-fold
    cross-validation variance exists (Bengio & Grandvalet 2004). The bounds are a
    dispersion summary at the requested nominal level, they are not calibrated,
    and they are not simultaneous across the declared families.
    """

    method: Literal["paired_group_t_dispersion_uncalibrated"]
    nominal_level: float
    groups: int
    mean_delta_r_squared: float
    group_standard_deviation: float
    dependence_naive_standard_error: float
    range_lower: float
    range_upper: float
    simultaneous_comparisons: int
    calibrated: bool = False
    simultaneous: bool = False
    dependence: str = (
        "held-out group deltas share overlapping training sets and are positively "
        "dependent; the naive standard error understates the true variance and the "
        "range under-covers the mean delta"
    )
    multiplicity: str = (
        "one range is reported per declared predictor family with no multiplicity "
        "adjustment; divide the complement of nominal_level by "
        "simultaneous_comparisons to read the bounds simultaneously"
    )


@dataclass(frozen=True)
class PredictorFamilyContribution:
    """One full-versus-reduced predictive comparison with safeguards."""

    family: str
    full_model: str
    reduced_model: str
    full_universe_id: str
    reduced_universe_id: str
    removed_predictors: tuple[str, ...]
    rationale: str
    status: PredictorFamilyComparisonStatus
    exact_same_observations: bool | None
    full_mean_r_squared: float | None
    reduced_mean_r_squared: float | None
    full_selected_alpha: float | None
    reduced_selected_alpha: float | None
    delta_mean_r_squared: float | None
    group_deltas: tuple[PredictorFamilyGroupDelta, ...]
    group_dispersion: PredictorFamilyDeltaDispersion | None
    reason: str


@dataclass(frozen=True)
class PredictorFamilyContributionResult:
    """Complete leave-family-out ledger without causal attribution."""

    spec: PredictorFamilyContributionSpec
    comparisons: tuple[PredictorFamilyContribution, ...]
    artifact_type: Literal["predictor_family_contribution_result"] = (
        "predictor_family_contribution_result"
    )
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def assess_predictor_family_contributions(
    multiverse: EncodingMultiverseResult,
    spec: PredictorFamilyContributionSpec,
) -> PredictorFamilyContributionResult:
    """Compare a full model with declared literal drop-family alternatives.

    Positive deltas mean that the full model predicted held-out observations better
    than the reduced model. They are predictive sensitivity summaries, not causal
    effects, unique variance partitions, or evidence that a predictor is necessary.

    Each family reports a ``group_dispersion`` summary rather than a
    calibrated confidence interval: held-out groups share overlapping training
    sets, so their deltas are positively dependent and the Student-*t* range
    under-covers. No multiplicity adjustment is applied across families; the
    number of simultaneous comparisons is recorded on every dispersion summary so
    a reader can adjust the nominal level explicitly.
    """

    universes = {item.name: item for item in multiverse.universes}
    if spec.full_model not in universes:
        raise ValueError("full model is not present in the encoding multiverse")
    missing = [
        item.reduced_model
        for item in spec.families
        if item.reduced_model not in universes
    ]
    if missing:
        raise ValueError(f"reduced models are absent from the multiverse: {missing}")
    full = universes[spec.full_model]
    for family in spec.families:
        _validate_literal_drop(
            full.model_spec, universes[family.reduced_model].model_spec, family
        )
    comparisons = tuple(
        _compare_family(
            full,
            universes[item.reduced_model],
            item,
            spec.confidence_level,
            len(spec.families),
        )
        for item in spec.families
    )
    return PredictorFamilyContributionResult(spec=spec, comparisons=comparisons)


def _compare_family(
    full: EncodingUniverseResult,
    reduced: EncodingUniverseResult,
    family: PredictorFamilyDropSpec,
    nominal_level: float,
    simultaneous_comparisons: int,
) -> PredictorFamilyContribution:
    full_score = _score(full.model_result)
    reduced_score = _score(reduced.model_result)
    if full.status == "failed" or reduced.status == "failed":
        return PredictorFamilyContribution(
            family=family.family,
            full_model=full.name,
            reduced_model=reduced.name,
            full_universe_id=full.universe_id,
            reduced_universe_id=reduced.universe_id,
            removed_predictors=family.removed_predictors,
            rationale=family.rationale,
            status="failed",
            exact_same_observations=None,
            full_mean_r_squared=full_score,
            reduced_mean_r_squared=reduced_score,
            full_selected_alpha=(
                full.model_result.selected_alpha
                if full.model_result is not None
                else None
            ),
            reduced_selected_alpha=(
                reduced.model_result.selected_alpha
                if reduced.model_result is not None
                else None
            ),
            delta_mean_r_squared=None,
            group_deltas=(),
            group_dispersion=None,
            reason=_failure_reason(full, reduced),
        )
    assert full.model_result is not None
    assert reduced.model_result is not None
    exact = _observation_evidence(full.model_result) == _observation_evidence(
        reduced.model_result
    )
    if not exact:
        return PredictorFamilyContribution(
            family=family.family,
            full_model=full.name,
            reduced_model=reduced.name,
            full_universe_id=full.universe_id,
            reduced_universe_id=reduced.universe_id,
            removed_predictors=family.removed_predictors,
            rationale=family.rationale,
            status="descriptive_only",
            exact_same_observations=False,
            full_mean_r_squared=full_score,
            reduced_mean_r_squared=reduced_score,
            full_selected_alpha=full.model_result.selected_alpha,
            reduced_selected_alpha=reduced.model_result.selected_alpha,
            delta_mean_r_squared=None,
            group_deltas=(),
            group_dispersion=None,
            reason="retained sample indices differ between full and reduced models",
        )
    full_groups = {
        item.group: item for item in full.model_result.residual_diagnostics.groups
    }
    reduced_groups = {
        item.group: item for item in reduced.model_result.residual_diagnostics.groups
    }
    if full_groups.keys() != reduced_groups.keys() or any(
        full_groups[name].observations != reduced_groups[name].observations
        for name in full_groups
    ):
        return PredictorFamilyContribution(
            family=family.family,
            full_model=full.name,
            reduced_model=reduced.name,
            full_universe_id=full.universe_id,
            reduced_universe_id=reduced.universe_id,
            removed_predictors=family.removed_predictors,
            rationale=family.rationale,
            status="descriptive_only",
            exact_same_observations=True,
            full_mean_r_squared=full_score,
            reduced_mean_r_squared=reduced_score,
            full_selected_alpha=full.model_result.selected_alpha,
            reduced_selected_alpha=reduced.model_result.selected_alpha,
            delta_mean_r_squared=None,
            group_deltas=(),
            group_dispersion=None,
            reason="held-out group identities or observation counts differ",
        )
    deltas = tuple(
        PredictorFamilyGroupDelta(
            group=name,
            observations=full_groups[name].observations,
            full_r_squared=full_groups[name].r_squared,
            reduced_r_squared=reduced_groups[name].r_squared,
            delta_r_squared=(
                full_groups[name].r_squared - reduced_groups[name].r_squared
            ),
        )
        for name in sorted(full_groups)
    )
    assert full_score is not None
    assert reduced_score is not None
    return PredictorFamilyContribution(
        family=family.family,
        full_model=full.name,
        reduced_model=reduced.name,
        full_universe_id=full.universe_id,
        reduced_universe_id=reduced.universe_id,
        removed_predictors=family.removed_predictors,
        rationale=family.rationale,
        status="paired_predictive_comparison",
        exact_same_observations=True,
        full_mean_r_squared=full_score,
        reduced_mean_r_squared=reduced_score,
        full_selected_alpha=full.model_result.selected_alpha,
        reduced_selected_alpha=reduced.model_result.selected_alpha,
        delta_mean_r_squared=full_score - reduced_score,
        group_deltas=deltas,
        group_dispersion=_paired_dispersion(
            deltas, nominal_level, simultaneous_comparisons
        ),
        reason=(
            "literal predictor drop with identical retained observations, tuning "
            "policy, and paired held-out groups"
        ),
    )


def _failure_reason(
    full: EncodingUniverseResult, reduced: EncodingUniverseResult
) -> str:
    failures = [
        f"{item.name}: {item.error or 'model failed without an error message'}"
        for item in (full, reduced)
        if item.status == "failed"
    ]
    return "full or reduced model failed; " + "; ".join(failures)


def _paired_dispersion(
    groups: tuple[PredictorFamilyGroupDelta, ...],
    nominal_level: float,
    simultaneous_comparisons: int,
) -> PredictorFamilyDeltaDispersion:
    values = [item.delta_r_squared for item in groups]
    count = len(values)
    if count < 2:
        raise ValueError("paired contribution dispersion requires at least two groups")
    estimate = mean(values)
    deviation = stdev(values)
    standard_error = deviation / sqrt(count)
    critical = float(student_t.ppf((1.0 + nominal_level) / 2.0, count - 1))
    margin = critical * standard_error
    return PredictorFamilyDeltaDispersion(
        method="paired_group_t_dispersion_uncalibrated",
        nominal_level=nominal_level,
        groups=count,
        mean_delta_r_squared=estimate,
        group_standard_deviation=deviation,
        dependence_naive_standard_error=standard_error,
        range_lower=estimate - margin,
        range_upper=estimate + margin,
        simultaneous_comparisons=simultaneous_comparisons,
    )


def _validate_literal_drop(
    full: EncodingModelSpec,
    reduced: EncodingModelSpec,
    family: PredictorFamilyDropSpec,
) -> None:
    if _model_policy(full) != _model_policy(reduced):
        raise ValueError(
            f"family {family.family!r} changes model or tuning policy beyond predictors"
        )
    full_predictors = _predictors(full)
    reduced_predictors = _predictors(reduced)
    changed = [
        name
        for name in full_predictors.keys() & reduced_predictors.keys()
        if full_predictors[name] != reduced_predictors[name]
    ]
    if changed:
        raise ValueError(
            f"family {family.family!r} changes shared predictor definitions: {changed}"
        )
    added = sorted(reduced_predictors.keys() - full_predictors.keys())
    if added:
        raise ValueError(
            f"family {family.family!r} reduced model adds predictors: {added}"
        )
    removed = tuple(sorted(full_predictors.keys() - reduced_predictors.keys()))
    declared = tuple(sorted(family.removed_predictors))
    if removed != declared:
        raise ValueError(
            f"family {family.family!r} declares removed predictors {declared}, "
            f"but the literal model difference is {removed}"
        )


def _predictors(spec: EncodingModelSpec) -> dict[str, tuple[str, object]]:
    result: dict[str, tuple[str, object]] = {}
    result.update((item.name, ("event", asdict(item))) for item in spec.event_kernels)
    result.update(
        (item.name, ("progress", asdict(item))) for item in spec.progress_kernels
    )
    result.update((name, ("continuous", name)) for name in spec.continuous_covariates)
    return result


def _model_policy(spec: EncodingModelSpec) -> tuple[object, ...]:
    return (
        spec.alpha_grid,
        spec.group_by,
        spec.folds,
        spec.sampling_tolerance,
        spec.minimum_session_coverage,
        spec.minimum_session_observations,
        spec.schema_version,
        spec.uncertainty,
    )
