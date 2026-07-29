"""Animal-level rate and kinetic inference for spontaneous transients."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Literal, TypeAlias

import numpy as np

from fipha.transient_product import TransientQuantificationResult

TransientMetric: TypeAlias = Literal["rate_per_minute", "amplitude", "width_s", "auc"]
TransientDesign: TypeAlias = Literal["independent", "paired"]
EffectScale: TypeAlias = Literal["difference", "ratio"]
Aggregation: TypeAlias = Literal["mean", "median"]
SessionAggregation: TypeAlias = Literal["mean", "median", "exposure_weighted"]


@dataclass(frozen=True)
class TransientStudySession:
    """Attach experimental identity to one quantified session."""

    subject: str
    session: str
    condition: str
    result: TransientQuantificationResult


@dataclass(frozen=True)
class TransientAnimalInferenceSpec:
    """Declare an animal-level contrast for event rate or kinetics.

    ``session_aggregation`` selects how sessions are combined within an animal.
    ``None`` requests the metric-appropriate default: ``exposure_weighted`` for
    ``rate_per_minute``, which pools event counts over acquired exposure, and
    ``median`` for kinetic metrics. ``exposure_weighted`` is defined only for
    ``rate_per_minute`` and is refused for kinetic metrics.
    """

    metric: TransientMetric
    condition_a: str
    condition_b: str
    channel: str
    design: TransientDesign = "independent"
    effect_scale: EffectScale = "difference"
    session_aggregation: SessionAggregation | None = None
    confidence_level: float = 0.95
    bootstrap_resamples: int = 10_000
    permutation_resamples: int = 10_000
    seed: int = 0


@dataclass(frozen=True)
class TransientAnimalEstimate:
    """One animal-condition estimate after session/event aggregation."""

    subject: str
    condition: str
    metric: TransientMetric
    value: float
    session_count: int
    event_count: int
    analyzed_duration_s: float


@dataclass(frozen=True)
class TransientAnimalInferenceResult:
    """Contrast, interval, randomization evidence, and complete animal ledger."""

    spec: TransientAnimalInferenceSpec
    estimates: tuple[TransientAnimalEstimate, ...]
    estimate: float
    interval_low: float
    interval_high: float
    permutation_pvalue: float
    animals_a: tuple[str, ...]
    animals_b: tuple[str, ...]
    excluded_subjects: tuple[str, ...]
    bootstrap_resamples: int
    permutation_resamples: int
    session_aggregation: SessionAggregation


def infer_transient_animals(
    sessions: tuple[TransientStudySession, ...] | list[TransientStudySession],
    spec: TransientAnimalInferenceSpec,
) -> TransientAnimalInferenceResult:
    """Infer a condition contrast without treating transient events as replicates."""
    _validate_spec(spec)
    if not sessions:
        raise ValueError("transient inference requires at least one session")
    _validate_sessions(sessions)
    aggregation = _resolve_session_aggregation(spec)
    estimates = _animal_estimates(sessions, spec, aggregation)
    by_condition = {
        condition: {
            estimate.subject: estimate
            for estimate in estimates
            if estimate.condition == condition
        }
        for condition in (spec.condition_a, spec.condition_b)
    }
    first = by_condition[spec.condition_a]
    second = by_condition[spec.condition_b]
    if spec.design == "paired":
        included = sorted(first.keys() & second.keys())
        excluded = sorted((first.keys() | second.keys()) - set(included))
        if len(included) < 2:
            raise ValueError(
                "paired transient inference requires at least two complete animals"
            )
        values_a = np.asarray([first[subject].value for subject in included])
        values_b = np.asarray([second[subject].value for subject in included])
        animals_a = animals_b = tuple(included)
    else:
        overlap = first.keys() & second.keys()
        if overlap:
            raise ValueError(
                "independent transient inference cannot reuse subjects "
                "across conditions; "
                "choose design='paired'"
            )
        if len(first) < 2 or len(second) < 2:
            raise ValueError(
                "independent transient inference requires at least two animals "
                "per condition"
            )
        animals_a = tuple(sorted(first))
        animals_b = tuple(sorted(second))
        excluded = []
        values_a = np.asarray([first[subject].value for subject in animals_a])
        values_b = np.asarray([second[subject].value for subject in animals_b])
    _validate_effect_values(values_a, values_b, spec.effect_scale)
    estimate = _effect(values_a, values_b, spec.design, spec.effect_scale)
    rng = np.random.default_rng(spec.seed)
    bootstrap = _bootstrap(values_a, values_b, spec, rng)
    alpha = 1 - spec.confidence_level
    interval_low, interval_high = np.quantile(bootstrap, [alpha / 2, 1 - alpha / 2])
    permutation, actual_permutations = _permutation_distribution(
        values_a, values_b, spec, rng
    )
    observed_distance = _null_distance(estimate, spec.effect_scale)
    permutation_pvalue = float(
        (
            1
            + np.count_nonzero(
                _null_distance(permutation, spec.effect_scale) >= observed_distance
            )
        )
        / (len(permutation) + 1)
    )
    return TransientAnimalInferenceResult(
        spec=spec,
        estimates=tuple(estimates),
        estimate=float(estimate),
        interval_low=float(interval_low),
        interval_high=float(interval_high),
        permutation_pvalue=permutation_pvalue,
        animals_a=animals_a,
        animals_b=animals_b,
        excluded_subjects=tuple(excluded),
        bootstrap_resamples=spec.bootstrap_resamples,
        permutation_resamples=actual_permutations,
        session_aggregation=aggregation,
    )


def _resolve_session_aggregation(
    spec: TransientAnimalInferenceSpec,
) -> SessionAggregation:
    if spec.session_aggregation is None:
        return "exposure_weighted" if spec.metric == "rate_per_minute" else "median"
    if spec.session_aggregation == "exposure_weighted" and (
        spec.metric != "rate_per_minute"
    ):
        raise ValueError(
            "session_aggregation='exposure_weighted' is defined only for "
            f"metric='rate_per_minute'; metric={spec.metric!r} summarizes sessions "
            "with 'mean' or 'median'"
        )
    return spec.session_aggregation


def _animal_estimates(
    sessions: tuple[TransientStudySession, ...] | list[TransientStudySession],
    spec: TransientAnimalInferenceSpec,
    aggregation: SessionAggregation,
) -> list[TransientAnimalEstimate]:
    grouped: dict[tuple[str, str], list[TransientStudySession]] = {}
    for session in sessions:
        if session.condition not in {spec.condition_a, spec.condition_b}:
            continue
        grouped.setdefault((session.subject, session.condition), []).append(session)
    estimates: list[TransientAnimalEstimate] = []
    for (subject, condition), subject_sessions in sorted(grouped.items()):
        evidence = [
            _session_evidence(session, spec.metric, spec.channel)
            for session in subject_sessions
        ]
        usable = [item for item in evidence if item[0] is not None]
        if not usable:
            continue
        session_values = [float(item[0]) for item in usable if item[0] is not None]
        event_count = sum(item[1] for item in usable)
        duration = sum(item[2] for item in usable)
        if aggregation == "exposure_weighted":
            value = 60 * event_count / duration if duration > 0 else float("nan")
        else:
            value = _aggregate(session_values, aggregation)
        if not np.isfinite(value):
            continue
        estimates.append(
            TransientAnimalEstimate(
                subject=subject,
                condition=condition,
                metric=spec.metric,
                value=float(value),
                session_count=len(usable),
                event_count=event_count,
                analyzed_duration_s=float(duration),
            )
        )
    return estimates


def _session_evidence(
    session: TransientStudySession,
    metric: TransientMetric,
    channel: str,
) -> tuple[float | None, int, float]:
    summaries = [
        summary for summary in session.result.summaries if summary.channel == channel
    ]
    if len(summaries) != 1:
        raise ValueError(
            f"session {session.session!r} does not contain exactly one summary "
            f"for channel {channel!r}"
        )
    summary = summaries[0]
    if metric == "rate_per_minute":
        value: float | None = summary.rate_per_minute
    else:
        events = [event for event in session.result.events if event.channel == channel]
        field = {
            "amplitude": "amplitude",
            "width_s": "full_width_half_height_s",
            "auc": "auc_above_baseline",
        }[metric]
        values = [float(getattr(event, field)) for event in events]
        finite = [item for item in values if np.isfinite(item)]
        value = float(np.median(finite)) if finite else None
    return value, summary.count, summary.analyzed_duration_s


def _bootstrap(
    values_a: np.ndarray,
    values_b: np.ndarray,
    spec: TransientAnimalInferenceSpec,
    rng: np.random.Generator,
) -> np.ndarray:
    output = np.empty(spec.bootstrap_resamples)
    for index in range(spec.bootstrap_resamples):
        if spec.design == "paired":
            selected = rng.integers(0, len(values_a), len(values_a))
            sample_a = values_a[selected]
            sample_b = values_b[selected]
        else:
            sample_a = rng.choice(values_a, len(values_a), replace=True)
            sample_b = rng.choice(values_b, len(values_b), replace=True)
        output[index] = _effect(sample_a, sample_b, spec.design, spec.effect_scale)
    return output


def _permutation_distribution(
    values_a: np.ndarray,
    values_b: np.ndarray,
    spec: TransientAnimalInferenceSpec,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    if spec.design == "paired" and 2 ** len(values_a) <= spec.permutation_resamples:
        swaps = np.asarray(list(product((False, True), repeat=len(values_a))))
        output = np.empty(len(swaps))
        for index, swap in enumerate(swaps):
            permuted_a = np.where(swap, values_b, values_a)
            permuted_b = np.where(swap, values_a, values_b)
            output[index] = _effect(
                permuted_a, permuted_b, spec.design, spec.effect_scale
            )
        return output, len(output)
    output = np.empty(spec.permutation_resamples)
    if spec.design == "paired":
        for index in range(spec.permutation_resamples):
            swap = rng.integers(0, 2, len(values_a), dtype=bool)
            permuted_a = np.where(swap, values_b, values_a)
            permuted_b = np.where(swap, values_a, values_b)
            output[index] = _effect(
                permuted_a, permuted_b, spec.design, spec.effect_scale
            )
    else:
        pooled = np.concatenate([values_a, values_b])
        for index in range(spec.permutation_resamples):
            shuffled = rng.permutation(pooled)
            output[index] = _effect(
                shuffled[: len(values_a)],
                shuffled[len(values_a) :],
                spec.design,
                spec.effect_scale,
            )
    return output, len(output)


def _effect(
    values_a: np.ndarray,
    values_b: np.ndarray,
    design: TransientDesign,
    scale: EffectScale,
) -> float:
    if scale == "difference":
        return float(
            np.mean(values_b - values_a)
            if design == "paired"
            else np.mean(values_b) - np.mean(values_a)
        )
    if design == "paired":
        return float(np.exp(np.mean(np.log(values_b / values_a))))
    return float(np.mean(values_b) / np.mean(values_a))


def _null_distance(value: float | np.ndarray, scale: EffectScale) -> float | np.ndarray:
    return np.abs(value) if scale == "difference" else np.abs(np.log(value))


def _aggregate(values: list[float], method: Aggregation) -> float:
    return float(np.mean(values) if method == "mean" else np.median(values))


def _validate_spec(spec: TransientAnimalInferenceSpec) -> None:
    if not spec.condition_a.strip() or not spec.condition_b.strip():
        raise ValueError("transient conditions must be non-empty")
    if spec.condition_a == spec.condition_b:
        raise ValueError("transient conditions must differ")
    if not spec.channel.strip():
        raise ValueError("transient inference channel must be non-empty")
    if spec.session_aggregation is not None and spec.session_aggregation not in {
        "mean",
        "median",
        "exposure_weighted",
    }:
        raise ValueError("unsupported transient session aggregation")
    if not 0 < spec.confidence_level < 1:
        raise ValueError("confidence_level must be between zero and one")
    if spec.bootstrap_resamples < 100 or spec.permutation_resamples < 100:
        raise ValueError("transient resample counts must each be at least 100")


def _validate_sessions(
    sessions: tuple[TransientStudySession, ...] | list[TransientStudySession],
) -> None:
    keys: set[tuple[str, str]] = set()
    for session in sessions:
        if not session.subject.strip() or not session.session.strip():
            raise ValueError("transient session identities must be non-empty")
        if not session.condition.strip():
            raise ValueError("transient session conditions must be non-empty")
        key = (session.subject, session.session)
        if key in keys:
            raise ValueError(f"duplicate transient session identity: {key}")
        keys.add(key)


def _validate_effect_values(
    values_a: np.ndarray, values_b: np.ndarray, scale: EffectScale
) -> None:
    if not np.all(np.isfinite(values_a)) or not np.all(np.isfinite(values_b)):
        raise ValueError("animal-level transient estimates must be finite")
    if scale == "ratio" and (np.any(values_a <= 0) or np.any(values_b <= 0)):
        raise ValueError("ratio effects require positive animal estimates")
