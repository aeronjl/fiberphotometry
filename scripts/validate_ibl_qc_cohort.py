"""Run channel-level QC on a frozen, heterogeneous public IBL cohort."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

import numpy as np
from one.api import ONE

from fipha.io.ibl import from_ibl_tables
from fipha.qc import assess_recording

SESSIONS = (
    ("fip_13", "early", "4a7c4b57-8279-4e39-83c5-7369dda98c37"),
    ("fip_13", "middle", "b6913f93-e7b1-4faf-ab4d-54261b0e31ea"),
    ("fip_13", "late", "56d057a7-d6bc-4b3b-b4a4-ff43870eb70b"),
    ("fip_14", "early", "287694fc-7ba0-417c-ae6e-86c298fdc257"),
    ("fip_14", "middle", "09ade9f3-e9e6-41dc-8e93-1c85a3492650"),
    ("fip_14", "late", "3c946c36-2eee-478e-8b16-f2b6272d4cf4"),
    ("fip_15", "early", "5e50a2a8-7466-4a35-a1ce-69856e372f44"),
    ("fip_15", "middle", "e8455785-cacd-4947-b2b5-89e1e6e88930"),
    ("fip_15", "late", "cb0fd340-20f3-4c71-8af5-193d9b69ad18"),
    ("fip_16", "early", "b1420283-3782-40fd-bb03-d8a80b63aa63"),
    ("fip_16", "middle", "d94b2ae4-e581-4dee-bc0a-5d8e2b048bf8"),
    ("fip_16", "late", "3204c2c4-83f2-495c-87d1-4d680a2fc8e4"),
)


def main() -> None:
    rows = []
    with tempfile.TemporaryDirectory(prefix="fipha-ibl-cohort-") as cache:
        one = ONE(
            base_url="https://openalyx.internationalbrainlab.org",
            password="international",
            cache_dir=Path(cache),
            silent=True,
        )
        for subject, phase, eid in SESSIONS:
            signal = one.load_dataset(
                eid, "photometry.signal.pqt", collection="alf/photometry"
            )
            roi = one.load_dataset(
                eid, "photometryROI.locations.pqt", collection="alf/photometry"
            )
            recording = from_ibl_tables(
                signal_table=signal,
                roi_locations=roi["brain_region"].to_dict(),
                subject=subject,
                session=eid,
            )
            qc = assess_recording(recording)
            for channel in qc.channels:
                rows.append(
                    {
                        "subject": subject,
                        "phase": phase,
                        "session": eid,
                        "estimated_rate_hz": qc.estimated_rate_hz,
                        "sampling_interval_cv": qc.sampling_interval_cv,
                        "large_gap_count": qc.large_gap_count,
                        **asdict(channel),
                    }
                )
    warning_counts = {}
    for warning in sorted({warning for row in rows for warning in row["warnings"]}):
        warning_counts[warning] = sum(warning in row["warnings"] for row in rows)
    payload = {
        "cohort": "ibl-qc-v0.1",
        "selection": "four subjects x early/middle/late sessions",
        "sessions": len(SESSIONS),
        "channels": len(rows),
        "summary": {
            "finite_paired_fraction_median": float(
                np.median([row["finite_paired_fraction"] for row in rows])
            ),
            "finite_paired_fraction_range": [
                float(np.min([row["finite_paired_fraction"] for row in rows])),
                float(np.max([row["finite_paired_fraction"] for row in rows])),
            ],
            "absolute_signal_reference_correlation_median": float(
                np.median([abs(row["signal_reference_correlation"]) for row in rows])
            ),
            "relative_slope_difference_median": float(
                np.median([row["relative_slope_difference"] for row in rows])
            ),
            "warning_channels": sum(bool(row["warnings"]) for row in rows),
            "warning_counts": warning_counts,
        },
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
