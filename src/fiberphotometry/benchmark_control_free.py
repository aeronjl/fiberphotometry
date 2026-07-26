"""Signal-only bleaching benchmark frozen in protocol-control-free-v0.1."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fiberphotometry.preprocess import baseline_dff
from fiberphotometry.simulate import simulate_bleaching_recording


@dataclass(frozen=True)
class ControlFreeBenchmarkResult:
    scenario: str
    method: str
    seed: int
    ground_truth_correlation: float
    ground_truth_rmse: float
    event_amplitude_relative_bias: float


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


def _event_amplitude(time: np.ndarray, values: np.ndarray, events: np.ndarray) -> float:
    amplitudes = []
    for event in events:
        baseline = values[(time >= event - 1) & (time < event)]
        response = values[(time >= event) & (time < event + 1)]
        amplitudes.append(float(np.mean(response) - np.mean(baseline)))
    return float(np.median(amplitudes))
