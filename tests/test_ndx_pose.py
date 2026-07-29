from datetime import UTC, datetime

import numpy as np
import pytest
from behavio.pose import PoseTrajectory

from fipha.io.ndx_pose import (
    NdxPoseMetadata,
    add_poses_to_nwb,
    inspect_ndx_pose_nwb,
    poses_from_ndx_pose,
    poses_from_ndx_pose_nwb,
)

pynwb = pytest.importorskip("pynwb")
ndx_pose = pytest.importorskip("ndx_pose")


def _nwbfile(identifier: str = "fixture"):
    nwbfile = pynwb.NWBFile(
        session_description="ndx-pose round-trip fixture",
        identifier=identifier,
        session_id="day-1",
        session_start_time=datetime.now(UTC),
    )
    nwbfile.subject = pynwb.file.Subject(subject_id="mouse-1")
    return nwbfile


def _poses() -> tuple[PoseTrajectory, ...]:
    return (
        PoseTrajectory(
            subject="mouse-1",
            session="day-1",
            keypoint="nose",
            time_s=np.asarray([0.0, 0.1, 0.2]),
            x=np.asarray([1.0, 2.0, 3.0]),
            y=np.asarray([4.0, 5.0, 6.0]),
            z=np.asarray([7.0, 8.0, 9.0]),
            confidence=np.asarray([0.9, 0.8, np.nan]),
            coordinate_unit="cm",
            source="SLEAP",
            source_version="1.5.0",
            clock_id="video",
            reference_frame="arena origin",
            confidence_definition="model point score",
            individual="track-0",
            clock_synchronization_ids=("sync-1",),
        ),
        PoseTrajectory(
            subject="mouse-1",
            session="day-1",
            keypoint="tail-base",
            time_s=np.asarray([0.0, 0.1, 0.2]),
            x=np.asarray([10.0, 11.0, 12.0]),
            y=np.asarray([13.0, 14.0, 15.0]),
            confidence=np.full(3, np.nan),
            coordinate_unit="cm",
            source="SLEAP",
            source_version="1.5.0",
            clock_id="video",
            reference_frame="arena origin",
            individual="track-0",
            clock_synchronization_ids=("sync-1",),
        ),
    )


def _metadata() -> NdxPoseMetadata:
    return NdxPoseMetadata(
        pose_estimation_name="TopCameraPose",
        description="SLEAP estimates from the top camera",
        scorer="model-2026-07",
        source_software="SLEAP",
        source_software_version="1.5.0",
        skeleton_name="mouse-skeleton",
        skeleton_nodes=("nose", "tail-base"),
        skeleton_edges=((0, 1),),
        original_videos=("videos/top-camera.mp4",),
        dimensions=((640, 480),),
        device_names=("top-camera",),
    )


def test_real_ndx_pose_file_roundtrip_retains_arrays_and_metadata(tmp_path) -> None:
    nwbfile = _nwbfile()
    camera = nwbfile.create_device(name="top-camera", description="top camera")
    written = add_poses_to_nwb(
        _poses(),
        nwbfile,
        metadata=_metadata(),
        devices=(camera,),
    )
    assert written.omitted_links == ()
    path = tmp_path / "pose.nwb"
    with pynwb.NWBHDF5IO(path, "w") as io:
        io.write(nwbfile)
    assert not pynwb.validate(path=str(path))

    inspection = inspect_ndx_pose_nwb(path)
    assert len(inspection.source_sha256) == 64
    assert inspection.pose_estimations[0].metadata.pose_estimation_name == (
        "TopCameraPose"
    )
    assert inspection.pose_estimations[0].metadata.skeleton_edges == ((0, 1),)
    assert [
        item.coordinate_dimensions for item in inspection.pose_estimations[0].series
    ] == [
        3,
        2,
    ]
    assert [item.has_confidence for item in inspection.pose_estimations[0].series] == [
        True,
        True,
    ]

    restored = poses_from_ndx_pose_nwb(
        path,
        subject="mouse-1",
        session="day-1",
        clock_id="video",
    )
    assert restored.source_sha256 == inspection.source_sha256
    assert restored.metadata.source_software == "SLEAP"
    assert restored.metadata.device_names == ("top-camera",)
    assert "destination Device" in restored.issues[0]
    nose, tail = restored.trajectories
    assert nose.z is not None
    assert nose.z.tolist() == [7.0, 8.0, 9.0]
    assert nose.confidence_definition == "model point score"
    assert nose.individual == "track-0"
    assert nose.clock_synchronization_ids == ("sync-1",)
    assert tail.z is None
    assert np.isnan(tail.confidence).all()

    destination = _nwbfile("second")
    second = add_poses_to_nwb(
        restored.trajectories,
        destination,
        metadata=restored.metadata,
    )
    assert second.omitted_links == ("devices", "original_videos", "dimensions")
    second_path = tmp_path / "pose-second.nwb"
    with pynwb.NWBHDF5IO(second_path, "w") as io:
        io.write(destination)
    assert not pynwb.validate(path=str(second_path))
    second_restored = poses_from_ndx_pose_nwb(
        second_path,
        subject="mouse-1",
        session="day-1",
        clock_id="video",
    )
    assert np.array_equal(second_restored.trajectories[0].x, nose.x)
    assert np.array_equal(second_restored.trajectories[0].time_s, nose.time_s)
    assert second_restored.metadata.skeleton_edges == ((0, 1),)


