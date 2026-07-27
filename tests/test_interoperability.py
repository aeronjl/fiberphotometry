from __future__ import annotations

import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest

from fiberphotometry import (
    BehaviorAnnotations,
    BehaviorCovariate,
    BehaviorInterval,
    ClockPulseMatches,
    ClockSynchronizationSpec,
    EncodingSession,
    annotations_from_boris,
    annotations_from_boris_tabular_file,
    annotations_from_moseq,
    annotations_from_moseq_results_h5,
    fit_clock_synchronization,
    pose_from_deeplabcut,
    pose_from_deeplabcut_file,
    pose_from_sleap,
    pose_from_sleap_analysis_h5,
)

FIXTURES = Path(__file__).parent / "fixtures" / "interoperability"


class _Frame:
    def __init__(self, columns: dict[tuple[str, ...], list[float]]) -> None:
        self._columns = columns
        self.columns = tuple(columns)

    def __getitem__(self, name: tuple[str, ...]) -> list[float]:
        return self._columns[name]


def _clock_synchronization():
    source = np.asarray([0.0, 20.0, 40.0, 60.0])
    target = 0.35 + 1.00012 * source + np.asarray([0.0, 0.0002, -0.0001, 0.0])
    matches = ClockPulseMatches.from_arrays(
        source_clock_id="video",
        target_clock_id="photometry",
        source_time_s=source,
        target_time_s=target,
        match_labels=("pulse-0", "pulse-1", "pulse-2", "pulse-3"),
    )
    spec = ClockSynchronizationSpec(
        maximum_absolute_residual_s=0.001,
        maximum_drift_ppm=200.0,
        minimum_source_span_s=30.0,
    )
    return fit_clock_synchronization(matches, spec)


def test_clock_synchronization_recovers_drift_and_retains_evidence() -> None:
    synchronization = _clock_synchronization()
    payload = json.loads(synchronization.to_json())

    assert synchronization.intercept_s == pytest.approx(0.35004, abs=1e-4)
    assert synchronization.scale == pytest.approx(1.000119, abs=1e-5)
    assert synchronization.drift_ppm == pytest.approx(119.0, abs=10.0)
    assert synchronization.matched_pulses == 4
    assert synchronization.maximum_absolute_residual_s < 0.001
    assert payload["artifact_type"] == "clock_synchronization"
    assert payload["schema_version"] == "1"
    assert len(payload["residual_s"]) == 4
    assert payload["match_labels"] == [
        "pulse-0",
        "pulse-1",
        "pulse-2",
        "pulse-3",
    ]
    assert synchronization.synchronization_id.startswith("clock-sync-")
    assert (
        synchronization.synchronization_id
        == _clock_synchronization().synchronization_id
    )

    transformed = synchronization.transform_time([5.0, 55.0])
    assert transformed == pytest.approx(
        synchronization.intercept_s
        + synchronization.scale * np.asarray([5.0, 55.0])
    )
    assert not transformed.flags.writeable
    with pytest.raises(ValueError, match="requires 1s extrapolation"):
        synchronization.transform_time([61.0])
    allowed = synchronization.transform_time([61.0], maximum_extrapolation_s=1.0)
    assert allowed[0] == pytest.approx(
        synchronization.intercept_s + synchronization.scale * 61.0
    )


def test_clock_synchronization_rejects_bad_matches_and_failed_thresholds() -> None:
    with pytest.raises(ValueError, match="pulse counts must match"):
        ClockPulseMatches.from_arrays(
            source_clock_id="video",
            target_clock_id="photometry",
            source_time_s=[0.0, 1.0],
            target_time_s=[0.0],
        )
    with pytest.raises(ValueError, match="target pulse times must be strictly"):
        ClockPulseMatches.from_arrays(
            source_clock_id="video",
            target_clock_id="photometry",
            source_time_s=[0.0, 1.0, 2.0],
            target_time_s=[0.0, 2.0, 1.0],
        )

    too_few = ClockPulseMatches.from_arrays(
        source_clock_id="video",
        target_clock_id="photometry",
        source_time_s=[0.0, 20.0],
        target_time_s=[0.0, 20.0],
    )
    spec = ClockSynchronizationSpec(0.01, 200.0)
    with pytest.raises(ValueError, match="has 2 matches"):
        fit_clock_synchronization(too_few, spec)

    excessive_drift = ClockPulseMatches.from_arrays(
        source_clock_id="video",
        target_clock_id="photometry",
        source_time_s=[0.0, 10.0, 20.0, 30.0],
        target_time_s=[0.0, 10.01, 20.02, 30.03],
    )
    with pytest.raises(ValueError, match="clock drift"):
        fit_clock_synchronization(excessive_drift, spec)

    nonlinear = ClockPulseMatches.from_arrays(
        source_clock_id="video",
        target_clock_id="photometry",
        source_time_s=[0.0, 10.0, 20.0, 30.0],
        target_time_s=[0.0, 10.0, 20.1, 30.0],
    )
    residual_spec = ClockSynchronizationSpec(0.01, 5_000.0)
    with pytest.raises(ValueError, match="maximum absolute residual"):
        fit_clock_synchronization(nonlinear, residual_spec)


