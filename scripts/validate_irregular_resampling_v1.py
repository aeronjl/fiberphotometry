"""Freeze smooth-signal interpolation checks for prospective regularization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from fipha import make_recording, resample_recording


def main() -> None:
    scenarios = []
    for rate_hz in (20.0, 50.0):
        for frequency_hz in (0.2, 1.0, 3.0):
            regular = np.arange(0, 60, 1 / rate_hz)
            jitter = 0.005 * (1 / rate_hz) * np.sin(np.arange(len(regular)) * 0.71)
            time = regular + jitter
            expected_source = np.sin(2 * np.pi * frequency_hz * time)
            recording = make_recording(
                time=time,
                signal=expected_source,
                subject="simulation",
                session=f"{rate_hz:g}hz-{frequency_hz:g}hz",
            )
            result = resample_recording(recording, rate_hz="median", max_gap_factor=1.5)
            expected = np.sin(2 * np.pi * frequency_hz * result.time.values)
            observed = result.signal.values[:, 0]
            rmse = float(np.sqrt(np.nanmean((observed - expected) ** 2)))
            peak = float(np.nanmax(np.abs(expected)))
            operation = json.loads(result.attrs["fipha_operations"])[0]
            scenarios.append(
                {
                    "source_rate_hz": rate_hz,
                    "signal_frequency_hz": frequency_hz,
                    "jitter_fraction": 0.005,
                    "normalized_rmse": rmse / peak,
                    "passed": rmse / peak < 0.01,
                    "resampling_diagnostics": operation,
                }
            )
    body = {
        "schema_version": "irregular-resampling-v0.1",
        "policy": {
            "rate_hz": "median",
            "max_gap_factor": 1.5,
            "method": "linear",
        },
        "acceptance": {
            "normalized_rmse_max": 0.01,
            "scope": "smooth sinusoids at 0.2, 1, and 3 Hz",
        },
        "all_passed": all(item["passed"] for item in scenarios),
        "scenarios": scenarios,
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = Path("benchmarks/irregular-resampling-v0.1.json")
    output.write_text(
        json.dumps({**body, "result_sha256": fingerprint}, indent=2, sort_keys=True)
        + "\n"
    )


if __name__ == "__main__":
    main()
