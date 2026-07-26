#!/usr/bin/env python3
"""Run the frozen outcome-blind IBL event-coverage audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from one.api import ONE

COHORT_SHA256 = "38197a26ab4804131423a9650a473a11e2b14f09ac2877875b574f2770d894e6"
PROTOCOL_SHA256 = "7cb78b6540c79cc35dec6a2a9d87c9d414db2e756f5d79b1d194b154aacee39c"
SOURCE_RESULTS_SHA256 = (
    "5c9b4e844380c8bd61ae0589f6c638920570f2c0e27c7100ea72b042c1caeef7"
)


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repository / "benchmarks/ibl-feedback-cohort-v0.3.json",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=repository / "benchmarks/ibl-event-coverage-protocol-v0.1.json",
    )
    parser.add_argument(
        "--source-results",
        type=Path,
        default=repository / "benchmarks/ibl-feedback-results-v0.3.2.json",
    )
    parser.add_argument("--cache", type=Path, default=Path.home() / "Downloads" / "ONE")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "benchmarks/ibl-event-coverage-results-v0.1.json",
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    protocol = json.loads(args.protocol.read_text())
    source_results = json.loads(args.source_results.read_text())
    _verify_payload(manifest, "manifest_sha256", COHORT_SHA256)
    _verify_payload(protocol, "protocol_sha256", PROTOCOL_SHA256)
    _verify_payload(source_results, "result_sha256", SOURCE_RESULTS_SHA256)
    if protocol["cohort_manifest_sha256"] != COHORT_SHA256:
        raise SystemExit("protocol does not reference the frozen cohort")

    expected_hashes = {
        item["session"]: item["source_sha256"]
        for item in source_results["session_diagnostics"]
        if item["status"] == "loaded"
    }
    rows = [row for row in manifest["sessions"] if row["status"] == "eligible"]
    if args.limit is not None:
        rows = rows[: args.limit]
    one = ONE(
        base_url=manifest["one_base_url"],
        password="international",
        cache_dir=args.cache,
        silent=True,
    )

    sessions: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        print(f"[{index}/{len(rows)}] {row['subject']} {row['session']}", flush=True)
        sessions.append(_audit_session(one, row, expected_hashes[row["session"]]))

    aggregate = _aggregate(sessions)
    readiness = _readiness(aggregate, protocol["readiness"])
    body = {
        "schema_version": "ibl-event-coverage-results-v0.1",
        "execution_timestamp_utc": datetime.now(UTC).isoformat(),
        "protocol_sha256": PROTOCOL_SHA256,
        "cohort_manifest_sha256": COHORT_SHA256,
        "source_results_sha256": SOURCE_RESULTS_SHA256,
        "outcome_access": (
            "no fluorescence columns loaded; timestamps, include flags, feedback "
            "times, and feedback condition only"
        ),
        "sessions_requested": len(rows),
        "sessions_loaded": len(sessions),
        "aggregate": aggregate,
        "readiness": readiness,
        "sessions": sessions,
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.output.write_text(
        json.dumps({**body, "result_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )
    print(json.dumps({"result_sha256": fingerprint, **readiness}, indent=2))
    if args.limit is None and not readiness["passed"]:
        raise SystemExit("event-coverage readiness gate failed")


def _audit_session(
    one: ONE, row: dict[str, Any], expected_hashes: dict[str, str]
) -> dict[str, Any]:
    eid = row["session"]
    signal_path = Path(
        one.load_dataset(
            eid,
            "photometry.signal.pqt",
            collection="alf/photometry",
            download_only=True,
        )
    )
    trials_path = Path(
        one.load_dataset(
            eid, "_ibl_trials.table.pqt", collection="alf", download_only=True
        )
    )
    actual_hashes = {
        "signal": _file_sha256(signal_path),
        "trials": _file_sha256(trials_path),
    }
    for kind, actual in actual_hashes.items():
        if actual != expected_hashes[kind]:
            raise ValueError(f"{eid} {kind} source hash changed: {actual}")

    signal = pd.read_parquet(signal_path, columns=["times", "wavelength", "include"])
    trials = pd.read_parquet(trials_path, columns=["feedback_times", "feedbackType"])
    signal_rows = np.isclose(np.asarray(signal["wavelength"], dtype=float), 470.0)
    source_time = np.asarray(signal["times"], dtype=float)[signal_rows]
    included = np.asarray(signal["include"], dtype=bool)[signal_rows]
    if len(source_time) < 2 or not np.all(np.diff(source_time) > 0):
        raise ValueError(f"{eid} does not have a strictly increasing 470-nm clock")

    events = np.asarray(trials["feedback_times"], dtype=float)
    feedback = np.asarray(trials["feedbackType"], dtype=float)
    recognized = np.isfinite(events) & np.isin(feedback, (-1, 1))
    boundary = (
        recognized
        & (events >= source_time[0] + 1.0)
        & (events <= source_time[-1] - 0.5)
    )
    frozen = np.zeros(len(events), dtype=bool)
    for lower, upper in row["valid_time_intervals"]:
        frozen |= (events >= lower + 1.0) & (events <= upper - 0.5)
    frozen &= recognized
    expected = row["usable_correct"] + row["usable_incorrect"]
    if int(frozen.sum()) != expected:
        raise ValueError(
            f"{eid} frozen event count changed: {frozen.sum()} != {expected}"
        )
    if np.any(frozen & ~boundary):
        raise ValueError(f"{eid} frozen events are not boundary eligible")

    median_interval = float(np.median(np.diff(source_time)))
    step = median_interval
    max_gap_s = 1.5 * median_interval
    target_time = np.arange(source_time[0], source_time[-1] + step / 2, step)
    target_time = target_time[target_time <= source_time[-1]]
    valid_time = source_time[included]
    observable = (target_time >= valid_time[0]) & (target_time <= valid_time[-1])
    protected_gap = np.zeros(len(target_time), dtype=bool)
    for left, right in pairwise(valid_time):
        if right - left > max_gap_s:
            protected_gap |= (target_time > left) & (target_time < right)
    observable &= ~protected_gap

    selected = np.flatnonzero(frozen)
    dispositions = _classify_events(target_time, observable, events[selected])
    labels = np.where(feedback[selected] == 1, "correct", "incorrect")
    counts = {
        condition: {
            "recognized": int(np.sum(recognized & (feedback == value))),
            "boundary_eligible": int(np.sum(boundary & (feedback == value))),
            "frozen_cohort_eligible": int(np.sum(frozen & (feedback == value))),
            "regularization_complete": int(
                np.sum((labels == condition) & (dispositions == "complete"))
            ),
        }
        for condition, value in (("correct", 1), ("incorrect", -1))
    }
    condition_rates = {
        condition: _rates(condition_counts)
        for condition, condition_counts in counts.items()
    }
    disposition_counts = Counter(dispositions.tolist())
    return {
        "session": eid,
        "subject": row["subject"],
        "source_sha256": actual_hashes,
        "source_samples": len(source_time),
        "included_source_samples": int(included.sum()),
        "excluded_source_samples": int((~included).sum()),
        "target_samples": len(target_time),
        "unobservable_target_samples": int((~observable).sum()),
        "median_interval_s": median_interval,
        "resolved_max_gap_s": max_gap_s,
        "protected_target_samples": int(protected_gap.sum()),
        "protected_gap_bridges": int(np.sum(protected_gap & observable)),
        "conditions": condition_rates,
        "incremental_condition_retention_difference": abs(
            float(condition_rates["correct"]["incremental_retention"])
            - float(condition_rates["incorrect"]["incremental_retention"])
        ),
        "dispositions": dict(sorted(disposition_counts.items())),
    }


def _classify_events(
    target_time: np.ndarray, observable: np.ndarray, events: np.ndarray
) -> np.ndarray:
    missing_prefix = np.concatenate(([0], np.cumsum(~observable)))
    baseline_missing = _window_has_missing(
        target_time, missing_prefix, events - 1.0, events
    )
    response_missing = _window_has_missing(
        target_time, missing_prefix, events, events + 0.5
    )
    right = np.searchsorted(target_time, events, side="left")
    right = np.clip(right, 0, len(target_time) - 1)
    left = np.maximum(right - 1, 0)
    nearest = np.where(
        abs(events - target_time[left]) <= abs(target_time[right] - events), left, right
    )
    output = np.full(len(events), "complete", dtype="U40")
    output[response_missing] = "response_intersects_gap"
    output[baseline_missing] = "baseline_intersects_gap"
    output[~observable[nearest]] = "event_inside_gap"
    return output


def _window_has_missing(
    target_time: np.ndarray,
    missing_prefix: np.ndarray,
    starts: np.ndarray,
    stops: np.ndarray,
) -> np.ndarray:
    left = np.searchsorted(target_time, starts, side="left")
    right = np.searchsorted(target_time, stops, side="left")
    counts = right - left
    missing = missing_prefix[right] - missing_prefix[left]
    return (counts == 0) | (missing > 0)


def _aggregate(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    by_condition: dict[str, Counter[str]] = defaultdict(Counter)
    by_animal: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    disposition_counts: Counter[str] = Counter()
    bridge_count = 0
    protected_target_samples = 0
    unobservable_target_samples = 0
    excluded_source_samples = 0
    for session in sessions:
        disposition_counts.update(session["dispositions"])
        bridge_count += session["protected_gap_bridges"]
        protected_target_samples += session["protected_target_samples"]
        unobservable_target_samples += session["unobservable_target_samples"]
        excluded_source_samples += session["excluded_source_samples"]
        for condition, counts_with_rates in session["conditions"].items():
            counts = {
                key: value
                for key, value in counts_with_rates.items()
                if key not in {"cohort_gate_retention", "incremental_retention"}
            }
            by_condition[condition].update(counts)
            by_animal[session["subject"]][condition].update(counts)

    conditions = {
        condition: _rates(dict(counts))
        for condition, counts in sorted(by_condition.items())
    }
    animals = {
        animal: {
            "conditions": {
                condition: _rates(dict(counts))
                for condition, counts in sorted(condition_counts.items())
            },
            "incremental_condition_retention_difference": _condition_difference(
                condition_counts
            ),
        }
        for animal, condition_counts in sorted(by_animal.items())
    }
    totals = Counter()
    for counts in by_condition.values():
        totals.update(counts)
    return {
        "totals": _rates(dict(totals)),
        "conditions": conditions,
        "incremental_condition_retention_difference": abs(
            conditions["correct"]["incremental_retention"]
            - conditions["incorrect"]["incremental_retention"]
        ),
        "animals": animals,
        "dispositions": dict(sorted(disposition_counts.items())),
        "excluded_source_samples": excluded_source_samples,
        "unobservable_target_samples": unobservable_target_samples,
        "protected_target_samples": protected_target_samples,
        "protected_gap_bridges": bridge_count,
    }


def _rates(counts: dict[str, int]) -> dict[str, int | float]:
    boundary = counts["boundary_eligible"]
    frozen = counts["frozen_cohort_eligible"]
    complete = counts["regularization_complete"]
    return {
        **counts,
        "cohort_gate_retention": frozen / boundary if boundary else 0.0,
        "incremental_retention": complete / frozen if frozen else 0.0,
    }


def _condition_difference(condition_counts: dict[str, Counter[str]]) -> float:
    rates = {
        condition: _rates(dict(counts))["incremental_retention"]
        for condition, counts in condition_counts.items()
    }
    return abs(float(rates["correct"]) - float(rates["incorrect"]))


def _readiness(aggregate: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    animal_differences = [
        item["incremental_condition_retention_difference"]
        for item in aggregate["animals"].values()
    ]
    checks = {
        "incremental_total_retention": (
            aggregate["totals"]["incremental_retention"]
            >= thresholds["incremental_total_retention_min"]
        ),
        "incremental_each_condition_retention": all(
            item["incremental_retention"]
            >= thresholds["incremental_each_condition_retention_min"]
            for item in aggregate["conditions"].values()
        ),
        "cohort_condition_retention_difference": (
            aggregate["incremental_condition_retention_difference"]
            <= thresholds["cohort_condition_retention_difference_max"]
        ),
        "animal_condition_retention_difference": (
            max(animal_differences, default=0.0)
            <= thresholds["animal_condition_retention_difference_max"]
        ),
        "all_noncomplete_events_classified": (
            sum(aggregate["dispositions"].values())
            == aggregate["totals"]["frozen_cohort_eligible"]
        ),
        "protected_gap_bridges": (
            aggregate["protected_gap_bridges"]
            <= thresholds["protected_gap_bridges_allowed"]
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "max_animal_condition_retention_difference": max(
            animal_differences, default=0.0
        ),
    }


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
