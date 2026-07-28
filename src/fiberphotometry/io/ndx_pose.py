"""Native ndx-pose inspection, import, and export boundaries."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np

from fiberphotometry.interoperability import PoseTrajectory
from fiberphotometry.io.acquisition import file_sha256


@dataclass(frozen=True)
class NdxPoseSeriesInspection:
    """Bounded structural evidence for one ndx-pose keypoint series."""

    name: str
    samples: int
    coordinate_dimensions: Literal[2, 3]
    coordinate_unit: str
    reference_frame: str
    has_confidence: bool
    confidence_definition: str | None
    timing: Literal["timestamps", "rate"]
    time_start_s: float
    time_stop_s: float


@dataclass(frozen=True)
class NdxPoseMetadata:
    """Container-level ndx-pose metadata retained independently of arrays."""

    processing_module_name: str = "behavior"
    processing_module_description: str = "Behavioral pose estimation"
    pose_estimation_name: str = "PoseEstimation"
    description: str | None = None
    scorer: str | None = None
    source_software: str | None = None
    source_software_version: str | None = None
    skeleton_name: str = "Skeleton"
    skeleton_nodes: tuple[str, ...] = ()
    skeleton_edges: tuple[tuple[int, int], ...] = ()
    original_videos: tuple[str, ...] = ()
    labeled_videos: tuple[str, ...] = ()
    dimensions: tuple[tuple[int, int], ...] = ()
    device_names: tuple[str, ...] = ()
    has_source_video_link: bool = False
    has_labeled_video_link: bool = False

    def __post_init__(self) -> None:
        for value, name in (
            (self.processing_module_name, "processing_module_name"),
            (self.processing_module_description, "processing_module_description"),
            (self.pose_estimation_name, "pose_estimation_name"),
            (self.skeleton_name, "skeleton_name"),
        ):
            if not value.strip():
                raise ValueError(f"{name} must be non-empty")
        for optional_value, name in (
            (self.description, "description"),
            (self.scorer, "scorer"),
            (self.source_software, "source_software"),
            (self.source_software_version, "source_software_version"),
        ):
            if optional_value is not None and not optional_value.strip():
                raise ValueError(f"{name} must be non-empty when provided")
        if self.source_software_version is not None and self.source_software is None:
            raise ValueError(
                "source_software_version requires a declared source_software"
            )
        if any(not value.strip() for value in self.skeleton_nodes):
            raise ValueError("skeleton nodes must be non-empty")
        if len(set(self.skeleton_nodes)) != len(self.skeleton_nodes):
            raise ValueError("skeleton nodes must be unique")
        for left, right in self.skeleton_edges:
            if left < 0 or right < 0 or left == right:
                raise ValueError("skeleton edges require distinct non-negative indices")
            if self.skeleton_nodes and (
                left >= len(self.skeleton_nodes) or right >= len(self.skeleton_nodes)
            ):
                raise ValueError("skeleton edge index is outside skeleton_nodes")
        if any(width <= 0 or height <= 0 for width, height in self.dimensions):
            raise ValueError("video dimensions must be positive")


@dataclass(frozen=True)
class NdxPoseEstimationInspection:
    """Discoverable structure and provenance for one PoseEstimation container."""

    metadata: NdxPoseMetadata
    series: tuple[NdxPoseSeriesInspection, ...]


@dataclass(frozen=True)
class NdxPoseFileInspection:
    """Dependency-backed inventory of ndx-pose containers in one NWB file."""

    source_name: str
    source_sha256: str
    pose_estimations: tuple[NdxPoseEstimationInspection, ...]
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


@dataclass(frozen=True)
class NdxPoseImportResult:
    """Copied pose trajectories plus retained container and source evidence."""

    trajectories: tuple[PoseTrajectory, ...]
    metadata: NdxPoseMetadata
    source_artifact: str | None = None
    source_sha256: str | None = None
    issues: tuple[str, ...] = ()
    schema_version: str = "1"


@dataclass(frozen=True)
class NdxPoseWriteResult:
    """Created extension objects and any links not supplied for the destination."""

    processing_module: Any
    skeletons: Any
    pose_estimation: Any
    omitted_links: tuple[str, ...]
    schema_version: str = "1"


def inspect_ndx_pose_nwb(path: str | Path) -> NdxPoseFileInspection:
    """Inventory all ndx-pose containers without loading full coordinate arrays."""

    source = _nwb_path(path)
    _require_dependencies()
    from pynwb import NWBHDF5IO  # type: ignore[import-untyped]

    with NWBHDF5IO(source, "r", load_namespaces=True) as io:
        nwbfile = io.read()
        inspections = tuple(
            _inspect_pose_estimation(module_name, module.description, value)
            for module_name, value, module in _pose_estimations(nwbfile)
        )
    return NdxPoseFileInspection(
        str(source),
        file_sha256(source),
        inspections,
    )


def poses_from_ndx_pose(
    pose_estimation: Any,
    *,
    subject: str,
    session: str,
    clock_id: str,
    processing_module_name: str = "behavior",
    processing_module_description: str = "Behavioral pose estimation",
    source_artifact: str | None = None,
    source_sha256: str | None = None,
) -> NdxPoseImportResult:
    """Copy one in-memory PoseEstimation into typed physical trajectories."""

    for value, name in (
        (subject, "subject"),
        (session, "session"),
        (clock_id, "clock_id"),
    ):
        if not value.strip():
            raise ValueError(f"{name} must be non-empty")
    metadata = _metadata_from_pose_estimation(
        processing_module_name,
        processing_module_description,
        pose_estimation,
    )
    items = tuple(getattr(pose_estimation, "pose_estimation_series", {}).values())
    if not items:
        raise ValueError("PoseEstimation contains no pose estimation series")
    trajectories = tuple(
        _trajectory_from_series(
            series,
            subject=subject,
            session=session,
            clock_id=clock_id,
            source_software=metadata.source_software,
            source_version=metadata.source_software_version,
            source_artifact=source_artifact,
        )
        for series in items
    )
    reference_time = trajectories[0].time_s
    for trajectory in trajectories[1:]:
        if not np.array_equal(trajectory.time_s, reference_time):
            raise ValueError(
                "PoseEstimation child series must use identical timestamps"
            )
    issues = []
    if metadata.device_names:
        issues.append(
            "camera device links require explicit destination Device objects on export"
        )
    if metadata.has_source_video_link:
        issues.append(
            "source_video link requires an explicit destination ImageSeries on export"
        )
    if metadata.has_labeled_video_link:
        issues.append(
            "labeled_video link requires an explicit destination ImageSeries on export"
        )
    return NdxPoseImportResult(
        trajectories,
        metadata,
        source_artifact,
        source_sha256,
        tuple(issues),
    )


def poses_from_ndx_pose_nwb(
    path: str | Path,
    *,
    subject: str,
    session: str,
    clock_id: str,
    processing_module_name: str | None = None,
    pose_estimation_name: str | None = None,
) -> NdxPoseImportResult:
    """Read one explicitly selected PoseEstimation from an NWB file."""

    source = _nwb_path(path)
    _require_dependencies()
    from pynwb import NWBHDF5IO

    with NWBHDF5IO(source, "r", load_namespaces=True) as io:
        nwbfile = io.read()
        matches = [
            (module_name, value, module)
            for module_name, value, module in _pose_estimations(nwbfile)
            if (processing_module_name is None or module_name == processing_module_name)
            and (pose_estimation_name is None or value.name == pose_estimation_name)
        ]
        if len(matches) != 1:
            available = tuple(
                f"{module_name}/{value.name}"
                for module_name, value, _ in _pose_estimations(nwbfile)
            )
            raise ValueError(
                "ndx-pose selection must identify exactly one PoseEstimation; "
                f"available={available}"
            )
        module_name, pose_estimation, module = matches[0]
        result = poses_from_ndx_pose(
            pose_estimation,
            subject=subject,
            session=session,
            clock_id=clock_id,
            processing_module_name=module_name,
            processing_module_description=str(module.description),
            source_artifact=str(source),
            source_sha256=file_sha256(source),
        )
    return result


def add_poses_to_nwb(
    trajectories: Sequence[PoseTrajectory],
    nwbfile: Any,
    *,
    metadata: NdxPoseMetadata | None = None,
    reference_frame: str | None = None,
    devices: Sequence[Any] = (),
    source_video: Any | None = None,
    labeled_video: Any | None = None,
) -> NdxPoseWriteResult:
    """Write compatible trajectories to a behavior processing module."""

    _require_dependencies()
    from ndx_pose import (  # type: ignore[import-untyped]
        PoseEstimation,
        PoseEstimationSeries,
        Skeleton,
        Skeletons,
    )

    poses = tuple(trajectories)
    if not poses:
        raise ValueError("at least one pose trajectory is required")
    _validate_trajectory_group(poses, nwbfile)
    selected_metadata = metadata or NdxPoseMetadata(
        source_software=_common_optional(
            tuple(pose.source for pose in poses), "pose source"
        ),
        source_software_version=_common_optional(
            tuple(pose.source_version for pose in poses), "pose source_version"
        ),
    )
    _validate_destination_links(selected_metadata, devices)
    keypoints = tuple(pose.keypoint for pose in poses)
    nodes = selected_metadata.skeleton_nodes or keypoints
    if nodes != keypoints:
        raise ValueError(
            "metadata skeleton_nodes must exactly match trajectory keypoint order"
        )
    if any(max(edge) >= len(nodes) for edge in selected_metadata.skeleton_edges):
        raise ValueError("skeleton edge index is outside trajectory keypoints")
    skeleton = Skeleton(
        name=selected_metadata.skeleton_name,
        nodes=list(nodes),
        edges=(
            np.asarray(selected_metadata.skeleton_edges, dtype=np.uint32)
            if selected_metadata.skeleton_edges
            else None
        ),
        subject=getattr(nwbfile, "subject", None),
    )
    skeletons = Skeletons(skeletons=[skeleton])
    series = []
    for pose in poses:
        frame = pose.reference_frame or reference_frame
        if frame is None or not frame.strip():
            raise ValueError(f"pose {pose.keypoint!r} needs a declared reference_frame")
        coordinates = np.column_stack(
            (pose.x, pose.y) if pose.z is None else (pose.x, pose.y, pose.z)
        )
        finite_confidence = pose.confidence[np.isfinite(pose.confidence)]
        if np.any((finite_confidence < 0) | (finite_confidence > 1)):
            raise ValueError("ndx-pose confidence values must lie between zero and one")
        comments = json.dumps(
            {
                "schema": "fiberphotometry-ndx-pose-v1",
                "clock_id": pose.clock_id,
                "subject": pose.subject,
                "session": pose.session,
                "individual": pose.individual,
                "clock_synchronization_ids": list(pose.clock_synchronization_ids),
            },
            sort_keys=True,
        )
        series.append(
            PoseEstimationSeries(
                name=pose.keypoint,
                data=coordinates,
                timestamps=pose.time_s,
                unit=pose.coordinate_unit,
                reference_frame=frame,
                confidence=pose.confidence,
                confidence_definition=pose.confidence_definition,
                comments=comments,
                description=f"Estimated position of {pose.keypoint}",
            )
        )
    pose_estimation = PoseEstimation(
        pose_estimation_series=series,
        name=selected_metadata.pose_estimation_name,
        description=selected_metadata.description,
        original_videos=(
            list(selected_metadata.original_videos)
            if selected_metadata.original_videos
            and (not selected_metadata.device_names or devices)
            else None
        ),
        labeled_videos=(
            list(selected_metadata.labeled_videos)
            if selected_metadata.labeled_videos
            and (not selected_metadata.device_names or devices)
            else None
        ),
        dimensions=(
            np.asarray(selected_metadata.dimensions, dtype=np.uint32)
            if selected_metadata.dimensions
            and (not selected_metadata.device_names or devices)
            else None
        ),
        devices=list(devices) or None,
        scorer=selected_metadata.scorer,
        source_software=selected_metadata.source_software,
        source_software_version=selected_metadata.source_software_version,
        skeleton=skeleton,
        source_video=source_video,
        labeled_video=labeled_video,
    )
    processing = _processing_module(nwbfile, selected_metadata)
    processing.add(skeletons)
    processing.add(pose_estimation)
    omitted = []
    if selected_metadata.device_names and not devices:
        omitted.append("devices")
        if selected_metadata.original_videos:
            omitted.append("original_videos")
        if selected_metadata.labeled_videos:
            omitted.append("labeled_videos")
        if selected_metadata.dimensions:
            omitted.append("dimensions")
    if selected_metadata.has_source_video_link and source_video is None:
        omitted.append("source_video")
    if selected_metadata.has_labeled_video_link and labeled_video is None:
        omitted.append("labeled_video")
    return NdxPoseWriteResult(
        processing,
        skeletons,
        pose_estimation,
        tuple(omitted),
    )


def _trajectory_from_series(
    series: Any,
    *,
    subject: str,
    session: str,
    clock_id: str,
    source_software: str | None,
    source_version: str | None,
    source_artifact: str | None,
) -> PoseTrajectory:
    raw = np.asarray(series.data[:], dtype=float)
    if raw.ndim != 2 or raw.shape[1] not in {2, 3}:
        raise ValueError(
            f"ndx-pose series {series.name!r} must have shape (samples, 2 or 3)"
        )
    conversion = float(getattr(series, "conversion", 1.0) or 1.0)
    offset = float(getattr(series, "offset", 0.0) or 0.0)
    if not np.isfinite(conversion) or not np.isfinite(offset):
        raise ValueError("ndx-pose conversion and offset must be finite")
    coordinates = raw * conversion + offset
    confidence_source = getattr(series, "confidence", None)
    confidence = (
        np.full(raw.shape[0], np.nan, dtype=float)
        if confidence_source is None
        else np.asarray(confidence_source[:], dtype=float)
    )
    if confidence.shape != (raw.shape[0],):
        raise ValueError(
            f"ndx-pose series {series.name!r} confidence length does not match data"
        )
    finite_confidence = confidence[np.isfinite(confidence)]
    if np.any((finite_confidence < 0) | (finite_confidence > 1)):
        raise ValueError("ndx-pose confidence must lie between zero and one")
    time = _series_timestamps(series, raw.shape[0])
    comments = _fiberphotometry_comments(getattr(series, "comments", ""))
    if comments:
        stored_clock = comments.get("clock_id")
        if stored_clock is not None and stored_clock != clock_id:
            raise ValueError(
                f"stored pose clock {stored_clock!r} does not match {clock_id!r}"
            )
        stored_subject = comments.get("subject")
        stored_session = comments.get("session")
        if stored_subject is not None and stored_subject != subject:
            raise ValueError("stored pose subject does not match declared subject")
        if stored_session is not None and stored_session != session:
            raise ValueError("stored pose session does not match declared session")
    synchronization_ids = tuple(
        str(value) for value in comments.get("clock_synchronization_ids", [])
    )
    individual = comments.get("individual")
    return PoseTrajectory(
        subject=subject,
        session=session,
        keypoint=str(series.name),
        time_s=time,
        x=coordinates[:, 0],
        y=coordinates[:, 1],
        z=coordinates[:, 2] if raw.shape[1] == 3 else None,
        confidence=confidence,
        coordinate_unit=str(series.unit),
        source=source_software or "ndx-pose",
        clock_id=clock_id,
        reference_frame=str(series.reference_frame),
        confidence_definition=_optional_text(
            getattr(series, "confidence_definition", None)
        ),
        individual=str(individual) if individual is not None else None,
        source_version=source_version,
        source_artifact=source_artifact,
        clock_synchronization_ids=synchronization_ids,
    )


def _inspect_pose_estimation(
    module_name: str, module_description: str, pose_estimation: Any
) -> NdxPoseEstimationInspection:
    metadata = _metadata_from_pose_estimation(
        module_name,
        module_description,
        pose_estimation,
    )
    series = []
    for value in pose_estimation.pose_estimation_series.values():
        shape = tuple(int(item) for item in value.data.shape)
        if len(shape) != 2 or shape[1] not in {2, 3}:
            raise ValueError(
                f"ndx-pose series {value.name!r} must have two or three coordinates"
            )
        timing, time_start, time_stop = _series_time_bounds(value, shape[0])
        series.append(
            NdxPoseSeriesInspection(
                name=str(value.name),
                samples=shape[0],
                coordinate_dimensions=cast(Literal[2, 3], shape[1]),
                coordinate_unit=str(value.unit),
                reference_frame=str(value.reference_frame),
                has_confidence=getattr(value, "confidence", None) is not None,
                confidence_definition=_optional_text(
                    getattr(value, "confidence_definition", None)
                ),
                timing=timing,
                time_start_s=time_start,
                time_stop_s=time_stop,
            )
        )
    return NdxPoseEstimationInspection(metadata, tuple(series))


def _metadata_from_pose_estimation(
    module_name: str, module_description: str, pose_estimation: Any
) -> NdxPoseMetadata:
    skeleton = getattr(pose_estimation, "skeleton", None)
    devices = getattr(pose_estimation, "devices", None) or ()
    return NdxPoseMetadata(
        processing_module_name=module_name,
        processing_module_description=module_description,
        pose_estimation_name=str(pose_estimation.name),
        description=_optional_text(getattr(pose_estimation, "description", None)),
        scorer=_optional_text(getattr(pose_estimation, "scorer", None)),
        source_software=_optional_text(
            getattr(pose_estimation, "source_software", None)
        ),
        source_software_version=_optional_text(
            getattr(pose_estimation, "source_software_version", None)
        ),
        skeleton_name=(str(skeleton.name) if skeleton is not None else "Skeleton"),
        skeleton_nodes=(
            tuple(str(value) for value in skeleton.nodes[:])
            if skeleton is not None
            else ()
        ),
        skeleton_edges=(
            _edge_array(skeleton.edges)
            if skeleton is not None and getattr(skeleton, "edges", None) is not None
            else ()
        ),
        original_videos=_text_array(getattr(pose_estimation, "original_videos", None)),
        labeled_videos=_text_array(getattr(pose_estimation, "labeled_videos", None)),
        dimensions=_dimension_array(getattr(pose_estimation, "dimensions", None)),
        device_names=tuple(str(value.name) for value in devices),
        has_source_video_link=getattr(pose_estimation, "source_video", None)
        is not None,
        has_labeled_video_link=getattr(pose_estimation, "labeled_video", None)
        is not None,
    )


def _validate_trajectory_group(
    trajectories: tuple[PoseTrajectory, ...], nwbfile: Any
) -> None:
    first = trajectories[0]
    names = tuple(pose.keypoint for pose in trajectories)
    if len(set(names)) != len(names):
        raise ValueError("pose trajectory keypoints must be unique")
    for pose in trajectories[1:]:
        if (pose.subject, pose.session, pose.clock_id) != (
            first.subject,
            first.session,
            first.clock_id,
        ):
            raise ValueError(
                "pose trajectories must share subject, session, and clock_id"
            )
        if not np.array_equal(pose.time_s, first.time_s):
            raise ValueError("pose trajectories must use identical timestamps")
    subject = getattr(nwbfile, "subject", None)
    nwb_subject = getattr(subject, "subject_id", None)
    if nwb_subject is not None and str(nwb_subject) != first.subject:
        raise ValueError("NWB subject_id does not match pose subject")
    nwb_session = getattr(nwbfile, "session_id", None)
    if nwb_session is not None and str(nwb_session) != first.session:
        raise ValueError("NWB session_id does not match pose session")


def _validate_destination_links(
    metadata: NdxPoseMetadata, devices: Sequence[Any]
) -> None:
    device_names = tuple(str(device.name) for device in devices)
    if metadata.device_names and devices and device_names != metadata.device_names:
        raise ValueError(
            "destination device names must match metadata device_names in order"
        )
    if not devices:
        return
    for values, name in (
        (metadata.original_videos, "original_videos"),
        (metadata.labeled_videos, "labeled_videos"),
        (metadata.dimensions, "dimensions"),
    ):
        if values and len(values) != len(devices):
            raise ValueError(f"{name} count must match destination devices")


def _processing_module(nwbfile: Any, metadata: NdxPoseMetadata) -> Any:
    existing = getattr(nwbfile, "processing", {}).get(metadata.processing_module_name)
    if existing is not None:
        return existing
    return nwbfile.create_processing_module(
        name=metadata.processing_module_name,
        description=metadata.processing_module_description,
    )


def _pose_estimations(nwbfile: Any) -> Iterator[tuple[str, Any, Any]]:
    for module_name, module in nwbfile.processing.items():
        for value in module.data_interfaces.values():
            if type(value).__name__ == "PoseEstimation":
                yield str(module_name), value, module


def _series_timestamps(series: Any, length: int) -> np.ndarray:
    timestamps = getattr(series, "timestamps", None)
    if timestamps is not None:
        if hasattr(timestamps, "timestamps") and not hasattr(timestamps, "shape"):
            time = _series_timestamps(timestamps, length)
        else:
            time = np.asarray(timestamps[:], dtype=float)
    else:
        rate = getattr(series, "rate", None)
        if rate is None or not np.isfinite(rate) or rate <= 0:
            raise ValueError(
                f"ndx-pose series {series.name!r} needs timestamps or positive rate"
            )
        start = float(getattr(series, "starting_time", 0.0) or 0.0)
        time = start + np.arange(length, dtype=float) / float(rate)
    if time.shape != (length,):
        raise ValueError(
            f"ndx-pose series {series.name!r} timestamps do not match data"
        )
    if not np.all(np.isfinite(time)) or (len(time) > 1 and np.any(np.diff(time) <= 0)):
        raise ValueError("ndx-pose timestamps must be finite and strictly increasing")
    return time


def _series_time_bounds(
    series: Any, length: int
) -> tuple[Literal["timestamps", "rate"], float, float]:
    if length < 1:
        raise ValueError(f"ndx-pose series {series.name!r} contains no samples")
    timestamps = getattr(series, "timestamps", None)
    if timestamps is not None:
        if hasattr(timestamps, "timestamps") and not hasattr(timestamps, "shape"):
            _, start, stop = _series_time_bounds(timestamps, length)
        else:
            if tuple(int(value) for value in timestamps.shape) != (length,):
                raise ValueError(
                    f"ndx-pose series {series.name!r} timestamps do not match data"
                )
            start = float(timestamps[0])
            stop = float(timestamps[-1])
        if not np.isfinite(start) or not np.isfinite(stop) or stop < start:
            raise ValueError("ndx-pose timestamp bounds must be finite and ordered")
        return "timestamps", start, stop
    rate = getattr(series, "rate", None)
    if rate is None or not np.isfinite(rate) or rate <= 0:
        raise ValueError(
            f"ndx-pose series {series.name!r} needs timestamps or positive rate"
        )
    start = float(getattr(series, "starting_time", 0.0) or 0.0)
    stop = start + (length - 1) / float(rate)
    if not np.isfinite(start):
        raise ValueError("ndx-pose starting_time must be finite")
    return "rate", start, stop


def _fiberphotometry_comments(comments: Any) -> dict[str, Any]:
    try:
        value = json.loads(str(comments))
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(value, dict) or value.get("schema") != (
        "fiberphotometry-ndx-pose-v1"
    ):
        return {}
    return value


def _common_optional(values: tuple[str | None, ...], name: str) -> str | None:
    observed = {value for value in values if value is not None}
    if len(observed) > 1:
        raise ValueError(f"trajectories have inconsistent {name}")
    return next(iter(observed), None)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text and text != "None" else None


def _text_array(value: Any) -> tuple[str, ...]:
    return () if value is None else tuple(str(item) for item in value[:])


def _dimension_array(value: Any) -> tuple[tuple[int, int], ...]:
    if value is None:
        return ()
    return tuple((int(row[0]), int(row[1])) for row in value[:])


def _edge_array(value: Any) -> tuple[tuple[int, int], ...]:
    return tuple((int(row[0]), int(row[1])) for row in value[:])


def _nwb_path(path: str | Path) -> Path:
    source = Path(path)
    if source.suffix.lower() != ".nwb":
        raise ValueError("ndx-pose source must have a .nwb suffix")
    if not source.is_file():
        raise FileNotFoundError(source)
    return source


def _require_dependencies() -> None:
    try:
        import ndx_pose  # noqa: F401  # type: ignore[import-untyped]
        import pynwb  # noqa: F401  # type: ignore[import-untyped]
    except ImportError as error:  # pragma: no cover - optional dependency
        raise ImportError(
            "ndx-pose interoperability requires the 'nwb' optional dependency"
        ) from error
