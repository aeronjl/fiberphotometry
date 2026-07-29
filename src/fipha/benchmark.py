"""Reproducible ground-truth preprocessing benchmarks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fipha.preprocess import reference_dff
from fipha.simulate import simulate_recording


@dataclass(frozen=True)
class BenchmarkResult:
    """Recovery metrics for one simulation and correction method."""

    scenario: str
    method: str
    seed: int
    slope_error: float
    neural_correlation: float
    null_rms: float


def run_reference_benchmark(
    *, scenario: str, seed: int, method: str
) -> BenchmarkResult:
    """Run one scenario defined by the frozen v0.1 benchmark protocol."""
    parameters = _scenario_parameters(scenario)
    recording, _ = simulate_recording(seed=seed, **parameters)
    corrected = reference_dff(recording, method=method)
    recovered = np.asarray(corrected.dff.values[:, 0])
    truth = np.asarray(recording.ground_truth_neural.values[:, 0])
    finite = np.isfinite(recovered) & np.isfinite(truth)
    correlation = float(np.corrcoef(recovered[finite], truth[finite])[0, 1])
    null = finite & np.isclose(truth, 0)
    null_rms = float(np.sqrt(np.mean(np.square(recovered[null]))))
    slope = float(corrected.reference_fit_coefficient.values[0, 1])
    return BenchmarkResult(
        scenario=scenario,
        method=method,
        seed=seed,
        slope_error=abs(slope - 1.4),
        neural_correlation=correlation,
        null_rms=null_rms,
    )


def _scenario_parameters(scenario: str) -> dict[str, float]:
    scenarios = {
        "linear_shared_artifact": {
            "artifact_scale": 0.25,
            "transient_scale": 0.08,
            "reference_contamination": 0.0,
        },
        "large_neural_transients": {
            "artifact_scale": 0.25,
            "transient_scale": 0.40,
            "reference_contamination": 0.0,
        },
        "reference_contamination": {
            "artifact_scale": 0.25,
            "transient_scale": 0.08,
            "reference_contamination": 0.04,
        },
    }
    try:
        return scenarios[scenario]
    except KeyError as error:
        raise ValueError(f"unknown benchmark scenario {scenario!r}") from error
