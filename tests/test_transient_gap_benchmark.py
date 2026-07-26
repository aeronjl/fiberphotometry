import hashlib
import json
from pathlib import Path

import numpy as np

from fiberphotometry.benchmark_resampling import TransientSpec, generate_transient


def _verified(path: str, fingerprint_name: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text())
    expected = payload.pop(fingerprint_name)
    observed = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert observed == expected
    return payload


def test_v11_protocol_and_results_are_fingerprinted_with_retained_failures() -> None:
    protocol = _verified(
        "benchmarks/transient-gap-protocol-v0.1.1.json", "protocol_sha256"
    )
    result = _verified("benchmarks/transient-gap-results-v0.1.1.json", "result_sha256")

    assert protocol["amendment"]["timing"] == (
        "after_v0.1_aggregate_execution_and_inspection"
    )
    assert result["scenario_count"] == 620
    assert result["condition_dependent_exclusion_warning"]
    assert result["summaries"] == {
        "contiguous_gap": {"failed": 82, "passed": 278, "scenarios": 360},
        "isolated_dropout": {"failed": 22, "passed": 158, "scenarios": 180},
        "timestamp_jitter": {"failed": 4, "passed": 76, "scenarios": 80},
    }
    jitter = [
        item
        for item in result["scenarios"]
        if item["family"] == "timestamp_jitter"
        and item["policy"] == "linear_median_rate"
    ]
    assert len(jitter) == 40
    assert all(item["passed"] for item in jitter)


def test_transient_generator_is_unit_scaled() -> None:
    time = np.arange(0, 10, 0.02)
    transient = generate_transient(
        time,
        event_time=5,
        rate_hz=50,
        spec=TransientSpec("alpha", "ordinary", rise_samples=5, decay_samples=25),
    )

    assert np.max(transient) == 1
    assert np.all(transient[time < 5] == 0)