def test_synchronization_composes_pose_covariates_and_annotations() -> None:
    synchronization = _clock_synchronization()
    pose = pose_from_sleap(
        np.zeros((2, 1, 1, 2)),
        subject="mouse-1",
        session="day-1",
        node_names=["nose"],
        node="nose",
        dims=("frame", "track", "node", "xy"),
        time_s=[10.0, 20.0],
        clock_id="video",
    )
    synchronized_pose = synchronization.synchronize_pose(pose)
    speed = synchronized_pose.speed(minimum_confidence=0.0)
    assert synchronized_pose.clock_id == "photometry"
    assert synchronized_pose.clock_synchronization_ids == (
        synchronization.synchronization_id,
    )
    assert (
        speed.clock_synchronization_ids
        == synchronized_pose.clock_synchronization_ids
    )

    covariate = BehaviorCovariate(
        subject="mouse-1",
        session="day-1",
        name="speed",
        time_s=np.asarray([10.0, 20.0]),
        values=np.asarray([1.0, 2.0]),
        valid=np.asarray([True, False]),
        unit="cm/s",
        source="pose",
        clock_id="video",
    )
    synchronized_covariate = synchronization.synchronize_covariate(covariate)
    assert synchronized_covariate.clock_id == "photometry"
    assert synchronized_covariate.values.tolist() == [1.0, 2.0]
    assert synchronized_covariate.valid.tolist() == [True, False]
    assert synchronized_covariate.clock_synchronization_ids == (
        synchronization.synchronization_id,
    )

    annotations = BehaviorAnnotations(
        subject="mouse-1",
        session="day-1",
        point_events={"cue": (10.0,)},
        intervals=(BehaviorInterval("rear", 20.0, 30.0),),
        source="boris",
        clock_id="video",
    )
    synchronized_annotations = synchronization.synchronize_annotations(annotations)
    assert synchronized_annotations.clock_id == "photometry"
    assert synchronized_annotations.point_events["cue"] == pytest.approx(
        (synchronization.intercept_s + synchronization.scale * 10.0,)
    )
    assert synchronized_annotations.intervals[0].start_s == pytest.approx(
        synchronization.intercept_s + synchronization.scale * 20.0
    )
    assert synchronized_annotations.clock_synchronization_ids == (
        synchronization.synchronization_id,
    )
    with pytest.raises(ValueError, match="expects 'video'"):
        synchronization.synchronize_covariate(synchronized_covariate)


