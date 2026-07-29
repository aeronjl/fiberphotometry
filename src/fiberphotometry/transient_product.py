"""Detection/quantification product boundary for spontaneous transients."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from itertools import pairwise
from typing import Literal, TypeAlias

import numpy as np
import xarray as xr
from scipy.signal import find_peaks, peak_prominences

from fiberphotometry.model import validate_recording

DetectorFamily: TypeAlias = Literal["guppy", "pasta", "prominence"]
BaselineMethod: TypeAlias = Literal["mean", "minimum", "last_local_minimum"]
CandidateExclusionReason: TypeAlias = Literal[
    "insufficient_baseline",
    "missing_local_minimum",
    "below_threshold",
    "below_frozen_threshold",
    "chunk_boundary",
    "degenerate_noise_scale",
]
QuantificationExclusionReason: TypeAlias = Literal[
    "candidate_mismatch",
    "insufficient_baseline",
    "missing_local_minimum",
    "nonpositive_amplitude",
    "incomplete_shape",
    "waveform_qc_failed",
]
ThresholdEstimator: TypeAlias = Literal["median_mad", "empirical_quantile"]
ThresholdSourceRole: TypeAlias = Literal["baseline", "negative_control"]
WaveformIssueSeverity: TypeAlias = Literal["warning", "error"]
WaveformStatus: TypeAlias = Literal["pass", "warning", "fail"]


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
    """GuPPY-compatible two-threshold MAD detector within fixed chunks.

    Both multipliers scale the **unscaled** median absolute deviation, matching
    the published GuPPy implementation. They are therefore not robust-sigma
    multiples: for Gaussian noise ``detection_mad=3.0`` gates at
    ``3 * 0.6745 = 2.02`` standard deviations, not three.
    ``fiberphotometry.transients.TransientDetectionSpec.threshold`` and
    ``TransientThresholdCalibrationSpec.mad_multiplier`` use the opposite
    convention and scale by ``1.4826``, so the same number is a stricter gate
    there. This divergence is deliberate reference compatibility, not an
    oversight; do not compare the two multipliers as if they shared units.
    """

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
    frozen_score_threshold: float | None = None


@dataclass(frozen=True)
class TransientCandidateExclusion:
    """A local maximum rejected during candidate detection."""

    family: DetectorFamily
    channel: str
    sample_index: int
    peak_time: float
    reason: CandidateExclusionReason
    observed_score: float | None = None
    required_score: float | None = None


@dataclass(frozen=True)
class TransientCandidateResult:
    """Candidate locations and detector-scale evidence, before quantification."""

    spec: TransientDetectorSpec
    variable: str
    candidates: tuple[TransientCandidate, ...]
    exclusions: tuple[TransientCandidateExclusion, ...]
    frozen_thresholds: FrozenTransientThresholds | None = None


@dataclass(frozen=True)
class TransientThresholdCalibrationSpec:
    """How candidate-scale scores are converted into frozen thresholds.

    ``mad_multiplier`` is a robust-sigma multiple: the score dispersion is
    ``1.4826 * MAD``, so ``6.0`` is six Gaussian standard deviations. This is
    the opposite convention to ``GuppyTransientDetectorSpec``, whose own
    multipliers scale the unscaled MAD.

    The calibration population is every scored local maximum inside a finite
    run, including negative scores and including maxima that the detector's own
    native threshold would reject. Gating the population first would truncate
    the null distribution and bias both the median and the MAD, so the frozen
    value is a robust null over ungated scores rather than a statistic of the
    detections it later gates.
    """

    estimator: ThresholdEstimator = "median_mad"
    mad_multiplier: float = 6.0
    quantile: float = 0.999
    minimum_score_count: int = 20

    def __post_init__(self) -> None:
        if self.estimator not in {"median_mad", "empirical_quantile"}:
            raise ValueError("unsupported transient threshold estimator")
        if not np.isfinite(self.mad_multiplier) or self.mad_multiplier <= 0:
            raise ValueError("mad_multiplier must be finite and positive")
        if not np.isfinite(self.quantile) or not 0 < self.quantile < 1:
            raise ValueError("quantile must lie strictly between zero and one")
        if self.minimum_score_count < 3:
            raise ValueError("minimum_score_count must be at least three")


@dataclass(frozen=True)
class ChannelFrozenTransientThreshold:
    """One channel-specific threshold and its calibration denominator."""

    channel: str
    threshold: float
    score_count: int
    finite_sample_count: int
    continuity_run_count: int
    analyzed_duration_s: float
    score_median: float
    score_mad: float
    score_quantile: float
    maximum_score: float

    def __post_init__(self) -> None:
        if not self.channel.strip():
            raise ValueError("frozen threshold channel must be non-empty")
        if not np.isfinite(self.threshold) or self.threshold < 0:
            raise ValueError(
                "frozen transient threshold must be finite and non-negative"
            )
        if self.score_count < 3 or self.finite_sample_count < self.score_count:
            raise ValueError("frozen threshold calibration counts are inconsistent")
        if self.continuity_run_count < 1 or self.analyzed_duration_s < 0:
            raise ValueError("frozen threshold continuity evidence is invalid")
        for name in (
            "score_median",
            "score_mad",
            "score_quantile",
            "maximum_score",
        ):
            if not np.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class FrozenTransientThresholds:
    """Immutable control/baseline thresholds bound to one detector contract."""

    detector_spec: TransientDetectorSpec
    detector_variable: str
    source_role: ThresholdSourceRole
    source_id: str
    preprocessing_fingerprint: str
    calibration_spec: TransientThresholdCalibrationSpec
    channels: tuple[ChannelFrozenTransientThreshold, ...]
    calibration_fingerprint: str
    interpretation: str = (
        "thresholds_are_frozen_from_separate_source_evidence_and_not_reestimated"
    )
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if self.source_role not in {"baseline", "negative_control"}:
            raise ValueError("unsupported threshold source role")
        for name in (
            "detector_variable",
            "source_id",
            "preprocessing_fingerprint",
            "calibration_fingerprint",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        channel_names = [item.channel for item in self.channels]
        if not channel_names or len(set(channel_names)) != len(channel_names):
            raise ValueError("frozen thresholds require unique channel names")

    def for_channel(self, channel: str) -> ChannelFrozenTransientThreshold:
        """Resolve one channel, refusing absent or duplicate calibration."""
        matches = [item for item in self.channels if item.channel == channel]
        if len(matches) != 1:
            raise KeyError(f"no unique frozen transient threshold for {channel!r}")
        return matches[0]

    def to_json(self) -> str:
        """Serialize threshold values, source identity, and denominators."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


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
    require_waveform_qc: bool = False
    allow_waveform_warnings: bool = True


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
    frozen_score_threshold: float | None = None
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
    waveform_fingerprint: str | None = None


