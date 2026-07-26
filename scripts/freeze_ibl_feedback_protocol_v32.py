#!/usr/bin/env python3
"""Freeze v0.3.2 after outcome-blind structural compatibility correction."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from freeze_ibl_feedback_protocol_v31 import build_spec as build_v31_spec

from fiberphotometry import (
    ChoiceRef,
    CompatibilityRule,
    materialize_multiverse,
)


def build_spec(manifest: dict[str, Any]):  # return type follows the v0.3.1 builder
    spec = build_v31_spec(manifest)
    asls_rule = CompatibilityRule(
        (ChoiceRef("baseline_estimator", "asls"),),
        "AsLS requires a regular time axis; the frozen raw IBL sessions require an "
        "explicit regularization operation that this protocol did not declare",
    )
    return replace(spec, compatibility_rules=(*spec.compatibility_rules, asls_rule))


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
        default=Path("benchmarks/ibl-feedback-protocol-v0.3.2.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    spec = build_spec(manifest)
    universes = materialize_multiverse(spec)
    body = {
        "schema_version": "ibl-feedback-protocol-v0.3.2",
        "status": "frozen_after_limited_outcome_access",
        "supersedes": "ibl-feedback-protocol-v0.3.1",
        "cohort_manifest_sha256": manifest["manifest_sha256"],
        "amendment_reason": (
            "outcome-blind compatibility preflight showed that undeclared timestamp "
            "regularization makes every AsLS universe mechanically incompatible"
        ),
        "outcome_access_before_amendment": {
            "sessions_downloaded": 19,
            "aggregate_results_computed": False,
            "effect_estimates_inspected": False,
            "structural_failure_inspected": (
                "AsLS rejected the first session because its interval CV was 0.00569"
            ),
            "note": (
                "the interrupted runner computed some session-level summaries in "
                "memory, but none were aggregated, reported, or used to choose the "
                "compatibility rule"
            ),
        },
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
        "outcome_access_at_freeze": "limited and disclosed above",
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    args.output.write_text(
        json.dumps({**body, "protocol_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )
    print(json.dumps({"protocol_sha256": fingerprint}, indent=2))


if __name__ == "__main__":
    main()
