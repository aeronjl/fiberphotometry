"""Compose external pose/state outputs with photometry and Unspool boundaries."""

from __future__ import annotations

from typing import Any

import numpy as np

from fiberphotometry import (
    ClockPulseMatches,
    ClockSynchronizationSpec,
    EncodingSession,
    ObservationTable,
    annotations_from_boris,
    annotations_from_moseq,
    fit_clock_synchronization,
    pose_from_deeplabcut,
    pose_from_sleap,
    prepare_unspool_study,
)


class DLCResult:
    """Minimal dataframe-like stand-in for a real pandas DeepLabCut result."""

    def __init__(self, columns: dict[tuple[str, ...], list[float]]) -> None:
        self._columns = columns
        self.columns = tuple(columns)

    def __getitem__(self, name: tuple[str, ...]) -> list[float]:
        return self._columns[name]


def run() -> dict[str, Any]:
    fps = 10.0
    dlc = DLCResult(
        {
            ("demo-network", "nose", "x"): [0, 1, 2, 3, 4, 5],
            ("demo-network", "nose", "y"): [0, 0, 0, 0, 0, 0],
            ("demo-network", "nose", "likelihood"): [0.99] * 6,
        }
    )
    dlc_pose = pose_from_deeplabcut(
        dlc,
        subject="mouse-1",
        session="day-1",
        keypoint="nose",
        scorer="demo-network",
        fps=fps,
        clock_id="video",
    )

    sleap_tracks = np.zeros((6, 1, 1, 2), dtype=float)
    sleap_tracks[:, 0, 0, 0] = np.arange(6)
    sleap_pose = pose_from_sleap(
        sleap_tracks,
        subject="mouse-1",
        session="day-1",
        node_names=["nose"],
        node="nose",
        dims=("frame", "track", "node", "xy"),
        fps=fps,
        clock_id="video",
    )

    moseq = annotations_from_moseq(
        [0, 0, 1, 1, 1, 0],
        subject="mouse-1",
        session="day-1",
        fps=fps,
        labels={0: "pause", 1: "approach"},
        clock_id="video",
    )
    boris = annotations_from_boris(
        {
            "Behavior": ["cue", "investigate"],
            "Type": ["POINT", "STATE"],
            "Start": [0.1, 0.2],
            "Stop": [np.nan, 0.5],
        },
        subject="mouse-1",
        session="day-1",
        behavior_column="Behavior",
        type_column="Type",
        start_column="Start",
        stop_column="Stop",
        clock_id="video",
    )

    video_pulses = np.asarray([0.0, 0.3, 0.6])
    photometry_pulses = 0.02 + 1.001 * video_pulses
    clock_synchronization = fit_clock_synchronization(
        ClockPulseMatches.from_arrays(
            source_clock_id="video",
            target_clock_id="photometry",
            source_time_s=video_pulses,
            target_time_s=photometry_pulses,
        ),
        ClockSynchronizationSpec(
            maximum_absolute_residual_s=1e-6,
            maximum_drift_ppm=2_000,
            minimum_source_span_s=0.5,
        ),
    )
    dlc_pose = clock_synchronization.synchronize_pose(dlc_pose)
    sleap_pose = clock_synchronization.synchronize_pose(sleap_pose)
    moseq = clock_synchronization.synchronize_annotations(moseq)
    boris = clock_synchronization.synchronize_annotations(boris)

    photometry_time = 0.02 + np.arange(6, dtype=float) / fps
    speed = dlc_pose.speed(minimum_confidence=0.9)
    aligned_speed = speed.aligned_to(
        photometry_time,
        target_clock_id="photometry",
        max_gap_s=0.11,
    )
    encoding_session = EncodingSession.from_arrays(
        subject="mouse-1",
        session="day-1",
        time=photometry_time,
        response=np.linspace(0.0, 0.2, len(photometry_time)),
        events={**moseq.event_times(), **boris.event_times()},
        continuous_covariates={"nose_speed": aligned_speed.values},
        continuous_covariate_validity={"nose_speed": aligned_speed.valid},
    )

    summaries = ObservationTable.from_columns(
        {
            "animal": ["mouse-1", "mouse-1"],
            "recording": ["day-1", "day-2"],
            "trial_index": [0, 0],
            "training_day": [0, 1],
            "approach_response": [0.12, 0.18],
        }
    )
    unspool_handoff = prepare_unspool_study(
        summaries,
        subject="animal",
        session="recording",
        trial="trial_index",
        session_order="training_day",
    )
    return {
        "deeplabcut_pose": dlc_pose,
        "sleap_pose": sleap_pose,
        "moseq_annotations": moseq,
        "boris_annotations": boris,
        "clock_synchronization": clock_synchronization,
        "encoding_session": encoding_session,
        "unspool_handoff": unspool_handoff,
    }


if __name__ == "__main__":
    result = run()
    print("Encoding predictors:", sorted(result["encoding_session"].events))
    print("Unspool columns:", result["unspool_handoff"].columns.keys())
