"""Gap-aware multiscale summaries and animal-level contrasts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import pairwise, product
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray

from fiberphotometry.spectral import StateEpoch

MultiscaleMetric: TypeAlias = Literal[
    "sample_mean",
    "sample_median",
    "sample_standard_deviation",
    "sample_iqr",
    "sample_rms",
    "sample_linear_slope",
    "time_weighted_mean",
    "time_weighted_standard_deviation",
    "time_weighted_rms",
]
Aggregation: TypeAlias = Literal["mean", "median"]
Design: TypeAlias = Literal["independent", "paired"]
EffectScale: TypeAlias = Literal["difference", "ratio"]

_METRICS: frozenset[str] = frozenset(
    {
        "sample_mean",
        "sample_median",
        "sample_standard_deviation",
        "sample_iqr",
        "sample_rms",
        "sample_linear_slope",
        "time_weighted_mean",
        "time_weighted_standard_deviation",
        "time_weighted_rms",
    }
)


@dataclass(frozen=True)
class MultiscaleContinuitySpec:
    """Declare when adjacent observations cease to be continuous evidence."""

    gap_factor: float = 3.0
    maximum_gap_s: float | None = None

    def __post_init__(self) -> None:
        if self.gap_factor <= 1:
            raise ValueError("gap_factor must be greater than one")
        if self.maximum_gap_s is not None and self.maximum_gap_s <= 0:
            raise ValueError("maximum_gap_s must be positive")


@dataclass(frozen=True)
class MultiscaleWindowSpec:
    """One named physical-time window and its acceptance denominator."""

    name: str
    duration_s: float
    step_s: float | None = None
    minimum_coverage: float = 0.95
    minimum_samples: int = 3

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("multiscale window name must be non-empty")
        if self.duration_s <= 0:
            raise ValueError("multiscale window duration_s must be positive")
        if self.step_s is not None and self.step_s <= 0:
            raise ValueError("multiscale window step_s must be positive")
        if not 0 < self.minimum_coverage <= 1:
            raise ValueError("minimum_coverage must lie in (0, 1]")
        if self.minimum_samples < 2:
            raise ValueError("minimum_samples must be at least two")

    @property
    def resolved_step_s(self) -> float:
        """Return the explicit step, or a non-overlapping duration-sized step."""
        return self.duration_s if self.step_s is None else self.step_s


@dataclass(frozen=True)
class MultiscaleSummarySpec:
    """Declare scales, observable metrics, and continuity policy."""

    windows: tuple[MultiscaleWindowSpec, ...]
    metrics: tuple[MultiscaleMetric, ...] = (
        "time_weighted_mean",
        "time_weighted_standard_deviation",
        "sample_median",
        "sample_iqr",
        "sample_linear_slope",
    )
    continuity: MultiscaleContinuitySpec = MultiscaleContinuitySpec()

    def __post_init__(self) -> None:
        if not self.windows:
            raise ValueError("multiscale summary requires at least one window")
        names = [window.name for window in self.windows]
        if len(set(names)) != len(names):
            raise ValueError("multiscale window names must be unique")
        if not self.metrics:
            raise ValueError("multiscale summary requires at least one metric")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("multiscale metrics must be unique")
        unsupported = set(self.metrics) - _METRICS
        if unsupported:
            raise ValueError(f"unsupported multiscale metrics: {sorted(unsupported)}")


@dataclass(frozen=True)
class MultiscaleContinuityRun:
    """One valid run bounded by missingness, a gap, or a state epoch."""

    run_id: int
    state: str | None
    epoch_id: str | None
    start_s: float
    stop_s: float
    sample_count: int
    observed_duration_s: float
    median_interval_s: float
    interval_cv: float


@dataclass(frozen=True)
class MultiscaleRunExclusion:
    """A valid segment that cannot support physical-time integration."""

    state: str | None
    epoch_id: str | None
    start_s: float
    stop_s: float
    sample_count: int
    reason: str


@dataclass(frozen=True)
class MultiscaleWindowRecord:
    """Acceptance ledger for one candidate physical-time window."""

    window_id: str
    scale: str
    run_id: int
    state: str | None
    epoch_id: str | None
    start_s: float
    stop_s: float
    center_s: float
    sample_count: int
    observed_duration_s: float
    coverage_fraction: float
    accepted: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class MultiscaleEstimate:
    """One observable metric tied to an accepted source window."""

    window_id: str
    scale: str
    run_id: int
    state: str | None
    epoch_id: str | None
    metric: MultiscaleMetric
    value: float
    unit: str


@dataclass(frozen=True)
class MultiscaleSummaryResult:
    """Multiscale estimates plus complete continuity and window evidence."""

    spec: MultiscaleSummarySpec
    runs: tuple[MultiscaleContinuityRun, ...]
    run_exclusions: tuple[MultiscaleRunExclusion, ...]
    windows: tuple[MultiscaleWindowRecord, ...]
    estimates: tuple[MultiscaleEstimate, ...]
    value_unit: str
    valid_sample_count: int
    invalid_sample_count: int
    gap_count: int
    state_epoch_count: int
    unassigned_valid_sample_count: int
    evidence_fingerprint: str
    method: str = "gap_and_epoch_bounded_physical_time_multiscale_summary"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize estimates and every acceptance denominator."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class MultiscaleStudySession:
    """Attach subject, session, and experimental condition identity."""

    subject: str
    session: str
    condition: str
    result: MultiscaleSummaryResult


@dataclass(frozen=True)
class MultiscaleAnimalInferenceSpec:
    """Declare a session-to-animal contrast for one scale and metric."""

    scale: str
    metric: MultiscaleMetric
    condition_a: str
    condition_b: str
    state: str | None = None
    design: Design = "independent"
    effect_scale: EffectScale = "difference"
    window_aggregation: Aggregation = "median"
    session_aggregation: Aggregation = "median"
    confidence_level: float = 0.95
    bootstrap_resamples: int = 10_000
    permutation_resamples: int = 10_000
    seed: int = 0

    def __post_init__(self) -> None:
        if not self.scale.strip():
            raise ValueError("multiscale inference scale must be non-empty")
        if self.metric not in _METRICS:
            raise ValueError("unsupported multiscale inference metric")
        if not self.condition_a.strip() or not self.condition_b.strip():
            raise ValueError("multiscale inference conditions must be non-empty")
        if self.condition_a == self.condition_b:
            raise ValueError("multiscale inference conditions must differ")
        if self.state is not None and not self.state.strip():
            raise ValueError("multiscale inference state must be non-empty or None")
        if self.design not in {"independent", "paired"}:
            raise ValueError("unsupported multiscale inference design")
        if self.effect_scale not in {"difference", "ratio"}:
            raise ValueError("unsupported multiscale effect scale")
        if self.window_aggregation not in {"mean", "median"}:
            raise ValueError("unsupported window aggregation")
        if self.session_aggregation not in {"mean", "median"}:
            raise ValueError("unsupported session aggregation")
        if not 0 < self.confidence_level < 1:
            raise ValueError("confidence_level must lie between zero and one")
        if self.bootstrap_resamples < 100 or self.permutation_resamples < 100:
            raise ValueError("multiscale inference requires at least 100 resamples")


@dataclass(frozen=True)
class MultiscaleAnimalEstimate:
    """One animal-condition estimate after window and session aggregation."""

    subject: str
    condition: str
    scale: str
    state: str | None
    metric: MultiscaleMetric
    value: float
    session_count: int
    window_count: int
    summed_window_observed_duration_s: float


@dataclass(frozen=True)
class MultiscaleAnimalInferenceResult:
    """Animal-level effect, interval, randomization test, and ledger."""

    spec: MultiscaleAnimalInferenceSpec
    estimates: tuple[MultiscaleAnimalEstimate, ...]
    estimate: float
    interval_low: float
    interval_high: float
    permutation_pvalue: float
    animals_a: tuple[str, ...]
    animals_b: tuple[str, ...]
    excluded_subjects: tuple[str, ...]
    bootstrap_resamples: int
    permutation_resamples: int
    effect_direction: str = "condition_b relative to condition_a"
    method: str = "equal_session_animal_bootstrap_and_randomization"


@dataclass(frozen=True)
class _Run:
    evidence: MultiscaleContinuityRun
    indices: NDArray[np.int64]


def summarize_multiscale(
    time: ArrayLike,
    values: ArrayLike,
    spec: MultiscaleSummarySpec,
    *,
    valid: ArrayLike | None = None,
    epochs: tuple[StateEpoch, ...] | list[StateEpoch] | None = None,
    value_unit: str = "a.u.",
) -> MultiscaleSummaryResult:
    """Summarize explicit physical-time scales without bridging gaps or epochs."""
    time_values, signal_values, sample_valid = _validate_signal(time, values, valid)
    partition, labels, assigned = _state_partition(time_values, epochs)
    analyzed_valid = sample_valid & assigned
    runs, run_exclusions, gap_count = _continuity_runs(
        time_values, analyzed_valid, partition, labels, spec.continuity
    )
    records: list[MultiscaleWindowRecord] = []
    estimates: list[MultiscaleEstimate] = []
    for run in runs:
        run_time = time_values[run.indices]
        run_values = signal_values[run.indices]
        for window_spec in spec.windows:
            _summarize_run_scale(
                run,
                run_time,
                run_values,
                window_spec,
                spec.metrics,
                value_unit,
                records,
                estimates,
            )
    if not records:
        raise ValueError(
            "no valid continuity run contains a multiscale candidate window"
        )
    fingerprint = _fingerprint(
        time_values, signal_values, sample_valid, spec, epochs, value_unit
    )
    return MultiscaleSummaryResult(
        spec=spec,
        runs=tuple(run.evidence for run in runs),
        run_exclusions=tuple(run_exclusions),
        windows=tuple(records),
        estimates=tuple(estimates),
        value_unit=value_unit,
        valid_sample_count=int(np.count_nonzero(sample_valid)),
        invalid_sample_count=int(len(sample_valid) - np.count_nonzero(sample_valid)),
        gap_count=gap_count,
        state_epoch_count=0 if epochs is None else len(epochs),
        unassigned_valid_sample_count=int(np.count_nonzero(sample_valid & ~assigned)),
        evidence_fingerprint=fingerprint,
    )


def infer_multiscale_animals(
    sessions: tuple[MultiscaleStudySession, ...] | list[MultiscaleStudySession],
    spec: MultiscaleAnimalInferenceSpec,
) -> MultiscaleAnimalInferenceResult:
    """Contrast conditions without treating windows or sessions as animals."""
    if not sessions:
        raise ValueError("multiscale inference requires at least one session")
    _validate_sessions(sessions)
    estimates = _animal_estimates(sessions, spec)
    first = {
        item.subject: item for item in estimates if item.condition == spec.condition_a
    }
    second = {
        item.subject: item for item in estimates if item.condition == spec.condition_b
    }
    all_subjects = {session.subject for session in sessions}
    if spec.design == "paired":
        included = sorted(first.keys() & second.keys())
        if len(included) < 2:
            raise ValueError(
                "paired multiscale inference requires two complete animals"
            )
        animals_a = animals_b = tuple(included)
        values_a = np.asarray([first[subject].value for subject in included])
        values_b = np.asarray([second[subject].value for subject in included])
        excluded = sorted(all_subjects - set(included))
    else:
        overlap = first.keys() & second.keys()
        if overlap:
            raise ValueError(
                "independent multiscale inference cannot reuse subjects "
                "across conditions"
            )
        if len(first) < 2 or len(second) < 2:
            raise ValueError(
                "independent multiscale inference requires two animals per condition"
            )
        animals_a = tuple(sorted(first))
        animals_b = tuple(sorted(second))
        values_a = np.asarray([first[subject].value for subject in animals_a])
        values_b = np.asarray([second[subject].value for subject in animals_b])
        excluded = sorted(all_subjects - set(animals_a) - set(animals_b))
    if spec.effect_scale == "ratio" and (
        np.any(values_a <= 0) or np.any(values_b <= 0)
    ):
        raise ValueError("ratio effects require positive animal estimates")
    observed = _effect(values_a, values_b, spec.design, spec.effect_scale)
    rng = np.random.default_rng(spec.seed)
    bootstrap = _bootstrap(values_a, values_b, spec, rng)
    alpha = 1 - spec.confidence_level
    low, high = np.quantile(bootstrap, [alpha / 2, 1 - alpha / 2])
    null, actual = _randomization(values_a, values_b, spec, rng)
    distance = _null_distance(observed, spec.effect_scale)
    pvalue = float(
        (1 + np.count_nonzero(_null_distance(null, spec.effect_scale) >= distance))
        / (len(null) + 1)
    )
    return MultiscaleAnimalInferenceResult(
        spec=spec,
        estimates=tuple(estimates),
        estimate=float(observed),
        interval_low=float(low),
        interval_high=float(high),
        permutation_pvalue=pvalue,
        animals_a=animals_a,
        animals_b=animals_b,
        excluded_subjects=tuple(excluded),
        bootstrap_resamples=spec.bootstrap_resamples,
        permutation_resamples=actual,
    )


def _validate_signal(
    time: ArrayLike, values: ArrayLike, valid: ArrayLike | None
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    time_values = np.asarray(time, dtype=float)
    signal_values = np.asarray(values, dtype=float)
    if time_values.ndim != 1 or signal_values.ndim != 1:
        raise ValueError("time and values must be one-dimensional")
    if len(time_values) != len(signal_values) or len(time_values) < 3:
        raise ValueError("time and values must contain the same three or more samples")
    if not np.all(np.isfinite(time_values)) or not np.all(np.diff(time_values) > 0):
        raise ValueError("time must be finite and strictly increasing")
    if valid is None:
        sample_valid = np.ones(len(time_values), dtype=bool)
    else:
        sample_valid = np.asarray(valid, dtype=bool)
        if sample_valid.shape != time_values.shape:
            raise ValueError("valid must match signal samples")
    sample_valid &= np.isfinite(signal_values)
    return time_values, signal_values, sample_valid


def _state_partition(
    time: NDArray[np.float64],
    epochs: tuple[StateEpoch, ...] | list[StateEpoch] | None,
) -> tuple[
    NDArray[np.int64],
    dict[int, tuple[str | None, str | None]],
    NDArray[np.bool_],
]:
    if epochs is None:
        return (
            np.zeros(len(time), dtype=np.int64),
            {0: (None, None)},
            np.ones(len(time), dtype=bool),
        )
    if not epochs:
        raise ValueError("state-conditioned multiscale analysis requires epochs")
    ordered = sorted(epochs, key=lambda item: (item.start_s, item.stop_s, item.state))
    for first, second in pairwise(ordered):
        if second.start_s < first.stop_s:
            raise ValueError("state epochs overlap; overlap_policy='error'")
    partition = np.full(len(time), -1, dtype=np.int64)
    labels: dict[int, tuple[str | None, str | None]] = {}
    for index, epoch in enumerate(epochs):
        selected = (time >= epoch.start_s) & (time < epoch.stop_s)
        partition[selected] = index
        labels[index] = (epoch.state, epoch.epoch_id or f"epoch-{index}")
    return partition, labels, partition >= 0


def _continuity_runs(
    time: NDArray[np.float64],
    valid: NDArray[np.bool_],
    partition: NDArray[np.int64],
    labels: dict[int, tuple[str | None, str | None]],
    spec: MultiscaleContinuitySpec,
) -> tuple[list[_Run], list[MultiscaleRunExclusion], int]:
    differences = np.diff(time)
    nominal = float(np.median(differences))
    threshold = spec.maximum_gap_s or spec.gap_factor * nominal
    gap_break = differences > threshold
    output: list[_Run] = []
    exclusions: list[MultiscaleRunExclusion] = []
    start: int | None = None
    for index in range(len(time)):
        begins = valid[index] and (
            index == 0
            or not valid[index - 1]
            or gap_break[index - 1]
            or partition[index] != partition[index - 1]
        )
        if begins:
            start = index
        ends = start is not None and (
            index == len(time) - 1
            or not valid[index + 1]
            or gap_break[index]
            or partition[index] != partition[index + 1]
        )
        if ends:
            indices = np.arange(start, index + 1, dtype=np.int64)
            if len(indices) >= 2:
                intervals = np.diff(time[indices])
                state, epoch_id = labels[int(partition[indices[0]])]
                evidence = MultiscaleContinuityRun(
                    run_id=len(output),
                    state=state,
                    epoch_id=epoch_id,
                    start_s=float(time[indices[0]]),
                    stop_s=float(time[indices[-1]]),
                    sample_count=len(indices),
                    observed_duration_s=float(time[indices[-1]] - time[indices[0]]),
                    median_interval_s=float(np.median(intervals)),
                    interval_cv=float(np.std(intervals) / np.mean(intervals)),
                )
                output.append(_Run(evidence, indices))
            else:
                state, epoch_id = labels[int(partition[indices[0]])]
                exclusions.append(
                    MultiscaleRunExclusion(
                        state=state,
                        epoch_id=epoch_id,
                        start_s=float(time[indices[0]]),
                        stop_s=float(time[indices[-1]]),
                        sample_count=len(indices),
                        reason="fewer_than_two_samples",
                    )
                )
            start = None
    return output, exclusions, int(np.count_nonzero(gap_break))


def _summarize_run_scale(
    run: _Run,
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    spec: MultiscaleWindowSpec,
    metrics: tuple[MultiscaleMetric, ...],
    value_unit: str,
    records: list[MultiscaleWindowRecord],
    estimates: list[MultiscaleEstimate],
) -> None:
    run_start = float(time[0])
    run_stop = float(time[-1])
    starts = np.arange(run_start, run_stop, spec.resolved_step_s)
    for ordinal, start in enumerate(starts):
        stop = float(start + spec.duration_s)
        observed_start = max(float(start), run_start)
        observed_stop = min(stop, run_stop)
        observed_duration = max(0.0, observed_stop - observed_start)
        selected = (time >= start) & (time < stop)
        sample_count = int(np.count_nonzero(selected))
        coverage = observed_duration / spec.duration_s
        reasons = []
        if coverage + 1e-12 < spec.minimum_coverage:
            reasons.append("below_minimum_coverage")
        if sample_count < spec.minimum_samples:
            reasons.append("fewer_than_minimum_samples")
        accepted = not reasons
        window_id = f"{spec.name}:run-{run.evidence.run_id}:window-{ordinal}"
        records.append(
            MultiscaleWindowRecord(
                window_id=window_id,
                scale=spec.name,
                run_id=run.evidence.run_id,
                state=run.evidence.state,
                epoch_id=run.evidence.epoch_id,
                start_s=float(start),
                stop_s=stop,
                center_s=float(start + spec.duration_s / 2),
                sample_count=sample_count,
                observed_duration_s=float(observed_duration),
                coverage_fraction=float(min(1.0, coverage)),
                accepted=accepted,
                exclusion_reason=";".join(reasons) or None,
            )
        )
        if not accepted:
            continue
        sample_values = values[selected]
        integration_time, integration_values = _integration_series(
            time, values, observed_start, observed_stop
        )
        for metric in metrics:
            estimates.append(
                MultiscaleEstimate(
                    window_id=window_id,
                    scale=spec.name,
                    run_id=run.evidence.run_id,
                    state=run.evidence.state,
                    epoch_id=run.evidence.epoch_id,
                    metric=metric,
                    value=_metric_value(
                        metric,
                        time[selected],
                        sample_values,
                        integration_time,
                        integration_values,
                    ),
                    unit=_metric_unit(metric, value_unit),
                )
            )


def _integration_series(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    start: float,
    stop: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    interior = (time > start) & (time < stop)
    x = np.concatenate(([start], time[interior], [stop]))
    x = np.unique(x)
    return x, np.interp(x, time, values)


def _metric_value(
    metric: MultiscaleMetric,
    sample_time: NDArray[np.float64],
    sample_values: NDArray[np.float64],
    integration_time: NDArray[np.float64],
    integration_values: NDArray[np.float64],
) -> float:
    if metric == "sample_mean":
        return float(np.mean(sample_values))
    if metric == "sample_median":
        return float(np.median(sample_values))
    if metric == "sample_standard_deviation":
        return float(np.std(sample_values, ddof=1))
    if metric == "sample_iqr":
        return float(np.subtract(*np.percentile(sample_values, [75, 25])))
    if metric == "sample_rms":
        return float(np.sqrt(np.mean(np.square(sample_values))))
    if metric == "sample_linear_slope":
        centered = sample_time - np.mean(sample_time)
        denominator = float(np.dot(centered, centered))
        return float(np.dot(centered, sample_values) / denominator)
    duration = float(integration_time[-1] - integration_time[0])
    mean = float(np.trapezoid(integration_values, integration_time) / duration)
    if metric == "time_weighted_mean":
        return mean
    if metric == "time_weighted_standard_deviation":
        variance = (
            np.trapezoid(np.square(integration_values - mean), integration_time)
            / duration
        )
        return float(np.sqrt(max(0.0, variance)))
    if metric == "time_weighted_rms":
        square_mean = (
            np.trapezoid(np.square(integration_values), integration_time) / duration
        )
        return float(np.sqrt(max(0.0, square_mean)))
    raise AssertionError(f"unhandled metric {metric}")


def _metric_unit(metric: MultiscaleMetric, value_unit: str) -> str:
    return f"{value_unit}/s" if metric == "sample_linear_slope" else value_unit


def _fingerprint(
    time: NDArray[np.float64],
    values: NDArray[np.float64],
    valid: NDArray[np.bool_],
    spec: MultiscaleSummarySpec,
    epochs: tuple[StateEpoch, ...] | list[StateEpoch] | None,
    value_unit: str,
) -> str:
    digest = hashlib.sha256()
    for array in (time.astype("<f8"), values.astype("<f8"), valid.astype("u1")):
        digest.update(array.tobytes())
    metadata = {
        "spec": asdict(spec),
        "epochs": [] if epochs is None else [asdict(epoch) for epoch in epochs],
        "value_unit": value_unit,
    }
    digest.update(json.dumps(metadata, sort_keys=True).encode())
    return f"sha256:{digest.hexdigest()}"


def _validate_sessions(
    sessions: tuple[MultiscaleStudySession, ...] | list[MultiscaleStudySession],
) -> None:
    identities: set[tuple[str, str]] = set()
    for session in sessions:
        if not session.subject.strip() or not session.session.strip():
            raise ValueError("multiscale session identities must be non-empty")
        if not session.condition.strip():
            raise ValueError("multiscale session condition must be non-empty")
        identity = (session.subject, session.session)
        if identity in identities:
            raise ValueError(f"duplicate multiscale session identity: {identity}")
        identities.add(identity)


def _animal_estimates(
    sessions: tuple[MultiscaleStudySession, ...] | list[MultiscaleStudySession],
    spec: MultiscaleAnimalInferenceSpec,
) -> list[MultiscaleAnimalEstimate]:
    grouped: dict[tuple[str, str], list[tuple[float, int, float]]] = {}
    for session in sessions:
        if session.condition not in {spec.condition_a, spec.condition_b}:
            continue
        matching = [
            item
            for item in session.result.estimates
            if item.scale == spec.scale
            and item.metric == spec.metric
            and item.state == spec.state
        ]
        if not matching:
            continue
        window_lookup = {item.window_id: item for item in session.result.windows}
        value = _aggregate([item.value for item in matching], spec.window_aggregation)
        duration = sum(
            window_lookup[item.window_id].observed_duration_s for item in matching
        )
        grouped.setdefault((session.subject, session.condition), []).append(
            (value, len(matching), duration)
        )
    output = []
    for (subject, condition), session_rows in sorted(grouped.items()):
        output.append(
            MultiscaleAnimalEstimate(
                subject=subject,
                condition=condition,
                scale=spec.scale,
                state=spec.state,
                metric=spec.metric,
                value=_aggregate(
                    [row[0] for row in session_rows], spec.session_aggregation
                ),
                session_count=len(session_rows),
                window_count=sum(row[1] for row in session_rows),
                summed_window_observed_duration_s=float(
                    sum(row[2] for row in session_rows)
                ),
            )
        )
    return output


def _aggregate(values: list[float], method: Aggregation) -> float:
    return float(np.mean(values) if method == "mean" else np.median(values))


def _effect(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    design: Design,
    scale: EffectScale,
) -> float:
    if scale == "difference":
        return float(
            np.mean(second - first)
            if design == "paired"
            else np.mean(second) - np.mean(first)
        )
    if design == "paired":
        return float(np.exp(np.mean(np.log(second / first))))
    return float(np.mean(second) / np.mean(first))


def _bootstrap(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    spec: MultiscaleAnimalInferenceSpec,
    rng: np.random.Generator,
) -> NDArray[np.float64]:
    output = np.empty(spec.bootstrap_resamples)
    for index in range(spec.bootstrap_resamples):
        if spec.design == "paired":
            selected = rng.integers(0, len(first), len(first))
            sample_a, sample_b = first[selected], second[selected]
        else:
            sample_a = rng.choice(first, len(first), replace=True)
            sample_b = rng.choice(second, len(second), replace=True)
        output[index] = _effect(sample_a, sample_b, spec.design, spec.effect_scale)
    return output


def _randomization(
    first: NDArray[np.float64],
    second: NDArray[np.float64],
    spec: MultiscaleAnimalInferenceSpec,
    rng: np.random.Generator,
) -> tuple[NDArray[np.float64], int]:
    if spec.design == "paired" and 2 ** len(first) <= spec.permutation_resamples:
        swaps = np.asarray(list(product((False, True), repeat=len(first))))
        output = np.empty(len(swaps))
        for index, swap in enumerate(swaps):
            output[index] = _effect(
                np.where(swap, second, first),
                np.where(swap, first, second),
                spec.design,
                spec.effect_scale,
            )
        return output, len(output)
    output = np.empty(spec.permutation_resamples)
    if spec.design == "paired":
        for index in range(spec.permutation_resamples):
            swap = rng.integers(0, 2, len(first), dtype=bool)
            output[index] = _effect(
                np.where(swap, second, first),
                np.where(swap, first, second),
                spec.design,
                spec.effect_scale,
            )
    else:
        pooled = np.concatenate((first, second))
        for index in range(spec.permutation_resamples):
            shuffled = rng.permutation(pooled)
            output[index] = _effect(
                shuffled[: len(first)],
                shuffled[len(first) :],
                spec.design,
                spec.effect_scale,
            )
    return output, len(output)


def _null_distance(
    value: float | NDArray[np.float64], scale: EffectScale
) -> float | NDArray[np.float64]:
    return np.abs(value) if scale == "difference" else np.abs(np.log(value))
