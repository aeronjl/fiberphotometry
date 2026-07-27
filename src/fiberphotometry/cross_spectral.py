"""Gap-aware cross-spectral coherence and phase for declared signal pairs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import signal

from fiberphotometry.multisignal import (
    JointContinuityEvidence,
    SignalPairMetadata,
    _prepare_pair,
    _PreparedPair,
)
from fiberphotometry.spectral import (
    SpectralAnalysisSpec,
    StateEpoch,
    _state_partitions,
)


@dataclass(frozen=True)
class CoherencePhaseResult:
    """Pooled cross-spectrum, magnitude-squared coherence, and relative phase."""

    pair: SignalPairMetadata
    spec: SpectralAnalysisSpec
    frequencies_hz: tuple[float, ...]
    coherence: tuple[float, ...]
    phase_radians: tuple[float, ...]
    cross_power_density_real: tuple[float, ...]
    cross_power_density_imaginary: tuple[float, ...]
    first_power_density: tuple[float, ...]
    second_power_density: tuple[float, ...]
    windows_per_run: tuple[int, ...]
    total_window_count: int
    evidence: JointContinuityEvidence
    cross_power_density_unit: str
    phase_convention: str = "angle_of_conjugate_first_fft_times_second_fft"
    method: str = "window_weighted_gap_separated_welch_cross_spectrum"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize cross-spectral values and joint continuity evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class StateCoherencePhase:
    """One supplied state and its cross-spectral result."""

    state: str
    epoch_count: int
    assigned_sample_count: int
    result: CoherencePhaseResult


@dataclass(frozen=True)
class StateConditionedCoherenceResult:
    """Cross-spectral results separated by user-supplied state epochs."""

    states: tuple[StateCoherencePhase, ...]
    epoch_count: int
    unassigned_sample_count: int
    overlap_policy: str = "error"
    schema_version: str = "1"

    def to_json(self) -> str:
        """Serialize state-conditioned cross-spectral evidence."""
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class CoherenceBandSummary:
    """One declared frequency-band summary from a pooled cross-spectrum."""

    pair_id: str
    frequency_band_hz: tuple[float, float]
    mean_coherence: float
    cross_spectrum_phase_radians: float
    integrated_cross_power_magnitude: float
    frequency_bin_count: int
    total_window_count: int
    method: str = "band_mean_coherence_and_integrated_cross_spectrum_phase"


def coherence_phase(
    time: ArrayLike,
    first: ArrayLike,
    second: ArrayLike,
    pair: SignalPairMetadata,
    spec: SpectralAnalysisSpec | None = None,
    *,
    valid_first: ArrayLike | None = None,
    valid_second: ArrayLike | None = None,
) -> CoherencePhaseResult:
    """Estimate coherence and phase without pooling across acquisition gaps."""
    spec = spec or SpectralAnalysisSpec()
    prepared = _prepare_pair(
        time,
        first,
        second,
        valid_first,
        valid_second,
        spec.gap,
    )
    return _coherence_from_prepared(prepared, pair, spec)


def state_conditioned_coherence(
    time: ArrayLike,
    first: ArrayLike,
    second: ArrayLike,
    pair: SignalPairMetadata,
    epochs: tuple[StateEpoch, ...] | list[StateEpoch],
    spec: SpectralAnalysisSpec | None = None,
    *,
    valid_first: ArrayLike | None = None,
    valid_second: ArrayLike | None = None,
) -> StateConditionedCoherenceResult:
    """Estimate cross-spectra within, but never across, supplied state epochs."""
    spec = spec or SpectralAnalysisSpec()
    time_values = np.asarray(time, dtype=float)
    partitions, assigned = _state_partitions(time_values, epochs)
    output = []
    for state in sorted(partitions):
        prepared = _prepare_pair(
            time_values,
            first,
            second,
            valid_first,
            valid_second,
            spec.gap,
            partition=partitions[state],
        )
        output.append(
            StateCoherencePhase(
                state,
                sum(epoch.state == state for epoch in epochs),
                int(np.count_nonzero(partitions[state] >= 0)),
                _coherence_from_prepared(prepared, pair, spec),
            )
        )
    return StateConditionedCoherenceResult(
        tuple(output),
        len(epochs),
        int(np.count_nonzero(~assigned)),
    )


def summarize_coherence_band(
    result: CoherencePhaseResult,
    frequency_band_hz: tuple[float, float],
) -> CoherenceBandSummary:
    """Integrate a declared band without treating frequency bins as replicates."""
    low, high = frequency_band_hz
    if low < 0 or low >= high:
        raise ValueError("frequency band must be increasing and non-negative")
    frequency = np.asarray(result.frequencies_hz, dtype=float)
    if low < frequency[0] or high > frequency[-1]:
        raise ValueError("cross-spectrum does not cover the requested band")
    coherence_values = np.asarray(result.coherence, dtype=float)
    cross_power = np.asarray(
        result.cross_power_density_real, dtype=float
    ) + 1j * np.asarray(result.cross_power_density_imaginary, dtype=float)
    interior = (frequency > low) & (frequency < high)
    integration_frequency = np.concatenate(([low], frequency[interior], [high]))
    integration_coherence = np.interp(
        integration_frequency, frequency, coherence_values
    )
    integration_cross = np.interp(
        integration_frequency, frequency, cross_power.real
    ) + 1j * np.interp(integration_frequency, frequency, cross_power.imag)
    mean_coherence = float(
        np.trapezoid(integration_coherence, integration_frequency) / (high - low)
    )
    integrated_cross = np.trapezoid(integration_cross, integration_frequency)
    return CoherenceBandSummary(
        result.pair.pair_id,
        frequency_band_hz,
        mean_coherence,
        float(np.angle(integrated_cross)),
        float(abs(integrated_cross)),
        int(np.count_nonzero((frequency >= low) & (frequency <= high))),
        result.total_window_count,
    )


def _coherence_from_prepared(
    prepared: _PreparedPair,
    pair: SignalPairMetadata,
    spec: SpectralAnalysisSpec,
) -> CoherencePhaseResult:
    rate = prepared.evidence.continuity.sampling_rate_hz
    samples = round(spec.window_duration_s * rate)
    if samples < 4:
        raise ValueError("cross-spectral window must contain at least four samples")
    overlap = int(np.floor(samples * spec.overlap_fraction))
    step = samples - overlap
    frequencies: NDArray[np.float64] | None = None
    first_spectra: list[NDArray[np.float64]] = []
    second_spectra: list[NDArray[np.float64]] = []
    cross_spectra: list[NDArray[np.complex128]] = []
    weights: list[int] = []
    counts = []
    detrend: str | bool = False if spec.detrend == "none" else spec.detrend
    for indices in prepared.indices:
        count = max(0, 1 + (len(indices) - samples) // step)
        counts.append(count)
        if count == 0:
            continue
        run_frequency, first_power = signal.welch(  # type: ignore[call-overload]
            prepared.first[indices],
            fs=rate,
            window=spec.window,
            nperseg=samples,
            noverlap=overlap,
            nfft=samples,
            detrend=detrend,
            scaling="density",
            average="mean",
        )
        _, second_power = signal.welch(  # type: ignore[call-overload]
            prepared.second[indices],
            fs=rate,
            window=spec.window,
            nperseg=samples,
            noverlap=overlap,
            nfft=samples,
            detrend=detrend,
            scaling="density",
            average="mean",
        )
        _, cross_power = signal.csd(  # type: ignore[call-overload]
            prepared.first[indices],
            prepared.second[indices],
            fs=rate,
            window=spec.window,
            nperseg=samples,
            noverlap=overlap,
            nfft=samples,
            detrend=detrend,
            scaling="density",
            average="mean",
        )
        frequencies = np.asarray(run_frequency, dtype=float)
        first_spectra.append(np.asarray(first_power, dtype=float))
        second_spectra.append(np.asarray(second_power, dtype=float))
        cross_spectra.append(np.asarray(cross_power, dtype=np.complex128))
        weights.append(count)
    if not cross_spectra or frequencies is None:
        raise ValueError("no joint continuity run contains a complete spectral window")
    window_weights = np.asarray(weights, dtype=float)
    first_power = np.average(np.asarray(first_spectra), axis=0, weights=window_weights)
    second_power = np.average(
        np.asarray(second_spectra), axis=0, weights=window_weights
    )
    cross_power = np.average(np.asarray(cross_spectra), axis=0, weights=window_weights)
    denominator = first_power * second_power
    coherence_values = np.divide(
        np.abs(cross_power) ** 2,
        denominator,
        out=np.full_like(first_power, np.nan),
        where=denominator > 0,
    )
    coherence_values = np.clip(coherence_values, 0, 1)
    selected = np.ones(len(frequencies), dtype=bool)
    if spec.maximum_frequency_hz is not None:
        selected &= frequencies <= spec.maximum_frequency_hz
    unit = f"{pair.first.unit}*{pair.second.unit}/Hz"
    return CoherencePhaseResult(
        pair,
        spec,
        _float_tuple(frequencies[selected]),
        _float_tuple(coherence_values[selected]),
        _float_tuple(np.angle(cross_power[selected])),
        _float_tuple(cross_power.real[selected]),
        _float_tuple(cross_power.imag[selected]),
        _float_tuple(first_power[selected]),
        _float_tuple(second_power[selected]),
        tuple(counts),
        int(sum(counts)),
        prepared.evidence,
        unit,
    )


def _float_tuple(values: ArrayLike) -> tuple[float, ...]:
    return tuple(float(value) for value in np.asarray(values, dtype=float))
