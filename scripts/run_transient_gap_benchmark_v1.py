"""Execute the frozen sharp-transient and missing-run benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from fiberphotometry.benchmark_resampling import (
    TransientSpec,
    generate_transient,
    reconstruction_metrics,
)
from fiberphotometry.events import condition_exclusion_warning

PROTOCOL_HASHES = {
    "v0.1": "4e88ee8fbd851d605c94125ef7ba8afb002a58bca65b8f16faa09f28b7bc1a3c",
    "v0.1.1": "5a3eea425b041c6bd31115bc4c12f165e496fbbea0269eb1119bfd3dcc994efc",
}


def _load_protocol(path: Path, expected_hash: str) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    expected = payload.pop("protocol_sha256")
    observed = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if expected != observed or expected != expected_hash:
        raise SystemExit("frozen transient-gap protocol fingerprint mismatch")
    return payload


def _transient(item: dict[str, Any]) -> TransientSpec:
    return TransientSpec(
        family=item["family"],
        transient_class=item["class"],
        width_samples=item.get("width_samples"),
        rise_samples=item.get("rise_samples"),
        decay_samples=item.get("decay_samples"),
        separation_samples=item.get("separation_samples"),
    )


def _passes(metrics: dict[str, Any], limits: dict[str, float]) -> bool:
    contrast_metric = (
        "event_contrast_peak_normalized_error"
        if "event_contrast_peak_normalized_error" in metrics
        else "event_contrast_relative_error"
    )
    contrast_limit = f"{contrast_metric}_max"
    checks = {
        "peak_amplitude_relative_error": "peak_amplitude_relative_error_max",
        "peak_time_error_samples": "peak_time_error_samples_max",
        "response_mean_relative_error": "response_mean_relative_error_max",
        contrast_metric: contrast_limit,
    }
    return metrics["event_disposition"] == "complete" and all(
        metrics[metric] is not None and metrics[metric] <= limits[limit]
        for metric, limit in checks.items()
    )


def _measure(
    time: np.ndarray,
    truth: np.ndarray,
    observed: np.ndarray,
    reconstructed: np.ndarray,
    *,
    event_time: float,
    rate_hz: float,
    contrast_denominator: str,
) -> dict[str, Any]:
    metrics = asdict(
        reconstruction_metrics(
            time,
            truth,
            observed,
            reconstructed,
            event_time=event_time,
            rate_hz=rate_hz,
            contrast_denominator=contrast_denominator,  # type: ignore[arg-type]
        )
    )
    if contrast_denominator == "peak_amplitude":
        metrics["event_contrast_peak_normalized_error"] = metrics.pop(
            "event_contrast_relative_error"
        )
    return metrics


def _jitter_results(
    protocol: dict[str, Any], contrast_denominator: str
) -> list[dict[str, Any]]:
    output = []
    acquisition = protocol["acquisition"]
    limits = protocol["acceptance"]
    for rate in acquisition["rates_hz"]:
        step = 1 / rate
        regular = np.arange(0, acquisition["duration_s"], step)
        for phase in acquisition["event_phase_samples"]:
            event_time = acquisition["event_time_s"] + phase * step
            for item in protocol["transients"]:
                spec = _transient(item)
                for jitter_fraction in acquisition["timestamp_jitter_fraction"]:
                    jitter = (
                        jitter_fraction * step * np.sin(np.arange(len(regular)) * 0.71)
                    )
                    source_time = regular + jitter
                    source = generate_transient(
                        source_time,
                        event_time=event_time,
                        rate_hz=rate,
                        spec=spec,
                    )
                    target_step = float(np.median(np.diff(source_time)))
                    target = np.arange(
                        source_time[0], source_time[-1] + target_step / 2, target_step
                    )
                    target = target[target <= source_time[-1]]
                    truth = generate_transient(
                        target, event_time=event_time, rate_hz=rate, spec=spec
                    )
                    for policy in protocol["policies"]["jitter"]:
                        if policy == "linear_median_rate":
                            observed = np.interp(target, source_time, source)
                        else:
                            right = np.searchsorted(source_time, target, side="left")
                            right = np.clip(right, 0, len(source_time) - 1)
                            left = np.maximum(right - 1, 0)
                            nearest = np.where(
                                abs(target - source_time[left])
                                <= abs(source_time[right] - target),
                                left,
                                right,
                            )
                            observed = source[nearest]
                        metrics = _measure(
                            target,
                            truth,
                            observed,
                            np.ones(len(target), dtype=bool),
                            event_time=event_time,
                            rate_hz=rate,
                            contrast_denominator=contrast_denominator,
                        )
                        output.append(
                            {
                                "family": "timestamp_jitter",
                                "rate_hz": rate,
                                "event_phase_samples": phase,
                                "transient": item,
                                "severity": jitter_fraction,
                                "policy": policy,
                                "metrics": metrics,
                                "passed": _passes(metrics, limits[item["class"]]),
                            }
                        )
    return output


def _missing_results(
    protocol: dict[str, Any], contrast_denominator: str
) -> list[dict[str, Any]]:
    output = []
    acquisition = protocol["acquisition"]
    perturbations = protocol["perturbations"]
    limits = protocol["acceptance"]
    for rate in acquisition["rates_hz"]:
        step = 1 / rate
        time = np.arange(0, acquisition["duration_s"], step)
        for phase in acquisition["event_phase_samples"]:
            event_time = acquisition["event_time_s"] + phase * step
            for item in protocol["transients"]:
                spec = _transient(item)
                truth = generate_transient(
                    time, event_time=event_time, rate_hz=rate, spec=spec
                )
                for offset in perturbations["isolated_dropout_offsets_samples"]:
                    missing = np.zeros(len(time), dtype=bool)
                    missing[
                        int(np.argmin(abs(time - (event_time + offset * step))))
                    ] = True
                    source_time = time[~missing]
                    source = truth[~missing]
                    for policy in protocol["policies"]["isolated_dropout"]:
                        observed = truth.copy()
                        if policy == "linear":
                            observed[missing] = np.interp(
                                time[missing], source_time, source
                            )
                        elif policy == "previous_value":
                            row = int(np.flatnonzero(missing)[0])
                            observed[row] = observed[max(row - 1, 0)]
                        else:
                            observed[missing] = np.nan
                        metrics = _measure(
                            time,
                            truth,
                            observed,
                            missing,
                            event_time=event_time,
                            rate_hz=rate,
                            contrast_denominator=contrast_denominator,
                        )
                        output.append(
                            {
                                "family": "isolated_dropout",
                                "rate_hz": rate,
                                "event_phase_samples": phase,
                                "transient": item,
                                "severity": 1,
                                "location": offset,
                                "policy": policy,
                                "metrics": metrics,
                                "passed": (
                                    metrics["event_disposition"] != "complete"
                                    if policy == "protected_missing"
                                    else _passes(metrics, limits[item["class"]])
                                ),
                            }
                        )
                centers = {
                    "baseline": event_time - 0.5,
                    "event": event_time,
                    "response": event_time + 0.5,
                }
                for length in perturbations["gap_lengths_samples"]:
                    for location, center in centers.items():
                        nearest = int(np.argmin(abs(time - center)))
                        start = max(0, nearest - length // 2)
                        stop = min(len(time), start + length)
                        missing = np.zeros(len(time), dtype=bool)
                        missing[start:stop] = True
                        source_time = time[~missing]
                        source = truth[~missing]
                        for policy in protocol["policies"]["contiguous_gap"]:
                            if policy == "protected_missing":
                                observed = truth.copy()
                                observed[missing] = np.nan
                            else:
                                observed = np.interp(time, source_time, source)
                            metrics = _measure(
                                time,
                                truth,
                                observed,
                                missing,
                                event_time=event_time,
                                rate_hz=rate,
                                contrast_denominator=contrast_denominator,
                            )
                            output.append(
                                {
                                    "family": "contiguous_gap",
                                    "rate_hz": rate,
                                    "event_phase_samples": phase,
                                    "transient": item,
                                    "severity": length,
                                    "location": location,
                                    "policy": policy,
                                    "metrics": metrics,
                                    "passed": (
                                        metrics["event_disposition"] != "complete"
                                        if policy == "protected_missing"
                                        else _passes(metrics, limits[item["class"]])
                                    ),
                                    "negative_control": (
                                        policy == "naive_linear_negative_control"
                                    ),
                                }
                            )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=tuple(PROTOCOL_HASHES), default="v0.1")
    args = parser.parse_args()
    suffix = args.version
    protocol_path = Path(f"benchmarks/transient-gap-protocol-{suffix}.json")
    protocol_hash = PROTOCOL_HASHES[suffix]
    protocol = _load_protocol(protocol_path, protocol_hash)
    contrast_denominator = "peak_amplitude" if suffix == "v0.1.1" else "truth_contrast"
    scenarios = _jitter_results(protocol, contrast_denominator) + _missing_results(
        protocol, contrast_denominator
    )
    conditions = np.asarray(["a", "a", "b", "b"])
    dispositions = np.asarray(
        ["complete", "complete", "complete", "response_intersects_gap"]
    )
    summaries = {}
    for family in sorted({item["family"] for item in scenarios}):
        rows = [item for item in scenarios if item["family"] == family]
        summaries[family] = {
            "scenarios": len(rows),
            "passed": sum(item["passed"] for item in rows),
            "failed": sum(not item["passed"] for item in rows),
        }
    body = {
        "schema_version": f"transient-gap-results-{suffix}",
        "protocol_sha256": protocol_hash,
        "scenario_count": len(scenarios),
        "summaries": summaries,
        "condition_dependent_exclusion_warning": condition_exclusion_warning(
            conditions, dispositions
        ),
        "scenarios": scenarios,
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = Path(f"benchmarks/transient-gap-results-{suffix}.json")
    output.write_text(
        json.dumps({**body, "result_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )
    print(json.dumps({**summaries, "result_sha256": fingerprint}, indent=2))


if __name__ == "__main__":
    main()
