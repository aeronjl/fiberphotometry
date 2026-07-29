#!/usr/bin/env python3
"""Freeze pre-outcome v0.3.1 with explicit equal-session contrast weighting."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from freeze_ibl_feedback_protocol_v3 import build_spec as build_v3_spec

from fipha.multiverse import materialize_multiverse


def build_spec(manifest: dict[str, Any]):  # type annotation inferred from v0.3 builder
    spec = build_v3_spec(manifest)
    plan = spec.base_pipeline.analysis_plan
    estimand = replace(plan.estimand, contrast_unit="session")
    corrected_plan = replace(plan, estimand=estimand)
    return replace(
        spec,
        base_pipeline=replace(spec.base_pipeline, analysis_plan=corrected_plan),
    )


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
        default=Path("benchmarks/ibl-feedback-protocol-v0.3.1.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if not manifest["readiness_gate_passed"]:
        raise SystemExit("cannot freeze v0.3.1 after a failed readiness gate")
    spec = build_spec(manifest)
    universes = materialize_multiverse(spec)
    body = {
        "schema_version": "ibl-feedback-protocol-v0.3.1",
        "status": "frozen_before_photometry-outcome access",
        "supersedes": "ibl-feedback-protocol-v0.3",
        "amendment_reason": (
            "v0.3 prose required equal session weighting within animal, but its "
            "typed estimand omitted the session contrast unit"
        ),
        "outcomes_accessed_before_amendment": False,
        "cohort_manifest_sha256": manifest["manifest_sha256"],
        "intent": "exploratory",
        "estimand": (
            "animal-level correct-minus-incorrect feedback response, with session "
            "contrasts equally weighted within animal"
        ),
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
    print(json.dumps({"protocol_sha256": fingerprint}, indent=2))


if __name__ == "__main__":
    main()
