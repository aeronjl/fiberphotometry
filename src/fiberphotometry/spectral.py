"""Gap-aware single-signal time, frequency, and state workflows."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from itertools import pairwise, product
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import signal

Detrend: TypeAlias = Literal["none", "constant", "linear"]
EffectScale: TypeAlias = Literal["difference", "ratio"]


@dataclass(frozen=True)
class GapHandlingSpec:
    """Declare how missing samples, acquisition gaps, and clock jitter are handled."""

    gap_factor: float = 1.5
    maximum_interval_cv: float = 0.01
    minimum_run_samples: int = 2

    def __post_init__(self) -> None:
        if self.gap_factor <= 1:
            raise ValueError("gap_factor must be greater than one")
        if self.maximum_interval_cv < 0:
            raise ValueError("maximum_interval_cv cannot be negative")
        if self.minimum_run_samples < 2:
            raise ValueError("minimum_run_samples must be at least two")


@dataclass(frozen=True)
class SpectralAnalysisSpec:
    """Explicit window, overlap, detrending, and continuity choices."""

    window_duration_s: float = 10.0
    overlap_fraction: float = 0.5
    window: str = "hann"
    detrend: Detrend = "constant"
    maximum_frequency_hz: float | None = None
    gap: GapHandlingSpec = GapHandlingSpec()

    def __post_init__(self) -> None:
        if self.window_duration_s <= 0:
            raise ValueError("window_duration_s must be positive")
        if not 0 <= self.overlap_fraction < 1:
            raise ValueError("overlap_fraction must lie in [0, 1)")
        if not self.window:
            raise ValueError("window must be non-empty")
        if self.detrend not in {"none", "constant", "linear"}:
            raise ValueError("unsupported detrend policy")
        if self.maximum_frequency_hz is not None and self.maximum_frequency_hz <= 0:
            raise ValueError("maximum_frequency_hz must be positive")


@dataclass(frozen=True)
class AutocorrelationSpec:
    """Explicit lag, detrending, and continuity choices."""

    maximum_lag_s: float = 10.0
    detrend: Detrend = "constant"
    gap: GapHandlingSpec = GapHandlingSpec()

    def __post_init__(self) -> None:
        if self.maximum_lag_s <= 0:
            raise ValueError("maximum_lag_s must be positive")
        if self.detrend not in {"none", "constant", "linear"}:
            raise ValueError("unsupported detrend policy")


@dataclass(frozen=True)
class StateEpoch:
    """One user-supplied, half-open state interval in signal-clock seconds."""

    state: str
    start_s: float
    stop_s: float
    epoch_id: str = ""

    def __post_init__(self) -> None:
        if not self.state:
            raise ValueError("state must be non-empty")
        if not np.isfinite(self.start_s) or not np.isfinite(self.stop_s):
            raise ValueError("state epoch bounds must be finite")
        if self.start_s >= self.stop_s:
            raise ValueError("state epoch start must be earlier than stop")


@dataclass(frozen=True)
class ContinuityRun:
    """Evidence for one uninterrupted, regular run used by an analysis."""

    run_id: int
    partition_id: int
    start_s: float
    stop_s: float
    sample_count: int
    exposure_s: float
    interval_cv: float


@dataclass(frozen=True)
class RunExclusion:
    """An uninterrupted run excluded before analysis."""

    start_s: float
    stop_s: float
    sample_count: int
    reason: str


@dataclass(frozen=True)
class ContinuityEvidence:
    """Sampling and missing-data evidence shared by spectral results."""

    sampling_interval_s: float
    sampling_rate_hz: float
    valid_sample_count: int
    invalid_sample_count: int
    gap_count: int
    analyzed_exposure_s: float
    runs: tuple[ContinuityRun, ...]
    exclusions: tuple[RunExclusion, ...]


@dataclass(frozen=True)
class AutocorrelationResult:
    """Energy-normalized autocorrelation that never pairs samples across gaps."""

    spec: AutocorrelationSpec
    lags_s: tuple[float, ...]
    correlation: tuple[float, ...]
    pairs_per_lag: tuple[int, ...]
    evidence: ContinuityEvidence
    method: str = "gap_separated_energy_normalized_autocorrelation"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize values and continuity evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class WelchPSDResult:
    """Welch PSD averaged across within-run windows only."""

    spec: SpectralAnalysisSpec
    frequencies_hz: tuple[float, ...]
    power_density: tuple[float, ...]
    windows_per_run: tuple[int, ...]
    total_window_count: int
    value_unit: str
    power_density_unit: str
    evidence: ContinuityEvidence
    method: str = "window_weighted_gap_separated_welch"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize the spectrum, declared choices, and continuity evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class SpectrogramResult:
    """A PSD spectrogram containing only complete within-run windows."""

    spec: SpectralAnalysisSpec
    frequencies_hz: tuple[float, ...]
    window_centers_s: tuple[float, ...]
    power_density: tuple[tuple[float, ...], ...]
    run_ids: tuple[int, ...]
    window_start_s: tuple[float, ...]
    window_stop_s: tuple[float, ...]
    distance_to_left_edge_s: tuple[float, ...]
    distance_to_right_edge_s: tuple[float, ...]
    value_unit: str
    power_density_unit: str
    evidence: ContinuityEvidence
    method: str = "complete_window_gap_separated_spectrogram"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize the time-frequency matrix and window-level evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class StatePSD:
    """One state label and its gap-aware Welch result."""

    state: str
    epoch_count: int
    assigned_sample_count: int
    result: WelchPSDResult


@dataclass(frozen=True)
class StateAutocorrelation:
    """One state label and its gap-aware autocorrelation result."""

    state: str
    epoch_count: int
    assigned_sample_count: int
    result: AutocorrelationResult


@dataclass(frozen=True)
class StateSpectrogram:
    """One state label and its complete-window spectrogram."""

    state: str
    epoch_count: int
    assigned_sample_count: int
    result: SpectrogramResult


@dataclass(frozen=True)
class StateConditionedPSDResult:
    """PSD results grouped by user-supplied state without inferred labels."""

    states: tuple[StatePSD, ...]
    epoch_count: int
    unassigned_sample_count: int
    overlap_policy: str = "error"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize state spectra and their source evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class StateConditionedAutocorrelationResult:
    """Autocorrelation results grouped by user-supplied state."""

    states: tuple[StateAutocorrelation, ...]
    epoch_count: int
    unassigned_sample_count: int
    overlap_policy: str = "error"
    schema_version: str = "1"


@dataclass(frozen=True)
class StateConditionedSpectrogramResult:
    """Spectrogram results grouped by user-supplied state."""

    states: tuple[StateSpectrogram, ...]
    epoch_count: int
    unassigned_sample_count: int
    overlap_policy: str = "error"
    schema_version: str = "1"


@dataclass(frozen=True)
class StatePSDSession:
    """Attach subject and session identity to state-conditioned spectra."""

    subject: str
    session: str
    result: StateConditionedPSDResult


@dataclass(frozen=True)
class StateBandPowerInferenceSpec:
    """Declare a paired animal-level contrast between two supplied states."""

    state_a: str
    state_b: str
    frequency_band_hz: tuple[float, float]
    effect_scale: EffectScale = "difference"
    confidence_level: float = 0.95
    bootstrap_resamples: int = 10_000
    permutation_resamples: int = 10_000
    seed: int = 0

    def __post_init__(self) -> None:
        low, high = self.frequency_band_hz
        if not self.state_a or not self.state_b or self.state_a == self.state_b:
            raise ValueError("state contrast requires two distinct labels")
        if low < 0 or low >= high:
            raise ValueError("frequency_band_hz must be increasing and non-negative")
        if self.effect_scale not in {"difference", "ratio"}:
            raise ValueError("unsupported effect scale")
        if not 0 < self.confidence_level < 1:
            raise ValueError("confidence_level must lie between zero and one")
        if self.bootstrap_resamples < 100 or self.permutation_resamples < 100:
            raise ValueError("state inference requires at least 100 resamples")


@dataclass(frozen=True)
class StateBandPowerEstimate:
    """One animal-state estimate after equal-session aggregation."""

    subject: str
    state: str
    value: float
    session_count: int


@dataclass(frozen=True)
class StateBandPowerInferenceResult:
    """Paired state contrast with animal-level bootstrap and sign flips."""

    spec: StateBandPowerInferenceSpec
    estimates: tuple[StateBandPowerEstimate, ...]
    estimate: float
    interval_low: float
    interval_high: float
    permutation_pvalue: float
    included_subjects: tuple[str, ...]
    excluded_subjects: tuple[str, ...]
    permutation_resamples: int
    method: str = "equal_session_animal_bootstrap_and_paired_sign_flip"


@dataclass(frozen=True)
class _PreparedRuns:
    time: NDArray[np.float64]
    values: NDArray[np.float64]
    indices: tuple[NDArray[np.int64], ...]
    evidence: ContinuityEvidence


def autocorrelation(
    time: ArrayLike,
    values: ArrayLike,
    spec: AutocorrelationSpec | None = None,
    *,
    valid: ArrayLike | None = None,
) -> AutocorrelationResult:
    """Estimate autocorrelation without constructing pairs across invalid runs."""
    spec = spec or AutocorrelationSpec()
    prepared = _prepare_runs(time, values, valid, spec.gap)
    return _autocorrelation_from_runs(prepared, spec)


def welch_psd(
    time: ArrayLike,
    values: ArrayLike,
    spec: SpectralAnalysisSpec | None = None,
    *,
    valid: ArrayLike | None = None,
    value_unit: str = "a.u.",
) -> WelchPSDResult:
    """Estimate a Welch PSD while treating each valid acquisition run separately."""
    spec = spec or SpectralAnalysisSpec()
    prepared = _prepare_runs(time, values, valid, spec.gap)
    return _welch_from_runs(prepared, spec, value_unit)


def spectrogram(
    time: ArrayLike,
    values: ArrayLike,
    spec: SpectralAnalysisSpec | None = None,
    *,
    valid: ArrayLike | None = None,
    value_unit: str = "a.u.",
) -> SpectrogramResult:
    """Compute only complete time-frequency windows contained within valid runs."""
    spec = spec or SpectralAnalysisSpec()
    prepared = _prepare_runs(time, values, valid, spec.gap)
    return _spectrogram_from_runs(prepared, spec, value_unit)


def state_conditioned_psd(
    time: ArrayLike,
    values: ArrayLike,
    epochs: tuple[StateEpoch, ...] | list[StateEpoch],
    spec: SpectralAnalysisSpec | None = None,
    *,
    valid: ArrayLike | None = None,
    value_unit: str = "a.u.",
) -> StateConditionedPSDResult:
    """Compute a separate PSD for each supplied state label."""
    spec = spec or SpectralAnalysisSpec()
    arrays = _validate_signal(time, values, valid)
    partitions, assigned = _state_partitions(arrays[0], epochs)
    output = []
    for state in sorted(partitions):
        prepared = _prepare_runs(*arrays, spec.gap, partition=partitions[state])
        output.append(
            StatePSD(
                state,
                sum(epoch.state == state for epoch in epochs),
                int(np.count_nonzero(partitions[state] >= 0)),
                _welch_from_runs(prepared, spec, value_unit),
            )
        )
    return StateConditionedPSDResult(
        tuple(output), len(epochs), int(np.count_nonzero(~assigned))
    )


def state_conditioned_autocorrelation(
    time: ArrayLike,
    values: ArrayLike,
    epochs: tuple[StateEpoch, ...] | list[StateEpoch],
    spec: AutocorrelationSpec | None = None,
    *,
    valid: ArrayLike | None = None,
) -> StateConditionedAutocorrelationResult:
    """Compute autocorrelation separately within each supplied state label."""
    spec = spec or AutocorrelationSpec()
    arrays = _validate_signal(time, values, valid)
    partitions, assigned = _state_partitions(arrays[0], epochs)
    output = []
    for state in sorted(partitions):
        prepared = _prepare_runs(*arrays, spec.gap, partition=partitions[state])
        output.append(
            StateAutocorrelation(
                state,
                sum(epoch.state == state for epoch in epochs),
                int(np.count_nonzero(partitions[state] >= 0)),
                _autocorrelation_from_runs(prepared, spec),
            )
        )
    return StateConditionedAutocorrelationResult(
        tuple(output), len(epochs), int(np.count_nonzero(~assigned))
    )


def state_conditioned_spectrogram(
    time: ArrayLike,
    values: ArrayLike,
    epochs: tuple[StateEpoch, ...] | list[StateEpoch],
    spec: SpectralAnalysisSpec | None = None,
    *,
    valid: ArrayLike | None = None,
    value_unit: str = "a.u.",
) -> StateConditionedSpectrogramResult:
    """Compute complete-window spectrograms separately within supplied states."""
    spec = spec or SpectralAnalysisSpec()
    arrays = _validate_signal(time, values, valid)
    partitions, assigned = _state_partitions(arrays[0], epochs)
    output = []
    for state in sorted(partitions):
        prepared = _prepare_runs(*arrays, spec.gap, partition=partitions[state])
        output.append(
            StateSpectrogram(
                state,
                sum(epoch.state == state for epoch in epochs),
                int(np.count_nonzero(partitions[state] >= 0)),
                _spectrogram_from_runs(prepared, spec, value_unit),
            )
        )
    return StateConditionedSpectrogramResult(
        tuple(output), len(epochs), int(np.count_nonzero(~assigned))
    )


def infer_state_band_power(
    sessions: tuple[StatePSDSession, ...] | list[StatePSDSession],
    spec: StateBandPowerInferenceSpec,
) -> StateBandPowerInferenceResult:
    """Contrast band power without treating sessions or windows as animals."""
    if not sessions:
        raise ValueError("state band-power inference requires sessions")
    identities = [(item.subject, item.session) for item in sessions]
    if any(not subject or not session for subject, session in identities):
        raise ValueError("state PSD sessions require subject and session identity")
    if len(set(identities)) != len(identities):
        raise ValueError("state PSD subject-session identities must be unique")

    session_values: dict[tuple[str, str], list[float]] = {}
    all_subjects = {session.subject for session in sessions}
    for session_item in sessions:
        by_state = {item.state: item for item in session_item.result.states}
        for state in (spec.state_a, spec.state_b):
            if state not in by_state:
                continue
            value = _band_power(by_state[state].result, spec.frequency_band_hz)
            session_values.setdefault((session_item.subject, state), []).append(value)

    estimates = tuple(
        StateBandPowerEstimate(subject, state, float(np.mean(values)), len(values))
        for (subject, state), values in sorted(session_values.items())
    )
    lookup = {(item.subject, item.state): item.value for item in estimates}
    included = tuple(
        sorted(
            subject
            for subject in all_subjects
            if (subject, spec.state_a) in lookup and (subject, spec.state_b) in lookup
        )
    )
    if len(included) < 2:
        raise ValueError("state band-power inference requires two complete animals")
    excluded = tuple(sorted(all_subjects - set(included)))
    first = np.asarray([lookup[(subject, spec.state_a)] for subject in included])
    second = np.asarray([lookup[(subject, spec.state_b)] for subject in included])
    if spec.effect_scale == "ratio" and np.any(second <= 0):
        raise ValueError("ratio effects require positive denominator band power")
    contrasts = first - second if spec.effect_scale == "difference" else first / second
    estimate = float(np.mean(contrasts))
    rng = np.random.default_rng(spec.seed)
    indices = rng.integers(
        0, len(contrasts), (spec.bootstrap_resamples, len(contrasts))
    )
    bootstrap = np.mean(contrasts[indices], axis=1)
    alpha = 1 - spec.confidence_level
    low, high = np.quantile(bootstrap, [alpha / 2, 1 - alpha / 2])
    centered = contrasts if spec.effect_scale == "difference" else np.log(contrasts)
    observed = abs(float(np.mean(centered)))
    null, actual = _sign_flip_distribution(centered, spec, rng)
    pvalue = float((1 + np.count_nonzero(np.abs(null) >= observed)) / (len(null) + 1))
    return StateBandPowerInferenceResult(
        spec,
        estimates,
        estimate,
        float(low),
        float(high),
        pvalue,
        included,
        excluded,
        actual,
    )


def _prepare_runs(
    time: ArrayLike,
    values: ArrayLike,
    valid: ArrayLike | None,
    spec: GapHandlingSpec,
    *,
    partition: NDArray[np.int64] | None = None,
) -> _PreparedRuns:
    time_values, signal_values, sample_valid = _validate_signal(time, values, valid)
    if partition is None:
        partition = np.zeros(len(time_values), dtype=np.int64)
    if partition.shape != time_values.shape:
        raise ValueError("partition must match signal samples")
    sample_valid = sample_valid & (partition >= 0)
    differences = np.diff(time_values)
    sampling_interval = float(np.median(differences))
    gap_break = differences > spec.gap_factor * sampling_interval
    gap_count = int(np.count_nonzero(gap_break))
    indices: list[NDArray[np.int64]] = []
    exclusions: list[RunExclusion] = []
    start: int | None = None
    for index in range(len(time_values)):
        begins = sample_valid[index] and (
            index == 0
            or not sample_valid[index - 1]
            or gap_break[index - 1]
            or partition[index] != partition[index - 1]
        )
        if begins:
            start = index
        ends = start is not None and (
            index == len(time_values) - 1
            or not sample_valid[index + 1]
            or gap_break[index]
            or partition[index] != partition[index + 1]
        )
        if ends:
            run = np.arange(start, index + 1, dtype=np.int64)
            if len(run) < spec.minimum_run_samples:
                exclusions.append(
                    RunExclusion(
                        float(time_values[run[0]]),
                        float(time_values[run[-1]]),
                        len(run),
                        "fewer_than_minimum_run_samples",
                    )
                )
            else:
                run_differences = np.diff(time_values[run])
                interval_cv = float(np.std(run_differences) / np.mean(run_differences))
                if interval_cv > spec.maximum_interval_cv:
                    raise ValueError(
                        "sampling interval CV exceeds maximum_interval_cv within "
                        "a valid run; resample prospectively before spectral analysis"
                    )
                indices.append(run)
            start = None
    if not indices:
        raise ValueError("no valid continuity run satisfies the analysis policy")
    runs = tuple(
        ContinuityRun(
            run_id,
            int(partition[run[0]]),
            float(time_values[run[0]]),
            float(time_values[run[-1]]),
            len(run),
            len(run) * sampling_interval,
            float(
                np.std(np.diff(time_values[run])) / np.mean(np.diff(time_values[run]))
            ),
        )
        for run_id, run in enumerate(indices)
    )
    evidence = ContinuityEvidence(
        sampling_interval,
        1 / sampling_interval,
        int(np.count_nonzero(sample_valid)),
        int(len(sample_valid) - np.count_nonzero(sample_valid)),
        gap_count,
        float(sum(run.exposure_s for run in runs)),
        runs,
        tuple(exclusions),
    )
    return _PreparedRuns(time_values, signal_values, tuple(indices), evidence)


def _validate_signal(
    time: ArrayLike,
    values: ArrayLike,
    valid: ArrayLike | None,
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


def _window_parameters(
    evidence: ContinuityEvidence, spec: SpectralAnalysisSpec
) -> tuple[int, int, int]:
    samples = round(spec.window_duration_s * evidence.sampling_rate_hz)
    if samples < 4:
        raise ValueError("spectral window must contain at least four samples")
    overlap = int(np.floor(samples * spec.overlap_fraction))
    step = samples - overlap
    return samples, overlap, step


def _welch_from_runs(
    prepared: _PreparedRuns, spec: SpectralAnalysisSpec, value_unit: str
) -> WelchPSDResult:
    samples, overlap, step = _window_parameters(prepared.evidence, spec)
    weighted: list[NDArray[np.float64]] = []
    weights: list[int] = []
    counts = []
    frequencies: NDArray[np.float64] | None = None
    for run in prepared.indices:
        count = max(0, 1 + (len(run) - samples) // step)
        counts.append(count)
        if count == 0:
            continue
        run_frequency, run_power = signal.welch(  # type: ignore[call-overload]
            prepared.values[run],
            fs=prepared.evidence.sampling_rate_hz,
            window=spec.window,
            nperseg=samples,
            noverlap=overlap,
            nfft=samples,
            detrend=False if spec.detrend == "none" else spec.detrend,
            scaling="density",
            average="mean",
        )
        frequencies = np.asarray(run_frequency, dtype=float)
        weighted.append(np.asarray(run_power, dtype=float))
        weights.append(count)
    if not weighted or frequencies is None:
        raise ValueError("no continuity run contains one complete spectral window")
    power = np.average(np.asarray(weighted), axis=0, weights=np.asarray(weights))
    selected = np.ones(len(frequencies), dtype=bool)
    if spec.maximum_frequency_hz is not None:
        selected &= frequencies <= spec.maximum_frequency_hz
    return WelchPSDResult(
        spec,
        _float_tuple(frequencies[selected]),
        _float_tuple(power[selected]),
        tuple(counts),
        int(sum(counts)),
        value_unit,
        f"{value_unit}^2/Hz",
        prepared.evidence,
    )


def _spectrogram_from_runs(
    prepared: _PreparedRuns, spec: SpectralAnalysisSpec, value_unit: str
) -> SpectrogramResult:
    samples, _, step = _window_parameters(prepared.evidence, spec)
    frequencies: NDArray[np.float64] | None = None
    columns: list[NDArray[np.float64]] = []
    centers: list[float] = []
    run_ids: list[int] = []
    starts: list[float] = []
    stops: list[float] = []
    left_edges: list[float] = []
    right_edges: list[float] = []
    for run_id, run in enumerate(prepared.indices):
        for offset in range(0, len(run) - samples + 1, step):
            window_indices = run[offset : offset + samples]
            frequency, power = signal.welch(  # type: ignore[call-overload]
                prepared.values[window_indices],
                fs=prepared.evidence.sampling_rate_hz,
                window=spec.window,
                nperseg=samples,
                noverlap=0,
                nfft=samples,
                detrend=False if spec.detrend == "none" else spec.detrend,
                scaling="density",
                average="mean",
            )
            frequencies = np.asarray(frequency, dtype=float)
            columns.append(np.asarray(power, dtype=float))
            start = float(prepared.time[window_indices[0]])
            stop = float(prepared.time[window_indices[-1]])
            starts.append(start)
            stops.append(stop)
            centers.append((start + stop) / 2)
            run_ids.append(run_id)
            left_edges.append(start - float(prepared.time[run[0]]))
            right_edges.append(float(prepared.time[run[-1]]) - stop)
    if not columns or frequencies is None:
        raise ValueError("no continuity run contains one complete spectrogram window")
    selected = np.ones(len(frequencies), dtype=bool)
    if spec.maximum_frequency_hz is not None:
        selected &= frequencies <= spec.maximum_frequency_hz
    matrix = np.asarray(columns, dtype=float).T[selected]
    return SpectrogramResult(
        spec,
        _float_tuple(frequencies[selected]),
        tuple(centers),
        tuple(_float_tuple(row) for row in matrix),
        tuple(run_ids),
        tuple(starts),
        tuple(stops),
        tuple(left_edges),
        tuple(right_edges),
        value_unit,
        f"{value_unit}^2/Hz",
        prepared.evidence,
    )


def _autocorrelation_from_runs(
    prepared: _PreparedRuns, spec: AutocorrelationSpec
) -> AutocorrelationResult:
    maximum_lag = round(spec.maximum_lag_s * prepared.evidence.sampling_rate_hz)
    maximum_lag = min(maximum_lag, max(len(run) for run in prepared.indices) - 1)
    numerator = np.zeros(maximum_lag + 1)
    left_power = np.zeros(maximum_lag + 1)
    right_power = np.zeros(maximum_lag + 1)
    pairs = np.zeros(maximum_lag + 1, dtype=int)
    for run in prepared.indices:
        values = prepared.values[run]
        if spec.detrend != "none":
            values = signal.detrend(values, type=spec.detrend)
        for lag in range(min(maximum_lag, len(values) - 1) + 1):
            left = values if lag == 0 else values[:-lag]
            right = values if lag == 0 else values[lag:]
            numerator[lag] += np.dot(left, right)
            left_power[lag] += np.dot(left, left)
            right_power[lag] += np.dot(right, right)
            pairs[lag] += len(left)
    denominator = np.sqrt(left_power * right_power)
    correlation = np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, np.nan),
        where=denominator > 0,
    )
    lags = np.arange(maximum_lag + 1) * prepared.evidence.sampling_interval_s
    return AutocorrelationResult(
        spec,
        _float_tuple(lags),
        _float_tuple(correlation),
        tuple(int(value) for value in pairs),
        prepared.evidence,
    )


def _state_partitions(
    time: NDArray[np.float64],
    epochs: tuple[StateEpoch, ...] | list[StateEpoch],
) -> tuple[dict[str, NDArray[np.int64]], NDArray[np.bool_]]:
    if not epochs:
        raise ValueError("state-conditioned analysis requires at least one epoch")
    ordered = sorted(epochs, key=lambda item: (item.start_s, item.stop_s, item.state))
    for first, second in pairwise(ordered):
        if second.start_s < first.stop_s:
            raise ValueError("state epochs overlap; overlap_policy='error'")
    partitions = {
        state: np.full(len(time), -1, dtype=np.int64)
        for state in sorted({epoch.state for epoch in epochs})
    }
    assigned = np.zeros(len(time), dtype=bool)
    for epoch_index, epoch in enumerate(epochs):
        selected = (time >= epoch.start_s) & (time < epoch.stop_s)
        partitions[epoch.state][selected] = epoch_index
        assigned |= selected
    return partitions, assigned


def _band_power(result: WelchPSDResult, band: tuple[float, float]) -> float:
    frequency = np.asarray(result.frequencies_hz)
    power = np.asarray(result.power_density)
    if band[0] < frequency[0] or band[1] > frequency[-1]:
        raise ValueError("PSD does not cover the complete requested frequency band")
    interior = (frequency > band[0]) & (frequency < band[1])
    integration_frequency = np.concatenate(([band[0]], frequency[interior], [band[1]]))
    integration_power = np.interp(integration_frequency, frequency, power)
    return float(np.trapezoid(integration_power, integration_frequency))


def _sign_flip_distribution(
    values: NDArray[np.float64],
    spec: StateBandPowerInferenceSpec,
    rng: np.random.Generator,
) -> tuple[NDArray[np.float64], int]:
    if len(values) <= 16 and 2 ** len(values) <= spec.permutation_resamples:
        signs = np.asarray(list(product((-1.0, 1.0), repeat=len(values))))
    else:
        signs = rng.choice(
            np.asarray([-1.0, 1.0]),
            size=(spec.permutation_resamples, len(values)),
        )
    return np.mean(signs * values, axis=1), len(signs)


def _float_tuple(values: ArrayLike) -> tuple[float, ...]:
    return tuple(float(value) for value in np.asarray(values, dtype=float))
