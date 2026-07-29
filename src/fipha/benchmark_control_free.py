"""Signal-only bleaching benchmark frozen in protocol-control-free-v0.1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

import numpy as np

from fipha.preprocess import baseline_dff
from fipha.simulate import (
    simulate_bleaching_recording,
    simulate_normalization_recording,
)


@dataclass(frozen=True)
class ControlFreeBenchmarkResult:
    scenario: str
    method: str
    seed: int
    ground_truth_correlation: float
    ground_truth_rmse: float
    event_amplitude_relative_bias: float


@dataclass(frozen=True)
class BaselineFidelityResult:
    scenario: str
    method: str
    seed: int
    rate_hz: float
    effective_asls_smoothness: float | None
    baseline_relative_rmse: float
    corrected_trace_correlation: float
    corrected_trace_rmse: float
    event_amplitude_relative_bias: float


@dataclass(frozen=True)
class NormalizationResult:
    mechanism: str
    normalization: str
    seed: int
    early_event_amplitude: float
    late_event_amplitude: float
    fractional_amplitude_change: float


def run_control_free_benchmark(
    *, scenario: str, method: str, seed: int
) -> ControlFreeBenchmarkResult:
    """Run one frozen signal-only bleaching benchmark case."""
    recording, events = simulate_bleaching_recording(scenario=scenario, seed=seed)
    result = baseline_dff(recording, method=method)
    estimated = np.asarray(result.dff.values[:, 0], dtype=float)
    truth = np.asarray(recording.ground_truth_dff.values[:, 0], dtype=float)
    valid = np.isfinite(estimated) & np.isfinite(truth)
    if valid.sum() < 3:
        raise ValueError("method produced fewer than three finite benchmark samples")
    correlation = float(np.corrcoef(estimated[valid], truth[valid])[0, 1])
    rmse = float(np.sqrt(np.mean((estimated[valid] - truth[valid]) ** 2)))
    estimated_amplitude = _event_amplitude(recording.time.values, estimated, events)
    truth_amplitude = _event_amplitude(recording.time.values, truth, events)
    relative_bias = float((estimated_amplitude - truth_amplitude) / truth_amplitude)
    return ControlFreeBenchmarkResult(
        scenario,
        method,
        seed,
        correlation,
        rmse,
        relative_bias,
    )


def run_baseline_fidelity_benchmark(
    *, scenario: str, method: str, seed: int, rate_hz: float
) -> BaselineFidelityResult:
    """Run one v0.2 baseline-fidelity cell."""
    recording, events = simulate_bleaching_recording(
        scenario=scenario, seed=seed, rate=rate_hz
    )
    result = baseline_dff(recording, method=method)
    baseline = np.asarray(result.fitted_baseline.values[:, 0], dtype=float)
    truth_baseline = np.asarray(
        recording.ground_truth_baseline.values[:, 0], dtype=float
    )
    estimated = np.asarray(result.dff.values[:, 0], dtype=float)
    truth = np.asarray(recording.ground_truth_dff.values[:, 0], dtype=float)
    valid = np.isfinite(baseline) & np.isfinite(estimated)
    baseline_rmse = float(
        np.sqrt(
            np.mean(
                ((baseline[valid] - truth_baseline[valid]) / truth_baseline[valid]) ** 2
            )
        )
    )
    correlation = float(np.corrcoef(estimated[valid], truth[valid])[0, 1])
    corrected_rmse = float(np.sqrt(np.mean((estimated[valid] - truth[valid]) ** 2)))
    estimated_amplitude = _event_amplitude(recording.time.values, estimated, events)
    truth_amplitude = _event_amplitude(recording.time.values, truth, events)
    operation = result.attrs["fipha_baseline_dff"]
    effective = None
    if method == "asls":
        effective = float(json.loads(operation)["effective_smoothness"])
    return BaselineFidelityResult(
        scenario,
        method,
        seed,
        rate_hz,
        effective,
        baseline_rmse,
        correlation,
        corrected_rmse,
        float((estimated_amplitude - truth_amplitude) / truth_amplitude),
    )


def run_normalization_benchmark(
    *, mechanism: str, normalization: Literal["divide", "subtract"], seed: int
) -> NormalizationResult:
    """Run one v0.2 subtraction-versus-division cell."""
    recording, events = simulate_normalization_recording(mechanism=mechanism, seed=seed)
    result = baseline_dff(recording, normalization=normalization)
    variable = "dff" if normalization == "divide" else "baseline_subtracted"
    values = np.asarray(result[variable].values[:, 0], dtype=float)
    split = len(events) // 3
    early = _event_amplitude(recording.time.values, values, events[:split])
    late = _event_amplitude(recording.time.values, values, events[-split:])
    return NormalizationResult(
        mechanism,
        normalization,
        seed,
        early,
        late,
        float((late - early) / early),
    )


def _event_amplitude(time: np.ndarray, values: np.ndarray, events: np.ndarray) -> float:
    amplitudes = []
    for event in events:
        baseline = values[(time >= event - 1) & (time < event)]
        response = values[(time >= event) & (time < event + 1)]
        amplitudes.append(float(np.mean(response) - np.mean(baseline)))
    return float(np.median(amplitudes))
