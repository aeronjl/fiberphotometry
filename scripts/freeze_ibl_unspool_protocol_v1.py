#!/usr/bin/env python3
"""Freeze the first fipha-to-Behavio public IBL benchmark.

The behaviour package was called ``unspool`` at freeze time; the pinned commit
and field names below are part of the frozen artifact and are left unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    manifest_path = repository / "benchmarks/ibl-feedback-cohort-v0.3.json"
    manifest = json.loads(manifest_path.read_text())
    sessions = [row for row in manifest["sessions"] if row["status"] == "eligible"]
    selected = []
    for subject in sorted({row["subject"] for row in sessions}):
        rows = [row for row in sessions if row["subject"] == subject]
        by_date = {}
        for row in sorted(rows, key=lambda item: (item["date"], item["session"])):
            by_date.setdefault(row["date"], row)
        for order, row in enumerate(by_date.values()):
            selected.append(
                {
                    "subject": subject,
                    "session": row["session"],
                    "date": row["date"],
                    "session_order": order,
                    "source_sha256": next(
                        item["source_sha256"]
                        for item in json.loads(
                            (
                                repository
                                / "benchmarks/ibl-feedback-results-v0.3.2.json"
                            ).read_text()
                        )["session_diagnostics"]
                        if item["session"] == row["session"]
                    ),
                }
            )
    body = {
        "schema_version": "ibl-unspool-longitudinal-protocol-v0.1",
        "status": "frozen_before_new_longitudinal_aggregate_execution",
        "freeze_date": "2026-07-27",
        "outcome_access_at_freeze": (
            "photometry and feedback outcomes were accessed in earlier disclosed IBL "
            "analyses; the lagged cross-package predictive comparison is new and "
            "post-hoc"
        ),
        "source_cohort_manifest_sha256": manifest["manifest_sha256"],
        "source_result_sha256": json.loads(
            (repository / "benchmarks/ibl-feedback-results-v0.3.2.json").read_text()
        )["result_sha256"],
        "session_selection": (
            "eligible v0.3 sessions; one session per subject/date selected by smallest "
            "session UUID; chronological order is ISO date order"
        ),
        "analysis_session_orders": [0, 11],
        "sessions": selected,
        "neural_summary": {
            "region": "DMS",
            "preprocessing": "published_rolling divide_standard",
            "baseline_seconds": [-0.5, 0.0],
            "response_seconds": [0.0, 0.5],
            "contrast": (
                "mean correct feedback delta minus mean incorrect feedback delta"
            ),
            "predictor": "immediately prior selected session contrast",
            "fixed_scale": "divide fractional dF/F by 0.01",
        },
        "behavioral_outcome": (
            "current-trial feedback correctness (1 correct, 0 incorrect)"
        ),
        "models": {
            "stationary": {"covariates": [], "choice_lags": 1, "l2": 1e-6},
            "session_progress": {
                "covariates": ["session_progress"],
                "choice_lags": 1,
                "l2": 1e-6,
            },
            "session_progress_plus_lagged_dms": {
                "covariates": [
                    "session_progress",
                    "prior_dms_contrast_per_0_01",
                ],
                "choice_lags": 1,
                "l2": 1e-6,
            },
        },
        "session_progress": "session_order divided by fixed constant 20",
        "validation": {
            "scheme": "one cohort-forward-session fold",
            "train_session_count": 10,
            "horizon_sessions": 1,
            "aggregation_unit": "animal",
            "primary_metric": "animal-balanced future-session log loss",
            "bootstrap_resamples": 5000,
            "bootstrap_seed": 20260727,
        },
        "interpretation": {
            "primary_comparison": (
                "session_progress minus session_progress_plus_lagged_dms log loss; "
                "positive favors the lagged-neural model"
            ),
            "claim_boundary": (
                "predictive association in one held-out session, not causality, "
                "biological replication, or validation of the 470-nm-only "
                "preprocessing path"
            ),
        },
        "software": {
            "fipha_commit": "82483a2",
            "unspool_commit": "1fca711574c3968cc5ff5b8609c6e40dbe99bf6c",
        },
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = repository / "benchmarks/ibl-unspool-longitudinal-protocol-v0.1.json"
    output.write_text(
        json.dumps({**body, "protocol_sha256": digest}, indent=2, sort_keys=True) + "\n"
    )
    print(output)


if __name__ == "__main__":
    main()
