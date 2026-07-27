#!/usr/bin/env python3
"""Execute the frozen FiberPhotometry-to-Unspool IBL benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from one.api import ONE
from run_ibl_feedback_signal_only_v32 import _load_session
from unspool import (
    BernoulliHistoryGLM,
    cohort_forward_session_splits,
    compare_models,
)

from fiberphotometry import ObservationTable, prepare_unspool_study
from fiberphotometry.events import summarize_event_windows
from fiberphotometry.preprocess import baseline_dff

PROTOCOL_SHA256 = "cf52883f2d65b495b2d6a0f3d99a757965916706e5e0c62494606798087b2de9"


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=repository / "benchmarks/ibl-unspool-longitudinal-protocol-v0.1.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=repository / "benchmarks/ibl-feedback-cohort-v0.3.json",
    )
    parser.add_argument("--cache", type=Path, default=Path.home() / "Downloads" / "ONE")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "benchmarks/ibl-unspool-longitudinal-result-v0.1.json",
    )
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text())
    _verify_protocol(protocol)
    manifest = json.loads(args.manifest.read_text())
    manifest_rows = {row["session"]: row for row in manifest["sessions"]}
    lower_order, upper_order = protocol["analysis_session_orders"]
    selected = [
        row
        for row in protocol["sessions"]
        if lower_order <= row["session_order"] <= upper_order
    ]

    one = ONE(
        base_url=manifest["one_base_url"],
        password="international",
        cache_dir=args.cache,
        silent=True,
    )
    summaries: dict[tuple[str, int], dict[str, Any]] = {}
    for index, frozen in enumerate(selected, start=1):
        print(
            f"[{index}/{len(selected)}] {frozen['subject']} "
            f"order={frozen['session_order']}",
            flush=True,
        )
        item, source_hashes, _ = _load_session(one, manifest_rows[frozen["session"]])
        if source_hashes != frozen["source_sha256"]:
            raise ValueError(f"source hashes changed for {frozen['session']}")
        processed = baseline_dff(
            item.recording, method="rolling_mean", normalization="both"
        )
        summary = summarize_event_windows(
            processed,
            item.event_times,
            baseline=(-0.5, 0.0),
            response=(0.0, 0.5),
            variable="dff",
        )
        dms = int(np.flatnonzero(processed.channel.values == "DMS")[0])
        values = np.asarray(summary.delta.values[:, dms], dtype=float)
        feedback = np.asarray(item.columns["feedback"], dtype=object)
        finite = np.isfinite(values)
        correct = finite & (feedback == "correct")
        incorrect = finite & (feedback == "incorrect")
        if not correct.any() or not incorrect.any():
            raise ValueError(
                f"both feedback levels are required in {frozen['session']}"
            )
        contrast = float(np.mean(values[correct]) - np.mean(values[incorrect]))
        summaries[(frozen["subject"], frozen["session_order"])] = {
            "subject": frozen["subject"],
            "session": frozen["session"],
            "session_order": frozen["session_order"],
            "source_sha256": source_hashes,
            "neural_contrast": contrast,
            "event_ids": np.asarray(item.event_ids, dtype=object)[finite]
            .astype(str)
            .tolist(),
            "feedback": feedback[finite].astype(str).tolist(),
            "neural_response": values[finite].tolist(),
        }

    columns: dict[str, list[Any]] = {
        "animal": [],
        "recording": [],
        "event_index": [],
        "session_order_source": [],
        "correct": [],
        "dms_feedback_response": [],
        "session_progress": [],
        "prior_dms_contrast_per_0_01": [],
    }
    for frozen in selected:
        order = frozen["session_order"]
        if order == lower_order:
            continue
        current = summaries[(frozen["subject"], order)]
        prior = summaries[(frozen["subject"], order - 1)]["neural_contrast"] / 0.01
        for trial, (feedback, response) in enumerate(
            zip(current["feedback"], current["neural_response"], strict=True)
        ):
            columns["animal"].append(frozen["subject"])
            columns["recording"].append(frozen["session"])
            columns["event_index"].append(trial)
            columns["session_order_source"].append(order)
            columns["correct"].append(int(feedback == "correct"))
            columns["dms_feedback_response"].append(response)
            columns["session_progress"].append(order / 20)
            columns["prior_dms_contrast_per_0_01"].append(prior)

    table = ObservationTable.from_columns(columns)
    handoff = prepare_unspool_study(
        table,
        subject="animal",
        session="recording",
        trial="event_index",
        session_order="session_order_source",
    )
    study = handoff.to_study()
    splits = cohort_forward_session_splits(
        study,
        min_train_sessions=protocol["validation"]["train_session_count"],
        horizon=protocol["validation"]["horizon_sessions"],
    )
    if not splits:
        raise ValueError("the frozen cohort-forward split was not available")
    split = splits[0]
    models = {
        name: BernoulliHistoryGLM(
            covariates=tuple(spec["covariates"]),
            outcome="correct",
            choice_lags=spec["choice_lags"],
            l2=spec["l2"],
        )
        for name, spec in protocol["models"].items()
    }
    report = compare_models(
        models,
        study,
        (split,),
        aggregation_column="subject",
        outcome_column="correct",
        bootstrap_resamples=protocol["validation"]["bootstrap_resamples"],
        bootstrap_seed=protocol["validation"]["bootstrap_seed"],
    )
    body = {
        "schema_version": "ibl-unspool-longitudinal-result-v0.1",
        "protocol_sha256": protocol["protocol_sha256"],
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "fiberphotometry_version": version("fiberphotometry"),
        "unspool_version": version("unspool"),
        "handoff_fingerprint": handoff.input_fingerprint,
        "observations": len(study),
        "animals": len(study.subjects),
        "session_summaries": [
            {
                key: value
                for key, value in item.items()
                if key not in {"event_ids", "feedback", "neural_response"}
            }
            for item in summaries.values()
        ],
        "comparison": report.to_dict(),
        "claim_boundary": protocol["interpretation"]["claim_boundary"],
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.output.write_text(
        json.dumps({**body, "result_sha256": digest}, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"output": str(args.output), "result_sha256": digest}, indent=2))


def _verify_protocol(protocol: dict[str, Any]) -> None:
    if protocol.get("protocol_sha256") != PROTOCOL_SHA256:
        raise ValueError("unexpected longitudinal protocol hash")
    body = dict(protocol)
    body.pop("protocol_sha256")
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != PROTOCOL_SHA256:
        raise ValueError("longitudinal protocol content verification failed")


if __name__ == "__main__":
    main()
