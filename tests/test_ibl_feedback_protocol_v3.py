import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np

from fipha.multiverse import materialize_multiverse


def _load_protocol_module() -> Any:
    path = Path("scripts/freeze_ibl_feedback_protocol_v3.py")
    spec = importlib.util.spec_from_file_location("ibl_feedback_protocol_v3", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cohort_module() -> Any:
    path = Path("scripts/freeze_ibl_feedback_cohort_v3.py")
    spec = importlib.util.spec_from_file_location("ibl_feedback_cohort_v3", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_signal_only_v3_has_fifteen_compatible_universes() -> None:
    manifest = json.loads(Path("benchmarks/ibl-feedback-cohort-v0.3.json").read_text())

    universes = materialize_multiverse(_load_protocol_module().build_spec(manifest))

    assert len(universes) == 18
    assert sum(item.incompatibility is None for item in universes) == 15
    assert sum(item.incompatibility is not None for item in universes) == 3
    assert all(
        not (
            {choice.alternative for choice in item.choices}
            >= {"published_rolling", "subtract_standard"}
        )
        for item in universes
        if item.incompatibility is None
    )


def test_frozen_v3_artifact_fingerprints_and_readiness() -> None:
    manifest = json.loads(Path("benchmarks/ibl-feedback-cohort-v0.3.json").read_text())
    protocol = json.loads(
        Path("benchmarks/ibl-feedback-protocol-v0.3.json").read_text()
    )

    manifest_hash = manifest.pop("manifest_sha256")
    protocol_hash = protocol.pop("protocol_sha256")
    assert (
        hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == manifest_hash
    )
    assert (
        hashlib.sha256(
            json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == protocol_hash
    )
    assert manifest["readiness_gate_passed"]
    assert manifest["eligible_animal_count"] == 18
    assert manifest["eligible_session_count"] == 383
    assert protocol["cohort_manifest_sha256"] == manifest_hash


def test_cohort_gate_uses_full_rolling_windows_and_splits_gaps() -> None:
    first = np.arange(0, 10, 1.0)
    second = np.arange(20, 30, 1.0)

    intervals = _load_cohort_module()._rolling_valid_intervals(
        np.concatenate([first, second]), window_samples=4, max_gap_s=1.5
    )

    assert intervals == [(2.0, 8.0), (22.0, 28.0)]


def test_v32_retains_asls_as_structurally_incompatible() -> None:
    protocol = json.loads(
        Path("benchmarks/ibl-feedback-protocol-v0.3.2.json").read_text()
    )
    expected = protocol.pop("protocol_sha256")

    assert (
        hashlib.sha256(
            json.dumps(protocol, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == expected
    )
    assert protocol["eligible_universe_count"] == 9
    assert protocol["incompatible_universe_count"] == 9
    assert (
        protocol["spec"]["base_pipeline"]["analysis_plan"]["estimand"]["contrast_unit"]
        == "session"
    )
    asls = [
        item
        for item in protocol["materialized_universes"]
        if any(choice["alternative"] == "asls" for choice in item["choices"])
    ]
    assert len(asls) == 6
    assert all(item["status"] == "incompatible" for item in asls)


def test_v32_result_artifact_is_complete_and_fingerprinted() -> None:
    result = json.loads(Path("benchmarks/ibl-feedback-results-v0.3.2.json").read_text())
    expected = result.pop("result_sha256")

    assert (
        hashlib.sha256(
            json.dumps(
                result,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        == expected
    )
    assert result["sessions_requested"] == result["sessions_loaded"] == 383
    assert result["animals"] == 18
    assert result["event_summaries"] == 224_272
    assert result["status_counts"] == {"success": 9, "incompatible": 9}
    assert all(item["status"] == "loaded" for item in result["session_diagnostics"])
    successful = [item for item in result["universes"] if item["status"] == "success"]
    assert all(item["confidence_interval"][0] > 0 for item in successful)
    assert all(
        item["estimate"] > 0 for item in result["reference_leave_one_animal_out"]
    )
