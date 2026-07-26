#!/usr/bin/env python3
"""Freeze the held-out IBL regularized-AsLS validation contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from one.api import ONE

COHORT_SHA256 = "38197a26ab4804131423a9650a473a11e2b14f09ac2877875b574f2770d894e6"


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cohort",
        type=Path,
        default=repository / "benchmarks/ibl-feedback-cohort-v0.3.json",
    )
    parser.add_argument("--cache", type=Path, default=Path.home() / "Downloads" / "ONE")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "benchmarks/ibl-regularized-asls-protocol-v0.1.json",
    )
    args = parser.parse_args()
    cohort = json.loads(args.cohort.read_text())
    _verify_payload(cohort, "manifest_sha256", COHORT_SHA256)
    selected = [
        row
        for row in cohort["sessions"]
        if row.get("reason") == "insufficient_usable_events"
    ]
    if len(selected) != 24:
        raise SystemExit(f"expected 24 held-out sessions, found {len(selected)}")
    one = ONE(
        base_url=cohort["one_base_url"],
        password="international",
        cache_dir=args.cache,
        silent=True,
    )
    sessions = []
    for index, row in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {row['subject']} {row['session']}")
        paths = {
            "signal": Path(
                one.load_dataset(
                    row["session"],
                    "photometry.signal.pqt",
                    collection="alf/photometry",
                    download_only=True,
                )
            ),
            "roi": Path(
                one.load_dataset(
                    row["session"],
                    "photometryROI.locations.pqt",
                    collection="alf/photometry",
                    download_only=True,
                )
            ),
            "trials": Path(
                one.load_dataset(
                    row["session"],
                    "_ibl_trials.table.pqt",
                    collection="alf",
                    download_only=True,
                )
            ),
        }
        sessions.append(
            {
                "session": row["session"],
                "subject": row["subject"],
                "date": row["date"],
                "lab": row["lab"],
                "task_protocol": row["task_protocol"],
                "sampling_rate_hz": row["sampling_rate_hz"],
                "valid_time_intervals": row["valid_time_intervals"],
                "usable_correct": row["usable_correct"],
                "usable_incorrect": row["usable_incorrect"],
                "source": {
                    name: {
                        "size_bytes": path.stat().st_size,
                        "sha256": _file_sha256(path),
                    }
                    for name, path in paths.items()
                },
            }
        )

    body: dict[str, Any] = {
        "schema_version": "ibl-regularized-asls-protocol-v0.1",
        "status": "frozen_before_held_out_fluorescence_access",
        "cohort_manifest_sha256": COHORT_SHA256,
        "held_out_basis": (
            "24 sessions excluded from v0.3 solely for insufficient balanced "
            "events; their fluorescence columns were not loaded by v0.3.2"
        ),
        "outcome_access_at_freeze": (
            "source files hashed; only prior timestamp/include and behavioral "
            "condition counts available; no fluorescence values loaded"
        ),
        "sessions": sessions,
        "regularization": {
            "method": "linear",
            "rate_hz": "median",
            "max_gap_factor": 1.5,
            "retain_source_arrays": True,
        },
        "methods": {
            "primary": "regularized_asls_divide",
            "raw_compatible_comparators": [
                "double_exponential_divide",
                "published_rolling_divide",
            ],
            "regularized_comparators": [
                "double_exponential_divide",
                "published_rolling_divide",
            ],
        },
        "event_windows_s": {"baseline": [-1.0, 0.0], "response": [0.0, 0.5]},
        "event_selection": (
            "exact usable feedback events from frozen valid intervals; no minimum "
            "condition count and no population inference"
        ),
        "metrics": {
            "engineering": [
                "source integrity",
                "method execution",
                "finite baseline fraction",
                "event coverage",
                "interpolation distance",
            ],
            "regularization_fidelity": [
                "raw-versus-regularized corrected-trace correlation",
                "raw-versus-regularized corrected-trace normalized RMSE",
                "raw-versus-regularized event-delta correlation",
                (
                    "raw-versus-regularized event-delta normalized median "
                    "absolute difference"
                ),
            ],
            "asls_sensitivity_descriptive": [
                "baseline correlation and normalized RMSE against each comparator",
                "event-delta correlation and normalized median absolute difference",
                "session contrast sign agreement where both conditions occur",
            ],
        },
        "acceptance": {
            "all_sources_match_frozen_hashes": True,
            "all_methods_execute_all_sessions": True,
            "finite_baseline_fraction_min": 0.99,
            "complete_event_fraction_min": 0.99,
            "nearest_source_distance_max_fraction_of_interval": 0.25,
            "comparator_trace_correlation_median_min": 0.995,
            "comparator_trace_correlation_case_min": 0.95,
            "comparator_trace_normalized_rmse_median_max": 0.10,
            "comparator_event_delta_correlation_min": 0.99,
            "comparator_event_delta_normalized_mad_max": 0.05,
            "asls_comparator_agreement_is_descriptive_only": True,
        },
        "interpretation": [
            (
                "The raw-compatible methods isolate distortion introduced by "
                "regularization."
            ),
            "Agreement between AsLS and another baseline is not ground truth.",
            (
                "These behaviorally imbalanced sessions support engineering "
                "validation only."
            ),
            "Retain every session and failure; do not tune after aggregate access.",
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.output.write_text(
        json.dumps({**body, "protocol_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )
    print(fingerprint)


def _verify_payload(payload: dict[str, Any], key: str, expected: str) -> None:
    if payload.get(key) != expected:
        raise SystemExit(f"unexpected {key}: {payload.get(key)}")
    body = dict(payload)
    body.pop(key)
    actual = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual != expected:
        raise SystemExit(f"{key} content verification failed: {actual}")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