@dataclass(frozen=True)
class TransientWaveformSpec:
    """Prospective cutout window and observable waveform-QC thresholds."""

    pre_peak_s: float = 1.0
    post_peak_s: float = 2.0
    maximum_gap_factor: float = 3.0
    require_complete_window: bool = True
    maximum_flat_step_fraction_warning: float = 0.05
    maximum_flat_step_fraction_error: float = 0.20
    detector_floor: float | None = None
    detector_ceiling: float | None = None
    saturation_tolerance: float = 0.0
    maximum_saturation_fraction_warning: float = 0.001
    maximum_saturation_fraction_error: float = 0.01
    warn_nearby_candidates: bool = True

    def __post_init__(self) -> None:
        for name in ("pre_peak_s", "post_peak_s", "maximum_gap_factor"):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        _validate_nested_maximum(
            self.maximum_flat_step_fraction_warning,
            self.maximum_flat_step_fraction_error,
            "flat-step fraction",
        )
        _validate_nested_maximum(
            self.maximum_saturation_fraction_warning,
            self.maximum_saturation_fraction_error,
            "saturation fraction",
        )
        if (self.detector_floor is None) != (self.detector_ceiling is None):
            raise ValueError(
                "detector_floor and detector_ceiling must be supplied together"
            )
        if self.detector_floor is not None:
            assert self.detector_ceiling is not None
            if not (
                np.isfinite(self.detector_floor)
                and np.isfinite(self.detector_ceiling)
                and self.detector_floor < self.detector_ceiling
            ):
                raise ValueError("detector bounds must be finite and increasing")
        if not np.isfinite(self.saturation_tolerance) or self.saturation_tolerance < 0:
            raise ValueError("saturation_tolerance must be finite and non-negative")


@dataclass(frozen=True)
class TransientWaveformIssue:
    """One actionable concern attached to a retained candidate waveform."""

    severity: WaveformIssueSeverity
    code: str
    candidate_id: str
    message: str
    value: float | str | None = None


