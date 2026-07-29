"""Execute the frozen event-kernel interval-coverage protocol v0.1."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from fipha.encoding import (
    EncodingModelResult,
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    LinearProgressBasisSpec,
    MultiplierSimultaneousBandSpec,
    ProgressKernelSpec,
    fit_event_kernel_model,
)

SCENARIOS = (
    "balanced_gaussian",
    "kernel_heterogeneity",
    "autocorrelated_residuals",
    "overlapping_selected_model",
    "blockwise_missingness",
    "normalized_progress",
)
DEFAULT_OUTPUT = (
    Path(__file__).parents[1]
    / "benchmarks"
    / "event-kernel-interval-coverage-v0.1.json"
)


@dataclass(frozen=True)
class SimulationStudy:
    sessions: tuple[EncodingSession, ...]
    model: EncodingModelSpec
    truth: dict[str, tuple[float, ...]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studies", type=int, default=80)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.studies < 1:
        raise SystemExit("--studies must be positive")
    rows = [
        _run_study(scenario, seed)
        for scenario in SCENARIOS
        for seed in range(args.studies)
    ]
    summaries = {
        scenario: _summarize(
            [row for row in rows if row["scenario"] == scenario], args.studies
        )
        for scenario in SCENARIOS
    }
    acceptance = {
        "simultaneous_coverage_at_least_0_85": all(
            item["simultaneous_family_coverage"] >= 0.85 for item in summaries.values()
        ),
        "marginal_pointwise_coverage_at_least_0_90": all(
            item["marginal_pointwise_coverage"] >= 0.90 for item in summaries.values()
        ),
        "all_studies_fit": all(
            item["successful_studies"] == args.studies for item in summaries.values()
        ),
        "all_bounds_finite": all(
            item["all_successful_bounds_finite"] for item in summaries.values()
        ),
        "simultaneous_never_narrower": all(
            item["simultaneous_never_narrower"] for item in summaries.values()
        ),
    }
    payload = {
        "artifact_type": "event_kernel_interval_coverage_benchmark",
        "schema_version": "1",
        "protocol": "protocol-event-kernel-interval-coverage-v0.1.md",
        "protocol_commit": "38656b2d08e8c2df60045e56118dff691d3c5a20",
        "candidate_implementation_commit": ("38f17aa254a91f44f4e4f5bff80bc1fe5b2fff7c"),
        "studies_per_scenario": args.studies,
        "scenarios": list(SCENARIOS),
        "candidate_procedure": {
            "confidence_level": 0.95,
            "method": "jackknife_gaussian_multiplier_max_t",
            "draws": 2_000,
            "seed": 20_260_727,
            "family_scope": "all evaluated event and progress kernel points",
            "conditional_on_selected_alpha": True,
        },
        "summaries": summaries,
        "acceptance": acceptance,
        "all_acceptance_met": all(acceptance.values()),
        "studies": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"summaries": summaries, "acceptance": acceptance}, indent=2))


def _run_study(scenario: str, seed: int) -> dict[str, Any]:
    study = _simulate(scenario, seed)
    try:
        result = fit_event_kernel_model(study.sessions, study.model)
    except Exception as error:  # benchmark retains every declared failure
        return {
            "scenario": scenario,
            "seed": seed,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
        }
    return {
        "scenario": scenario,
        "seed": seed,
        "status": "success",
        "error": None,
        **_coverage_metrics(result, study.truth),
    }


def _coverage_metrics(
    result: EncodingModelResult, truth: dict[str, tuple[float, ...]]
) -> dict[str, Any]:
    point_lower = []
    point_upper = []
    simultaneous_lower = []
    simultaneous_upper = []
    true_values = []
    for interval in result.kernel_uncertainty.event_kernels:
        key = f"event:{interval.name}"
        if interval.simultaneous_lower is None or interval.simultaneous_upper is None:
            raise RuntimeError("calibration model did not emit simultaneous bounds")
        true_values.extend(truth[key])
        point_lower.extend(interval.lower)
        point_upper.extend(interval.upper)
        simultaneous_lower.extend(interval.simultaneous_lower)
        simultaneous_upper.extend(interval.simultaneous_upper)
    for interval in result.kernel_uncertainty.progress_kernels:
        key = f"progress:{interval.name}"
        if interval.simultaneous_lower is None or interval.simultaneous_upper is None:
            raise RuntimeError("calibration model did not emit simultaneous bounds")
        true_values.extend(truth[key])
        point_lower.extend(interval.lower)
        point_upper.extend(interval.upper)
        simultaneous_lower.extend(interval.simultaneous_lower)
        simultaneous_upper.extend(interval.simultaneous_upper)
    true_array = np.asarray(true_values)
    point_lower_array = np.asarray(point_lower)
    point_upper_array = np.asarray(point_upper)
    simultaneous_lower_array = np.asarray(simultaneous_lower)
    simultaneous_upper_array = np.asarray(simultaneous_upper)
    point_covered = (point_lower_array <= true_array) & (
        true_array <= point_upper_array
    )
    simultaneous_covered = (simultaneous_lower_array <= true_array) & (
        true_array <= simultaneous_upper_array
    )
    point_width = point_upper_array - point_lower_array
    simultaneous_width = simultaneous_upper_array - simultaneous_lower_array
    selected = next(
        item for item in result.cross_validation if item.alpha == result.selected_alpha
    )
    arrays = (
        true_array,
        point_lower_array,
        point_upper_array,
        simultaneous_lower_array,
        simultaneous_upper_array,
    )
    return {
        "selected_alpha": result.selected_alpha,
        "held_out_mean_r_squared": selected.mean_r_squared,
        "family_size": len(true_array),
        "marginal_pointwise_coverage": float(np.mean(point_covered)),
        "pointwise_family_covered": bool(np.all(point_covered)),
        "simultaneous_family_covered": bool(np.all(simultaneous_covered)),
        "median_pointwise_width": float(np.median(point_width)),
        "median_simultaneous_width": float(np.median(simultaneous_width)),
        "simultaneous_never_narrower": bool(
            np.all(simultaneous_width + 1e-12 >= point_width)
        ),
        "all_bounds_finite": bool(all(np.all(np.isfinite(item)) for item in arrays)),
        "pointwise_critical_value": (
            result.kernel_uncertainty.pointwise_critical_value
        ),
        "simultaneous_critical_value": (
            result.kernel_uncertainty.simultaneous_critical_value
        ),
    }


def _summarize(rows: list[dict[str, Any]], expected: int) -> dict[str, Any]:
    successful = [row for row in rows if row["status"] == "success"]
    return {
        "declared_studies": expected,
        "successful_studies": len(successful),
        "failed_studies": expected - len(successful),
        "marginal_pointwise_coverage": _mean(successful, "marginal_pointwise_coverage"),
        "pointwise_family_coverage": _mean(successful, "pointwise_family_covered"),
        "simultaneous_family_coverage": _mean(
            successful, "simultaneous_family_covered"
        ),
        "median_pointwise_width": _median(successful, "median_pointwise_width"),
        "median_simultaneous_width": _median(successful, "median_simultaneous_width"),
        "median_simultaneous_critical_value": _median(
            successful, "simultaneous_critical_value"
        ),
        "all_successful_bounds_finite": bool(successful)
        and all(row["all_bounds_finite"] for row in successful),
        "simultaneous_never_narrower": bool(successful)
        and all(row["simultaneous_never_narrower"] for row in successful),
    }


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    return float(np.mean([row[key] for row in rows])) if rows else None


def _median(rows: list[dict[str, Any]], key: str) -> float | None:
    return float(np.median([row[key] for row in rows])) if rows else None


def _simulate(scenario: str, seed: int) -> SimulationStudy:
    if scenario == "normalized_progress":
        return _simulate_progress(seed)
    return _simulate_events(scenario, seed)


def _simulate_events(scenario: str, seed: int) -> SimulationStudy:
    rng = np.random.default_rng(seed)
    time = np.arange(0.0, 20.0, 0.1)
    cue = np.arange(2.0, 18.0, 3.0)
    cue_truth = np.asarray([0.2, 0.6, 1.0, 0.5, 0.15])
    reward_truth = np.asarray([-0.1, 0.35, 0.75, 0.3, 0.1])
    sessions = []
    for animal in range(8):
        response = np.full(len(time), rng.normal(0.0, 0.08))
        scale = rng.normal(1.0, 0.25) if scenario == "kernel_heterogeneity" else 1.0
        for event_time in cue:
            index = round(event_time / 0.1)
            response[index : index + len(cue_truth)] += scale * cue_truth
        events = {"cue": cue}
        covariates: dict[str, np.ndarray] = {}
        if scenario == "overlapping_selected_model":
            reward = cue + 0.2 + 0.1 * ((np.arange(len(cue)) + animal) % 3)
            motion = np.sin(time * 0.7 + animal * 0.3) + rng.normal(0.0, 0.1, len(time))
            response += 0.25 * motion
            for event_time in reward:
                index = round(event_time / 0.1)
                response[index : index + len(reward_truth)] += reward_truth
            events["reward"] = reward
            covariates["motion"] = motion
        if scenario == "autocorrelated_residuals":
            residual = _ar1_noise(rng, len(time), phi=0.65, standard_deviation=0.12)
        else:
            residual = rng.normal(0.0, 0.12, len(time))
        response += residual
        response_valid = None
        if scenario == "blockwise_missingness":
            response_valid = np.ones(len(time), dtype=bool)
            start = 20 + ((seed * 11 + animal * 17) % 140)
            response_valid[start : start + 20] = False
        sessions.append(
            EncodingSession.from_arrays(
                subject=f"mouse-{animal}",
                session="day-0",
                time=time,
                response=response,
                events=events,
                continuous_covariates=covariates,
                response_valid=response_valid,
            )
        )
    event_kernels = [EventKernelSpec("cue", (0.0, 0.4))]
    continuous_covariates: tuple[str, ...] = ()
    alpha_grid = (0.0,)
    truth = {"event:cue": tuple(float(item) for item in cue_truth)}
    if scenario == "overlapping_selected_model":
        event_kernels.append(EventKernelSpec("reward", (0.0, 0.4)))
        continuous_covariates = ("motion",)
        alpha_grid = (0.0, 0.1, 1.0)
        truth["event:reward"] = tuple(float(item) for item in reward_truth)
    model = EncodingModelSpec(
        event_kernels=tuple(event_kernels),
        continuous_covariates=continuous_covariates,
        alpha_grid=alpha_grid,
        group_by="animal",
        folds=4,
        minimum_session_coverage=(0.7 if scenario == "blockwise_missingness" else 0.9),
        uncertainty=MultiplierSimultaneousBandSpec(),
    )
    return SimulationStudy(tuple(sessions), model, truth)


def _simulate_progress(seed: int) -> SimulationStudy:
    rng = np.random.default_rng(seed)
    time = np.arange(0.0, 40.0, 0.1)
    centers = np.linspace(0.0, 1.0, 4)
    coefficients = np.asarray([0.2, 0.8, 1.0, 0.3])
    progress_grid = np.linspace(0.0, 1.0, 31)
    truth = np.interp(progress_grid, centers, coefficients)
    starts = np.arange(2.0, 37.0, 3.5)[:10]
    durations = np.asarray([1.0, 1.5, 2.0, 2.5, 1.2] * 2)
    intervals = tuple(
        (float(start), float(start + duration))
        for start, duration in zip(starts, durations, strict=True)
    )
    sessions = []
    for animal in range(6):
        response = np.full(len(time), rng.normal(0.0, 0.08))
        for start, stop in intervals:
            inside = (time >= start) & (time < stop)
            progress = (time[inside] - start) / (stop - start)
            response[inside] += np.interp(progress, centers, coefficients)
        response += rng.normal(0.0, 0.12, len(time))
        sessions.append(
            EncodingSession.from_arrays(
                subject=f"mouse-{animal}",
                session="day-0",
                time=time,
                response=response,
                events={},
                intervals={"rear": intervals},
            )
        )
    model = EncodingModelSpec(
        event_kernels=(),
        progress_kernels=(
            ProgressKernelSpec(
                "rear-progress",
                source_interval="rear",
                basis=LinearProgressBasisSpec(functions=4, evaluation_points=31),
            ),
        ),
        alpha_grid=(0.0,),
        folds=3,
        uncertainty=MultiplierSimultaneousBandSpec(),
    )
    return SimulationStudy(
        tuple(sessions),
        model,
        {"progress:rear-progress": tuple(float(item) for item in truth)},
    )


def _ar1_noise(
    rng: np.random.Generator,
    count: int,
    *,
    phi: float,
    standard_deviation: float,
) -> np.ndarray:
    result = np.zeros(count)
    innovation_sd = standard_deviation * np.sqrt(1.0 - phi**2)
    result[0] = rng.normal(0.0, standard_deviation)
    for index in range(1, count):
        result[index] = phi * result[index - 1] + rng.normal(0.0, innovation_sd)
    return result


if __name__ == "__main__":
    main()
