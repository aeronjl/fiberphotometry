"""Run the frozen raw-NWB rewarded/unrewarded DMS robustness tutorial."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import numpy as np

from fiberphotometry import (
    Contrast,
    Estimand,
    EventSummarySpec,
    Factor,
    LowpassFilterOperation,
    ObservationTable,
    PipelineSpec,
    QualityGateSpec,
    RecordingInput,
    ReferenceDFFOperation,
    StudyDesign,
    Unit,
    run_pipeline,
)
from fiberphotometry.io.dandi import resolve_dandi_download_url
from fiberphotometry.io.dandi_000971 import (
    from_dandi_000971_nwb,
    rewarded_unrewarded_nose_pokes,
)
from fiberphotometry.multiverse import (
    ChoiceRef,
    DecisionAlternative,
    DecisionNode,
    MultiverseReportGroup,
    MultiverseSpec,
    run_multiverse,
)
from fiberphotometry.planning import create_analysis_plan

DEFAULT_MANIFEST = Path("benchmarks/dandi-000971-tutorial-manifest-v0.1.json")
DEFAULT_CACHE = Path.home() / "Library/Caches/fiberphotometry/dandi-000971-tutorial"
DEFAULT_OUTPUT = Path("dandi-000971-tutorial-artifacts")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inputs, audit, failures = load_public_inputs(manifest, args.cache_dir)
    _write_json(args.output_dir / "preflight.json", audit)
    if failures:
        _write_manifest(args.output_dir, "failed", error="source preflight failed")
        raise SystemExit(f"preflight retained {len(failures)} asset failure(s)")

    spec = build_spec(manifest["assets"])
    result = run_multiverse(spec, inputs)
    reference = next(universe for universe in result.universes if universe.is_reference)
    primary = run_pipeline(reference.pipeline, inputs)
    if primary.analysis is None:
        raise RuntimeError("reference workflow was blocked by its quality policy")
    _write_json(args.output_dir / "primary-analysis.json", asdict(primary.analysis))
    (args.output_dir / "multiverse.json").write_text(result.to_json() + "\n")
    group = MultiverseReportGroup.from_choice(
        result,
        name="Fitted-reference dF/F",
        units="ΔF/F",
        node="preprocessing",
        alternatives=(
            "unfiltered_ols",
            "unfiltered_irls",
            "filtered_ols",
            "filtered_irls",
        ),
    )
    result.write_grouped_html(
        args.output_dir / "report.html",
        (group,),
        title="Rewarded minus unrewarded DMS response robustness",
    )
    _write_manifest(args.output_dir, "complete")
    print(f"Artifacts: {args.output_dir.resolve()}")
    print(f"Reference estimate: {primary.analysis.estimate:.6g} ΔF/F")
    print(f"Animals: {len(manifest['assets'])}")


def load_public_inputs(
    manifest: dict[str, Any], cache_dir: Path
) -> tuple[tuple[RecordingInput, ...], dict[str, Any], list[dict[str, str]]]:
    """Download, verify, and structurally audit the frozen public cohort."""
    inputs = []
    sessions = []
    failures = []
    for asset in manifest["assets"]:
        destination = cache_dir / f"{asset['asset_id']}.nwb"
        try:
            _download_verified(asset, destination)
            recording = from_dandi_000971_nwb(destination)
            times, conditions = rewarded_unrewarded_nose_pokes(destination)
            lower = float(recording.time.values[0]) + 5.0
            upper = float(recording.time.values[-1]) - 1.5
            complete = (times >= lower) & (times <= upper)
            complete_times = times[complete]
            complete_conditions = tuple(
                condition
                for condition, keep in zip(conditions, complete, strict=True)
                if keep
            )
            counts = {
                label: complete_conditions.count(label)
                for label in ("rewarded", "unrewarded")
            }
            if min(counts.values()) < 1:
                raise ValueError("boundary-complete events require both conditions")
            subject = str(asset["subject"])
            session = str(recording.attrs["session"])
            inputs.append(
                RecordingInput(
                    recording,
                    complete_times,
                    [
                        f"{asset['asset_id']}:{index}"
                        for index in np.flatnonzero(complete)
                    ],
                    {
                        "animal": [subject] * len(complete_times),
                        "session": [session] * len(complete_times),
                        "condition": complete_conditions,
                    },
                )
            )
            sessions.append(
                {
                    "asset_id": asset["asset_id"],
                    "subject": subject,
                    "family": asset["family"],
                    "source_events": len(times),
                    "boundary_complete_events": len(complete_times),
                    "excluded_at_boundary": int((~complete).sum()),
                    "rewarded_events": counts["rewarded"],
                    "unrewarded_events": counts["unrewarded"],
                    "source_rate_hz": recording.attrs["source_rate_hz"],
                    "analysis_rate_hz": recording.attrs["sampling_rate_hz"],
                    "verified_sha256": asset["sha256"],
                }
            )
        except Exception as error:  # retain source-level failures before execution
            failures.append(
                {
                    "asset_id": str(asset["asset_id"]),
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
    audit = {
        "schema_version": "dandi-000971-tutorial-preflight-v0.1",
        "dandiset": manifest["dandiset"],
        "published_version": manifest["published_version"],
        "doi": manifest["doi"],
        "sessions": sessions,
        "failures": failures,
        "replacement_policy": "none after protocol freeze",
    }
    return tuple(inputs), audit, failures


def build_spec(assets: list[dict[str, Any]]) -> MultiverseSpec:
    """Construct the frozen scientific specification without reading outcomes."""
    design = StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        factors=(Factor("condition", "condition", "categorical", "event"),),
    )
    estimand = Estimand(
        "dms_delta", Contrast("condition", "rewarded", "unrewarded"), "animal"
    )
    planning_table = ObservationTable.from_columns(
        {
            "event_id": [
                f"planning:{asset['asset_id']}:{condition}"
                for asset in assets
                for condition in ("rewarded", "unrewarded")
            ],
            "animal": [
                str(asset["subject"])
                for asset in assets
                for _ in ("rewarded", "unrewarded")
            ],
            "session": [
                str(asset["asset_id"])
                for asset in assets
                for _ in ("rewarded", "unrewarded")
            ],
            "condition": [
                condition for _ in assets for condition in ("rewarded", "unrewarded")
            ],
            "dms_delta": [0.0] * (2 * len(assets)),
        }
    )
    draft = create_analysis_plan(
        planning_table, design, estimand, randomized=False, intent="descriptive"
    )
    plan = create_analysis_plan(
        planning_table,
        design,
        estimand,
        randomized=False,
        intent="descriptive",
        acknowledged_assumptions=draft.required_assumptions,
    )
    base = PipelineSpec(
        (LowpassFilterOperation(3.0), ReferenceDFFOperation("irls")),
        QualityGateSpec(()),
        EventSummarySpec(
            (-5.0, 0.0),
            (0.0, 1.5),
            "DMS",
            output_column="dms_delta",
        ),
        design,
        plan,
        schema_version="2",
    )
    preprocessing = DecisionNode(
        "preprocessing",
        "preprocessing",
        (
            DecisionAlternative(
                "unfiltered_ols",
                "source-study least-squares reference fit without tutorial filtering",
                (ReferenceDFFOperation("ols"),),
            ),
            DecisionAlternative(
                "unfiltered_irls",
                "robust reference fit without tutorial filtering",
                (ReferenceDFFOperation("irls"),),
            ),
            DecisionAlternative(
                "filtered_ols",
                "3 Hz zero-phase filter then source-study least-squares fit",
                (LowpassFilterOperation(3.0), ReferenceDFFOperation("ols")),
            ),
            DecisionAlternative(
                "filtered_irls",
                "3 Hz zero-phase filter then robust reference fit",
                (LowpassFilterOperation(3.0), ReferenceDFFOperation("irls")),
            ),
        ),
    )
    windows = DecisionNode(
        "response_window",
        "event_summary",
        (
            DecisionAlternative(
                "500ms",
                "early phasic response sensitivity window",
                EventSummarySpec(
                    (-5.0, 0.0),
                    (0.0, 0.5),
                    "DMS",
                    output_column="dms_delta",
                ),
            ),
            DecisionAlternative(
                "1500ms",
                "frozen source-aligned primary response window",
                EventSummarySpec(
                    (-5.0, 0.0),
                    (0.0, 1.5),
                    "DMS",
                    output_column="dms_delta",
                ),
            ),
        ),
    )
    return MultiverseSpec(
        base,
        (preprocessing, windows),
        (),
        (
            ChoiceRef("preprocessing", "filtered_irls"),
            ChoiceRef("response_window", "1500ms"),
        ),
        "descriptive",
        direction="either",
        leave_one_unit_out=True,
    )


def _download_verified(asset: dict[str, Any], destination: Path) -> None:
    expected = (int(asset["size_bytes"]), str(asset["sha256"]))
    if destination.exists() and _digest(destination) == expected:
        return
    partial = destination.with_suffix(".nwb.partial")
    if partial.exists() and _digest(partial) == expected:
        partial.replace(destination)
        return
    size = partial.stat().st_size if partial.exists() else 0
    if size > expected[0]:
        raise ValueError(f"partial asset exceeds frozen size: {asset['asset_id']}")
    request = Request(
        resolve_dandi_download_url(asset["asset_id"]),
        headers={"Range": f"bytes={size}-"} if size else {},
    )
    with (
        urlopen(request, timeout=120) as source,
        partial.open("ab" if size else "wb") as output,
    ):
        if size and getattr(source, "status", None) != 206:
            raise ValueError("DANDI server did not honor the partial-download range")
        while chunk := source.read(1024 * 1024):
            output.write(chunk)
            size += len(chunk)
    if _digest(partial) != expected:
        raise ValueError(f"asset integrity mismatch: {asset['asset_id']}")
    partial.replace(destination)


def _digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_manifest(output: Path, status: str, *, error: str | None = None) -> None:
    names = (
        "preflight.json",
        "primary-analysis.json",
        "multiverse.json",
        "report.html",
    )
    artifacts = {
        name: {"sha256": _digest(output / name)[1]}
        for name in names
        if (output / name).exists()
    }
    payload: dict[str, Any] = {
        "schema_version": "dandi-000971-tutorial-artifacts-v0.1",
        "fiberphotometry_version": version("fiberphotometry"),
        "status": status,
        "artifacts": artifacts,
        "scientific_protocol": "protocol-dandi-000971-tutorial-v0.1",
    }
    if error is not None:
        payload["error"] = error
    _write_json(output / "manifest.json", payload)


if __name__ == "__main__":
    main()
