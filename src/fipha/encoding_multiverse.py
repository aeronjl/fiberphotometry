"""Reproducible comparison of defensible event-kernel model specifications."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal

from fipha.encoding import (
    EncodingModelResult,
    EncodingModelSpec,
    EncodingSession,
    fit_event_kernel_model,
)

EncodingUniverseStatus = Literal["success", "failed"]
EncodingComparisonStatus = Literal[
    "reference",
    "direct_predictive_comparison",
    "descriptive_only",
    "failed",
]


@dataclass(frozen=True)
class EncodingModelAlternative:
    """One named, scientifically justified event-kernel model specification."""

    name: str
    rationale: str
    model: EncodingModelSpec

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("encoding alternative name must be non-empty")
        if not self.rationale.strip():
            raise ValueError("encoding alternative rationale must be non-empty")


@dataclass(frozen=True)
class EncodingMultiverseSpec:
    """Named model alternatives sharing one predictive-validation policy."""

    alternatives: tuple[EncodingModelAlternative, ...]
    reference: str
    intent: Literal["confirmatory", "exploratory", "descriptive"]
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if len(self.alternatives) < 2:
            raise ValueError("encoding multiverse requires at least two alternatives")
        names = [item.name for item in self.alternatives]
        if len(names) != len(set(names)):
            raise ValueError("encoding alternative names must be unique")
        if self.reference not in names:
            raise ValueError("encoding multiverse reference must name an alternative")
        policies = {_validation_policy(item.model) for item in self.alternatives}
        if len(policies) != 1:
            raise ValueError(
                "encoding alternatives must share grouping, folds, sampling, and "
                "coverage and uncertainty policy"
            )
        model_payloads = [_canonical_model(item.model) for item in self.alternatives]
        if len(model_payloads) != len(set(model_payloads)):
            raise ValueError("encoding alternatives must have distinct model specs")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class MaterializedEncodingUniverse:
    """Stable pre-execution identity for one declared model alternative."""

    universe_id: str
    name: str
    rationale: str
    model: EncodingModelSpec
    is_reference: bool


@dataclass(frozen=True)
class EncodingUniverseResult:
    """One successful or failed model fit retained in the execution ledger."""

    universe_id: str
    name: str
    rationale: str
    status: EncodingUniverseStatus
    model_spec: EncodingModelSpec
    model_result: EncodingModelResult | None
    error: str | None
    is_reference: bool


@dataclass(frozen=True)
class EncodingModelComparison:
    """Predictive comparison to the reference with denominator safeguards."""

    universe_id: str
    name: str
    status: EncodingComparisonStatus
    exact_same_observations: bool | None
    reference_mean_r_squared: float | None
    alternative_mean_r_squared: float | None
    delta_mean_r_squared: float | None
    reason: str


@dataclass(frozen=True)
class EncodingMultiverseSummary:
    """Failure-aware counts and directly comparable held-out score range."""

    total_universes: int
    successful_universes: int
    failed_universes: int
    directly_comparable_universes: int
    descriptive_only_universes: int
    reference: str
    reference_mean_r_squared: float | None
    direct_comparison_r_squared_range: tuple[float, float] | None


@dataclass(frozen=True)
class EncodingMultiverseResult:
    """Complete event-kernel model ledger without automatic winner selection."""

    spec: EncodingMultiverseSpec
    universes: tuple[EncodingUniverseResult, ...]
    comparisons: tuple[EncodingModelComparison, ...]
    summary: EncodingMultiverseSummary
    artifact_type: Literal["event_kernel_encoding_multiverse"] = (
        "event_kernel_encoding_multiverse"
    )
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def materialize_encoding_multiverse(
    spec: EncodingMultiverseSpec,
) -> tuple[MaterializedEncodingUniverse, ...]:
    """Assign stable identifiers before any response values are fitted."""

    universes = tuple(
        MaterializedEncodingUniverse(
            universe_id=_universe_id(item),
            name=item.name,
            rationale=item.rationale,
            model=item.model,
            is_reference=item.name == spec.reference,
        )
        for item in spec.alternatives
    )
    identifiers = [item.universe_id for item in universes]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("encoding universe identifiers collided")
    return universes


def run_encoding_multiverse(
    sessions: Sequence[EncodingSession],
    spec: EncodingMultiverseSpec,
) -> EncodingMultiverseResult:
    """Fit every model, retain failures, and compare only common evidence."""

    if not sessions:
        raise ValueError("encoding multiverse requires at least one session")
    materialized = materialize_encoding_multiverse(spec)
    session_values = tuple(sessions)
    results = []
    for universe in materialized:
        try:
            fitted = fit_event_kernel_model(session_values, universe.model)
            results.append(
                EncodingUniverseResult(
                    universe_id=universe.universe_id,
                    name=universe.name,
                    rationale=universe.rationale,
                    status="success",
                    model_spec=universe.model,
                    model_result=fitted,
                    error=None,
                    is_reference=universe.is_reference,
                )
            )
        except Exception as error:  # retained as a declared model outcome
            results.append(
                EncodingUniverseResult(
                    universe_id=universe.universe_id,
                    name=universe.name,
                    rationale=universe.rationale,
                    status="failed",
                    model_spec=universe.model,
                    model_result=None,
                    error=f"{type(error).__name__}: {error}",
                    is_reference=universe.is_reference,
                )
            )
    result_values = tuple(results)
    comparisons = _comparisons(result_values)
    return EncodingMultiverseResult(
        spec=spec,
        universes=result_values,
        comparisons=comparisons,
        summary=_summary(result_values, comparisons, spec.reference),
    )


def _comparisons(
    universes: tuple[EncodingUniverseResult, ...],
) -> tuple[EncodingModelComparison, ...]:
    reference = next(item for item in universes if item.is_reference)
    reference_score = _score(reference.model_result)
    reference_evidence = _observation_evidence(reference.model_result)
    comparisons = []
    for universe in universes:
        score = _score(universe.model_result)
        if universe.is_reference:
            status: EncodingComparisonStatus = (
                "reference" if universe.status == "success" else "failed"
            )
            comparisons.append(
                EncodingModelComparison(
                    universe_id=universe.universe_id,
                    name=universe.name,
                    status=status,
                    exact_same_observations=True
                    if universe.status == "success"
                    else None,
                    reference_mean_r_squared=reference_score,
                    alternative_mean_r_squared=score,
                    delta_mean_r_squared=0.0 if universe.status == "success" else None,
                    reason=(
                        "declared reference model"
                        if universe.status == "success"
                        else "declared reference model failed"
                    ),
                )
            )
            continue
        if reference.status == "failed" or universe.status == "failed":
            comparisons.append(
                EncodingModelComparison(
                    universe_id=universe.universe_id,
                    name=universe.name,
                    status="failed",
                    exact_same_observations=None,
                    reference_mean_r_squared=reference_score,
                    alternative_mean_r_squared=score,
                    delta_mean_r_squared=None,
                    reason="reference or alternative model failed",
                )
            )
            continue
        exact = _observation_evidence(universe.model_result) == reference_evidence
        comparisons.append(
            EncodingModelComparison(
                universe_id=universe.universe_id,
                name=universe.name,
                status=(
                    "direct_predictive_comparison" if exact else "descriptive_only"
                ),
                exact_same_observations=exact,
                reference_mean_r_squared=reference_score,
                alternative_mean_r_squared=score,
                delta_mean_r_squared=(
                    score - reference_score
                    if exact and score is not None and reference_score is not None
                    else None
                ),
                reason=(
                    "same retained sample indices and validation policy"
                    if exact
                    else "retained sample indices differ from the reference"
                ),
            )
        )
    return tuple(comparisons)


def _summary(
    universes: tuple[EncodingUniverseResult, ...],
    comparisons: tuple[EncodingModelComparison, ...],
    reference: str,
) -> EncodingMultiverseSummary:
    direct_scores = [
        item.alternative_mean_r_squared
        for item in comparisons
        if item.status in {"reference", "direct_predictive_comparison"}
        and item.alternative_mean_r_squared is not None
    ]
    reference_comparison = next(item for item in comparisons if item.name == reference)
    return EncodingMultiverseSummary(
        total_universes=len(universes),
        successful_universes=sum(item.status == "success" for item in universes),
        failed_universes=sum(item.status == "failed" for item in universes),
        directly_comparable_universes=len(direct_scores),
        descriptive_only_universes=sum(
            item.status == "descriptive_only" for item in comparisons
        ),
        reference=reference,
        reference_mean_r_squared=reference_comparison.reference_mean_r_squared,
        direct_comparison_r_squared_range=(
            (float(min(direct_scores)), float(max(direct_scores)))
            if direct_scores
            else None
        ),
    )


def _score(result: EncodingModelResult | None) -> float | None:
    if result is None:
        return None
    selected = next(
        item for item in result.cross_validation if item.alpha == result.selected_alpha
    )
    return selected.mean_r_squared


def _observation_evidence(
    result: EncodingModelResult | None,
) -> tuple[tuple[str, str, int, str], ...] | None:
    if result is None:
        return None
    return tuple(
        sorted(
            (
                item.subject,
                item.session,
                item.total_observations,
                item.retained_index_fingerprint,
            )
            for item in result.validity.sessions
        )
    )


def _validation_policy(spec: EncodingModelSpec) -> tuple[object, ...]:
    return (
        spec.group_by,
        spec.folds,
        spec.sampling_tolerance,
        spec.minimum_session_coverage,
        spec.minimum_session_observations,
        spec.uncertainty,
    )


def _canonical_model(spec: EncodingModelSpec) -> str:
    return json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))


def _universe_id(alternative: EncodingModelAlternative) -> str:
    payload = json.dumps(
        {"name": alternative.name, "model": asdict(alternative.model)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode()).hexdigest()[:16]
