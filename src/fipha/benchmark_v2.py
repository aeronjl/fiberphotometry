"""Scenario matrix frozen in preprocessing benchmark protocol v0.2."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fipha.preprocess import reference_dff
from fipha.qc import assess_recording
from fipha.simulate import simulate_recording


@dataclass(frozen=True)
class BenchmarkV2Result:
    scenario: str
    method: str
    seed: int
    ground_truth_correlation: float
    ground_truth_rmse: float
    event_amplitude_bias: float
    null_rms: float
    shared_artifact_slope_error: float
    warning_count: int
    warnings: tuple[str, ...]


def run_benchmark_v2(*, scenario: str, method: str, seed: int) -> BenchmarkV2Result:
    """Run one pre-specified v0.2 scenario and correction method."""
    recording, event_times = simulate_recording(seed=seed, **_parameters(scenario))
    corrected = reference_dff(recording, method=method)
    recovered = np.asarray(corrected.dff.values[:, 0], dtype=float)
    truth = np.asarray(recording.ground_truth_dff.values[:, 0], dtype=float)
    valid = np.isfinite(recovered) & np.isfinite(truth)
    null = valid & np.isclose(truth, 0)
    time = np.asarray(recording.time.values, dtype=float)
    event = np.zeros_like(valid)
    for event_time in event_times:
        event |= (time >= event_time) & (time < event_time + 2.0)
    event &= valid
    qc = assess_recording(recording).channels[0]
    fitted_slope = qc.irls_slope if method == "irls" else qc.ols_slope
    return BenchmarkV2Result(
        scenario=scenario,
        method=method,
        seed=seed,
        ground_truth_correlation=float(
            np.corrcoef(recovered[valid], truth[valid])[0, 1]
        ),
        ground_truth_rmse=float(
            np.sqrt(np.mean(np.square(recovered[valid] - truth[valid])))
        ),
        event_amplitude_bias=float(np.mean(recovered[event]) - np.mean(truth[event])),
        null_rms=float(np.sqrt(np.mean(np.square(recovered[null])))),
        shared_artifact_slope_error=float(fitted_slope - 1.4),
        warning_count=len(qc.warnings),
        warnings=qc.warnings,
    )


def _parameters(scenario: str) -> dict[str, float]:
    base = {"transient_scale": 0.4, "artifact_scale": 0.25}
    scenarios = {
        "clean_linear": {},
        "large_transients": {"transient_scale": 0.8},
        "dropout_blocks": {"dropout_fraction": 0.15},
        "event_locked_motion": {"event_artifact_scale": 0.3},
        "nonlinear_coupling": {"nonlinear_signal_scale": 1.0},
        "lagged_reference": {"reference_lag_s": 0.25},
        "reference_contamination": {"reference_contamination": 0.2},
    }
    try:
        return {**base, **scenarios[scenario]}
    except KeyError as error:
        raise ValueError(f"unknown v0.2 scenario {scenario!r}") from error
