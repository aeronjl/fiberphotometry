#!/usr/bin/env python3
"""Run timestamp-aligned DANDI:000351 parity protocol v0.2."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import numpy as np

from fipha.io.dandi import resolve_dandi_download_url
from fipha.model import make_recording
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
        default=Path("benchmarks/dandi-000351-parity-v0.2.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    cases, failures, verified = [], [], []

    for asset in manifest["assets"]:
        destination = args.cache_dir / f"{asset['asset_id']}.nwb"
        try:
            _download_verified(asset, destination)
            verified.append(asset["asset_id"])
            raw_time, raw, archived_time, archived = _arrays(destination)
            raw_valid = np.isfinite(raw_time) & np.isfinite(raw).all(axis=1)
            source_time = raw_time[raw_valid]
            if not np.all(np.diff(source_time) > 0):
                raise ValueError("finite raw timestamps are not strictly increasing")
            recording = make_recording(
                time=source_time,
                signal=raw[raw_valid, 1],
                reference=raw[raw_valid, 0],
                subject=str(asset["subject"]),
                session=str(asset["path"]),
            )
            archived_time_valid = np.isfinite(archived_time)
            target_time = archived_time[archived_time_valid]
            if not np.all(np.diff(target_time) > 0):
                raise ValueError(
                    "finite archived timestamps are not strictly increasing"
                )
            shared = (target_time >= source_time[0]) & (target_time <= source_time[-1])
            target_archived = archived[archived_time_valid][shared]
            for method in ("ols", "irls"):
                raw_candidate = (
                    100 * reference_dff(recording, method=method).dff.values[:, 0]
                )
                candidate = np.interp(target_time[shared], source_time, raw_candidate)
                cases.append(
                    _metrics(asset, method, candidate, target_archived, len(archived))
                )
        except Exception as error:
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
        "schema_version": "dandi-000351-parity-v0.2",
        "dandiset": manifest["dandiset"],
        "version": "draft",
        "draft_observed_at": manifest["draft_observed_at"],
        "alignment": "linear interpolation to archived timestamps; no extrapolation",
        "verified_asset_ids": verified,
        "cases": cases,
        "failures": failures,
        "summary": summaries,
        "engineering_gates": {
            "all_assets_digest_verified": len(verified) == len(manifest["assets"]),
            "all_assets_executed": not failures,
            "all_cases_have_shared_samples": bool(cases)
            and all(case["compared_sample_count"] > 0 for case in cases),
        },
        "interpretation": (
            "Parity after explicit recorded-clock interpolation; archived dF/F is "
            "not ground truth and DANDI:000351 remains a mutable draft."
        ),
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["engineering_gates"], indent=2))
    print(json.dumps(summaries, indent=2))
    if failures:
        raise SystemExit(f"audit retained {len(failures)} asset failure(s)")


def _arrays(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    import h5py  # type: ignore[import-untyped]

    with h5py.File(path, "r") as nwb:
        raw_group = nwb["acquisition/photometry"]
        identity = raw_group.attrs.get("data_identity", "")
        if identity != "raw405,raw470":
            raise ValueError(f"unexpected data_identity: {identity!r}")
        raw = np.asarray(raw_group["data"][:], dtype=float)
        if raw.ndim != 2 or raw.shape[1] != 2:
            raise ValueError("raw photometry does not have two columns")
        return (
            np.asarray(raw_group["timestamps"][:], dtype=float),
            raw,
            np.asarray(nwb["processing/photometry/dff/timestamps"][:], dtype=float),
            np.asarray(nwb["processing/photometry/dff/data"][:], dtype=float),
        )


def _metrics(
    asset: dict[str, object],
    method: str,
    candidate: np.ndarray,
    archived: np.ndarray,
    archived_total: int,
) -> dict[str, object]:
    valid = np.isfinite(candidate) & np.isfinite(archived)
    difference = candidate[valid] - archived[valid]
    excluded = archived_total - len(archived)
    return {
        "asset_id": asset["asset_id"],
        "cohort": asset["cohort"],
        "subject": asset["subject"],
        "method": method,
        "compared_sample_count": int(valid.sum()),
        "outside_shared_domain_count": excluded,
        "outside_shared_domain_fraction": excluded / archived_total,
        "correlation": float(np.corrcoef(candidate[valid], archived[valid])[0, 1]),
        "rmse_percentage_points": float(np.sqrt(np.mean(np.square(difference)))),
        "mean_signed_difference_percentage_points": float(np.mean(difference)),
        "p99_absolute_difference_percentage_points": float(
            np.quantile(np.abs(difference), 0.99)
        ),
    }


def _summary(cases: list[dict[str, object]]) -> dict[str, object]:
    correlations = [float(str(case["correlation"])) for case in cases]
    errors = [float(str(case["rmse_percentage_points"])) for case in cases]
    minimum = min(correlations) if cases else None
    maximum = max(errors) if cases else None
    return {
        "case_count": len(cases),
        "minimum_session_correlation": minimum,
        "median_session_correlation": float(np.median(correlations)) if cases else None,
        "maximum_session_rmse_percentage_points": maximum,
        "median_session_rmse_percentage_points": float(np.median(errors))
        if cases
        else None,
        "exact_parity_gate": bool(cases)
        and minimum is not None
        and maximum is not None
        and minimum >= 0.95
        and maximum <= 0.50,
    }


def _download_verified(asset: dict[str, object], destination: Path) -> None:
    expected = (int(str(asset["size_bytes"])), str(asset["sha256"]))
    if destination.exists() and _digest(destination) == expected:
        return
    partial = destination.with_suffix(".nwb.partial")
    digest, size = hashlib.sha256(), 0
    url = resolve_dandi_download_url(str(asset["asset_id"]))
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
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


if __name__ == "__main__":
    main()
