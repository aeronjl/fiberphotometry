#!/usr/bin/env python3
"""Execute the frozen held-out IBL regularized-AsLS comparison."""

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
from one.api import ONE

from fipha.events import summarize_event_windows
from fipha.io.ibl import from_ibl_tables
from fipha.preprocess import baseline_dff, resample_recording

PROTOCOL_SHA256 = "f7a448ee82779d1332dea86f748536bb36a3f1845d116dcd2b7f8f56ea9f7bcf"
METHODS = (
    "raw_double_exponential",
    "raw_published_rolling",
    "regularized_double_exponential",
    "regularized_published_rolling",
    "regularized_asls",
)
COMPARATOR_PAIRS = (
    ("raw_double_exponential", "regularized_double_exponential"),
    ("raw_published_rolling", "regularized_published_rolling"),
)
ASLS_PAIRS = (
    ("regularized_asls", "regularized_double_exponential"),
    ("regularized_asls", "regularized_published_rolling"),
)


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=repository / "benchmarks/ibl-regularized-asls-protocol-v0.1.json",
    )
    parser.add_argument("--cache", type=Path, default=Path.home() / "Downloads" / "ONE")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository / "benchmarks/ibl-regularized-asls-results-v0.1.json",
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    _verify_payload(protocol, "protocol_sha256", PROTOCOL_SHA256)
    rows = protocol["sessions"]
    if args.limit is not None:
        rows = rows[: args.limit]
    one = ONE(
        base_url="https://openalyx.internationalbrainlab.org",
        password="international",
        cache_dir=args.cache,
        silent=True,
    )
    sessions = []
    pooled_events: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    failures = []
    for index, row in enumerate(rows, start=1):
        print(f"[{index}/{len(rows)}] {row['subject']} {row['session']}", flush=True)
        try:
            session, event_pairs = _run_session(one, row)
            sessions.append(session)
            for pair, values in event_pairs.items():
                pooled_events[pair].extend(values)
        except Exception as error:
            failures.append(
                {
                    "session": row["session"],
                    "subject": row["subject"],
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
    summary = _summary(sessions, pooled_events)
    gates = _gates(protocol["acceptance"], sessions, summary, failures, len(rows))
    body = {
        "schema_version": "ibl-regularized-asls-results-v0.1",
        "execution_timestamp_utc": datetime.now(UTC).isoformat(),
        "protocol_sha256": PROTOCOL_SHA256,
        "sessions_requested": len(rows),
        "sessions_completed": len(sessions),
        "failures": failures,
        "sessions": sessions,
        "summary": summary,
        "gates": gates,
        "interpretation": (
            "Held-out engineering comparison without population inference; "
            "AsLS agreement with another baseline is descriptive, not truth."
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.output.write_text(
        json.dumps({**body, "result_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )
    print(json.dumps({"result_sha256": fingerprint, "gates": gates}, indent=2))
    if args.limit is None and not gates["passed"]:
        raise SystemExit("held-out regularized-AsLS gate failed; result retained")


def _run_session(
    one: ONE, row: dict[str, Any]
) -> tuple[dict[str, Any], dict[tuple[str, str], list[tuple[float, float]]]]:
    paths = _paths(one, row["session"])
    for name, path in paths.items():
        expected = row["source"][name]
        if path.stat().st_size != expected["size_bytes"]:
            raise ValueError(f"{name} source size changed")
        if _file_sha256(path) != expected["sha256"]:
            raise ValueError(f"{name} source hash changed")
    roi = pd.read_parquet(paths["roi"], columns=["brain_region"])
    dms_columns = [
        str(column)
        for column, region in roi["brain_region"].items()
        if str(region) == "DMS"
    ]
    if len(dms_columns) != 1:
        raise ValueError(f"expected exactly one DMS column, found {dms_columns}")
    signal = pd.read_parquet(
        paths["signal"], columns=["times", "wavelength", "include", dms_columns[0]]
    )
    trials = pd.read_parquet(
        paths["trials"], columns=["feedback_times", "feedbackType"]
    )
    recording = from_ibl_tables(
        signal_table=signal,
        roi_locations={dms_columns[0]: "DMS"},
        subject=row["subject"],
        session=row["session"],
        reference_wavelength=None,
    )
    regularized = resample_recording(recording, rate_hz="median", max_gap_factor=1.5)
    operation = json.loads(regularized.attrs["fipha_operations"])[-1]
    event_times, conditions = _events(trials, row)
    processed: dict[str, Any] = {}
    method_records: dict[str, Any] = {}
    for name in METHODS:
        source = regularized if name.startswith("regularized_") else recording
        method = (
            "double_exponential"
            if name.endswith("double_exponential")
            else "rolling_mean"
            if name.endswith("published_rolling")
            else "asls"
        )
        result = baseline_dff(source, method=method, normalization="divide")
        summary = summarize_event_windows(
            result,
            event_times,
            baseline=(-1.0, 0.0),
            response=(0.0, 0.5),
            variable="dff",
        )
        deltas = np.asarray(summary.delta.values[:, 0], dtype=float)
        dispositions = np.asarray(summary.event_disposition.values[:, 0], dtype=str)
        processed[name] = {
            "time": np.asarray(result.time.values, dtype=float),
            "dff": np.asarray(result.dff.values[:, 0], dtype=float),
            "baseline": np.asarray(result.fitted_baseline.values[:, 0], dtype=float),
            "deltas": deltas,
        }
        method_records[name] = {
            "finite_baseline_fraction": float(
                np.isfinite(result.fitted_baseline.values[:, 0]).mean()
            ),
            "complete_events": int(np.sum(dispositions == "complete")),
            "total_events": len(event_times),
            "complete_event_fraction": float(np.mean(dispositions == "complete")),
            "event_dispositions": dict(sorted(Counter(dispositions.tolist()).items())),
        }

    comparisons = {}
    event_pairs: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for left, right in (*COMPARATOR_PAIRS, *ASLS_PAIRS):
        key = f"{left}__vs__{right}"
        comparison, pairs = _compare(processed[left], processed[right])
        comparisons[key] = comparison
        event_pairs[(left, right)] = pairs
    contrasts = {
        name: _session_contrast(processed[name]["deltas"], conditions)
        for name in METHODS
    }
    return (
        {
            "session": row["session"],
            "subject": row["subject"],
            "source_integrity": True,
            "events": len(event_times),
            "regularization": {
                key: operation[key]
                for key in (
                    "source_interval_cv",
                    "source_median_interval_s",
                    "nearest_source_distance_max_s",
                    "nearest_source_distance_p95_s",
                    "gap_masked_target_fraction",
                    "interpolated_target_fraction",
                )
            },
            "methods": method_records,
            "comparisons": comparisons,
            "session_contrasts": contrasts,
        },
        event_pairs,
    )


def _compare(
    left: dict[str, np.ndarray], right: dict[str, np.ndarray]
) -> tuple[dict[str, float | int], list[tuple[float, float]]]:
    right_dff = _onto(left["time"], right["time"], right["dff"])
    right_baseline = _onto(left["time"], right["time"], right["baseline"])
    trace = _pair_metrics(left["dff"], right_dff)
    baseline = _pair_metrics(left["baseline"], right_baseline)
    event = _pair_metrics(left["deltas"], right["deltas"])
    valid = np.isfinite(left["deltas"]) & np.isfinite(right["deltas"])
    pairs = list(
        zip(
            left["deltas"][valid].tolist(),
            right["deltas"][valid].tolist(),
            strict=True,
        )
    )
    return (
        {
            "trace_correlation": trace["correlation"],
            "trace_normalized_rmse": trace["normalized_rmse"],
            "baseline_correlation": baseline["correlation"],
            "baseline_normalized_rmse": baseline["normalized_rmse"],
            "event_delta_correlation": event["correlation"],
            "event_delta_normalized_mad": event["normalized_mad"],
            "paired_events": event["count"],
        },
        pairs,
    )


def _pair_metrics(left: np.ndarray, right: np.ndarray) -> dict[str, float | int]:
    valid = np.isfinite(left) & np.isfinite(right)
    x, y = left[valid], right[valid]
    if len(x) < 3:
        return {
            "count": len(x),
            "correlation": float("nan"),
            "normalized_rmse": float("nan"),
            "normalized_mad": float("nan"),
        }
    scale = _robust_scale(x)
    difference = x - y
    return {
        "count": len(x),
        "correlation": float(np.corrcoef(x, y)[0, 1]),
        "normalized_rmse": float(np.sqrt(np.mean(difference**2)) / scale),
        "normalized_mad": float(np.median(np.abs(difference)) / scale),
    }


def _robust_scale(values: np.ndarray) -> float:
    scale = float((np.quantile(values, 0.75) - np.quantile(values, 0.25)) / 1.349)
    if scale <= np.finfo(float).eps:
        scale = float(np.std(values))
    return max(scale, np.finfo(float).eps)


def _onto(
    target: np.ndarray, source_time: np.ndarray, values: np.ndarray
) -> np.ndarray:
    valid = np.isfinite(values)
    output = np.full(len(target), np.nan)
    if valid.sum() < 2:
        return output
    changes = np.diff(np.concatenate(([False], valid, [False])).astype(int))
    starts = np.flatnonzero(changes == 1)
    stops = np.flatnonzero(changes == -1)
    for start, stop in zip(starts, stops, strict=True):
        if stop - start < 2:
            continue
        within = (target >= source_time[start]) & (target <= source_time[stop - 1])
        output[within] = np.interp(
            target[within], source_time[start:stop], values[start:stop]
        )
    return output


def _session_contrast(values: np.ndarray, conditions: np.ndarray) -> float | None:
    correct = values[(conditions == "correct") & np.isfinite(values)]
    incorrect = values[(conditions == "incorrect") & np.isfinite(values)]
    if not len(correct) or not len(incorrect):
        return None
    return float(np.mean(correct) - np.mean(incorrect))


def _events(trials: pd.DataFrame, row: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    times = np.asarray(trials["feedback_times"], dtype=float)
    feedback = np.asarray(trials["feedbackType"], dtype=float)
    usable = np.zeros(len(times), dtype=bool)
    for lower, upper in row["valid_time_intervals"]:
        usable |= (times >= lower + 1.0) & (times <= upper - 0.5)
    usable &= np.isfinite(times) & np.isin(feedback, (-1, 1))
    expected = row["usable_correct"] + row["usable_incorrect"]
    if int(usable.sum()) != expected:
        raise ValueError(f"frozen event count changed: {usable.sum()} != {expected}")
    return times[usable], np.where(feedback[usable] == 1, "correct", "incorrect")


def _summary(
    sessions: list[dict[str, Any]],
    pooled_events: dict[tuple[str, str], list[tuple[float, float]]],
) -> dict[str, Any]:
    method_summary = {}
    for method in METHODS:
        records = [session["methods"][method] for session in sessions]
        method_summary[method] = {
            "sessions": len(records),
            "minimum_finite_baseline_fraction": min(
                (record["finite_baseline_fraction"] for record in records),
                default=None,
            ),
            "complete_events": sum(record["complete_events"] for record in records),
            "total_events": sum(record["total_events"] for record in records),
            "complete_event_fraction": (
                sum(record["complete_events"] for record in records)
                / sum(record["total_events"] for record in records)
                if records
                else None
            ),
        }
    comparison_summary = {}
    for left, right in (*COMPARATOR_PAIRS, *ASLS_PAIRS):
        key = f"{left}__vs__{right}"
        records = [session["comparisons"][key] for session in sessions]
        pairs = np.asarray(pooled_events[(left, right)], dtype=float)
        pooled = (
            _pair_metrics(pairs[:, 0], pairs[:, 1])
            if len(pairs)
            else _pair_metrics(np.array([]), np.array([]))
        )
        signs = [
            (
                session["session_contrasts"][left],
                session["session_contrasts"][right],
            )
            for session in sessions
            if session["session_contrasts"][left] is not None
            and session["session_contrasts"][right] is not None
        ]
        comparison_summary[key] = {
            "case_count": len(records),
            "trace_correlation_median": _median(records, "trace_correlation"),
            "trace_correlation_minimum": _minimum(records, "trace_correlation"),
            "trace_normalized_rmse_median": _median(records, "trace_normalized_rmse"),
            "baseline_correlation_median": _median(records, "baseline_correlation"),
            "baseline_normalized_rmse_median": _median(
                records, "baseline_normalized_rmse"
            ),
            "pooled_event_delta_correlation": pooled["correlation"],
            "pooled_event_delta_normalized_mad": pooled["normalized_mad"],
            "paired_events": pooled["count"],
            "session_contrast_pairs": len(signs),
            "session_contrast_sign_agreement": (
                float(np.mean([np.sign(a) == np.sign(b) for a, b in signs]))
                if signs
                else None
            ),
        }
    distance_fractions = [
        session["regularization"]["nearest_source_distance_max_s"]
        / session["regularization"]["source_median_interval_s"]
        for session in sessions
    ]
    return {
        "methods": method_summary,
        "comparisons": comparison_summary,
        "maximum_nearest_source_distance_fraction": max(
            distance_fractions, default=None
        ),
    }


def _gates(
    acceptance: dict[str, Any],
    sessions: list[dict[str, Any]],
    summary: dict[str, Any],
    failures: list[dict[str, Any]],
    expected_sessions: int,
) -> dict[str, Any]:
    checks = {
        "all_sources_and_sessions_completed": (
            not failures and len(sessions) == expected_sessions
        ),
        "all_methods_execute_all_sessions": all(
            item["sessions"] == expected_sessions
            for item in summary["methods"].values()
        ),
        "finite_baseline_fraction": all(
            item["minimum_finite_baseline_fraction"]
            >= acceptance["finite_baseline_fraction_min"]
            for item in summary["methods"].values()
        ),
        "complete_event_fraction": all(
            item["complete_event_fraction"] >= acceptance["complete_event_fraction_min"]
            for item in summary["methods"].values()
        ),
        "nearest_source_distance": (
            summary["maximum_nearest_source_distance_fraction"]
            <= acceptance["nearest_source_distance_max_fraction_of_interval"]
        ),
    }
    for left, right in COMPARATOR_PAIRS:
        name = f"{left}__vs__{right}"
        item = summary["comparisons"][name]
        checks[f"{name}:trace_correlation_median"] = (
            item["trace_correlation_median"]
            >= acceptance["comparator_trace_correlation_median_min"]
        )
        checks[f"{name}:trace_correlation_case"] = (
            item["trace_correlation_minimum"]
            >= acceptance["comparator_trace_correlation_case_min"]
        )
        checks[f"{name}:trace_normalized_rmse"] = (
            item["trace_normalized_rmse_median"]
            <= acceptance["comparator_trace_normalized_rmse_median_max"]
        )
        checks[f"{name}:event_delta_correlation"] = (
            item["pooled_event_delta_correlation"]
            >= acceptance["comparator_event_delta_correlation_min"]
        )
        checks[f"{name}:event_delta_normalized_mad"] = (
            item["pooled_event_delta_normalized_mad"]
            <= acceptance["comparator_event_delta_normalized_mad_max"]
        )
    return {"passed": all(checks.values()), "checks": checks}


def _median(records: list[dict[str, Any]], key: str) -> float | None:
    values = [float(record[key]) for record in records if np.isfinite(record[key])]
    return float(np.median(values)) if values else None


def _minimum(records: list[dict[str, Any]], key: str) -> float | None:
    values = [float(record[key]) for record in records if np.isfinite(record[key])]
    return min(values) if values else None


def _paths(one: ONE, eid: str) -> dict[str, Path]:
    return {
        "signal": Path(
            one.load_dataset(
                eid,
                "photometry.signal.pqt",
                collection="alf/photometry",
                download_only=True,
            )
        ),
        "roi": Path(
            one.load_dataset(
                eid,
                "photometryROI.locations.pqt",
                collection="alf/photometry",
                download_only=True,
            )
        ),
        "trials": Path(
            one.load_dataset(
                eid, "_ibl_trials.table.pqt", collection="alf", download_only=True
            )
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
