"""Generate an evidence report from four fixed public IBL sessions."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from one.api import ONE

from fiberphotometry import EventAnalysisConfig, EventSession
from fiberphotometry.events import summarize_event_windows
from fiberphotometry.io.ibl import from_ibl_tables

SESSIONS = (
    ("fip_13", "b6913f93-e7b1-4faf-ab4d-54261b0e31ea"),
    ("fip_14", "09ade9f3-e9e6-41dc-8e93-1c85a3492650"),
    ("fip_15", "e8455785-cacd-4947-b2b5-89e1e6e88930"),
    ("fip_16", "d94b2ae4-e581-4dee-bc0a-5d8e2b048bf8"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("examples/feedback-analysis.toml")
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / "Library/Caches/fiberphotometry/ibl-tutorial",
    )
    parser.add_argument("--output", type=Path, default=Path("ibl-feedback-report.html"))
    args = parser.parse_args()
    config = EventAnalysisConfig.from_toml(args.config)
    sessions = load_sessions(args.cache_dir)
    result = config.run(sessions)
    destination = result.write_html(args.output)
    destination.with_suffix(".json").write_text(result.to_json() + "\n")
    print(f"Report: {destination}")
    print(f"Configuration SHA-256: {config.fingerprint}")


def load_sessions(cache_dir: Path) -> tuple[EventSession, ...]:
    """Load fixed public sessions while retaining only events with acquired data."""
    one = ONE(
        base_url="https://openalyx.internationalbrainlab.org",
        password="international",
        cache_dir=cache_dir,
        silent=True,
    )
    sessions = []
    for animal, eid in SESSIONS:
        signal = one.load_dataset(
            eid, "photometry.signal.pqt", collection="alf/photometry"
        )
        roi = one.load_dataset(
            eid, "photometryROI.locations.pqt", collection="alf/photometry"
        )
        trials = one.load_object(eid, "trials", collection="alf")
        recording = from_ibl_tables(
            signal_table=signal,
            roi_locations=roi["brain_region"].to_dict(),
            subject=animal,
            session=eid,
        )
        feedback_times = np.asarray(trials["feedback_times"], dtype=float)
        feedback_type = np.asarray(trials["feedbackType"], dtype=float)
        summary = summarize_event_windows(
            recording,
            feedback_times,
            baseline=(-0.5, 0.0),
            response=(0.0, 0.5),
            variable="signal",
        )
        dms = int(np.flatnonzero(recording.channel.values == "DMS")[0])
        usable = np.isfinite(summary.delta.values[:, dms]) & np.isin(
            feedback_type, (-1, 1)
        )
        indices = np.flatnonzero(usable)
        sessions.append(
            EventSession.from_arrays(
                recording,
                feedback_times[indices],
                [
                    "correct" if feedback_type[index] == 1 else "incorrect"
                    for index in indices
                ],
                event_ids=[f"{eid}:{index}" for index in indices],
            )
        )
    return tuple(sessions)


if __name__ == "__main__":
    main()
