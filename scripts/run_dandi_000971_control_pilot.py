#!/usr/bin/env python3
"""Run the frozen DANDI:000971 independent-control pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from scipy.signal import butter, sosfiltfilt

from fiberphotometry.io.dandi import resolve_dandi_download_url
from fiberphotometry.io.dandi_000971 import from_dandi_000971_nwb
from fiberphotometry.preprocess import baseline_dff, reference_dff


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("benchmarks/dandi-000971-pilot-manifest-v0.1.json"),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / "Library/Caches/fiberphotometry/dandi-000971",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/dandi-000971-control-v0.1.json"),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    assets = []
    cases = []
    failures = []
    for asset in manifest["assets"]:
        destination = args.cache_dir / f"{asset['asset_id']}.nwb"
        try:
            _download_verified(asset, destination)
            assets.append({**asset, "verified": True})
            recording = from_dandi_000971_nwb(destination)
            reference_result = reference_dff(recording, method="irls")
            slow_reference = _lowpass(
                reference_result.fitted_reference.values,
                float(recording.attrs["sampling_rate_hz"]),
            )
            for method in ("double_exponential", "asls"):
                result = baseline_dff(recording, method=method)
                slow_baseline = _lowpass(
                    result.fitted_baseline.values,
                    float(recording.attrs["sampling_rate_hz"]),
                )
                for channel_index, channel in enumerate(recording.channel.values):
                    cases.append(
                        _metrics(
                            asset=asset,
                            channel=str(channel),
                            method=method,
                            baseline=slow_baseline[:, channel_index],
                            comparator=slow_reference[:, channel_index],
                            corrected=result.dff.values[:, channel_index],
                            acquired_reference=recording.reference.values[
                                :, channel_index
                            ],
                        )
                    )
        except Exception as error:  # retain every asset-level failure in output
            failures.append(
                {
                    "asset_id": asset["asset_id"],
                    "family": asset["family"],
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )

    summaries = {}
    for method in ("double_exponential", "asls"):
        selected = [case for case in cases if case["method"] == method]
        summaries[method] = _summary(selected)
    payload = {
        "schema_version": "dandi-000971-control-pilot-v0.1",
        "manifest": str(args.manifest),
        "dandiset": manifest["dandiset"],
        "published_version": manifest["published_version"],
        "assets": assets,
        "cases": cases,
        "failures": failures,
        "summary": summaries,
        "engineering_gates": {
            "all_assets_digest_verified": len(assets) == len(manifest["assets"]),
            "all_assets_schema_valid": not failures,
            "all_baselines_at_least_99pct_finite": bool(cases)
            and all(case["finite_fraction"] >= 0.99 for case in cases),
        },
        "interpretation": (
            "Engineering and assumption audit only; the fitted isosbestic trend "
            "is an independent comparator, not ground-truth bleaching."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["engineering_gates"], indent=2))
    print(json.dumps(summaries, indent=2))
    if failures:
        raise SystemExit(f"pilot retained {len(failures)} asset failure(s)")


def _download_verified(asset: dict[str, object], destination: Path) -> None:
    expected_size = int(asset["size_bytes"])
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
    if (size, digest.hexdigest()) != (expected_size, expected_digest):
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


def _lowpass(values: np.ndarray, rate_hz: float) -> np.ndarray:
    sos = butter(4, 0.05, btype="lowpass", fs=rate_hz, output="sos")
    return sosfiltfilt(sos, values, axis=0)


def _metrics(
    *,
    asset: dict[str, object],
    channel: str,
    method: str,
    baseline: np.ndarray,
    comparator: np.ndarray,
    corrected: np.ndarray,
    acquired_reference: np.ndarray,
) -> dict[str, object]:
    valid = np.isfinite(baseline) & np.isfinite(comparator)
    difference = baseline[valid] - comparator[valid]
    denominator = np.sqrt(np.mean(np.square(comparator[valid])))
    window = max(1, valid.sum() // 20)
    return {
        "asset_id": asset["asset_id"],
        "family": asset["family"],
        "subject": asset["subject"],
        "channel": channel,
        "method": method,
        "finite_fraction": float(np.isfinite(baseline).mean()),
        "slow_trend_correlation": _correlation(baseline, comparator),
        "relative_rmse": float(np.sqrt(np.mean(np.square(difference))) / denominator),
        "baseline_fractional_change": _fractional_change(baseline[valid], window),
        "comparator_fractional_change": _fractional_change(comparator[valid], window),
        "corrected_reference_correlation": _correlation(corrected, acquired_reference),
    }


def _fractional_change(values: np.ndarray, window: int) -> float:
    start = float(np.median(values[:window]))
    end = float(np.median(values[-window:]))
    return (end - start) / start


def _correlation(left: np.ndarray, right: np.ndarray) -> float:
    valid = np.isfinite(left) & np.isfinite(right)
    if valid.sum() < 3:
        return float("nan")
    return float(np.corrcoef(left[valid], right[valid])[0, 1])


def _summary(cases: list[dict[str, object]]) -> dict[str, object]:
    correlations = [float(case["slow_trend_correlation"]) for case in cases]
    errors = [float(case["relative_rmse"]) for case in cases]
    median_correlation = float(np.median(correlations)) if cases else None
    median_relative_rmse = float(np.median(errors)) if cases else None
    return {
        "case_count": len(cases),
        "median_slow_trend_correlation": median_correlation,
        "median_relative_rmse": median_relative_rmse,
        "descriptive_correlation_gate": bool(cases) and median_correlation >= 0.90,
        "descriptive_relative_rmse_gate": bool(cases) and median_relative_rmse <= 0.10,
    }


if __name__ == "__main__":
    main()
