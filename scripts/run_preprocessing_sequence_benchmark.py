"""Execute frozen preprocessing-sequence benchmark v0.8."""

from __future__ import annotations

import json

import numpy as np

from fiberphotometry import lowpass_filter, make_recording, resample_recording


def main() -> None:
    source_time = np.arange(0, 10, 0.047)
    source_time = source_time + 0.002 * np.sin(source_time * 2.1)
    source_time = source_time[(source_time <= 4) | (source_time >= 5)]
    source_signal = np.sin(2 * np.pi * 1.3 * source_time)
    irregular = make_recording(
        time=source_time,
        signal=source_signal,
        reference=np.ones_like(source_signal),
        subject="benchmark",
        session="resampling",
    )
    resampled = resample_recording(irregular, rate_hz=20, max_gap_s=0.1)
    truth = np.sin(2 * np.pi * 1.3 * resampled.time.values)
    outside = (resampled.time.values <= 4) | (resampled.time.values >= 5)
    finite = np.isfinite(resampled.signal.values[:, 0])
    resampling_rmse = float(
        np.sqrt(
            np.mean(
                (resampled.signal.values[outside & finite, 0] - truth[outside & finite])
                ** 2
            )
        )
    )
    interpolated_inside_gap = int(
        np.isfinite(
            resampled.signal.values[
                (resampled.time.values > 4) & (resampled.time.values < 5), 0
            ]
        ).sum()
    )

    time = np.arange(0, 10, 0.01)
    low = np.sin(2 * np.pi * time)
    high = 0.5 * np.sin(2 * np.pi * 20 * time)
    regular = make_recording(
        time=time,
        signal=low + high,
        reference=1 + high,
        subject="benchmark",
        session="filtering",
    )
    filtered = lowpass_filter(regular, cutoff_hz=5, order=4)
    filtered_signal = filtered.signal.values[:, 0]
    lowpass_rmse = float(np.sqrt(np.mean((filtered_signal - low) ** 2)))
    projected_20hz_amplitude = float(
        2
        * abs(np.dot(filtered_signal - low, np.sin(2 * np.pi * 20 * time)))
        / len(time)
    )
    attenuation = 1 - projected_20hz_amplitude / 0.5
    resample_operation = json.loads(resampled.attrs["fiberphotometry_operations"])[0]
    filter_operation = json.loads(filtered.attrs["fiberphotometry_operations"])[0]
    results = {
        "resampling_rmse": resampling_rmse,
        "interpolated_samples_inside_gap": interpolated_inside_gap,
        "source_retained_exactly": bool(
            np.array_equal(resampled.source_signal.values[:, 0], source_signal)
        ),
        "lowpass_rmse": lowpass_rmse,
        "twenty_hz_attenuation_fraction": attenuation,
        "prefilter_retained_exactly": bool(
            np.array_equal(filtered.prefilter_signal.values, regular.signal.values)
        ),
        "resample_provenance": resample_operation,
        "filter_provenance": filter_operation,
    }
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
