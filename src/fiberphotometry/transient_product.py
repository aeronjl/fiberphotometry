"""Detection/quantification product boundary for spontaneous transients."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Literal, TypeAlias

import numpy as np
import xarray as xr
from scipy.signal import find_peaks

from fiberphotometry.model import validate_recording

DetectorFamily: TypeAlias = Literal["guppy", "pasta", "prominence"]
BaselineMethod: TypeAlias = Literal["mean", "minimum", "last_local_minimum"]
CandidateExclusionReason: TypeAlias = Literal[
    "insufficient_baseline", "missing_local_minimum", "below_threshold"
]
QuantificationExclusionReason: TypeAlias = Literal[
    "candidate_mismatch",
    "insufficient_baseline",
    "missing_local_minimum",
    "nonpositive_amplitude",
    "incomplete_shape",
]


@dataclass(frozen=True)
class PastaTransientDetectorSpec:
    """PASTa-compatible local-baseline amplitude detector."""

    amplitude_threshold: float
    baseline_method: BaselineMethod = "mean"
    baseline_start_s: float = 1.0
    baseline_end_s: float = 0.2
    minimum_distance_s: float = 0.0
    maximum_gap_factor: float = 3.0
    family: Literal["pasta"] = "pasta"


@dataclass(frozen=True)
class GuppyTransientDetectorSpec:
    """GuPPY-compatible two-threshold MAD detector within fixed chunks."""

    chunk_duration_s: float = 10.0
    high_amplitude_mad: float = 4.0
    detection_mad: float = 3.0
    maximum_gap_factor: float = 3.0
    family: Literal["guppy"] = "guppy"


@dataclass(frozen=True)
class ProminenceTransientDetectorSpec:
    """Height-plus-prominence detection on a gap-local z-scored stream."""

    minimum_height_z: float = 1.0
    minimum_prominence_z: float = 2.0
    minimum_distance_s: float = 0.25
    detrend_window_s: float | None = 100.0
    maximum_gap_factor: float = 3.0
    family: Literal["prominence"] = "prominence"


TransientDetectorSpec: TypeAlias = (
    PastaTransientDetectorSpec
    | GuppyTransientDetectorSpec
    | ProminenceTransientDetectorSpec
)


@dataclass(frozen=True)
class TransientCandidate:
    """One accepted location with detector-scale evidence only."""

    candidate_id: str
    family: DetectorFamily
    channel: str
    sample_index: int
    peak_time: float
    detection_value: float
    detection_baseline: float | None
    detection_amplitude: float | None
    detection_threshold: float
    detection_score: float


@dataclass(frozen=True)
class TransientCandidateExclusion:
    """A local maximum rejected during candidate detection."""

    family: DetectorFamily
    channel: str
    sample_index: int
    peak_time: float
    reason: CandidateExclusionReason


@dataclass(frozen=True)
class TransientCandidateResult:
    """Candidate locations and detector-scale evidence, before quantification."""

    spec: TransientDetectorSpec
    variable: str
    candidates: tuple[TransientCandidate, ...]
    exclusions: tuple[TransientCandidateExclusion, ...]


@dataclass(frozen=True)
class TransientQuantificationSpec:
    """Measurements applied to candidates on an explicitly chosen variable."""

    baseline_method: BaselineMethod = "mean"
    baseline_start_s: float = 1.0
    baseline_end_s: float = 0.2
    maximum_gap_factor: float = 3.0
    require_complete_shape: bool = True
    compound_window_s: float = 2.0
    bin_width_s: float | None = 30.0


@dataclass(frozen=True)
class QuantifiedTransient:
    """Kinetics on the quantification scale, linked to detector evidence."""

    candidate_id: str
    detection_family: DetectorFamily
    channel: str
    sample_index: int
    peak_time: float
    detection_value: float
    detection_threshold: float
    detection_score: float
    peak_value: float
    baseline: float
    amplitude: float
    onset_half_height_time: float
    offset_half_height_time: float
    rise_half_height_s: float
    fall_half_height_s: float
    full_width_half_height_s: float
    auc_above_baseline: float
    previous_interval_s: float | None
    compound_group: int | None = None
    compound_rank: int = 0


@dataclass(frozen=True)
class TransientQuantificationExclusion:
    """A detected candidate that cannot be quantified as requested."""

    candidate_id: str
    channel: str
    peak_time: float
    reason: QuantificationExclusionReason


@dataclass(frozen=True)
class TransientQuantificationSummary:
    """Exposure-adjusted descriptive summary for one session and channel."""

    channel: str
    analyzed_duration_s: float
    count: int
    rate_per_minute: float
    median_amplitude: float | None
    median_width_s: float | None
    median_auc: float | None
    median_interval_s: float | None


@dataclass(frozen=True)
class TransientQuantificationResult:
    """Quantified candidates, explicit failures, summaries, and time bins."""

    spec: TransientQuantificationSpec
    variable: str
    detector_variable: str
    events: tuple[QuantifiedTransient, ...]
    exclusions: tuple[TransientQuantificationExclusion, ...]
    summaries: tuple[TransientQuantificationSummary, ...]
    bins: xr.Dataset | None


def detect_transient_candidates(
    recording: xr.Dataset,
    *,
    variable: str,
    spec: TransientDetectorSpec,
) -> TransientCandidateResult:
    """Detect candidate locations without assigning quantification-scale kinetics."""
    time, values, channels = _recording_values(recording, variable)
    _validate_detector_spec(spec)
    sample_step = float(np.median(np.diff(time)))
    maximum_gap = spec.maximum_gap_factor * sample_step
    candidates: list[TransientCandidate] = []
    exclusions: list[TransientCandidateExclusion] = []
    for channel_index, channel in enumerate(channels):
        signal = values[:, channel_index]
        for run_index, run in enumerate(_finite_runs(time, signal, maximum_gap)):
            if len(run) < 3:
                continue
            if isinstance(spec, PastaTransientDetectorSpec):
                detected, rejected = _detect_pasta(
                    time, signal, run, channel, run_index, sample_step, spec
                )
            elif isinstance(spec, GuppyTransientDetectorSpec):
                detected, rejected = _detect_guppy(
                    time, signal, run, channel, run_index, sample_step, spec
                )
            else:
                detected, rejected = _detect_prominence(
                    time, signal, run, channel, run_index, sample_step, spec
                )
            candidates.extend(detected)
            exclusions.extend(rejected)
    candidates.sort(key=lambda item: (item.channel, item.peak_time, item.sample_index))
    return TransientCandidateResult(
        spec, variable, tuple(candidates), tuple(exclusions)
    )


def quantify_transient_candidates(
    recording: xr.Dataset,
    candidates: TransientCandidateResult,
    *,
    variable: str,
    spec: TransientQuantificationSpec | None = None,
) -> TransientQuantificationResult:
    """Measure candidates on a possibly different, non-normalized signal stream."""
    chosen = spec or TransientQuantificationSpec()
    _validate_quantification_spec(chosen)
    time, values, channels = _recording_values(recording, variable)
    channel_indices = {channel: index for index, channel in enumerate(channels)}
    sample_step = float(np.median(np.diff(time)))
    maximum_gap = chosen.maximum_gap_factor * sample_step
    events: list[QuantifiedTransient] = []
    exclusions: list[TransientQuantificationExclusion] = []
    previous_by_run: dict[tuple[str, int], float] = {}
    runs_by_channel = {
        channel: _finite_runs(time, values[:, channel_index], maximum_gap)
        for channel_index, channel in enumerate(channels)
    }
    for candidate in candidates.candidates:
        channel_index = channel_indices.get(candidate.channel)
        if channel_index is None or not _candidate_matches(time, candidate):
            exclusions.append(
                _quantification_exclusion(candidate, "candidate_mismatch")
            )
            continue
        signal = values[:, channel_index]
        run_index, run = _run_containing(
            runs_by_channel[candidate.channel], candidate.sample_index
        )
        if run is None:
            exclusions.append(
                _quantification_exclusion(candidate, "candidate_mismatch")
            )
            continue
        baseline_rows = _baseline_rows(time, run, candidate.sample_index, chosen)
        if len(baseline_rows) < 2:
            exclusions.append(
                _quantification_exclusion(candidate, "insufficient_baseline")
            )
            continue
        baseline = _baseline_value(signal, baseline_rows, chosen.baseline_method)
        if baseline is None:
            exclusions.append(
                _quantification_exclusion(candidate, "missing_local_minimum")
            )
            continue
        peak_value = float(signal[candidate.sample_index])
        amplitude = peak_value - baseline
        if not np.isfinite(amplitude) or amplitude <= 0:
            exclusions.append(
                _quantification_exclusion(candidate, "nonpositive_amplitude")
            )
            continue
        position = int(np.searchsorted(run, candidate.sample_index))
        crossings = _half_height_crossings(
            time, signal, run, candidate.sample_index, position, baseline
        )
        if crossings is None:
            exclusions.append(_quantification_exclusion(candidate, "incomplete_shape"))
            if chosen.require_complete_shape:
                continue
            onset = offset = auc = float("nan")
        else:
            onset, offset, left_row, right_row = crossings
            auc = float(
                np.trapezoid(
                    signal[left_row : right_row + 1] - baseline,
                    time[left_row : right_row + 1],
                )
            )
        run_key = (candidate.channel, run_index)
        previous_time = previous_by_run.get(run_key)
        previous = (
            candidate.peak_time - previous_time if previous_time is not None else None
        )
        events.append(
            QuantifiedTransient(
                candidate_id=candidate.candidate_id,
                detection_family=candidate.family,
                channel=candidate.channel,
                sample_index=candidate.sample_index,
                peak_time=candidate.peak_time,
                detection_value=candidate.detection_value,
                detection_threshold=candidate.detection_threshold,
                detection_score=candidate.detection_score,
                peak_value=peak_value,
                baseline=baseline,
                amplitude=amplitude,
                onset_half_height_time=onset,
                offset_half_height_time=offset,
                rise_half_height_s=float(candidate.peak_time - onset),
                fall_half_height_s=float(offset - candidate.peak_time),
                full_width_half_height_s=float(offset - onset),
                auc_above_baseline=auc,
                previous_interval_s=previous,
            )
        )
        previous_by_run[run_key] = candidate.peak_time
    events = _assign_compound_groups(events, chosen.compound_window_s)
    summaries = tuple(
        _summarize(
            channel,
            _analyzed_duration(time, values[:, index], maximum_gap),
            [event for event in events if event.channel == channel],
        )
        for index, channel in enumerate(channels)
    )
    bins = _bin_quantified_events(
        time, values, channels, events, chosen.bin_width_s, maximum_gap
    )
    return TransientQuantificationResult(
        chosen,
        variable,
        candidates.variable,
        tuple(events),
        tuple(exclusions),
        summaries,
        bins,
    )


def _detect_pasta(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    channel: str,
    run_index: int,
    sample_step: float,
    spec: PastaTransientDetectorSpec,
) -> tuple[list[TransientCandidate], list[TransientCandidateExclusion]]:
    distance = max(1, int(np.ceil(spec.minimum_distance_s / sample_step)))
    peaks, _ = find_peaks(signal[run], distance=distance)
    accepted: list[TransientCandidate] = []
    rejected: list[TransientCandidateExclusion] = []
    for position in peaks:
        peak = int(run[position])
        baseline_rows = _baseline_rows(time, run, peak, spec)
        if len(baseline_rows) < 2:
            rejected.append(
                _candidate_exclusion(spec, channel, peak, time, "insufficient_baseline")
            )
            continue
        baseline = _baseline_value(signal, baseline_rows, spec.baseline_method)
        if baseline is None:
            rejected.append(
                _candidate_exclusion(spec, channel, peak, time, "missing_local_minimum")
            )
            continue
        amplitude = float(signal[peak] - baseline)
        if amplitude < spec.amplitude_threshold:
            rejected.append(
                _candidate_exclusion(spec, channel, peak, time, "below_threshold")
            )
            continue
        accepted.append(
            _candidate(
                spec,
                channel,
                run_index,
                peak,
                time,
                float(signal[peak]),
                baseline,
                amplitude,
                spec.amplitude_threshold,
                amplitude,
            )
        )
    return accepted, rejected


def _detect_guppy(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    channel: str,
    run_index: int,
    sample_step: float,
    spec: GuppyTransientDetectorSpec,
) -> tuple[list[TransientCandidate], list[TransientCandidateExclusion]]:
    chunk_samples = max(3, int(np.ceil(spec.chunk_duration_s / sample_step)))
    accepted: list[TransientCandidate] = []
    for chunk_start in range(0, len(run), chunk_samples):
        chunk = run[chunk_start : chunk_start + chunk_samples]
        if len(chunk) < 3:
            continue
        chunk_values = signal[chunk]
        median = float(np.median(chunk_values))
        mad = float(np.median(np.abs(chunk_values - median)))
        first_threshold = median + spec.high_amplitude_mad * mad
        filtered = chunk_values[chunk_values <= first_threshold]
        if not len(filtered):
            continue
        filtered_median = float(np.median(filtered))
        filtered_mad = float(np.median(np.abs(filtered - filtered_median)))
        threshold = filtered_median + spec.detection_mad * filtered_mad
        thresholded = np.where(chunk_values > threshold, chunk_values, 0.0)
        peaks = 1 + np.flatnonzero(
            (thresholded[1:-1] > thresholded[:-2])
            & (thresholded[1:-1] > thresholded[2:])
        )
        for position in peaks:
            peak = int(chunk[position])
            amplitude = float(signal[peak] - filtered_median)
            accepted.append(
                _candidate(
                    spec,
                    channel,
                    run_index,
                    peak,
                    time,
                    float(signal[peak]),
                    filtered_median,
                    amplitude,
                    threshold,
                    amplitude,
                )
            )
    return accepted, []


def _detect_prominence(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    channel: str,
    run_index: int,
    sample_step: float,
    spec: ProminenceTransientDetectorSpec,
) -> tuple[list[TransientCandidate], list[TransientCandidateExclusion]]:
    values = signal[run]
    if spec.detrend_window_s is not None:
        window = min(len(values), max(1, round(spec.detrend_window_s / sample_step)))
        kernel = np.ones(window, dtype=float)
        moving = np.convolve(values, kernel, mode="same") / np.convolve(
            np.ones(len(values)), kernel, mode="same"
        )
        values = values - moving
    standard_deviation = float(np.std(values))
    if standard_deviation <= np.finfo(float).eps:
        return [], []
    zscore = (values - float(np.mean(values))) / standard_deviation
    distance = max(1, int(np.ceil(spec.minimum_distance_s / sample_step)))
    peaks, properties = find_peaks(
        zscore,
        height=spec.minimum_height_z,
        prominence=spec.minimum_prominence_z,
        distance=distance,
    )
    prominences = np.asarray(properties["prominences"], dtype=float)
    accepted = [
        _candidate(
            spec,
            channel,
            run_index,
            int(run[position]),
            time,
            float(zscore[position]),
            0.0,
            float(zscore[position]),
            spec.minimum_height_z,
            float(prominence),
        )
        for position, prominence in zip(peaks, prominences, strict=True)
    ]
    return accepted, []


def _candidate(
    spec: TransientDetectorSpec,
    channel: str,
    run_index: int,
    peak: int,
    time: np.ndarray,
    value: float,
    baseline: float | None,
    amplitude: float | None,
    threshold: float,
    score: float,
) -> TransientCandidate:
    return TransientCandidate(
        candidate_id=f"{channel}:run-{run_index}:sample-{peak}",
        family=spec.family,
        channel=channel,
        sample_index=peak,
        peak_time=float(time[peak]),
        detection_value=value,
        detection_baseline=baseline,
        detection_amplitude=amplitude,
        detection_threshold=float(threshold),
        detection_score=float(score),
    )


def _candidate_exclusion(
    spec: TransientDetectorSpec,
    channel: str,
    peak: int,
    time: np.ndarray,
    reason: CandidateExclusionReason,
) -> TransientCandidateExclusion:
    return TransientCandidateExclusion(
        spec.family, channel, peak, float(time[peak]), reason
    )


def _quantification_exclusion(
    candidate: TransientCandidate, reason: QuantificationExclusionReason
) -> TransientQuantificationExclusion:
    return TransientQuantificationExclusion(
        candidate.candidate_id, candidate.channel, candidate.peak_time, reason
    )


def _recording_values(
    recording: xr.Dataset, variable: str
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    validate_recording(recording)
    if variable not in recording:
        raise ValueError(f"recording does not contain {variable!r}")
    if recording[variable].dims != ("time", "channel"):
        raise ValueError("transient variables must have ('time', 'channel') dimensions")
    return (
        np.asarray(recording.time.values, dtype=float),
        np.asarray(recording[variable].values, dtype=float),
        [str(value) for value in recording.channel.values],
    )


def _finite_runs(
    time: np.ndarray, signal: np.ndarray, maximum_gap: float
) -> list[np.ndarray]:
    finite = np.flatnonzero(np.isfinite(signal))
    if not len(finite):
        return []
    breaks = (np.diff(finite) > 1) | (np.diff(time[finite]) > maximum_gap)
    return [run for run in np.split(finite, np.flatnonzero(breaks) + 1) if len(run)]


def _baseline_rows(
    time: np.ndarray,
    run: np.ndarray,
    peak: int,
    spec: PastaTransientDetectorSpec | TransientQuantificationSpec,
) -> np.ndarray:
    run_time = time[run]
    left = int(
        np.searchsorted(run_time, time[peak] - spec.baseline_start_s, side="left")
    )
    right = int(
        np.searchsorted(run_time, time[peak] - spec.baseline_end_s, side="left")
    )
    return run[left:right]


def _baseline_value(
    signal: np.ndarray, rows: np.ndarray, method: BaselineMethod
) -> float | None:
    values = signal[rows]
    if method == "mean":
        return float(np.mean(values))
    if method == "minimum":
        return float(np.min(values))
    minima, _ = find_peaks(-values)
    return float(values[minima[-1]]) if len(minima) else None


def _half_height_crossings(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    peak: int,
    position: int,
    baseline: float,
) -> tuple[float, float, int, int] | None:
    target = baseline + (float(signal[peak]) - baseline) / 2
    left_position = position - 1
    while left_position >= 0 and signal[run[left_position]] > target:
        left_position -= 1
    right_position = position + 1
    while right_position < len(run) and signal[run[right_position]] > target:
        right_position += 1
    if left_position < 0 or right_position >= len(run):
        return None
    left_low = int(run[left_position])
    left_high = int(run[left_position + 1])
    right_high = int(run[right_position - 1])
    right_low = int(run[right_position])
    return (
        _interpolate_crossing(time, signal, left_low, left_high, target),
        _interpolate_crossing(time, signal, right_high, right_low, target),
        left_low,
        right_low,
    )


def _interpolate_crossing(
    time: np.ndarray, signal: np.ndarray, first: int, second: int, target: float
) -> float:
    change = float(signal[second] - signal[first])
    if change == 0:
        return float(time[first])
    return float(
        time[first]
        + (target - float(signal[first])) / change * (time[second] - time[first])
    )


def _candidate_matches(time: np.ndarray, candidate: TransientCandidate) -> bool:
    return 0 <= candidate.sample_index < len(time) and np.isclose(
        time[candidate.sample_index], candidate.peak_time, rtol=0, atol=1e-9
    )


def _run_containing(
    runs: list[np.ndarray], sample_index: int
) -> tuple[int, np.ndarray | None]:
    for index, run in enumerate(runs):
        position = int(np.searchsorted(run, sample_index))
        if position < len(run) and run[position] == sample_index:
            return index, run
    return -1, None


def _assign_compound_groups(
    events: list[QuantifiedTransient], window_s: float
) -> list[QuantifiedTransient]:
    output = list(events)
    group_number = 0
    for channel in sorted({event.channel for event in events}):
        indices = [
            index for index, event in enumerate(output) if event.channel == channel
        ]
        start = 0
        while start < len(indices):
            stop = start + 1
            while stop < len(indices):
                previous = output[indices[stop - 1]]
                current = output[indices[stop]]
                if current.peak_time - previous.peak_time >= window_s:
                    break
                stop += 1
            members = indices[start:stop]
            if len(members) > 1:
                group_number += 1
                for rank, index in enumerate(members, start=1):
                    output[index] = replace(
                        output[index],
                        compound_group=group_number,
                        compound_rank=rank,
                    )
            start = stop
    return output


def _analyzed_duration(
    time: np.ndarray, signal: np.ndarray, maximum_gap: float
) -> float:
    return float(
        sum(
            time[run[-1]] - time[run[0]]
            for run in _finite_runs(time, signal, maximum_gap)
            if len(run) > 1
        )
    )


def _summarize(
    channel: str, duration: float, events: list[QuantifiedTransient]
) -> TransientQuantificationSummary:
    def median(values: list[float]) -> float | None:
        finite = [value for value in values if np.isfinite(value)]
        return float(np.median(finite)) if finite else None

    intervals = [
        event.previous_interval_s
        for event in events
        if event.previous_interval_s is not None
    ]
    return TransientQuantificationSummary(
        channel=channel,
        analyzed_duration_s=duration,
        count=len(events),
        rate_per_minute=60 * len(events) / duration if duration > 0 else 0.0,
        median_amplitude=median([event.amplitude for event in events]),
        median_width_s=median([event.full_width_half_height_s for event in events]),
        median_auc=median([event.auc_above_baseline for event in events]),
        median_interval_s=median(intervals),
    )


def _bin_quantified_events(
    time: np.ndarray,
    values: np.ndarray,
    channels: list[str],
    events: list[QuantifiedTransient],
    bin_width_s: float | None,
    maximum_gap: float,
) -> xr.Dataset | None:
    if bin_width_s is None:
        return None
    edges = np.arange(time[0], time[-1] + bin_width_s, bin_width_s)
    if len(edges) < 2 or edges[-1] < time[-1]:
        edges = np.append(edges, time[-1])
    shape = (len(edges) - 1, len(channels))
    count = np.zeros(shape, dtype=int)
    exposure = np.zeros(shape, dtype=float)
    median_amplitude = np.full(shape, np.nan)
    for channel_index, channel in enumerate(channels):
        channel_events = [event for event in events if event.channel == channel]
        for bin_index, (start, stop) in enumerate(pairwise(edges)):
            selected = [
                event for event in channel_events if start <= event.peak_time < stop
            ]
            count[bin_index, channel_index] = len(selected)
            if selected:
                median_amplitude[bin_index, channel_index] = float(
                    np.median([event.amplitude for event in selected])
                )
            for run in _finite_runs(time, values[:, channel_index], maximum_gap):
                exposure[bin_index, channel_index] += max(
                    0.0, min(stop, time[run[-1]]) - max(start, time[run[0]])
                )
    rate = np.divide(
        60 * count, exposure, out=np.zeros_like(exposure), where=exposure > 0
    )
    return xr.Dataset(
        data_vars={
            "count": (("bin", "channel"), count),
            "analyzed_duration_s": (("bin", "channel"), exposure),
            "rate_per_minute": (("bin", "channel"), rate),
            "median_amplitude": (("bin", "channel"), median_amplitude),
        },
        coords={
            "bin": np.arange(len(edges) - 1),
            "bin_start": ("bin", edges[:-1]),
            "bin_stop": ("bin", edges[1:]),
            "channel": channels,
        },
        attrs={
            "interpretation": "descriptive transient bins; not a tonic-signal estimate"
        },
    )


def _validate_detector_spec(spec: TransientDetectorSpec) -> None:
    if spec.maximum_gap_factor <= 0:
        raise ValueError("maximum_gap_factor must be positive")
    if isinstance(spec, PastaTransientDetectorSpec):
        if spec.amplitude_threshold <= 0:
            raise ValueError("PASTa amplitude_threshold must be positive")
        _validate_baseline_window(spec.baseline_start_s, spec.baseline_end_s)
        if spec.minimum_distance_s < 0:
            raise ValueError("minimum_distance_s cannot be negative")
    elif isinstance(spec, GuppyTransientDetectorSpec):
        if (
            min(
                spec.chunk_duration_s,
                spec.high_amplitude_mad,
                spec.detection_mad,
            )
            <= 0
        ):
            raise ValueError("GuPPY duration and MAD multipliers must be positive")
    elif (
        spec.minimum_height_z <= 0
        or spec.minimum_prominence_z < 0
        or spec.minimum_distance_s < 0
        or (spec.detrend_window_s is not None and spec.detrend_window_s <= 0)
    ):
        raise ValueError("prominence detector thresholds and windows are invalid")


def _validate_quantification_spec(spec: TransientQuantificationSpec) -> None:
    _validate_baseline_window(spec.baseline_start_s, spec.baseline_end_s)
    if spec.maximum_gap_factor <= 0 or spec.compound_window_s <= 0:
        raise ValueError("quantification gap and compound windows must be positive")
    if spec.bin_width_s is not None and spec.bin_width_s <= 0:
        raise ValueError("bin_width_s must be positive when provided")


def _validate_baseline_window(start_s: float, end_s: float) -> None:
    if start_s <= 0 or end_s < 0 or start_s <= end_s:
        raise ValueError("baseline_start_s must be greater than baseline_end_s >= 0")
