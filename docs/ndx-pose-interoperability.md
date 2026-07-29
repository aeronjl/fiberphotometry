# Native ndx-pose interoperability

`ndx-pose` is the NWB extension used by tools including DeepLabCut, SLEAP,
Keypoint-MoSeq, NeuroConv, and movement to exchange pose-estimation data. The
fipha adapter reads and writes the extension directly while keeping pose
discovery in those upstream tools.

The values it exchanges are `behavio.pose.PoseTrajectory` objects: the pose
type belongs to the peer package [Behavio](https://github.com/aeronjl/behavio),
not to fipha. This adapter therefore needs both the `nwb` and `behavior` extras.

<figure class="fp-figure">
  <img src="../assets/ndx-pose-roundtrip-v0.1.svg" alt="A native ndx-pose NWB file is first inspected, then an explicitly selected PoseEstimation container is copied into two- or three-dimensional PoseTrajectory objects. Those trajectories feed gap-safe covariates or can be written back with skeleton and provenance metadata. Unsupported device or video links remain named omissions.">
  <figcaption>Figure 1. The adapter preserves scientific arrays and declares structural omissions instead of pretending that a file path is a camera or video link.</figcaption>
</figure>

Install both extras:

```bash
uv add "fipha[nwb,behavior]"
```

`nwb` supplies PyNWB and `ndx-pose`; `behavior` supplies Behavio, whose
`PoseTrajectory` type this module imports lazily. Reaching a pose entry point
without it raises an `ImportError` naming the missing extra rather than failing at
`import fipha`.

The current contract is tested against `ndx-pose` 0.3.0 and PyNWB. It supports
explicit timestamps and regular `starting_time`/`rate`, 2D and 3D coordinates,
confidence, coordinate units, conversion/offset, reference frames, skeletons,
source software, scorer metadata, and original/labeled video path arrays.

## Inspect before loading arrays

An NWB file can contain several cameras or estimators. Inventory the file first:

```python
from fipha.io.ndx_pose import inspect_ndx_pose_nwb

inspection = inspect_ndx_pose_nwb("mouse-07-day-04.nwb")
for item in inspection.pose_estimations:
    print(
        item.metadata.processing_module_name,
        item.metadata.pose_estimation_name,
        [series.name for series in item.series],
    )
```

The bounded inspection reports each keypoint's sample count, coordinate dimension,
unit, reference frame, confidence presence, timing representation, and physical time
range. It also records the file SHA-256, source software/version, skeleton, videos,
and linked-device names without reading the full coordinate arrays.

## Read one declared estimator

```python
from fipha.io.ndx_pose import poses_from_ndx_pose_nwb

result = poses_from_ndx_pose_nwb(
    "mouse-07-day-04.nwb",
    subject="mouse-07",
    session="day-04",
    clock_id="video",
    processing_module_name="behavior",
    pose_estimation_name="TopCameraPose",
)
nose = next(pose for pose in result.trajectories if pose.keypoint == "nose")
```

Selection may be omitted only when the file contains exactly one
`PoseEstimation`. Multiple matches are refused with the available module/name pairs.
Subject, session, and clock remain explicit because a valid NWB structure does not
prove that a video clock is already synchronized to photometry.

Coordinates are returned in the declared unit after applying NWB's
`physical = stored × conversion + offset` rule. A two-column series produces `x`
and `y`; a three-column series also retains `z`. Missing confidence becomes an
all-`NaN` vector rather than an invented score. Finite extension confidence must
lie in `[0, 1]`.

Every child series in one estimator must have identical timestamps. This follows
the extension contract and prevents keypoints from appearing to share frames when
they do not. `PoseTrajectory.speed()` uses all present spatial axes and invalidates
steps touching a non-finite coordinate or insufficient confidence.

## Write native extension objects

```python
from fipha.io.ndx_pose import NdxPoseMetadata, add_poses_to_nwb

metadata = NdxPoseMetadata(
    pose_estimation_name="TopCameraPose",
    scorer="DLC_resnet50_arena",
    source_software="DeepLabCut",
    source_software_version="3.0.0",
    skeleton_name="mouse-skeleton",
    skeleton_nodes=("nose", "tail-base"),
    skeleton_edges=((0, 1),),
    original_videos=("videos/mouse-07-day-04.mp4",),
    dimensions=((1280, 720),),
    device_names=("top-camera",),
)

camera = nwbfile.create_device(name="top-camera", description="arena camera")
write = add_poses_to_nwb(
    result.trajectories,
    nwbfile,
    metadata=metadata,
    devices=(camera,),
)
```

The writer creates `Skeletons` and `PoseEstimation` interfaces in the declared
processing module. It refuses duplicate keypoints, inconsistent subject/session or
clock identity, unequal timestamps, mismatched skeleton order, invalid edges,
missing reference frames, and confidence outside `[0, 1]`.

The extension's Python constructor currently describes confidence as optional,
while its 0.3.0 NWB schema validator requires the dataset. fipha therefore
writes all-`NaN` confidence when it is unknown. This preserves missingness and keeps
the generated NWB file schema-valid.

## Understand link fidelity

Formal `Device`, source-video `ImageSeries`, and labeled-video `ImageSeries` objects
are links to objects owned by the destination `NWBFile`. An imported link cannot be
recreated safely from its name alone. `NdxPoseImportResult.issues` reports such
links, and `NdxPoseWriteResult.omitted_links` records which were not supplied during
export. Video paths and dimensions are omitted when their linked camera devices are
omitted, avoiding a structurally misleading partial container.

Provide destination `devices`, `source_video`, and `labeled_video` objects when
those relationships are known. fipha will never invent camera hardware or
claim that a path string is a formal NWB link.

## Continue into photometry analysis

The restored trajectories are ordinary `behavio.pose.PoseTrajectory` objects,
so they are the same type Behavio's DeepLabCut, SLEAP, and movement adapters
produce. Everything Behavio can do with a trajectory — speed, confidence gating,
clock synchronization, resampling onto the photometry clock — applies unchanged:

```python
nose_speed = nose.speed(minimum_confidence=0.9)
nose_speed = synchronization.synchronize_covariate(nose_speed)
aligned_speed = nose_speed.aligned_to(
    photometry_time,
    target_clock_id="photometry",
    max_gap_s=2 / 30,
)
```

`synchronization` here is a `behavio.sync.ClockSynchronization` fitted from
explicit matched pulses; `synchronize_covariate` and `aligned_to` are Behavio
methods, documented under
[clock synchronization](https://aeronjl.github.io/behavio/clock-synchronization/).
fipha never infers that a camera clock and a photometry clock agree.

See the complete executable
[`examples/ndx_pose_roundtrip.py`](https://github.com/aeronjl/fipha/blob/main/examples/ndx_pose_roundtrip.py),
Behavio's
[behavior-tool composition tutorial](https://aeronjl.github.io/behavio/tutorials/behavior-tool-interoperability/),
and the upstream [`ndx-pose` format documentation](https://pypi.org/project/ndx-pose/).

## Current limits

- One NWB file is expected to describe one experimental subject, matching the
  upstream extension design.
- Training frames and `PoseTraining` are outside this neural-analysis boundary.
- Import copies complete selected series into memory; bounded remote DANDI reading
  is not yet exposed here.
- Multi-animal identity switches remain an upstream tracking/QC responsibility.
- Coordinate calibration is retained, not inferred from pixels or camera metadata.
