import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np

from fiberphotometry import materialize_multiverse


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