def test_deeplabcut_pose_speed_and_gap_safe_alignment() -> None:
    frame = _Frame(
        {
            ("network", "nose", "x"): [0.0, 1.0, 2.0, 30.0, 31.0],
            ("network", "nose", "y"): [0.0, 0.0, 0.0, 0.0, 0.0],
            ("network", "nose", "likelihood"): [0.99, 0.99, 0.2, 0.99, 0.99],
        }
    )
    pose = pose_from_deeplabcut(
        frame,
        subject="mouse-1",
        session="day-1",
        keypoint="nose",
        fps=1.0,
        scorer="network",
    )
    speed = pose.speed(minimum_confidence=0.9)
    aligned_covariate = speed.aligned_to(
        [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        target_clock_id="video",
        max_gap_s=1.1,
    )
    aligned = aligned_covariate.values

    assert speed.unit == "px/s"
    assert speed.valid.tolist() == [False, True, False, False, True]
    assert aligned_covariate.valid.tolist() == [
        True,
        False,
        False,
        False,
        False,
        False,
        True,
    ]
    assert aligned[0] == pytest.approx(1.0)
    assert np.isnan(aligned[1:6]).all()
    assert aligned[6] == pytest.approx(1.0)
    with pytest.raises(ValueError, match="clock mismatch"):
        speed.align_to([1.0], target_clock_id="photometry", max_gap_s=1.1)


def test_deeplabcut_requires_explicit_identity_when_columns_are_ambiguous() -> None:
    columns: dict[tuple[str, ...], list[float]] = {}
    for scorer in ("network-a", "network-b"):
        columns[(scorer, "nose", "x")] = [0.0, 1.0]
        columns[(scorer, "nose", "y")] = [0.0, 1.0]
        columns[(scorer, "nose", "likelihood")] = [0.9, 0.9]
    with pytest.raises(ValueError, match="missing or ambiguous"):
        pose_from_deeplabcut(
            _Frame(columns),
            subject="mouse-1",
            session="day-1",
            keypoint="nose",
            fps=30.0,
        )


def test_sleap_matlab_and_standard_axes_are_explicit() -> None:
    standard = np.zeros((4, 1, 2, 2), dtype=float)
    standard[:, 0, 1, 0] = [0.0, 1.0, 2.0, 3.0]
    standard[:, 0, 1, 1] = [4.0, 5.0, 6.0, 7.0]
    scores = np.ones((4, 1, 2), dtype=float)
    pose = pose_from_sleap(
        standard,
        subject="mouse-1",
        session="day-1",
        node_names=["tail", "nose"],
        node="nose",
        dims=("frame", "track", "node", "xy"),
        point_scores=scores,
        fps=20.0,
    )
    matlab = np.transpose(standard, (1, 3, 2, 0))
    matlab_scores = np.transpose(scores, (1, 2, 0))
    same_pose = pose_from_sleap(
        matlab,
        subject="mouse-1",
        session="day-1",
        node_names=["tail", "nose"],
        node="nose",
        dims=("track", "xy", "node", "frame"),
        point_scores=matlab_scores,
        fps=20.0,
    )

    assert pose.x.tolist() == [0.0, 1.0, 2.0, 3.0]
    assert same_pose.x.tolist() == pose.x.tolist()
    assert same_pose.y.tolist() == pose.y.tolist()


def test_moseq_bouts_preserve_duration_and_expose_edges() -> None:
    annotations = annotations_from_moseq(
        [2, 2, 2, 5, 5, 2],
        subject="mouse-1",
        session="day-1",
        fps=2.0,
        labels={2: "rear", 5: "groom"},
    )

    assert [item.label for item in annotations.intervals] == [
        "rear",
        "groom",
        "rear",
    ]
    assert annotations.intervals[0].start_s == 0.0
    assert annotations.intervals[0].stop_s == 1.5
    assert annotations.event_times()["groom"] == (1.5,)
    assert annotations.event_times(edge="offset")["groom"] == (2.5,)


def test_boris_points_states_and_normalized_progress_feed_encoding() -> None:
    annotations = annotations_from_boris(
        {
            "Behavior": ["cue", "approach"],
            "Type": ["POINT", "STATE"],
            "Start": [0.5, 1.0],
            "Stop": [np.nan, 3.0],
        },
        subject="mouse-1",
        session="day-1",
        behavior_column="Behavior",
        type_column="Type",
        start_column="Start",
        stop_column="Stop",
    )
    progress = annotations.normalized_progress(
        [0.0, 1.0, 2.0, 3.0, 4.0], label="approach"
    )
    session = EncodingSession.from_arrays(
        subject="mouse-1",
        session="day-1",
        time=[0.0, 1.0, 2.0, 3.0, 4.0],
        response=[0.0, 0.1, 0.2, 0.3, 0.4],
        events=annotations.event_times(),
        continuous_covariates={"approach_progress": progress.values},
        continuous_covariate_validity={"approach_progress": progress.valid},
    )

    assert annotations.point_events == {"cue": (0.5,)}
    assert progress.values[1:4].tolist() == [0.0, 0.5, 1.0]
    assert session.events["approach"] == (1.0,)


def test_progress_rejects_overlapping_bouts() -> None:
    annotations = BehaviorAnnotations(
        subject="mouse-1",
        session="day-1",
        point_events={},
        intervals=(
            BehaviorInterval("groom", 0.0, 2.0),
            BehaviorInterval("groom", 1.0, 3.0),
        ),
        source="manual",
        clock_id="video",
    )
    with pytest.raises(ValueError, match="overlapping"):
        annotations.normalized_progress([0.0, 1.0, 2.0, 3.0], label="groom")


def test_covariate_validity_excludes_nonfinite_values() -> None:
    covariate = BehaviorCovariate(
        subject="mouse-1",
        session="day-1",
        name="speed",
        time_s=np.array([0.0, 1.0]),
        values=np.array([1.0, np.nan]),
        valid=np.array([True, True]),
        unit="cm/s",
        source="pose",
        clock_id="video",
    )
    assert covariate.valid.tolist() == [True, False]


def test_upstream_fixture_checksums_match_manifest() -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for item in manifest["fixtures"]:
        digest = hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
        assert digest == item["sha256"]


def test_official_sleap_analysis_h5_fixture() -> None:
    pose = pose_from_sleap_analysis_h5(
        FIXTURES / "sleap-small-robot.analysis.h5",
        subject="robot-1",
        session="three-frames",
        node="front",
        dims=("track", "xy", "node", "frame"),
        fps=25.0,
        source_version="legacy-format-v1",
    )

    assert pose.keypoint == "front"
    assert pose.x.tolist() == pytest.approx([382.74652904, 384.70135498, 382.74652904])
    assert pose.y.tolist() == pytest.approx([243.01542777, 244.34580994, 243.01542777])
    assert pose.confidence[1] > 1.0
    assert pose.source_artifact is not None


def test_legacy_sleap_file_requires_explicit_axes() -> None:
    with pytest.raises(ValueError, match="declare dims"):
        pose_from_sleap_analysis_h5(
            FIXTURES / "sleap-small-robot.analysis.h5",
            subject="robot-1",
            session="three-frames",
            node="front",
            fps=25.0,
        )


def test_sleap_file_uses_json_dimension_metadata(tmp_path: Path) -> None:
    path = tmp_path / "current.analysis.h5"
    with h5py.File(path, "w") as file:
        tracks = file.create_dataset("tracks", data=np.zeros((3, 1, 1, 2)))
        tracks.attrs["dims"] = '["frame", "track", "node", "xy"]'
        scores = file.create_dataset("point_scores", data=np.ones((3, 1, 1)))
        scores.attrs["dims"] = '["frame", "track", "node"]'
        file.create_dataset("node_names", data=[b"nose"])

    pose = pose_from_sleap_analysis_h5(
        path,
        subject="mouse-1",
        session="day-1",
        node="nose",
        fps=30.0,
    )

    assert pose.x.tolist() == [0.0, 0.0, 0.0]
    assert pose.confidence.tolist() == [1.0, 1.0, 1.0]


def test_official_boris_tabular_fixture_pairs_state_rows() -> None:
    annotations = annotations_from_boris_tabular_file(
        FIXTURES / "boris-test-export-events-tabular.csv",
        subject="canonical-mouse-1",
        session="observation-1",
        source_subject="subject1",
        source_version="upstream-fixture",
    )

    assert annotations.point_events == {}
    assert [(item.start_s, item.stop_s) for item in annotations.intervals] == [
        (3.3, 7.75),
        (9.9, 16.2),
        (18.35, 24.475),
    ]
    assert {item.label for item in annotations.intervals} == {"s"}


def test_boris_tabular_fixture_requires_subject_selection() -> None:
    with pytest.raises(ValueError, match="multiple subjects"):
        annotations_from_boris_tabular_file(
            FIXTURES / "boris-test-export-events-tabular.csv",
            subject="mouse-1",
            session="observation-1",
        )


def test_boris_tabular_file_preserves_point_rows(tmp_path: Path) -> None:
    path = tmp_path / "point.csv"
    path.write_text(
        "Observation id,demo,,,,\n"
        "Time,Subject,Behavior,Status\n"
        "1.25,mouse-1,cue,POINT\n"
        "2.50,mouse-1,reward,\n"
    )

    annotations = annotations_from_boris_tabular_file(
        path,
        subject="mouse-1",
        session="day-1",
    )

    assert annotations.point_events == {"cue": (1.25,), "reward": (2.5,)}


@pytest.mark.parametrize("suffix", [".csv", ".h5"])
def test_deeplabcut_documented_file_shapes(tmp_path: Path, suffix: str) -> None:
    columns = pd.MultiIndex.from_product(
        [["network"], ["nose"], ["x", "y", "likelihood"]]
    )
    frame = pd.DataFrame(
        [[0.0, 2.0, 0.99], [1.0, 3.0, 0.95], [2.0, 4.0, 0.91]],
        columns=columns,
    )
    path = tmp_path / f"predictions{suffix}"
    if suffix == ".csv":
        frame.to_csv(path)
    else:
        frame.to_hdf(path, key="df_with_missing")

    pose = pose_from_deeplabcut_file(
        path,
        subject="mouse-1",
        session="day-1",
        keypoint="nose",
        scorer="network",
        fps=30.0,
        source_version="schema-generated",
    )

    assert pose.x.tolist() == [0.0, 1.0, 2.0]
    assert pose.confidence.tolist() == [0.99, 0.95, 0.91]
    assert pose.source_artifact == str(path)


def test_moseq_documented_results_h5_shape(tmp_path: Path) -> None:
    path = tmp_path / "results.h5"
    with h5py.File(path, "w") as file:
        recording = file.create_group("recording-01")
        recording.create_dataset("syllable", data=[3, 3, 1, 1, 1, 3])
        recording.create_dataset("latent_state", data=np.zeros((6, 2)))
        recording.create_dataset("centroid", data=np.zeros((6, 2)))
        recording.create_dataset("heading", data=np.zeros(6))

    annotations = annotations_from_moseq_results_h5(
        path,
        recording="recording-01",
        subject="mouse-1",
        session="day-1",
        fps=30.0,
        labels={1: "rear", 3: "pause"},
        source_version="schema-generated",
    )

    assert [item.label for item in annotations.intervals] == [
        "pause",
        "rear",
        "pause",
    ]
    assert annotations.source_artifact == str(path)
