#!/usr/bin/env python3
"""Freeze the outcome-blind IBL event-coverage audit contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

COHORT_SHA256 = "38197a26ab4804131423a9650a473a11e2b14f09ac2877875b574f2770d894e6"


def protocol() -> dict[str, object]:
    return {
        "schema_version": "ibl-event-coverage-protocol-v0.1",
        "status": "frozen_before_aggregate_execution",
        "cohort_manifest_sha256": COHORT_SHA256,
        "scope": {
            "sessions": "all 383 eligible sessions in the frozen IBL v0.3 cohort",
            "signal_wavelength_nm": 470,
            "conditions": {"correct": 1, "incorrect": -1},
            "permitted_signal_columns": ["times", "wavelength", "include"],
            "permitted_trial_columns": ["feedback_times", "feedbackType"],
            "fluorescence_values_loaded": False,
        },
        "source_integrity": {
            "verify_against": "ibl-feedback-results-v0.3.2 session source hashes",
            "required_files": ["photometry.signal.pqt", "_ibl_trials.table.pqt"],
        },
        "event_denominators": {
            "boundary_eligible": (
                "finite +/-1 feedback events whose full [-1.0, 0.5] second "
                "window lies inside the first and last 470-nm timestamp"
            ),
            "frozen_cohort_eligible": (
                "the exact events retained by the cohort v0.3 valid intervals; "
                "counts must equal its usable_correct plus usable_incorrect"
            ),
            "regularization_complete": (
                "frozen-cohort events with structurally observable baseline and "
                "response windows after the prospective regularization policy"
            ),
        },
        "regularization": {
            "target_rate": "median source interval within each session",
            "target_grid_origin": "first 470-nm source timestamp",
            "method": "linear",
            "maximum_gap_factor": 1.5,
            "included_source_samples_only": True,
            "finite_runs_split_at": [
                "include=false source rows",
                "adjacent timestamp intervals greater than 1.5x the median",
            ],
            "bridge_across_split_runs": False,
        },
        "event_windows_s": {
            "baseline": [-1.0, 0.0],
            "response": [0.0, 0.5],
            "left_closed_right_open": True,
        },
        "event_disposition_priority": [
            "event_inside_gap",
            "baseline_intersects_gap",
            "response_intersects_gap",
            "complete",
        ],
        "reporting": {
            "stratify_by": ["condition", "session", "animal"],
            "report_existing_cohort_gate_attrition_separately": True,
            "report_incremental_regularization_attrition": True,
            "report_absolute_condition_retention_difference": True,
            "retain_all_noncomplete_dispositions": True,
        },
        "readiness": {
            "incremental_total_retention_min": 0.99,
            "incremental_each_condition_retention_min": 0.99,
            "cohort_condition_retention_difference_max": 0.005,
            "animal_condition_retention_difference_max": 0.05,
            "all_noncomplete_events_must_be_classified": True,
            "protected_gap_bridges_allowed": 0,
            "interpretation": (
                "Prospective engineering thresholds for product readiness, not "
                "universal scientific validity thresholds. Existing cohort-gate "
                "attrition is disclosed but does not count as incremental loss."
            ),
        },
    }


def main() -> None:
    body = protocol()
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = Path("benchmarks/ibl-event-coverage-protocol-v0.1.json")
    output.write_text(
        json.dumps({**body, "protocol_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )
    print(fingerprint)


if __name__ == "__main__":
    main()
