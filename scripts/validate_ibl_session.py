"""Validate the public IBL adapter and event summaries on one real session."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from one.api import ONE

from fipha import align_events, summarize_event_windows
from fipha.io.ibl import from_ibl_tables
from fipha.preprocess import reference_dff

EID = "7a867587-aba3-48da-ace9-3f4ac7082b6f"
SUBJECT = "fip_13"


@dataclass(frozen=True)
class RegionAlignment:
    region: str
    valid_events: int
    correlation: float
    rmse: float
    bias: float
    max_absolute_error: float


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fipha-ibl-") as cache:
        one = ONE(
            base_url="https://openalyx.internationalbrainlab.org",
            password="international",
            cache_dir=Path(cache),
            silent=True,
        )
        signal = one.load_dataset(
            EID, "photometry.signal.pqt", collection="alf/photometry"
        )
        roi = one.load_dataset(
            EID, "photometryROI.locations.pqt", collection="alf/photometry"
        )
        trials = one.load_object(EID, "trials", collection="alf")

        recording = from_ibl_tables(
            signal_table=signal,
            roi_locations=roi["brain_region"].to_dict(),
            subject=SUBJECT,
            session=EID,
        )
        event_times = np.asarray(trials["stimOn_times"], dtype=float)
        direct = summarize_event_windows(
            recording,
            event_times,
            baseline=(-0.5, 0.0),
            response=(0.0, 0.5),
        )
        rate = 1 / float(np.median(np.diff(recording.time.values)))
        aligned = align_events(
            recording,
            event_times,
            window=(-0.5, 0.5),
            rate=rate,
            variable="signal",
        )
        relative_time = aligned.relative_time.values
        pre = (relative_time >= -0.5) & (relative_time < 0)
        post = (relative_time >= 0) & (relative_time < 0.5)
        aligned_delta = np.nanmean(aligned.values[:, post], axis=1) - np.nanmean(
            aligned.values[:, pre], axis=1
        )

        comparisons = []
        for channel, region in enumerate(recording.channel.values):
            expected = direct.delta.values[:, channel]
            observed = aligned_delta[:, channel]
            valid = np.isfinite(expected) & np.isfinite(observed)
            difference = observed[valid] - expected[valid]
            comparisons.append(
                RegionAlignment(
                    region=str(region),
                    valid_events=int(valid.sum()),
                    correlation=float(
                        np.corrcoef(observed[valid], expected[valid])[0, 1]
                    ),
                    rmse=float(np.sqrt(np.mean(np.square(difference)))),
                    bias=float(np.mean(difference)),
                    max_absolute_error=float(np.max(np.abs(difference))),
                )
            )

        corrected = reference_dff(recording)
        payload = {
            "session": EID,
            "subject": SUBJECT,
            "samples": recording.sizes["time"],
            "channels": [str(value) for value in recording.channel.values],
            "trials": len(event_times),
            "included_fraction": float(recording.included.values.mean()),
            "reference_finite_fraction": float(
                np.isfinite(recording.reference.values).mean()
            ),
            "estimated_rate_hz": rate,
            "reference_fit_coefficients": (
                corrected.reference_fit_coefficient.values.tolist()
            ),
            "alignment_vs_acquired_window": [asdict(value) for value in comparisons],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
