#!/usr/bin/env python3
"""Freeze the outcome-blind signal-only cohort for IBL protocol v0.3."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from importlib.metadata import version
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from one.api import ONE

BASE_URL = "https://openalyx.internationalbrainlab.org"
DEVELOPMENT_ANIMALS = {"fip_13", "fip_14", "fip_15", "fip_16"}
REQUIRED_DATASETS = (
    "photometry.signal.pqt",
    "photometryROI.locations.pqt",
    "_ibl_trials.table.pqt",
)
ROLLING_WINDOW_S = 60.0
ROLLING_GAP_FACTOR = 1.5
READINESS_ANIMALS = 12
MINIMUM_EVENTS_PER_CONDITION = 20


def main() -> None:
    from one.api import ONE

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / "Library/Caches/fiberphotometry/ibl-prospective-v0.2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/ibl-feedback-cohort-v0.3.json"),
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    one = ONE(
        base_url=BASE_URL,
        password="international",
        cache_dir=args.cache_dir,
        silent=True,
    )
    eids, details = one.search(
        datasets=list(REQUIRED_DATASETS), details=True, query_type="remote"
    )
    metadata = {str(eid): detail for eid, detail in zip(eids, details, strict=True)}
    rows: list[dict[str, Any]] = []
    candidates = []
    for eid in sorted(metadata):
        detail = metadata[eid]
        if detail["subject"] in DEVELOPMENT_ANIMALS:
            rows.append(_excluded_row(eid, detail, "development_animal"))
        else:
            candidates.append(eid)

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_inspect_session, one, eid, metadata[eid]): eid
            for eid in candidates
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            eid = futures[future]
            try:
                rows.append(future.result())
            except Exception as error:
                rows.append(
                    _excluded_row(
                        eid,
                        metadata[eid],
                        "metadata_or_schema_failure",
                        f"{type(error).__name__}: {error}",
                    )
                )
            if completed % 25 == 0:
                print(f"inspected {completed}/{len(candidates)} candidate sessions")

    rows.sort(key=lambda row: row["session"])
    eligible_animals = sorted(
        {row["subject"] for row in rows if row["status"] == "eligible"}
    )
    reason_counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("reason", "eligible"))
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    body = {
        "schema_version": "ibl-feedback-cohort-v0.3",
        "query_timestamp_utc": datetime.now(UTC).isoformat(),
        "one_base_url": BASE_URL,
        "one_api_version": version("ONE-api"),
        "query_datasets": list(REQUIRED_DATASETS),
        "outcome_access": (
            "photometry values not loaded; behavioral condition counts only"
        ),
        "development_animals": sorted(DEVELOPMENT_ANIMALS),
        "returned_session_count": len(rows),
        "returned_animal_count": len({row["subject"] for row in rows}),
        "eligible_session_count": sum(row["status"] == "eligible" for row in rows),
        "eligible_animals": eligible_animals,
        "eligible_animal_count": len(eligible_animals),
        "readiness_threshold": READINESS_ANIMALS,
        "readiness_gate_passed": len(eligible_animals) >= READINESS_ANIMALS,
        "signal_wavelength_nm": 470,
        "reference_wavelength_nm": None,
        "rolling_window_s": ROLLING_WINDOW_S,
        "rolling_boundary_policy": "full_window_only",
        "rolling_gap_factor": ROLLING_GAP_FACTOR,
        "minimum_events_per_condition": MINIMUM_EVENTS_PER_CONDITION,
        "reason_counts": reason_counts,
        "sessions": rows,
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {**body, "manifest_sha256": fingerprint}
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "eligible_animals": len(eligible_animals),
                "eligible_sessions": body["eligible_session_count"],
                "gate_passed": body["readiness_gate_passed"],
                "manifest_sha256": fingerprint,
                "reason_counts": reason_counts,
            },
            indent=2,
        )
    )
    if not body["readiness_gate_passed"]:
        raise SystemExit("prospective readiness gate not met")


def _inspect_session(one: ONE, eid: str, detail: dict[str, Any]) -> dict[str, Any]:
    roi_path = one.load_dataset(
        eid,
        "photometryROI.locations.pqt",
        collection="alf/photometry",
        download_only=True,
    )
    trials_path = one.load_dataset(
        eid, "_ibl_trials.table.pqt", collection="alf", download_only=True
    )
    signal_path = one.load_dataset(
        eid,
        "photometry.signal.pqt",
        collection="alf/photometry",
        download_only=True,
    )
    roi = pd.read_parquet(roi_path, columns=["brain_region"])
    if "DMS" not in set(roi["brain_region"].astype(str)):
        return _excluded_row(eid, detail, "absent_dms")
    trials = pd.read_parquet(trials_path, columns=["feedback_times", "feedbackType"])
    signal = pd.read_parquet(signal_path, columns=["times", "wavelength", "include"])
    wavelengths = np.asarray(signal["wavelength"], dtype=float)
    times = np.asarray(signal["times"], dtype=float)
    included = np.asarray(signal["include"], dtype=bool)
    signal_times = times[np.isclose(wavelengths, 470) & included]
    if len(signal_times) < 2:
        return _excluded_row(eid, detail, "adapter_schema_failure")
    intervals = np.diff(signal_times)
    median_interval = float(np.median(intervals))
    max_gap_s = ROLLING_GAP_FACTOR * median_interval
    contiguous_intervals = intervals[intervals <= max_gap_s]
    rate_hz = round(1 / float(np.mean(contiguous_intervals)))
    window_samples = int(ROLLING_WINDOW_S * rate_hz)
    valid_intervals = _rolling_valid_intervals(
        signal_times, window_samples=window_samples, max_gap_s=max_gap_s
    )
    feedback_times = np.asarray(trials["feedback_times"], dtype=float)
    feedback_type = np.asarray(trials["feedbackType"], dtype=float)
    usable = np.zeros(len(feedback_times), dtype=bool)
    for lower, upper in valid_intervals:
        usable |= (feedback_times >= lower + 1.0) & (feedback_times <= upper - 0.5)
    usable &= np.isfinite(feedback_times)
    correct = int(np.sum(usable & (feedback_type == 1)))
    incorrect = int(np.sum(usable & (feedback_type == -1)))
    details_common = {
        "usable_correct": correct,
        "usable_incorrect": incorrect,
        "signal_sample_count": len(signal_times),
        "sampling_rate_hz": rate_hz,
        "rolling_window_samples": window_samples,
        "valid_time_intervals": [[lower, upper] for lower, upper in valid_intervals],
    }
    insufficient_events = (
        correct < MINIMUM_EVENTS_PER_CONDITION
        or incorrect < MINIMUM_EVENTS_PER_CONDITION
    )
    if insufficient_events:
        return _excluded_row(
            eid, detail, "insufficient_usable_events", **details_common
        )
    return {**_identity(eid, detail), "status": "eligible", **details_common}


def _rolling_valid_intervals(
    times: np.ndarray, *, window_samples: int, max_gap_s: float
) -> list[tuple[float, float]]:
    gap_starts = np.flatnonzero(np.diff(times) > max_gap_s) + 1
    boundaries = [0, *gap_starts.tolist(), len(times)]
    output = []
    for start, stop in pairwise(boundaries):
        count = stop - start
        if count < window_samples:
            continue
        first_center = start + window_samples // 2
        last_center = first_center + count - window_samples
        output.append((float(times[first_center]), float(times[last_center])))
    return output


def _identity(eid: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "session": eid,
        "subject": detail["subject"],
        "lab": detail["lab"],
        "date": str(detail["date"]),
        "task_protocol": detail["task_protocol"],
    }


def _excluded_row(
    eid: str,
    detail: dict[str, Any],
    reason: str,
    error: str | None = None,
    **extra: object,
) -> dict[str, Any]:
    row = {**_identity(eid, detail), "status": "excluded", "reason": reason, **extra}
    if error is not None:
        row["error"] = error
    return row


if __name__ == "__main__":
    main()
