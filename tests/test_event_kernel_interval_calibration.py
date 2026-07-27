import json
from pathlib import Path


def test_frozen_kernel_interval_calibration_retains_failed_progress_gate() -> None:
    payload = json.loads(
        Path("benchmarks/event-kernel-interval-coverage-v0.1.json").read_text()
    )

    assert payload["artifact_type"] == "event_kernel_interval_coverage_benchmark"
    assert payload["schema_version"] == "1"
    assert payload["protocol_commit"].startswith("38656b2")
    assert payload["candidate_implementation_commit"].startswith("38f17aa")
    assert payload["studies_per_scenario"] == 80
    assert len(payload["scenarios"]) == 6
    assert len(payload["studies"]) == 480
    assert all(item["status"] == "success" for item in payload["studies"])
    assert (
        payload["summaries"]["normalized_progress"]["simultaneous_family_coverage"]
        == 0.825
    )
    assert payload["acceptance"] == {
        "all_bounds_finite": True,
        "all_studies_fit": True,
        "marginal_pointwise_coverage_at_least_0_90": True,
        "simultaneous_coverage_at_least_0_85": False,
        "simultaneous_never_narrower": True,
    }
    assert payload["all_acceptance_met"] is False
