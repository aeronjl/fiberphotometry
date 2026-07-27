import hashlib
import json
from pathlib import Path

import pytest


def test_frozen_ibl_unspool_result_is_self_verifying() -> None:
    path = Path("benchmarks/ibl-unspool-longitudinal-result-v0.1.json")
    payload = json.loads(path.read_text())
    expected = payload.pop("result_sha256")

    assert (
        hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == expected
    )
    assert payload["animals"] == 18
    assert payload["observations"] == 107_636
    assert len(payload["session_summaries"]) == 216


def test_lagged_dms_result_retains_the_negative_forecast() -> None:
    payload = json.loads(
        Path("benchmarks/ibl-unspool-longitudinal-result-v0.1.json").read_text()
    )
    comparison = payload["comparison"]
    models = comparison["models"]
    pair = comparison["pairwise_log_loss_differences"][
        "session_progress_minus_session_progress_plus_lagged_dms"
    ]

    assert comparison["winner_by_unit_balanced_log_loss"] == "session_progress"
    assert all(item["audit_status"] == "pass" for item in models.values())
    assert pair["left_minus_right"]["estimate"] == pytest.approx(-0.0009073407209333535)
    assert pair["left_minus_right"]["lower"] < 0 < pair["left_minus_right"]["upper"]
    assert pair["bootstrap_probability_positive"] == pytest.approx(0.3182)
