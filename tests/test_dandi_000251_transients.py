import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


def _module():
    path = Path("scripts/run_dandi_000251_transients.py")
    spec = importlib.util.spec_from_file_location("dandi_000251_transients", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_event_hit_fraction_uses_frozen_inclusive_window() -> None:
    module = _module()
    peaks = np.asarray([1.6, 4.1, 8.2])
    events = np.asarray([1.0, 2.0, 6.0])

    assert module.event_hit_fraction(peaks, events) == 2 / 3
    assert module.event_hit_fraction(peaks, np.asarray([])) is None


def test_peak_jaccard_is_tolerant_and_one_to_one() -> None:
    module = _module()

    assert module.peak_jaccard(np.asarray([1.0, 2.0]), np.asarray([1.05, 3.0])) == 1 / 3
    assert module.peak_jaccard(np.asarray([]), np.asarray([])) == 1


def test_frozen_null_has_999_deterministic_offsets() -> None:
    module = _module()
    first = module.shifted_hit_distribution(
        [np.asarray([2.0, 7.0])],
        [np.asarray([1.0, 6.0])],
        [(0.0, 10.0)],
    )
    second = module.shifted_hit_distribution(
        [np.asarray([2.0, 7.0])],
        [np.asarray([1.0, 6.0])],
        [(0.0, 10.0)],
    )

    assert len(first) == 999
    assert first == second


def test_committed_result_is_fingerprinted_and_retains_disagreement() -> None:
    path = Path("benchmarks/dandi-000251-transients-results-v0.1.json")
    payload = json.loads(path.read_text())
    expected = payload.pop("result_sha256")
    observed = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert observed == expected
    assert len(payload["sessions"]) == 6
    enrichment = payload["aggregate"]["external_enrichment"]
    enriched = [
        universe
        for universe, result in enrichment.items()
        if result["upper_tail_probability"] <= 0.05
    ]
    assert enriched == [
        "global_mad-3mad-minimum",
        "rolling_mad-3mad-median",
        "rolling_mad-3mad-minimum",
    ]
    assert payload["aggregate"]["agreement"]["median_jaccard"] < 0.13