def test_object_import_applies_conversion_offset_and_rate() -> None:
    series = ndx_pose.PoseEstimationSeries(
        name="nose",
        data=np.asarray([[0.0, 2.0], [4.0, 6.0]]),
        conversion=0.5,
        offset=1.0,
        unit="cm",
        reference_frame="arena origin",
        starting_time=2.0,
        rate=10.0,
    )
    pose_estimation = ndx_pose.PoseEstimation(
        name="ConvertedPose",
        pose_estimation_series=[series],
        source_software="DeepLabCut",
        source_software_version="3.0.0",
    )

    result = poses_from_ndx_pose(
        pose_estimation,
        subject="mouse-1",
        session="day-1",
        clock_id="video",
    )

    pose = result.trajectories[0]
    assert pose.x.tolist() == [1.0, 3.0]
    assert pose.y.tolist() == [2.0, 4.0]
    assert pose.time_s.tolist() == [2.0, 2.1]
    assert np.isnan(pose.confidence).all()
    assert pose.source == "DeepLabCut"


def test_default_export_writes_a_schema_valid_single_keypoint(tmp_path) -> None:
    nwbfile = _nwbfile()
    result = add_poses_to_nwb((_poses()[0],), nwbfile)
    assert result.omitted_links == ()
    path = tmp_path / "single-keypoint.nwb"
    with pynwb.NWBHDF5IO(path, "w") as io:
        io.write(nwbfile)
    assert not pynwb.validate(path=str(path))


def test_object_import_rejects_inconsistent_child_timestamps() -> None:
    first = ndx_pose.PoseEstimationSeries(
        name="nose",
        data=np.zeros((2, 2)),
        reference_frame="origin",
        timestamps=[0.0, 1.0],
    )
    second = ndx_pose.PoseEstimationSeries(
        name="tail",
        data=np.zeros((2, 2)),
        reference_frame="origin",
        timestamps=[0.0, 2.0],
    )
    container = ndx_pose.PoseEstimation(pose_estimation_series=[first, second])

    with pytest.raises(ValueError, match="identical timestamps"):
        poses_from_ndx_pose(
            container,
            subject="mouse-1",
            session="day-1",
            clock_id="video",
        )


def test_file_selection_refuses_ambiguous_pose_estimations(tmp_path) -> None:
    nwbfile = _nwbfile()
    add_poses_to_nwb(_poses(), nwbfile, metadata=_metadata())
    second_metadata = NdxPoseMetadata(
        processing_module_name="second-camera",
        pose_estimation_name="SideCameraPose",
        skeleton_nodes=("nose", "tail-base"),
        skeleton_edges=((0, 1),),
    )
    add_poses_to_nwb(_poses(), nwbfile, metadata=second_metadata)
    path = tmp_path / "multiple.nwb"
    with pynwb.NWBHDF5IO(path, "w") as io:
        io.write(nwbfile)

    with pytest.raises(ValueError, match=r"available=.*TopCameraPose.*SideCameraPose"):
        poses_from_ndx_pose_nwb(
            path,
            subject="mouse-1",
            session="day-1",
            clock_id="video",
        )
    selected = poses_from_ndx_pose_nwb(
        path,
        subject="mouse-1",
        session="day-1",
        clock_id="video",
        processing_module_name="second-camera",
    )
    assert selected.metadata.pose_estimation_name == "SideCameraPose"


def test_export_refuses_ndx_incompatible_confidence_and_identity() -> None:
    pose = _poses()[0]
    invalid_confidence = PoseTrajectory(
        **{
            **vars(pose),
            "confidence": np.asarray([0.9, 1.2, 0.8]),
        }
    )
    with pytest.raises(ValueError, match="between zero and one"):
        add_poses_to_nwb((invalid_confidence,), _nwbfile())

    other_session = PoseTrajectory(
        **{
            **vars(_poses()[1]),
            "session": "day-2",
        }
    )
    with pytest.raises(ValueError, match="share subject, session, and clock_id"):
        add_poses_to_nwb((pose, other_session), _nwbfile())

    nwbfile = _nwbfile()
    wrong_camera = nwbfile.create_device(name="side-camera")
    with pytest.raises(ValueError, match="device names must match"):
        add_poses_to_nwb(
            _poses(),
            nwbfile,
            metadata=_metadata(),
            devices=(wrong_camera,),
        )


def test_three_dimensional_speed_uses_all_coordinate_axes() -> None:
    pose = _poses()[0]
    speed = pose.speed(minimum_confidence=0.5)

    assert speed.values[1] == pytest.approx(np.sqrt(3.0) / 0.1)
    assert not speed.valid[2]

    missing_z = PoseTrajectory(
        **{
            **vars(pose),
            "z": np.asarray([7.0, np.nan, 9.0]),
            "confidence": np.asarray([0.9, 0.9, 0.9]),
        }
    )
    assert not missing_z.speed(minimum_confidence=0.5).valid[1:].any()
