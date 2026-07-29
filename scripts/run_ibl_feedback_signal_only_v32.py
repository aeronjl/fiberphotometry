#!/usr/bin/env python3
"""Execute the checksum-frozen IBL signal-only multiverse v0.3.2."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from freeze_ibl_feedback_protocol_v32 import build_spec
from one.api import ONE

from fipha import ObservationTable, assess_signal_recording
from fipha.events import summarize_event_windows
from fipha.io.ibl import from_ibl_tables
from fipha.planning import execute_analysis_plan
from fipha.preprocess import baseline_dff

COHORT_SHA256 = "38197a26ab4804131423a9650a473a11e2b14f09ac2877875b574f2770d894e6"
PROTOCOL_SHA256 = "237f2263a969cb52db71d771286aee093c0ef07fa151d74ae463decec2d3c44a"
WINDOWS = {
    "standard": ((-0.5, 0.0), (0.0, 0.5)),
    "early": ((-0.5, 0.0), (0.0, 0.25)),
    "displaced_baseline": ((-1.0, -0.2), (0.0, 0.5)),
}


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
        default=repository / "benchmarks/ibl-feedback-protocol-v0.3.2.json",
    )
    parser.add_argument("--cache", type=Path, default=Path.home() / "Downloads" / "ONE")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "benchmarks/ibl-feedback-results-v0.3.2.json",
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    protocol = json.loads(args.protocol.read_text())
    _verify_frozen_input(manifest, "manifest_sha256", COHORT_SHA256)
    _verify_frozen_input(protocol, "protocol_sha256", PROTOCOL_SHA256)
    if protocol["cohort_manifest_sha256"] != COHORT_SHA256:
        raise SystemExit("protocol does not reference the frozen cohort")
    spec = build_spec(manifest)
    materialized = _materialized_by_choices(protocol, spec)
    rows = [row for row in manifest["sessions"] if row["status"] == "eligible"]
    if args.limit is not None:
        rows = rows[: args.limit]

    one = ONE(
        base_url=manifest["one_base_url"],
        password="international",
        cache_dir=args.cache,
        silent=True,
    )
    outcome_columns: dict[tuple[str, str], list[float]] = defaultdict(list)
    common: dict[str, list[str]] = defaultdict(list)
    diagnostics = []
    estimator_failures: dict[str, list[str]] = defaultdict(list)
    for index, row in enumerate(rows, start=1):
        print(f"[{index}/{len(rows)}] {row['subject']} {row['session']}", flush=True)
        try:
            item, source_hashes, roi_column = _load_session(one, row)
            report = assess_signal_recording(item.recording)
        except Exception as error:
            rendered = f"{row['session']}: {type(error).__name__}: {error}"
            for estimator in ("double_exponential", "asls", "published_rolling"):
                estimator_failures[estimator].append(rendered)
            diagnostics.append(
                {"session": row["session"], "status": "load_failed", "error": rendered}
            )
            continue

        for event_id, feedback in zip(
            item.event_ids, item.columns["feedback"], strict=True
        ):
            common["event_id"].append(str(event_id))
            common["animal"].append(str(row["subject"]))
            common["session"].append(str(row["session"]))
            common["feedback"].append(str(feedback))
        session_result: dict[str, Any] = {
            "session": row["session"],
            "subject": row["subject"],
            "status": "loaded",
            "events": len(item.event_ids),
            "sampling_rate_hz": row["sampling_rate_hz"],
            "roi_column": roi_column,
            "source_sha256": source_hashes,
            "qc_warnings": sorted(
                {warning for channel in report.channels for warning in channel.warnings}
            ),
            "estimators": {},
        }
        for estimator, method in (
            ("double_exponential", "double_exponential"),
            ("published_rolling", "rolling_mean"),
        ):
            try:
                processed = baseline_dff(
                    item.recording, method=method, normalization="both"
                )
                operation = json.loads(processed.attrs["fipha_baseline_dff"])
                session_result["estimators"][estimator] = {
                    "status": "success",
                    "failed_short_runs": operation["failed_short_runs"],
                }
                for normalization, variable in (
                    ("divide", "dff"),
                    ("subtract", "baseline_subtracted"),
                ):
                    if estimator == "published_rolling" and normalization == "subtract":
                        continue
                    for window, (baseline, response) in WINDOWS.items():
                        summary = summarize_event_windows(
                            processed,
                            item.event_times,
                            baseline=baseline,
                            response=response,
                            variable=variable,
                        )
                        dms = int(np.flatnonzero(processed.channel.values == "DMS")[0])
                        values = np.asarray(summary.delta.values[:, dms], dtype=float)
                        outcome_columns[
                            (estimator, f"{normalization}_{window}")
                        ].extend(values.tolist())
            except Exception as error:
                rendered = f"{row['session']}: {type(error).__name__}: {error}"
                estimator_failures[estimator].append(rendered)
                session_result["estimators"][estimator] = {
                    "status": "failed",
                    "error": rendered,
                }
                for normalization in ("divide", "subtract"):
                    if estimator == "published_rolling" and normalization == "subtract":
                        continue
                    for window in WINDOWS:
                        outcome_columns[
                            (estimator, f"{normalization}_{window}")
                        ].extend([float("nan")] * len(item.event_ids))
        diagnostics.append(session_result)

    universes = []
    successful_tables: dict[str, ObservationTable] = {}
    for frozen in protocol["materialized_universes"]:
        choices = {item["node"]: item["alternative"] for item in frozen["choices"]}
        estimator = choices["baseline_estimator"]
        normalization_window = choices["normalization_window"]
        record: dict[str, Any] = {
            "universe_id": frozen["universe_id"],
            "choices": frozen["choices"],
            "units": "fractional_dff"
            if normalization_window.startswith("divide_")
            else "acquired_fluorescence",
        }
        if frozen["status"] == "incompatible":
            universes.append(
                {
                    **record,
                    "status": "incompatible",
                    "error": frozen["incompatibility"],
                }
            )
            continue
        failures = estimator_failures[estimator]
        if failures:
            universes.append(
                {
                    **record,
                    "status": "failed",
                    "error": "one or more session preprocessing failures",
                    "session_errors": failures,
                }
            )
            continue
        outcome = outcome_columns[(estimator, normalization_window)]
        table = ObservationTable.from_columns({**common, "feedback_delta": outcome})
        pipeline = materialized[(estimator, normalization_window)]
        try:
            result = execute_analysis_plan(
                pipeline.analysis_plan, table, pipeline.design
            )
            successful_tables[frozen["universe_id"]] = table
            universes.append(
                {
                    **record,
                    "status": "success",
                    "estimate": result.estimate,
                    "confidence_interval": result.confidence_interval,
                    "p_value": result.p_value,
                    "analysis_input_sha256": result.input_fingerprint,
                    "finite_event_summaries": int(np.isfinite(outcome).sum()),
                    "total_event_summaries": len(outcome),
                }
            )
        except Exception as error:
            universes.append(
                {
                    **record,
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    reference = next(
        item
        for item in universes
        if {choice["alternative"] for choice in item["choices"]}
        == {"published_rolling", "divide_standard"}
    )
    leave_one_out = []
    if reference["status"] == "success":
        table = successful_tables[reference["universe_id"]]
        pipeline = materialized[("published_rolling", "divide_standard")]
        animals = table.values("animal")
        for animal in sorted(set(animals.tolist())):
            keep = np.flatnonzero(animals != animal)
            reduced = ObservationTable(
                {
                    name: tuple(np.asarray(values, dtype=object)[keep].tolist())
                    for name, values in table.columns.items()
                }
            )
            try:
                result = execute_analysis_plan(
                    pipeline.analysis_plan, reduced, pipeline.design
                )
                leave_one_out.append(
                    {
                        "omitted_animal": animal,
                        "status": "success",
                        "estimate": result.estimate,
                    }
                )
            except Exception as error:
                leave_one_out.append(
                    {
                        "omitted_animal": animal,
                        "status": "failed",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )

    body = {
        "schema_version": "ibl-feedback-results-v0.3.2",
        "protocol_sha256": PROTOCOL_SHA256,
        "cohort_manifest_sha256": COHORT_SHA256,
        "execution_timestamp_utc": datetime.now(UTC).isoformat(),
        "outcome_access": "photometry outcomes accessed under disclosed v0.3.2 freeze",
        "sessions_requested": len(rows),
        "sessions_loaded": sum(item["status"] == "loaded" for item in diagnostics),
        "animals": len({row["subject"] for row in rows}),
        "event_summaries": len(common["event_id"]),
        "status_counts": dict(Counter(item["status"] for item in universes)),
        "evidence_lanes": _evidence_lanes(universes),
        "universes": universes,
        "reference_leave_one_animal_out": leave_one_out,
        "session_diagnostics": diagnostics,
    }
    result_sha256 = hashlib.sha256(
        json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    args.output.write_text(
        json.dumps({**body, "result_sha256": result_sha256}, indent=2, sort_keys=True)
        + "\n"
    )
    print(json.dumps({"output": str(args.output), **body["status_counts"]}, indent=2))


def _load_session(one: ONE, row: dict[str, Any]):
    eid = row["session"]
    signal_path = Path(
        one.load_dataset(
            eid,
            "photometry.signal.pqt",
            collection="alf/photometry",
            download_only=True,
        )
    )
    roi_path = Path(
        one.load_dataset(
            eid,
            "photometryROI.locations.pqt",
            collection="alf/photometry",
            download_only=True,
        )
    )
    trials_path = Path(
        one.load_dataset(
            eid, "_ibl_trials.table.pqt", collection="alf", download_only=True
        )
    )
    roi = pd.read_parquet(roi_path, columns=["brain_region"])
    dms_columns = [
        str(column)
        for column, region in roi["brain_region"].items()
        if str(region) == "DMS"
    ]
    if len(dms_columns) != 1:
        raise ValueError(f"expected exactly one DMS ROI column, found {dms_columns}")
    roi_column = dms_columns[0]
    signal = pd.read_parquet(
        signal_path, columns=["times", "wavelength", "include", roi_column]
    )
    trials = pd.read_parquet(trials_path, columns=["feedback_times", "feedbackType"])
    recording = from_ibl_tables(
        signal_table=signal,
        roi_locations={roi_column: "DMS"},
        subject=str(row["subject"]),
        session=str(eid),
        reference_wavelength=None,
    )
    times = np.asarray(trials["feedback_times"], dtype=float)
    feedback = np.asarray(trials["feedbackType"], dtype=float)
    usable = np.zeros(len(times), dtype=bool)
    for lower, upper in row["valid_time_intervals"]:
        usable |= (times >= lower + 1.0) & (times <= upper - 0.5)
    usable &= np.isfinite(times) & np.isin(feedback, (-1, 1))
    selected = np.flatnonzero(usable)
    expected = row["usable_correct"] + row["usable_incorrect"]
    if len(selected) != expected:
        raise ValueError(f"frozen event count {expected} changed to {len(selected)}")
    from fipha.pipeline import RecordingInput

    item = RecordingInput(
        recording,
        times[selected].tolist(),
        [f"{eid}:{index}" for index in selected],
        {
            "animal": [str(row["subject"])] * len(selected),
            "session": [str(eid)] * len(selected),
            "feedback": [
                "correct" if feedback[index] == 1 else "incorrect" for index in selected
            ],
        },
    )
    return (
        item,
        {
            "signal": _file_sha256(signal_path),
            "roi": _file_sha256(roi_path),
            "trials": _file_sha256(trials_path),
        },
        roi_column,
    )


def _materialized_by_choices(protocol: dict[str, Any], spec: Any):
    from fipha.multiverse import materialize_multiverse

    output = {}
    for universe in materialize_multiverse(spec):
        choices = {choice.node: choice.alternative for choice in universe.choices}
        output[(choices["baseline_estimator"], choices["normalization_window"])] = (
            universe.pipeline
        )
    frozen = {item["universe_id"] for item in protocol["materialized_universes"]}
    if {universe.universe_id for universe in materialize_multiverse(spec)} != frozen:
        raise SystemExit("materialized universe IDs differ from frozen protocol")
    return output


def _evidence_lanes(universes: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for lane in ("fractional_dff", "acquired_fluorescence"):
        selected = [
            item
            for item in universes
            if item["units"] == lane and item["status"] == "success"
        ]
        estimates = [item["estimate"] for item in selected]
        output[lane] = {
            "successful_universes": len(selected),
            "estimate_range": [min(estimates), max(estimates)] if estimates else None,
            "median_estimate": float(np.median(estimates)) if estimates else None,
            "fraction_positive": float(np.mean(np.asarray(estimates) > 0))
            if estimates
            else None,
        }
    return output


def _verify_frozen_input(payload: dict[str, Any], key: str, expected: str) -> None:
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
