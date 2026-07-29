#!/usr/bin/env python3
"""Run the frozen DANDI:000351 raw-to-archived dF/F parity audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import numpy as np

from fipha.io.dandi import resolve_dandi_download_url
from fipha.io.dandi_000351 import from_dandi_000351_nwb
from fipha.preprocess import reference_dff


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("benchmarks/dandi-000351-parity-manifest-v0.1.json"),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / "Library/Caches/fipha/dandi-000351",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/dandi-000351-parity-v0.1.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    verified_assets = []
    cases = []
    failures = []
    for asset in manifest["assets"]:
        destination = args.cache_dir / f"{asset['asset_id']}.nwb"
        try:
            _download_verified(asset, destination)
            verified_assets.append(asset["asset_id"])
            recording = from_dandi_000351_nwb(destination)
            archived = recording.archived_dff_percentage.values[:, 0]
            raw_finite = np.isfinite(recording.signal.values[:, 0]) & np.isfinite(
                recording.reference.values[:, 0]
            )
            for method in ("ols", "irls"):
                calculated = reference_dff(recording, method=method).dff.values[:, 0]
                calculated_percentage = 100 * calculated
                cases.append(
                    _metrics(
                        asset,
                        method,
                        calculated_percentage,
                        archived,
                        raw_finite,
                        float(recording.attrs["timestamp_max_abs_error_s"]),
                    )
                )
        except Exception as error:  # retain all asset-level failures
            failures.append(
                {
                    "asset_id": asset["asset_id"],
                    "cohort": asset["cohort"],
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    summaries = {
        method: _summary([case for case in cases if case["method"] == method])
        for method in ("ols", "irls")
    }
    payload = {
        "schema_version": "dandi-000351-parity-v0.1",
        "dandiset": manifest["dandiset"],
        "version": manifest["version"],
        "draft_observed_at": manifest["draft_observed_at"],
        "manifest": str(args.manifest),
        "verified_asset_ids": verified_assets,
        "cases": cases,
        "failures": failures,
        "summary": summaries,
        "engineering_gates": {
            "all_assets_digest_verified": len(verified_assets)
            == len(manifest["assets"]),
            "all_assets_schema_valid": not failures,
            "all_timestamps_within_1us": bool(cases)
            and all(case["timestamp_max_abs_error_s"] <= 1e-6 for case in cases),
            "all_candidates_finite_for_finite_raw": bool(cases)
            and all(case["candidate_finite_on_finite_raw"] for case in cases),
        },
        "interpretation": (
            "Archived percentage dF/F is an interoperability target, not ground "
            "truth; DANDI:000351 was an unpublished mutable draft at execution."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["engineering_gates"], indent=2))
    print(json.dumps(summaries, indent=2))
    if failures:
        raise SystemExit(f"audit retained {len(failures)} asset failure(s)")


def _metrics(
    asset: dict[str, object],
    method: str,
    calculated: np.ndarray,
    archived: np.ndarray,
    raw_finite: np.ndarray,
    timestamp_error: float,
) -> dict[str, object]:
    valid = np.isfinite(calculated) & np.isfinite(archived)
    difference = calculated[valid] - archived[valid]
    return {
        "asset_id": asset["asset_id"],
        "cohort": asset["cohort"],
        "subject": asset["subject"],
        "method": method,
        "sample_count": len(archived),
        "raw_finite_fraction": float(raw_finite.mean()),
        "archived_finite_fraction": float(np.isfinite(archived).mean()),
        "candidate_finite_fraction": float(np.isfinite(calculated).mean()),
        "candidate_finite_on_finite_raw": bool(
            np.isfinite(calculated[raw_finite]).all()
        ),
        "timestamp_max_abs_error_s": timestamp_error,
        "correlation": float(np.corrcoef(calculated[valid], archived[valid])[0, 1]),
        "rmse_percentage_points": float(np.sqrt(np.mean(np.square(difference)))),
        "mean_signed_difference_percentage_points": float(np.mean(difference)),
        "p99_absolute_difference_percentage_points": float(
            np.quantile(np.abs(difference), 0.99)
        ),
    }


def _summary(cases: list[dict[str, object]]) -> dict[str, object]:
    correlations = [float(str(case["correlation"])) for case in cases]
    errors = [float(str(case["rmse_percentage_points"])) for case in cases]
    minimum_correlation = min(correlations) if cases else None
    maximum_rmse = max(errors) if cases else None
    return {
        "case_count": len(cases),
        "minimum_session_correlation": minimum_correlation,
        "median_session_correlation": float(np.median(correlations)) if cases else None,
        "maximum_session_rmse_percentage_points": maximum_rmse,
        "median_session_rmse_percentage_points": float(np.median(errors))
        if cases
        else None,
        "exact_parity_gate": bool(cases)
        and minimum_correlation is not None
        and maximum_rmse is not None
        and minimum_correlation >= 0.95
        and maximum_rmse <= 0.50,
    }


def _download_verified(asset: dict[str, object], destination: Path) -> None:
    expected_size = int(str(asset["size_bytes"]))
    expected_digest = str(asset["sha256"])
    expected = (expected_size, expected_digest)
    if destination.exists() and _digest(destination) == expected:
        return
    partial = destination.with_suffix(".nwb.partial")
    url = resolve_dandi_download_url(str(asset["asset_id"]))
    digest = hashlib.sha256()
    size = 0
    with urlopen(url, timeout=120) as response, partial.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    if (size, digest.hexdigest()) != expected:
        partial.unlink(missing_ok=True)
        raise ValueError(f"asset integrity mismatch: {asset['asset_id']}")
    partial.replace(destination)


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