@dataclass(frozen=True)
class TransientWaveform:
    """One non-resampled, gap-bounded cutout with explicit QC evidence."""

    candidate_id: str
    channel: str
    peak_time: float
    sample_index: int
    relative_time_s: tuple[float, ...]
    values: tuple[float, ...]
    sample_count: int
    requested_start_s: float
    requested_stop_s: float
    observed_start_s: float
    observed_stop_s: float
    pre_coverage_s: float
    post_coverage_s: float
    coverage_fraction: float
    baseline_median: float | None
    baseline_standard_deviation: float | None
    baseline_slope_per_s: float | None
    flat_step_fraction: float
    saturation_fraction: float | None
    nearby_candidate_ids: tuple[str, ...]
    issues: tuple[TransientWaveformIssue, ...]
    status: WaveformStatus


@dataclass(frozen=True)
class TransientWaveformResult:
    """All candidate cutouts, QC outcomes, and a stable evidence fingerprint."""

    spec: TransientWaveformSpec
    variable: str
    detector_variable: str
    waveforms: tuple[TransientWaveform, ...]
    evidence_fingerprint: str
    method: str = "nonresampled_gap_bounded_candidate_cutouts"
    schema_version: str = "1"

    def for_candidate(self, candidate_id: str) -> TransientWaveform:
        """Resolve exactly one retained candidate cutout."""
        matches = [item for item in self.waveforms if item.candidate_id == candidate_id]
        if len(matches) != 1:
            raise KeyError(f"no unique transient waveform for {candidate_id!r}")
        return matches[0]

    def to_json(self) -> str:
        """Serialize cutout values, QC evidence, and identity."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_xarray(self) -> xr.Dataset:
        """Return padded values and native relative times without interpolation."""
        maximum = max((item.sample_count for item in self.waveforms), default=0)
        values = np.full((len(self.waveforms), maximum), np.nan, dtype=float)
        relative = np.full_like(values, np.nan)
        present = np.zeros_like(values, dtype=bool)
        for index, item in enumerate(self.waveforms):
            length = item.sample_count
            values[index, :length] = item.values
            relative[index, :length] = item.relative_time_s
            present[index, :length] = True
        return xr.Dataset(
            data_vars={
                "value": (("event", "sample"), values),
                "relative_time_s": (("event", "sample"), relative),
                "present": (("event", "sample"), present),
                "status": ("event", [item.status for item in self.waveforms]),
            },
            coords={
                "event": [item.candidate_id for item in self.waveforms],
                "channel": ("event", [item.channel for item in self.waveforms]),
                "peak_time": ("event", [item.peak_time for item in self.waveforms]),
                "sample": np.arange(maximum),
            },
            attrs={
                "variable": self.variable,
                "detector_variable": self.detector_variable,
                "evidence_fingerprint": self.evidence_fingerprint,
                "interpretation": "native samples padded only; no interpolation",
            },
        )


def calibrate_transient_thresholds(
    recording: xr.Dataset,
    *,
    variable: str,
    detector_spec: TransientDetectorSpec,
    source_role: ThresholdSourceRole,
    source_id: str,
    preprocessing_fingerprint: str,
    calibration_spec: TransientThresholdCalibrationSpec | None = None,
) -> FrozenTransientThresholds:
    """Freeze channel-specific detector-score gates from separate source evidence."""
    chosen = calibration_spec or TransientThresholdCalibrationSpec()
    _validate_detector_spec(detector_spec)
    source_id = _nonempty(source_id, "source_id")
    preprocessing_fingerprint = _nonempty(
        preprocessing_fingerprint, "preprocessing_fingerprint"
    )
    if source_role not in {"baseline", "negative_control"}:
        raise ValueError("source_role must be 'baseline' or 'negative_control'")
    time, values, channels = _recording_values(recording, variable)
    sample_step = float(np.median(np.diff(time)))
    maximum_gap = detector_spec.maximum_gap_factor * sample_step
    frozen = []
    for channel_index, channel in enumerate(channels):
        signal = values[:, channel_index]
        runs = _finite_runs(time, signal, maximum_gap)
        scores = _calibration_scores(
            time,
            signal,
            runs,
            sample_step,
            detector_spec,
        )
        if len(scores) < chosen.minimum_score_count:
            raise ValueError(
                f"channel {channel!r} has {len(scores)} calibration scores; "
                f"at least {chosen.minimum_score_count} are required"
            )
        median = float(np.median(scores))
        mad = float(np.median(np.abs(scores - median)))
        quantile = float(np.quantile(scores, chosen.quantile))
        if chosen.estimator == "median_mad" and mad <= 0:
            raise ValueError(
                f"channel {channel!r} calibration scores have a zero median "
                "absolute deviation; this source carries no usable score "
                "dispersion for a median_mad threshold"
            )
        threshold = (
            median + chosen.mad_multiplier * 1.4826 * mad
            if chosen.estimator == "median_mad"
            else quantile
        )
        frozen.append(
            ChannelFrozenTransientThreshold(
                channel=channel,
                threshold=float(threshold),
                score_count=len(scores),
                finite_sample_count=int(np.count_nonzero(np.isfinite(signal))),
                continuity_run_count=len(runs),
                analyzed_duration_s=_analyzed_duration(time, signal, maximum_gap),
                score_median=median,
                score_mad=mad,
                score_quantile=quantile,
                maximum_score=float(np.max(scores)),
            )
        )
    fingerprint = _threshold_fingerprint(
        time,
        values,
        detector_spec,
        variable,
        source_role,
        source_id,
        preprocessing_fingerprint,
        chosen,
        frozen,
    )
    return FrozenTransientThresholds(
        detector_spec,
        variable,
        source_role,
        source_id,
        preprocessing_fingerprint,
        chosen,
        tuple(frozen),
        fingerprint,
    )


def detect_transient_candidates(
    recording: xr.Dataset,
    *,
    variable: str,
    spec: TransientDetectorSpec,
    frozen_thresholds: FrozenTransientThresholds | None = None,
) -> TransientCandidateResult:
    """Detect candidate locations without assigning quantification-scale kinetics."""
    time, values, channels = _recording_values(recording, variable)
    _validate_detector_spec(spec)
    sample_step = float(np.median(np.diff(time)))
    maximum_gap = spec.maximum_gap_factor * sample_step
    _validate_frozen_thresholds(frozen_thresholds, spec, variable, channels)
    candidates: list[TransientCandidate] = []
    exclusions: list[TransientCandidateExclusion] = []
    for channel_index, channel in enumerate(channels):
        signal = values[:, channel_index]
        frozen_score = (
            frozen_thresholds.for_channel(channel).threshold
            if frozen_thresholds is not None
            else None
        )
        for run_index, run in enumerate(_finite_runs(time, signal, maximum_gap)):
            if len(run) < 3:
                continue
            if isinstance(spec, PastaTransientDetectorSpec):
                detected, rejected = _detect_pasta(
                    time,
                    signal,
                    run,
                    channel,
                    run_index,
                    sample_step,
                    spec,
                    frozen_score,
                )
            elif isinstance(spec, GuppyTransientDetectorSpec):
                detected, rejected = _detect_guppy(
                    time,
                    signal,
                    run,
                    channel,
                    run_index,
                    sample_step,
                    spec,
                    frozen_score,
                )
            else:
                detected, rejected = _detect_prominence(
                    time,
                    signal,
                    run,
                    channel,
                    run_index,
                    sample_step,
                    spec,
                    frozen_score,
                )
            candidates.extend(detected)
            exclusions.extend(rejected)
    candidates.sort(key=lambda item: (item.channel, item.peak_time, item.sample_index))
    return TransientCandidateResult(
        spec, variable, tuple(candidates), tuple(exclusions), frozen_thresholds
    )


def cut_transient_waveforms(
    recording: xr.Dataset,
    candidates: TransientCandidateResult,
    *,
    variable: str,
    spec: TransientWaveformSpec | None = None,
) -> TransientWaveformResult:
    """Retain native candidate cutouts without crossing gaps or interpolating."""
    chosen = spec or TransientWaveformSpec()
    time, values, channels = _recording_values(recording, variable)
    channel_indices = {channel: index for index, channel in enumerate(channels)}
    sample_step = float(np.median(np.diff(time)))
    maximum_gap = chosen.maximum_gap_factor * sample_step
    runs_by_channel = {
        channel: _finite_runs(time, values[:, index], maximum_gap)
        for index, channel in enumerate(channels)
    }
    candidate_ids = [item.candidate_id for item in candidates.candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("transient candidate IDs must be unique")
    cutouts = []
    for candidate in candidates.candidates:
        channel_index = channel_indices.get(candidate.channel)
        if channel_index is None or not _candidate_matches(time, candidate):
            raise ValueError(
                f"candidate {candidate.candidate_id!r} does not match the recording"
            )
        _, run = _run_containing(
            runs_by_channel[candidate.channel], candidate.sample_index
        )
        if run is None:
            raise ValueError(
                f"candidate {candidate.candidate_id!r} is outside finite continuity"
            )
        signal = values[:, channel_index]
        cutouts.append(
            _cut_waveform(
                time,
                signal,
                run,
                candidate,
                candidates.candidates,
                chosen,
                sample_step,
            )
        )
    fingerprint = _waveform_fingerprint(chosen, variable, candidates, tuple(cutouts))
    return TransientWaveformResult(
        chosen,
        variable,
        candidates.variable,
        tuple(cutouts),
        fingerprint,
    )


def quantify_transient_candidates(
    recording: xr.Dataset,
    candidates: TransientCandidateResult,
    *,
    variable: str,
    spec: TransientQuantificationSpec | None = None,
    waveforms: TransientWaveformResult | None = None,
) -> TransientQuantificationResult:
    """Measure candidates on a possibly different, non-normalized signal stream."""
    chosen = spec or TransientQuantificationSpec()
    _validate_quantification_spec(chosen)
    if chosen.require_waveform_qc and waveforms is None:
        raise ValueError("require_waveform_qc requires waveform evidence")
    if waveforms is not None:
        if waveforms.variable != variable:
            raise ValueError("waveform evidence variable must match quantification")
        if waveforms.detector_variable != candidates.variable:
            raise ValueError("waveform detector variable must match candidates")
        waveform_ids = {item.candidate_id for item in waveforms.waveforms}
        expected_ids = {item.candidate_id for item in candidates.candidates}
        if waveform_ids != expected_ids:
            raise ValueError("waveform evidence must cover exactly the candidate set")
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
        if chosen.require_waveform_qc:
            assert waveforms is not None
            waveform = waveforms.for_candidate(candidate.candidate_id)
            unacceptable = waveform.status == "fail" or (
                waveform.status == "warning" and not chosen.allow_waveform_warnings
            )
            if unacceptable:
                exclusions.append(
                    _quantification_exclusion(candidate, "waveform_qc_failed")
                )
                continue
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
                frozen_score_threshold=candidate.frozen_score_threshold,
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
        waveforms.evidence_fingerprint if waveforms is not None else None,
    )


def _detect_pasta(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    channel: str,
    run_index: int,
    sample_step: float,
    spec: PastaTransientDetectorSpec,
    frozen_score_threshold: float | None,
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
                _candidate_exclusion(
                    spec,
                    channel,
                    peak,
                    time,
                    "below_threshold",
                    amplitude,
                    spec.amplitude_threshold,
                )
            )
            continue
        if frozen_score_threshold is not None and amplitude < frozen_score_threshold:
            rejected.append(
                _candidate_exclusion(
                    spec,
                    channel,
                    peak,
                    time,
                    "below_frozen_threshold",
                    amplitude,
                    frozen_score_threshold,
                )
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
                frozen_score_threshold,
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
    frozen_score_threshold: float | None,
) -> tuple[list[TransientCandidate], list[TransientCandidateExclusion]]:
    chunk_samples = max(3, int(np.ceil(spec.chunk_duration_s / sample_step)))
    accepted: list[TransientCandidate] = []
    rejected: list[TransientCandidateExclusion] = []
    for chunk_start in range(0, len(run), chunk_samples):
        chunk = run[chunk_start : chunk_start + chunk_samples]
        maxima = _run_interior_maxima(signal, run, chunk)
        if len(chunk) < 3:
            rejected.extend(
                _candidate_exclusion(
                    spec, channel, int(chunk[position]), time, "chunk_boundary"
                )
                for position in maxima
            )
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
        if filtered_mad <= 0:
            rejected.extend(
                _candidate_exclusion(
                    spec, channel, int(chunk[position]), time, "degenerate_noise_scale"
                )
                for position in maxima
            )
            continue
        threshold = filtered_median + spec.detection_mad * filtered_mad
        rejected.extend(
            _candidate_exclusion(
                spec,
                channel,
                int(chunk[position]),
                time,
                "chunk_boundary",
                float(signal[chunk[position]]),
                threshold,
            )
            for position in maxima
            if position in (0, len(chunk) - 1)
            and float(signal[chunk[position]]) > threshold
        )
        thresholded = np.where(chunk_values > threshold, chunk_values, 0.0)
        peaks = 1 + np.flatnonzero(
            (thresholded[1:-1] > thresholded[:-2])
            & (thresholded[1:-1] > thresholded[2:])
        )
        for position in peaks:
            peak = int(chunk[position])
            amplitude = float(signal[peak] - filtered_median)
            if (
                frozen_score_threshold is not None
                and amplitude < frozen_score_threshold
            ):
                rejected.append(
                    _candidate_exclusion(
                        spec,
                        channel,
                        peak,
                        time,
                        "below_frozen_threshold",
                        amplitude,
                        frozen_score_threshold,
                    )
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
                    filtered_median,
                    amplitude,
                    threshold,
                    amplitude,
                    frozen_score_threshold,
                )
            )
    return accepted, rejected


def _run_interior_maxima(
    signal: np.ndarray, run: np.ndarray, chunk: np.ndarray
) -> np.ndarray:
    index = np.asarray(chunk, dtype=int)
    interior = (index > int(run[0])) & (index < int(run[-1]))
    inside = index[interior]
    maximum = np.zeros(len(index), dtype=bool)
    maximum[interior] = (signal[inside] > signal[inside - 1]) & (
        signal[inside] > signal[inside + 1]
    )
    return np.flatnonzero(maximum)


def _detect_prominence(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    channel: str,
    run_index: int,
    sample_step: float,
    spec: ProminenceTransientDetectorSpec,
    frozen_score_threshold: float | None,
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
    accepted = []
    rejected = []
    for position, prominence in zip(peaks, prominences, strict=True):
        peak = int(run[position])
        score = float(prominence)
        if frozen_score_threshold is not None and score < frozen_score_threshold:
            rejected.append(
                _candidate_exclusion(
                    spec,
                    channel,
                    peak,
                    time,
                    "below_frozen_threshold",
                    score,
                    frozen_score_threshold,
                )
            )
            continue
        accepted.append(
            _candidate(
                spec,
                channel,
                run_index,
                peak,
                time,
                float(zscore[position]),
                0.0,
                float(zscore[position]),
                spec.minimum_height_z,
                score,
                frozen_score_threshold,
            )
        )
    return accepted, rejected


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
    frozen_score_threshold: float | None = None,
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
        frozen_score_threshold=frozen_score_threshold,
    )


def _candidate_exclusion(
    spec: TransientDetectorSpec,
    channel: str,
    peak: int,
    time: np.ndarray,
    reason: CandidateExclusionReason,
    observed_score: float | None = None,
    required_score: float | None = None,
) -> TransientCandidateExclusion:
    return TransientCandidateExclusion(
        spec.family,
        channel,
        peak,
        float(time[peak]),
        reason,
        observed_score,
        required_score,
    )


def _quantification_exclusion(
    candidate: TransientCandidate, reason: QuantificationExclusionReason
) -> TransientQuantificationExclusion:
    return TransientQuantificationExclusion(
        candidate.candidate_id, candidate.channel, candidate.peak_time, reason
    )


def _calibration_scores(
    time: np.ndarray,
    signal: np.ndarray,
    runs: list[np.ndarray],
    sample_step: float,
    spec: TransientDetectorSpec,
) -> np.ndarray:
    scores = []
    for run in runs:
        if len(run) < 3:
            continue
        if isinstance(spec, PastaTransientDetectorSpec):
            distance = max(1, int(np.ceil(spec.minimum_distance_s / sample_step)))
            peaks, _ = find_peaks(signal[run], distance=distance)
            for position in peaks:
                peak = int(run[position])
                rows = _baseline_rows(time, run, peak, spec)
                if len(rows) < 2:
                    continue
                baseline = _baseline_value(signal, rows, spec.baseline_method)
                if baseline is not None:
                    scores.append(float(signal[peak] - baseline))
        elif isinstance(spec, GuppyTransientDetectorSpec):
            chunk_samples = max(3, int(np.ceil(spec.chunk_duration_s / sample_step)))
            for chunk_start in range(0, len(run), chunk_samples):
                chunk = run[chunk_start : chunk_start + chunk_samples]
                if len(chunk) < 3:
                    continue
                values = signal[chunk]
                median = float(np.median(values))
                mad = float(np.median(np.abs(values - median)))
                high = median + spec.high_amplitude_mad * mad
                filtered = values[values <= high]
                if not len(filtered):
                    continue
                baseline = float(np.median(filtered))
                peaks, _ = find_peaks(values)
                scores.extend(float(values[position] - baseline) for position in peaks)
        else:
            values = _prominence_values(signal[run], sample_step, spec)
            if values is None:
                continue
            distance = max(1, int(np.ceil(spec.minimum_distance_s / sample_step)))
            peaks, _ = find_peaks(values, distance=distance)
            if len(peaks):
                scores.extend(
                    float(value) for value in peak_prominences(values, peaks)[0]
                )
    array = np.asarray(scores, dtype=float)
    return np.asarray(array[np.isfinite(array)], dtype=float)


def _prominence_values(
    values: np.ndarray,
    sample_step: float,
    spec: ProminenceTransientDetectorSpec,
) -> np.ndarray | None:
    prepared = np.asarray(values, dtype=float)
    if spec.detrend_window_s is not None:
        window = min(len(prepared), max(1, round(spec.detrend_window_s / sample_step)))
        kernel = np.ones(window, dtype=float)
        moving = np.convolve(prepared, kernel, mode="same") / np.convolve(
            np.ones(len(prepared)), kernel, mode="same"
        )
        prepared = prepared - moving
    standard_deviation = float(np.std(prepared))
    if standard_deviation <= np.finfo(float).eps:
        return None
    return (prepared - float(np.mean(prepared))) / standard_deviation


def _validate_frozen_thresholds(
    thresholds: FrozenTransientThresholds | None,
    detector_spec: TransientDetectorSpec,
    variable: str,
    channels: list[str],
) -> None:
    if thresholds is None:
        return
    if thresholds.detector_spec != detector_spec:
        raise ValueError("frozen thresholds are bound to a different detector spec")
    if thresholds.detector_variable != variable:
        raise ValueError("frozen thresholds are bound to a different variable")
    calibrated = [item.channel for item in thresholds.channels]
    if calibrated != channels:
        raise ValueError("frozen threshold channels must exactly match the recording")


def _threshold_fingerprint(
    time: np.ndarray,
    values: np.ndarray,
    detector_spec: TransientDetectorSpec,
    variable: str,
    source_role: ThresholdSourceRole,
    source_id: str,
    preprocessing_fingerprint: str,
    calibration_spec: TransientThresholdCalibrationSpec,
    channels: list[ChannelFrozenTransientThreshold],
) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(time, dtype="<f8").tobytes())
    digest.update(np.asarray(values, dtype="<f8").tobytes())
    digest.update(
        json.dumps(
            {
                "detector_spec": asdict(detector_spec),
                "variable": variable,
                "source_role": source_role,
                "source_id": source_id,
                "preprocessing_fingerprint": preprocessing_fingerprint,
                "calibration_spec": asdict(calibration_spec),
                "channels": [asdict(item) for item in channels],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    return digest.hexdigest()


def _cut_waveform(
    time: np.ndarray,
    signal: np.ndarray,
    run: np.ndarray,
    candidate: TransientCandidate,
    all_candidates: tuple[TransientCandidate, ...],
    spec: TransientWaveformSpec,
    sample_step: float,
) -> TransientWaveform:
    requested_start = candidate.peak_time - spec.pre_peak_s
    requested_stop = candidate.peak_time + spec.post_peak_s
    selected = run[(time[run] >= requested_start) & (time[run] <= requested_stop)]
    if not len(
        selected
    ):  # pragma: no cover - matching finite candidate guarantees this
        raise ValueError(
            f"candidate {candidate.candidate_id!r} has no waveform samples"
        )
    observed_time = time[selected]
    observed_values = signal[selected]
    relative = observed_time - candidate.peak_time
    pre_coverage = float(candidate.peak_time - observed_time[0])
    post_coverage = float(observed_time[-1] - candidate.peak_time)
    complete_pre = pre_coverage + sample_step * 1.01 >= spec.pre_peak_s
    complete_post = post_coverage + sample_step * 1.01 >= spec.post_peak_s
    coverage = float(
        (min(pre_coverage, spec.pre_peak_s) + min(post_coverage, spec.post_peak_s))
        / (spec.pre_peak_s + spec.post_peak_s)
    )
    issues: list[TransientWaveformIssue] = []
    boundary_severity: WaveformIssueSeverity = (
        "error" if spec.require_complete_window else "warning"
    )
    if not complete_pre:
        issues.append(
            TransientWaveformIssue(
                boundary_severity,
                "pre_window_truncated",
                candidate.candidate_id,
                "pre-peak cutout stops at a recording boundary or acquisition gap",
                pre_coverage,
            )
        )
    if not complete_post:
        issues.append(
            TransientWaveformIssue(
                boundary_severity,
                "post_window_truncated",
                candidate.candidate_id,
                "post-peak cutout stops at a recording boundary or acquisition gap",
                post_coverage,
            )
        )
    baseline_values = observed_values[relative < 0]
    baseline_time = relative[relative < 0]
    baseline_median = (
        float(np.median(baseline_values)) if len(baseline_values) else None
    )
    baseline_sd = float(np.std(baseline_values)) if len(baseline_values) else None
    baseline_slope = (
        float(np.polyfit(baseline_time, baseline_values, 1)[0])
        if len(baseline_values) >= 2
        else None
    )
    flat_fraction = _waveform_flat_fraction(observed_values)
    _maximum_waveform_issue(
        flat_fraction,
        spec.maximum_flat_step_fraction_warning,
        spec.maximum_flat_step_fraction_error,
        "flat_step_fraction",
        candidate.candidate_id,
        issues,
    )
    saturation = _waveform_saturation_fraction(observed_values, spec)
    if saturation is not None:
        _maximum_waveform_issue(
            saturation,
            spec.maximum_saturation_fraction_warning,
            spec.maximum_saturation_fraction_error,
            "detector_saturation_fraction",
            candidate.candidate_id,
            issues,
        )
    nearby = tuple(
        item.candidate_id
        for item in all_candidates
        if item.candidate_id != candidate.candidate_id
        and item.channel == candidate.channel
        and requested_start <= item.peak_time <= requested_stop
    )
    if nearby and spec.warn_nearby_candidates:
        issues.append(
            TransientWaveformIssue(
                "warning",
                "nearby_candidate_in_window",
                candidate.candidate_id,
                "another detected candidate lies inside the requested cutout",
                ",".join(nearby),
            )
        )
    status: WaveformStatus = (
        "fail"
        if any(item.severity == "error" for item in issues)
        else "warning"
        if issues
        else "pass"
    )
    return TransientWaveform(
        candidate.candidate_id,
        candidate.channel,
        candidate.peak_time,
        candidate.sample_index,
        tuple(float(value) for value in relative),
        tuple(float(value) for value in observed_values),
        len(selected),
        requested_start,
        requested_stop,
        float(observed_time[0]),
        float(observed_time[-1]),
        pre_coverage,
        post_coverage,
        coverage,
        baseline_median,
        baseline_sd,
        baseline_slope,
        flat_fraction,
        saturation,
        nearby,
        tuple(issues),
        status,
    )


def _waveform_flat_fraction(values: np.ndarray) -> float:
    if len(values) < 2:
        return float("nan")
    return float(np.mean(np.diff(values) == 0))


def _waveform_saturation_fraction(
    values: np.ndarray, spec: TransientWaveformSpec
) -> float | None:
    if spec.detector_floor is None or spec.detector_ceiling is None:
        return None
    saturated = (values <= spec.detector_floor + spec.saturation_tolerance) | (
        values >= spec.detector_ceiling - spec.saturation_tolerance
    )
    return float(np.mean(saturated))


def _maximum_waveform_issue(
    value: float,
    warning: float,
    error: float,
    code: str,
    candidate_id: str,
    issues: list[TransientWaveformIssue],
) -> None:
    if not np.isfinite(value) or value <= warning:
        return
    severity: WaveformIssueSeverity = "error" if value > error else "warning"
    issues.append(
        TransientWaveformIssue(
            severity,
            code,
            candidate_id,
            f"{code.replace('_', ' ')} crosses the {severity} threshold",
            value,
        )
    )


def _waveform_fingerprint(
    spec: TransientWaveformSpec,
    variable: str,
    candidates: TransientCandidateResult,
    waveforms: tuple[TransientWaveform, ...],
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "spec": asdict(spec),
                "variable": variable,
                "detector_variable": candidates.variable,
                "candidate_ids": [item.candidate_id for item in candidates.candidates],
                "frozen_threshold_fingerprint": (
                    candidates.frozen_thresholds.calibration_fingerprint
                    if candidates.frozen_thresholds is not None
                    else None
                ),
                "waveforms": [asdict(item) for item in waveforms],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _validate_nested_maximum(warning: float, error: float, name: str) -> None:
    if not 0 <= warning <= error <= 1:
        raise ValueError(f"{name} thresholds must satisfy 0 <= warning <= error <= 1")


def _nonempty(value: str, name: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError(f"{name} must be non-empty")
    return cleaned


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
