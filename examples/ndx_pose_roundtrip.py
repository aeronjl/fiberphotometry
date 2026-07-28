"""Write, inspect, and restore native ndx-pose trajectories."""

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from pynwb import NWBHDF5IO, NWBFile
from pynwb.file import Subject

from fiberphotometry import (
    NdxPoseMetadata,
    PoseTrajectory,
    add_poses_to_nwb,
    inspect_ndx_pose_nwb,
    poses_from_ndx_pose_nwb,
)


def run(path: str | Path) -> dict[str, object]:
    destination = Path(path)
    time_s = np.arange(5, dtype=float) / 30.0
    poses = (
        PoseTrajectory(
            subject="mouse-1",
            session="day-1",
            keypoint="nose",
            time_s=time_s,
            x=np.asarray([10.0, 11.0, 12.0, 13.0, 14.0]),
            y=np.asarray([20.0, 20.5, 21.0, 21.5, 22.0]),
            confidence=np.asarray([0.99, 0.98, 0.97, 0.96, 0.95]),
            coordinate_unit="pixels",
            source="DeepLabCut",
            source_version="3.0.0",
            clock_id="video",
            reference_frame="top-left video pixel",
            confidence_definition="DeepLabCut likelihood",
        ),
        PoseTrajectory(
            subject="mouse-1",
            session="day-1",
            keypoint="tail-base",
            time_s=time_s,
            x=np.asarray([7.0, 8.0, 9.0, 10.0, 11.0]),
            y=np.asarray([25.0, 25.5, 26.0, 26.5, 27.0]),
            confidence=np.asarray([0.95, 0.94, 0.93, 0.92, 0.91]),
            coordinate_unit="pixels",
            source="DeepLabCut",
            source_version="3.0.0",
            clock_id="video",
            reference_frame="top-left video pixel",
            confidence_definition="DeepLabCut likelihood",
        ),
    )
    metadata = NdxPoseMetadata(
        pose_estimation_name="TopCameraPose",
        scorer="DLC_resnet50_arena",
        source_software="DeepLabCut",
        source_software_version="3.0.0",
        skeleton_name="mouse-skeleton",
        skeleton_nodes=("nose", "tail-base"),
        skeleton_edges=((0, 1),),
        original_videos=("videos/mouse-1-day-1.mp4",),
        dimensions=((1280, 720),),
        device_names=("top-camera",),
    )

    nwbfile = NWBFile(
        session_description="ndx-pose interoperability example",
        identifier="mouse-1-day-1",
        session_id="day-1",
        session_start_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    nwbfile.subject = Subject(subject_id="mouse-1")
    camera = nwbfile.create_device(name="top-camera", description="arena camera")
    add_poses_to_nwb(poses, nwbfile, metadata=metadata, devices=(camera,))
    with NWBHDF5IO(destination, "w") as io:
        io.write(nwbfile)

    inspection = inspect_ndx_pose_nwb(destination)
    restored = poses_from_ndx_pose_nwb(
        destination,
        subject="mouse-1",
        session="day-1",
        clock_id="video",
    )
    return {"inspection": inspection, "restored": restored}


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        artifacts = run(Path(directory) / "ndx-pose-example.nwb")
        inspection = artifacts["inspection"]
        restored = artifacts["restored"]
        print(inspection.to_json())
        print("Restored keypoints:", [pose.keypoint for pose in restored.trajectories])
