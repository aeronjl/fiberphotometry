"""Freeze the disclosed metric amendment to transient-gap protocol v0.1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def main() -> None:
    original: dict[str, Any] = json.loads(
        Path("benchmarks/transient-gap-protocol-v0.1.json").read_text()
    )
    parent_hash = original.pop("protocol_sha256")
    original["schema_version"] = "transient-gap-protocol-v0.1.1"
    original["parent_protocol_sha256"] = parent_hash
    original["amendment"] = {
        "timing": "after_v0.1_aggregate_execution_and_inspection",
        "outcomes_inspected": (
            "scenario pass counts and failing metric values by family and policy"
        ),
        "reason": (
            "response-minus-baseline truth is approximately zero for symmetric "
            "event-centred transients, making relative contrast error undefined"
        ),
        "changed": (
            "normalize absolute event-contrast error by known simulated peak "
            "amplitude instead of the true event contrast"
        ),
        "unchanged": [
            "scenarios",
            "policies",
            "seeds",
            "transient parameters",
            "all numerical acceptance thresholds",
            "all other metric definitions",
        ],
    }
    metrics = original["metrics"]
    metrics[metrics.index("event_contrast_relative_error")] = (
        "event_contrast_peak_normalized_error"
    )
    for transient_class in ("ordinary", "stress"):
        acceptance = original["acceptance"][transient_class]
        acceptance["event_contrast_peak_normalized_error_max"] = acceptance.pop(
            "event_contrast_relative_error_max"
        )
    fingerprint = hashlib.sha256(
        json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = Path("benchmarks/transient-gap-protocol-v0.1.1.json")
    output.write_text(
        json.dumps(
            {**original, "protocol_sha256": fingerprint}, indent=2, sort_keys=True
        )
        + "\n"
    )
    print(fingerprint)


if __name__ == "__main__":
    main()
