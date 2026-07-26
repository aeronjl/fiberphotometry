import hashlib
import json
from pathlib import Path


def test_frozen_irregular_resampling_benchmark_passes_and_is_fingerprinted() -> None:
    result = json.loads(Path("benchmarks/irregular-resampling-v0.1.json").read_text())
    expected = result.pop("result_sha256")

    assert (
        hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == expected
    )
    assert result["all_passed"]
    assert len(result["scenarios"]) == 6
    assert max(item["normalized_rmse"] for item in result["scenarios"]) < 0.01
