"""Animal-level inference for scalar paired-signal association summaries."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import NDArray

from fipha.cross_spectral import (
    CoherencePhaseResult,
    summarize_coherence_band,
)
from fipha.multisignal import LaggedAssociationResult

AssociationDesign: TypeAlias = Literal["paired", "independent"]
Aggregation: TypeAlias = Literal["mean", "median"]


@dataclass(frozen=True)
class AssociationSessionEstimate:
    """One session-level scalar with its support and source method."""

    subject: str
    session: str
    condition: str
    pair_id: str
    metric: str
    value: float
    support: int
    source_method: str
    within_session_pvalue: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "subject",
            "session",
            "condition",
            "pair_id",
            "metric",
            "source_method",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if not np.isfinite(self.value):
            raise ValueError("association session value must be finite")
        if self.support < 1:
            raise ValueError("association session support must be positive")
        if self.within_session_pvalue is not None and not (
            0 <= self.within_session_pvalue <= 1
        ):
            raise ValueError("within_session_pvalue must lie between zero and one")


@dataclass(frozen=True)
class AssociationAnimalInferenceSpec:
    """Declare a condition contrast without treating sites or sessions as animals."""

    metric: str
    pair_id: str
    condition_a: str
    condition_b: str
    design: AssociationDesign = "paired"
    session_aggregation: Aggregation = "mean"
    confidence_level: float = 0.95
    bootstrap_resamples: int = 10_000
    permutation_resamples: int = 10_000
    seed: int = 0

    def __post_init__(self) -> None:
        for name in ("metric", "pair_id", "condition_a", "condition_b"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.condition_a == self.condition_b:
            raise ValueError("association contrast conditions must differ")
        if self.design not in {"paired", "independent"}:
            raise ValueError("unsupported association design")
        if self.session_aggregation not in {"mean", "median"}:
            raise ValueError("unsupported session aggregation")
        if not 0 < self.confidence_level < 1:
            raise ValueError("confidence_level must lie between zero and one")
        if self.bootstrap_resamples < 100 or self.permutation_resamples < 100:
            raise ValueError("association inference requires at least 100 resamples")


@dataclass(frozen=True)
class AssociationAnimalEstimate:
    """One animal-condition value after equal-session aggregation."""

    subject: str
    condition: str
    metric: str
    value: float
    session_count: int
    total_support: int


@dataclass(frozen=True)
class AssociationAnimalInferenceResult:
    """Animal-level contrast, interval, randomization test, and complete ledger."""

    spec: AssociationAnimalInferenceSpec
    session_estimates: tuple[AssociationSessionEstimate, ...]
    animal_estimates: tuple[AssociationAnimalEstimate, ...]
    estimate: float
    interval_low: float
    interval_high: float
    permutation_pvalue: float
    animals_a: tuple[str, ...]
    animals_b: tuple[str, ...]
    excluded_subjects: tuple[str, ...]
    permutation_resamples: int
    method: str = "equal_session_animal_bootstrap_and_randomization"


def session_estimate_from_lagged(
    result: LaggedAssociationResult,
    condition: str,
    *,
    lag_s: float = 0.0,
) -> AssociationSessionEstimate:
    """Extract a declared physical lag and its actual pair-count denominator."""
    lags = np.asarray(result.lags_s, dtype=float)
    index = int(np.argmin(np.abs(lags - lag_s)))
    tolerance = result.evidence.continuity.sampling_interval_s / 2 + 1e-12
    if abs(lags[index] - lag_s) > tolerance:
        raise ValueError("requested lag is not represented by the sampling grid")
    value = result.correlation[index]
    if not np.isfinite(value):
        raise ValueError("requested lag has no finite association estimate")
    pvalue = None
    if lag_s == 0 and result.blocked_permutation is not None:
        pvalue = result.blocked_permutation.zero_lag_pvalue
    return AssociationSessionEstimate(
        result.pair.subject,
        result.pair.session,
        condition,
        result.pair.pair_id,
        f"lagged_correlation_at_{lags[index]:g}s",
        float(value),
        result.pairs_per_lag[index],
        result.method,
        pvalue,
    )


def session_estimate_from_coherence(
    result: CoherencePhaseResult,
    condition: str,
    frequency_band_hz: tuple[float, float],
) -> AssociationSessionEstimate:
    """Extract mean band coherence while retaining its window denominator."""
    summary = summarize_coherence_band(result, frequency_band_hz)
    low, high = frequency_band_hz
    return AssociationSessionEstimate(
        result.pair.subject,
        result.pair.session,
        condition,
        result.pair.pair_id,
        f"mean_coherence_{low:g}_{high:g}Hz",
        summary.mean_coherence,
        summary.total_window_count,
        result.method,
    )


def infer_association_animals(
    sessions: tuple[AssociationSessionEstimate, ...] | list[AssociationSessionEstimate],
    spec: AssociationAnimalInferenceSpec,
) -> AssociationAnimalInferenceResult:
    """Infer a condition contrast after aggregating sessions within animals."""
    selected = tuple(
        item
        for item in sessions
        if item.metric == spec.metric
        and item.pair_id == spec.pair_id
        and item.condition in {spec.condition_a, spec.condition_b}
    )
    if not selected:
        raise ValueError("no session estimates match the association inference spec")
    identities = [(item.subject, item.session, item.condition) for item in selected]
    if len(set(identities)) != len(identities):
        raise ValueError(
            "association subject-session-condition identities must be unique"
        )
    animal_estimates = _animal_estimates(selected, spec)
    by_condition = {
        condition: {
            item.subject: item
            for item in animal_estimates
            if item.condition == condition
        }
        for condition in (spec.condition_a, spec.condition_b)
    }
    first = by_condition[spec.condition_a]
    second = by_condition[spec.condition_b]
    if spec.design == "paired":
        included = tuple(sorted(first.keys() & second.keys()))
        excluded = tuple(sorted((first.keys() | second.keys()) - set(included)))
        if len(included) < 2:
            raise ValueError(
                "paired association inference requires two complete animals"
            )
        values_a = np.asarray([first[subject].value for subject in included])
        values_b = np.asarray([second[subject].value for subject in included])
        animals_a = animals_b = included
    else:
        overlap = first.keys() & second.keys()
        if overlap:
            raise ValueError(
                "independent association inference cannot reuse subjects across "
                "conditions"
            )
        if len(first) < 2 or len(second) < 2:
            raise ValueError(
                "independent association inference requires two animals per condition"
            )
        animals_a = tuple(sorted(first))
        animals_b = tuple(sorted(second))
        excluded = ()
        values_a = np.asarray([first[subject].value for subject in animals_a])
        values_b = np.asarray([second[subject].value for subject in animals_b])
    estimate = float(np.mean(values_a) - np.mean(values_b))
    rng = np.random.default_rng(spec.seed)
    bootstrap = _bootstrap(values_a, values_b, spec, rng)
    alpha = 1 - spec.confidence_level
    interval_low, interval_high = np.quantile(bootstrap, [alpha / 2, 1 - alpha / 2])
    null, actual = _permutation(values_a, values_b, spec, rng)
    pvalue = float(
        (1 + np.count_nonzero(np.abs(null) >= abs(estimate))) / (len(null) + 1)
    )
    return AssociationAnimalInferenceResult(
        spec,
        selected,
        tuple(animal_estimates),
        estimate,
        float(interval_low),
        float(interval_high),
        pvalue,
        animals_a,
        animals_b,
        excluded,
        actual,
    )


def _animal_estimates(
    sessions: tuple[AssociationSessionEstimate, ...],
    spec: AssociationAnimalInferenceSpec,
) -> list[AssociationAnimalEstimate]:
    grouped: dict[tuple[str, str], list[AssociationSessionEstimate]] = {}
    for item in sessions:
        grouped.setdefault((item.subject, item.condition), []).append(item)
    output = []
    for (subject, condition), items in sorted(grouped.items()):
        values = np.asarray([item.value for item in items])
        value = (
            float(np.mean(values))
            if spec.session_aggregation == "mean"
            else float(np.median(values))
        )
        output.append(
            AssociationAnimalEstimate(
                subject,
                condition,
                spec.metric,
                value,
                len(items),
                sum(item.support for item in items),
            )
        )
    return output


def _bootstrap(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    spec: AssociationAnimalInferenceSpec,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    if spec.design == "paired":
        differences = first - second
        indices = rng.integers(
            0, len(differences), (spec.bootstrap_resamples, len(differences))
        )
        return np.asarray(np.mean(differences[indices], axis=1), dtype=float)
    first_indices = rng.integers(0, len(first), (spec.bootstrap_resamples, len(first)))
    second_indices = rng.integers(
        0, len(second), (spec.bootstrap_resamples, len(second))
    )
    return np.asarray(
        np.mean(first[first_indices], axis=1) - np.mean(second[second_indices], axis=1),
        dtype=float,
    )


def _permutation(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    spec: AssociationAnimalInferenceSpec,
    rng: np.random.Generator,
) -> tuple[NDArray[np.float64], int]:
    if spec.design == "paired":
        differences = first - second
        if (
            len(differences) <= 16
            and 2 ** len(differences) <= spec.permutation_resamples
        ):
            signs = np.asarray(list(product((-1.0, 1.0), repeat=len(differences))))
        else:
            signs = rng.choice(
                np.asarray([-1.0, 1.0]),
                size=(spec.permutation_resamples, len(differences)),
            )
        return np.mean(signs * differences, axis=1), len(signs)
    combined = np.concatenate((first, second))
    possible = _combination_count(len(combined), len(first))
    if possible <= spec.permutation_resamples:
        selections = combinations(range(len(combined)), len(first))
        exact_values: list[float] = []
        all_indices = set(range(len(combined)))
        for selection in selections:
            selected = np.asarray(selection)
            remaining = np.asarray(sorted(all_indices - set(selection)))
            exact_values.append(
                float(np.mean(combined[selected]) - np.mean(combined[remaining]))
            )
        return np.asarray(exact_values), len(exact_values)
    sampled_values = np.empty(spec.permutation_resamples)
    for draw in range(spec.permutation_resamples):
        shuffled = rng.permutation(combined)
        sampled_values[draw] = np.mean(shuffled[: len(first)]) - np.mean(
            shuffled[len(first) :]
        )
    return sampled_values, len(sampled_values)


def _combination_count(total: int, selected: int) -> int:
    numerator = denominator = 1
    for index in range(1, selected + 1):
        numerator *= total - selected + index
        denominator *= index
    return numerator // denominator
