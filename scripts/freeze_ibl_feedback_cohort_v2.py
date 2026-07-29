#!/usr/bin/env python3
"""Freeze the outcome-blind cohort for prospective IBL protocol v0.2."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from one.api import ONE

BASE_URL = "https://openalyx.internationalbrainlab.org"
DEVELOPMENT_ANIMALS = {"fip_13", "fip_14", "fip_15", "fip_16"}
REQUIRED_DATASETS = (
    "photometry.signal.pqt",
    "photometryROI.locations.pqt",
    "_ibl_trials.table.pqt",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / "Library/Caches/fipha/ibl-prospective-v0.2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/ibl-feedback-cohort-v0.2.json"),
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

    def inspect(eid: str) -> dict[str, Any]:
        return _inspect_session(one, eid, metadata[eid])

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(inspect, eid): eid for eid in candidates}
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
        "schema_version": "ibl-feedback-cohort-v0.2",
        "query_timestamp_utc": datetime.now(UTC).isoformat(),
        "one_base_url": BASE_URL,
        "one_api_version": version("ONE-api"),
        "query_datasets": list(REQUIRED_DATASETS),
        "development_animals": sorted(DEVELOPMENT_ANIMALS),
        "returned_session_count": len(rows),
        "returned_animal_count": len({row["subject"] for row in rows}),
        "eligible_session_count": sum(row["status"] == "eligible" for row in rows),
        "eligible_animals": eligible_animals,
        "eligible_animal_count": len(eligible_animals),
        "readiness_threshold": 12,
        "readiness_gate_passed": len(eligible_animals) >= 12,
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
    reference_times = times[np.isclose(wavelengths, 415) & included]
    if len(signal_times) < 2 or len(reference_times) < 2:
        return _excluded_row(eid, detail, "adapter_schema_failure")
    lower = max(np.nanmin(signal_times), np.nanmin(reference_times)) + 1.0
    upper = min(np.nanmax(signal_times), np.nanmax(reference_times)) - 0.5
    feedback_times = np.asarray(trials["feedback_times"], dtype=float)
    feedback_type = np.asarray(trials["feedbackType"], dtype=float)
    usable = (
        np.isfinite(feedback_times)
        & (feedback_times >= lower)
        & (feedback_times <= upper)
    )
    correct = int(np.sum(usable & (feedback_type == 1)))
    incorrect = int(np.sum(usable & (feedback_type == -1)))
    if correct < 20 or incorrect < 20:
        return _excluded_row(
            eid,
            detail,
            "insufficient_usable_events",
            usable_correct=correct,
            usable_incorrect=incorrect,
        )
    return {
        **_identity(eid, detail),
        "status": "eligible",
        "usable_correct": correct,
        "usable_incorrect": incorrect,
        "analysis_time_lower_s": float(lower),
        "analysis_time_upper_s": float(upper),
    }


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
