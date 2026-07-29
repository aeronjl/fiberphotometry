#!/usr/bin/env python3
"""Freeze the typed signal-only IBL feedback multiverse v0.3."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fipha import (
    BaselineDFFOperation,
    Contrast,
    Estimand,
    EventSummarySpec,
    Factor,
    ObservationTable,
    PipelineSpec,
    QualityGateSpec,
    StudyDesign,
    Unit,
)
from fipha.multiverse import (
    ChoiceRef,
    CompatibilityRule,
    DecisionAlternative,
    DecisionNode,
    MultiverseSpec,
    materialize_multiverse,
)
from fipha.planning import create_analysis_plan

WINDOWS = {
    "standard": ((-0.5, 0.0), (0.0, 0.5)),
    "early": ((-0.5, 0.0), (0.0, 0.25)),
    "displaced_baseline": ((-1.0, -0.2), (0.0, 0.5)),
}


def build_spec(manifest: dict[str, Any]) -> MultiverseSpec:
    """Build the typed spec using outcome-free event counts for plan routing."""
    table = _routing_table(manifest)
    design = StudyDesign(
        observation_id="event_id",
        units=(
            Unit("animal", "animal"),
            Unit("session", "session", "animal"),
            Unit("event", "event_id", "session"),
        ),
        factors=(Factor("feedback", "feedback", "categorical", "event"),),
    )
    estimand = Estimand(
        "feedback_delta", Contrast("feedback", "correct", "incorrect"), "animal"
    )
    draft = create_analysis_plan(
        table, design, estimand, randomized=False, intent="exploratory"
    )
    plan = create_analysis_plan(
        table,
        design,
        estimand,
        randomized=False,
        intent="exploratory",
        acknowledged_assumptions=draft.required_assumptions,
    )
    base_summary = EventSummarySpec(
        *WINDOWS["standard"],
        "DMS",
        variable="dff",
        output_column="feedback_delta",
    )
    base = PipelineSpec(
        (BaselineDFFOperation("rolling_mean", normalization="both"),),
        QualityGateSpec(()),
        base_summary,
        design,
        plan,
        schema_version="2",
    )
    estimator = DecisionNode(
        "baseline_estimator",
        "preprocessing",
        (
            DecisionAlternative(
                "double_exponential",
                "robust non-negative two-timescale bleaching fit",
                (BaselineDFFOperation("double_exponential", normalization="both"),),
            ),
            DecisionAlternative(
                "asls",
                "rate-aware asymmetric least-squares lower envelope",
                (BaselineDFFOperation("asls", normalization="both"),),
            ),
            DecisionAlternative(
                "published_rolling",
                "published centred 60-second rolling-mean comparator",
                (BaselineDFFOperation("rolling_mean", normalization="both"),),
            ),
        ),
    )
    summaries = []
    for normalization, variable in (
        ("divide", "dff"),
        ("subtract", "baseline_subtracted"),
    ):
        for window_name, (baseline, response) in WINDOWS.items():
            summaries.append(
                DecisionAlternative(
                    f"{normalization}_{window_name}",
                    f"{normalization} normalization with {window_name} event window",
                    EventSummarySpec(
                        baseline,
                        response,
                        "DMS",
                        variable=variable,
                        output_column="feedback_delta",
                    ),
                )
            )
    summary = DecisionNode("normalization_window", "event_summary", tuple(summaries))
    incompatible = tuple(
        CompatibilityRule(
            (
                ChoiceRef("baseline_estimator", "published_rolling"),
                ChoiceRef("normalization_window", f"subtract_{window_name}"),
            ),
            "the published rolling comparator was declared only as divisive dF/F",
        )
        for window_name in WINDOWS
    )
    return MultiverseSpec(
        base,
        (estimator, summary),
        incompatible,
        (
            ChoiceRef("baseline_estimator", "published_rolling"),
            ChoiceRef("normalization_window", "divide_standard"),
        ),
        "exploratory",
        direction="either",
        leave_one_unit_out=True,
    )


def _routing_table(manifest: dict[str, Any]) -> ObservationTable:
    columns: dict[str, list[str | float]] = {
        "event_id": [],
        "animal": [],
        "session": [],
        "feedback": [],
        "feedback_delta": [],
    }
    for row in manifest["sessions"]:
        if row["status"] != "eligible":
            continue
        for feedback, count_key in (
            ("correct", "usable_correct"),
            ("incorrect", "usable_incorrect"),
        ):
            for index in range(int(row[count_key])):
                columns["event_id"].append(f"{row['session']}:{feedback}:{index}")
                columns["animal"].append(str(row["subject"]))
                columns["session"].append(str(row["session"]))
                columns["feedback"].append(feedback)
                columns["feedback_delta"].append(0.0)
    return ObservationTable.from_columns(columns)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("benchmarks/ibl-feedback-cohort-v0.3.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/ibl-feedback-protocol-v0.3.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if not manifest["readiness_gate_passed"]:
        raise SystemExit("cannot freeze v0.3 after a failed readiness gate")
    spec = build_spec(manifest)
    universes = materialize_multiverse(spec)
    body = {
        "schema_version": "ibl-feedback-protocol-v0.3",
        "status": "frozen_before_photometry-outcome access",
        "cohort_manifest_sha256": manifest["manifest_sha256"],
        "intent": "exploratory",
        "estimand": "animal-level correct-minus-incorrect feedback response",
        "reference_role": (
            "published rolling/standard is a display and leave-one-animal-out "
            "reference, not a preferred or confirmatory workflow"
        ),
        "spec": json.loads(spec.to_json()),
        "materialized_universes": [
            {
                "universe_id": universe.universe_id,
                "choices": [
                    {"node": choice.node, "alternative": choice.alternative}
                    for choice in universe.choices
                ],
                "status": (
                    "incompatible"
                    if universe.incompatibility is not None
                    else "eligible_for_execution"
                ),
                "incompatibility": universe.incompatibility,
            }
            for universe in universes
        ],
        "eligible_universe_count": sum(
            universe.incompatibility is None for universe in universes
        ),
        "incompatible_universe_count": sum(
            universe.incompatibility is not None for universe in universes
        ),
        "outcome_access_at_freeze": (
            "no photometry values or condition-specific fluorescence summaries"
        ),
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload = {**body, "protocol_sha256": fingerprint}
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "eligible_universes": body["eligible_universe_count"],
                "incompatible_universes": body["incompatible_universe_count"],
                "protocol_sha256": fingerprint,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
