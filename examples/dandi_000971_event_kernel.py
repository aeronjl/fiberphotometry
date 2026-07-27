"""Run the frozen DANDI:000971 public event-kernel reproduction."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from fiberphotometry import (
    EncodingModelResult,
    EncodingModelSpec,
    EncodingSession,
    EventKernelSpec,
    fit_event_kernel_model,
    lowpass_filter,
    reference_dff,
)
from fiberphotometry.io.dandi_000971 import (
    from_dandi_000971_nwb,
    rewarded_unrewarded_nose_pokes,
)

DEFAULT_MANIFEST = Path("benchmarks/dandi-000971-tutorial-manifest-v0.1.json")
DEFAULT_CACHE = Path.home() / "Library/Caches/fiberphotometry/dandi-000971-tutorial"
DEFAULT_OUTPUT = Path("benchmarks/dandi-000971-event-kernel-v0.2")
REGIONS = ("DMS", "DLS")


def build_spec() -> EncodingModelSpec:
    """Return the model frozen before event-kernel outcome execution."""
    return EncodingModelSpec(
        event_kernels=(
            EventKernelSpec("active_poke", (-1.0, 3.0)),
            EventKernelSpec("reward_increment", (-1.0, 3.0)),
        ),
        alpha_grid=(0.0, 0.1, 1.0, 10.0, 100.0, 1000.0),
        group_by="animal",
        folds=6,
    )


def run_models(
    sessions: dict[str, tuple[EncodingSession, ...]],
) -> dict[str, EncodingModelResult]:
    """Fit the same frozen model separately to each declared region."""
    spec = build_spec()
    return {
        region: fit_event_kernel_model(sessions[region], spec) for region in REGIONS
    }


def load_public_sessions(
    manifest: dict[str, Any], cache_dir: Path
) -> tuple[dict[str, tuple[EncodingSession, ...]], list[dict[str, Any]]]:
    """Verify pinned assets and create corrected regional encoding sessions."""
    regional: dict[str, list[EncodingSession]] = {region: [] for region in REGIONS}
    audit = []
    for asset in manifest["assets"]:
        path = cache_dir / f"{asset['asset_id']}.nwb"
        observed_size, observed_digest = _digest(path)
        if (observed_size, observed_digest) != (
            int(asset["size_bytes"]),
            str(asset["sha256"]),
        ):
            raise ValueError(f"asset integrity mismatch: {asset['asset_id']}")
        recording = from_dandi_000971_nwb(path)
        corrected = reference_dff(
            lowpass_filter(recording, cutoff_hz=3.0), method="irls"
        )
        pokes, labels = rewarded_unrewarded_nose_pokes(path)
        rewards = pokes[np.asarray(labels) == "rewarded"]
        subject = str(asset["subject"])
        session = str(recording.attrs["session"])
        for region in REGIONS:
            response = np.asarray(
                corrected["dff"].sel(channel=region).values, dtype=float
            )
            regional[region].append(
                EncodingSession.from_arrays(
                    subject=subject,
                    session=session,
                    time=recording.time.values,
                    response=response,
                    events={
                        "active_poke": pokes,
                        "reward_increment": rewards,
                    },
                )
            )
        audit.append(
            {
                "asset_id": asset["asset_id"],
                "subject": subject,
                "family": asset["family"],
                "active_pokes": len(pokes),
                "rewarded_pokes": len(rewards),
                "unrewarded_pokes": len(pokes) - len(rewards),
                "observations": len(recording.time),
                "analysis_rate_hz": recording.attrs["sampling_rate_hz"],
                "verified_sha256": observed_digest,
            }
        )
    return {key: tuple(value) for key, value in regional.items()}, audit


def evidence_payload(
    manifest: dict[str, Any],
    audit: list[dict[str, Any]],
    results: dict[str, EncodingModelResult],
) -> dict[str, Any]:
    """Build deterministic, versioned evidence around the model results."""
    return {
        "schema_version": "dandi-000971-event-kernel-v0.2",
        "artifact_type": "public_event_kernel_reproduction",
        "fiberphotometry_version": version("fiberphotometry"),
        "scientific_protocol": (
            "protocol-dandi-000971-event-kernel-v0.1 + "
            "protocol-event-kernel-uncertainty-diagnostics-v0.1"
        ),
        "source": {
            "dandiset": manifest["dandiset"],
            "published_version": manifest["published_version"],
            "doi": manifest["doi"],
            "license": manifest["license"],
        },
        "preprocessing": {
            "target_rate_hz": 20.0,
            "lowpass_cutoff_hz": 3.0,
            "lowpass_order": 4,
            "reference_fit": "huber_irls",
            "normalization": "fitted_reference_dff",
        },
        "event_design": {
            "active_poke_window_s": [-1.0, 3.0],
            "reward_increment_window_s": [-1.0, 3.0],
            "reward_relation": "exact subset of active_poke",
            "analysis_support": "complete recording",
            "group_by": "animal",
            "folds": 6,
            "alpha_grid": [0.0, 0.1, 1.0, 10.0, 100.0, 1000.0],
        },
        "sessions": audit,
        "regions": {
            region: json.loads(result.to_json()) for region, result in results.items()
        },
        "interpretation": {
            "active_poke": "pooled response associated with an unrewarded active poke",
            "reward_increment": (
                "additional pooled response for a rewarded active poke conditional "
                "on the common active-poke kernel"
            ),
            "causal": False,
            "coefficient_uncertainty_available": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    sessions, audit = load_public_sessions(manifest, args.cache_dir)
    results = run_models(sessions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "result.json"
    result_path.write_text(
        json.dumps(evidence_payload(manifest, audit, results), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    _, result_digest = _digest(result_path)
    manifest_payload = {
        "schema_version": "dandi-000971-event-kernel-manifest-v0.2",
        "status": "complete",
        "artifacts": {"result.json": {"sha256": result_digest}},
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for region, result in results.items():
        selected = next(
            item
            for item in result.cross_validation
            if item.alpha == result.selected_alpha
        )
        print(
            f"{region}: alpha={result.selected_alpha:g}, "
            f"animal-held-out mean R²={selected.mean_r_squared:.6f}"
        )
    print(f"Artifacts: {args.output_dir.resolve()}")


def _digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


if __name__ == "__main__":
    main()
