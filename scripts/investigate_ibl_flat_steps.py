"""Characterize repeated consecutive values in the four flagged IBL sessions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
from one.api import ONE

from fiberphotometry.io.ibl import from_ibl_tables

SESSIONS = (
    ("fip_13", "b6913f93-e7b1-4faf-ab4d-54261b0e31ea"),
    ("fip_13", "56d057a7-d6bc-4b3b-b4a4-ff43870eb70b"),
    ("fip_16", "b1420283-3782-40fd-bb03-d8a80b63aa63"),
    ("fip_16", "d94b2ae4-e581-4dee-bc0a-5d8e2b048bf8"),
)


def main() -> None:
    rows = []
    with tempfile.TemporaryDirectory(prefix="fiberphotometry-ibl-flat-") as cache:
        one = ONE(
            base_url="https://openalyx.internationalbrainlab.org",
            password="international",
            cache_dir=Path(cache),
            silent=True,
        )
        for subject, eid in SESSIONS:
            table = one.load_dataset(
                eid, "photometry.signal.pqt", collection="alf/photometry"
            )
            roi = one.load_dataset(
                eid, "photometryROI.locations.pqt", collection="alf/photometry"
            )
            recording = from_ibl_tables(
                signal_table=table,
                roi_locations=roi["brain_region"].to_dict(),
                subject=subject,
                session=eid,
            )
            signals = np.asarray(recording.signal.values)
            references = np.asarray(recording.reference.values)
            for index, channel in enumerate(recording.channel.values):
                signal_flat = _flat_pairs(signals[:, index])
                reference_flat = _flat_pairs(references[:, index])
                valid_pairs = np.isfinite(signals[:-1, index]) & np.isfinite(
                    signals[1:, index]
                )
                rows.append(
                    {
                        "subject": subject,
                        "session": eid,
                        "channel": str(channel),
                        "signal_flat_fraction": float(
                            signal_flat.sum() / valid_pairs.sum()
                        ),
                        "reference_flat_fraction": float(
                            reference_flat.sum()
                            / np.isfinite(references[:-1, index]).sum()
                        ),
                        "shared_flat_fraction_of_signal_flat": float(
                            np.sum(signal_flat & reference_flat)
                            / max(signal_flat.sum(), 1)
                        ),
                        "longest_signal_flat_run_samples": _longest_run(signal_flat),
                        "signal_unique_fraction": float(
                            len(
                                np.unique(
                                    signals[np.isfinite(signals[:, index]), index]
                                )
                            )
                            / np.isfinite(signals[:, index]).sum()
                        ),
                    }
                )
    print(
        json.dumps({"sessions": len(SESSIONS), "rows": rows}, indent=2, sort_keys=True)
    )


def _flat_pairs(values: np.ndarray) -> np.ndarray:
    return (
        np.isfinite(values[:-1]) & np.isfinite(values[1:]) & (values[:-1] == values[1:])
    )


def _longest_run(values: np.ndarray) -> int:
    padded = np.concatenate([[False], values, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return int(np.max(edges[1::2] - edges[::2], initial=0))


if __name__ == "__main__":
    main()
