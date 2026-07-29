# Behavioral ecosystem interoperability

fipha does not need to rediscover behavior to relate behavior to neural
signals. It needs a loss-aware boundary to tools that already estimate pose,
discover behavioral states, or record an ethogram.

!!! info "Experimental v0.1 boundary"
    Typed in-memory and file adapters are implemented. Checksum-pinned official
    SLEAP and BORIS fixtures pass; DeepLabCut and Keypoint-MoSeq currently have
    documented-schema fixtures only. See the
    [validation matrix](https://github.com/aeronjl/fipha/blob/main/research/interoperability-validation-v0.1.md).

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/behavior-ecosystem-v0.1.svg" alt="DeepLabCut and SLEAP pose trajectories, Keypoint-MoSeq state bouts, and BORIS annotations enter typed pose, covariate, point-event, and interval boundaries. fipha relates them to neural signals and exports trial summaries to Unspool for longitudinal modelling.">
  <figcaption><strong>Each package keeps the job it is good at.</strong> Pose estimators retain keypoints and confidence, behavior tools retain point-versus-state semantics, fipha owns neural alignment and inference, and Unspool owns longitudinal clocks and models.</figcaption>
</figure>

## What each package owns

| Package or tool | Owns | fipha consumes |
|---|---|---|
| DeepLabCut | markerless pose inference, scorer and individual identity | keypoint coordinates and likelihood by video frame |
| SLEAP | single- and multi-animal pose inference and tracking | node coordinates, track identity and point scores |
| movement | pose input/output across tools, kinematics, regions of interest | its `poses` dataset, via `pose_from_movement()` |
| Keypoint-MoSeq | unsupervised behavioral state discovery | frame-level syllable labels, run-length encoded as bouts |
| BORIS | human ethogram annotation | distinct point events and state intervals |
| fipha | optical signal identity, QC, preprocessing, neural alignment and inference | the typed boundaries below |
| Unspool | longitudinal behavioral clocks, models and prospective validation | trial-level neural summaries with explicit subject/session/trial coordinates |

This division follows the scientific capabilities of the source tools. DeepLabCut
exports MultiIndex pose columns containing scorer, body part, coordinates and
likelihood. SLEAP Analysis HDF5 retains tracks, nodes and confidence-like scores.
Keypoint-MoSeq returns a syllable label per time point. BORIS explicitly
distinguishes point from state events. Flattening those outputs to an anonymous
`time,value` CSV would discard information that affects analysis.

## Four exchange shapes

The public Python boundary deliberately uses a few small types rather than one
universal table.

| Shape | Required meaning | Current type | Typical source |
|---|---|---|---|
| Pose trajectory | one keypoint, one tracked individual, coordinates, confidence and time | `PoseTrajectory` | DeepLabCut, SLEAP |
| Continuous covariate | one named value and validity mask per source timestamp | `BehaviorCovariate` | confidence-gated speed, pupil area, state probability |
| Point events | named instantaneous occurrences | `BehaviorAnnotations.point_events` | BORIS POINT, cue timestamps |
| Intervals | named half-closed behavioral bouts with physical start and stop | `BehaviorInterval` | BORIS STATE, MoSeq syllable run |

`BehaviorAnnotations.event_times(edge="onset")` provides an explicit projection
from intervals to event-kernel predictors. The original intervals are retained, so
an onset analysis does not silently become the only representation of the data.
`normalized_progress()` maps samples inside a declared bout to zero-to-one progress
while the source interval retains its physical duration.

For inference, `interval_encoding_inputs()` returns aligned edge events,
`duration_s` values, and physical bounds. `ProgressKernelSpec` then evaluates
normalized progress only inside each bout while retaining outside-bout samples as
zero-valued design rows. This avoids turning absence of a behavior into missing
data.

## Clock, identity, confidence and units

Interoperability is valid only when these fields remain explicit:

- `subject` and `session` identify the biological and recording units;
- `individual` distinguishes tracks in multi-animal pose output;
- `clock_id` names the time coordinate used by every timestamp;
- `coordinate_unit` and covariate `unit` prevent pixels from masquerading as
  centimetres;
- confidence-like scores or likelihood determine a visible validity mask rather
  than an invisible fill operation;
- `source_version` and `source_artifact` can retain the producing software version
  and path, URI or digest-bearing artifact identity.

`fit_clock_synchronization()` consumes explicit pulse pairs observed on both
clocks, fits an affine offset-and-drift mapping, and refuses residual, drift,
pulse-count or span failures against prospective thresholds. Its artifact retains
every pulse residual and a stable evidence ID. Applying the mapping to pose,
covariates or annotations changes their clock ID and appends that evidence ID to
their lineage. See the [clock synchronization contract](clock-synchronization.md).

Only after synchronization does `BehaviorCovariate.aligned_to()` interpolate onto
the photometry grid. It does not extrapolate or cross invalid samples or source
gaps larger than the declared maximum, and it retains the aligned validity mask;
`align_to()` is the numeric-array convenience form. Giving two unsynchronised
clocks the same name is not synchronisation.

## Native adapters

### DeepLabCut

`pose_from_deeplabcut()` reads a pandas-like result without taking a hard
dependency on DeepLabCut. `pose_from_deeplabcut_file()` reads prediction CSV or
pandas HDF5 with the optional `behavior` dependencies. Both require a scorer or
individual when the MultiIndex would otherwise select more than one
x/y/likelihood triplet.

```python
from importlib.metadata import version

from fipha.interoperability import pose_from_deeplabcut_file

pose = pose_from_deeplabcut_file(
    "sessionDLC_resnet50.h5",
    subject="mouse-07",
    session="day-04",
    keypoint="nose",
    scorer="DLC_resnet50_project",
    fps=30.0,
    clock_id="camera-0",
    source_version=version("deeplabcut"),
)
speed = pose.speed(minimum_confidence=0.9)
```

The likelihood threshold is an analysis choice and must be declared. The adapter
does not adopt a universal cutoff or interpolate low-confidence coordinates.

### SLEAP

`pose_from_sleap()` consumes dense arrays. `pose_from_sleap_analysis_h5()` reads
the file and uses its dimension attributes when present. Legacy files have no
dimension attributes, so the caller must declare them; Python-native and
MATLAB-compatible presets use different axis orders.

```python
from fipha.interoperability import pose_from_sleap_analysis_h5

pose = pose_from_sleap_analysis_h5(
    "predictions.analysis.h5",
    node="nose",
    dims=("track", "xy", "node", "frame"),
    subject="mouse-07",
    session="day-04",
    track=0,
    fps=30.0,
)
```

SLEAP point scores are confidence-like values, not guaranteed probabilities. An
official legacy fixture contains scores above one, so only non-negativity is
assumed; thresholds must be calibrated to the producing SLEAP version and model.

SLEAP also exports NWB through `ndx-pose`. fipha now provides native
inspection, explicit estimator selection, 2D/3D import, schema-valid export, and a
tested file round trip while reporting device/video links that cannot be recreated
without destination objects. See the
[native ndx-pose contract](ndx-pose-interoperability.md).

### movement

[`movement`](https://github.com/neuroinformatics-unit/movement) is the maintained
community package for pose input and output, built by the Neuroinformatics Unit on
the same xarray substrate this package uses. It is BSD-3-Clause and actively
released. fipha consumes its output rather than competing with it:

```python
from movement.io import load_poses

from fipha.interoperability import pose_from_movement

dataset = load_poses.from_dlc_file("sessionDLC_resnet50.h5", fps=30.0)
pose = pose_from_movement(
    dataset,
    subject="mouse-07",
    session="day-04",
    keypoint="nose",
    clock_id="camera-0",
)
speed = pose.speed(minimum_confidence=0.9)
```

This gives access to `movement`'s readers that fipha does not implement,
including Anipose, Lightning Pose and its NWB path. `pose_from_movement()`
duck-types on the xarray interface and never imports `movement`, so it adds no
dependency and no Python version floor.

`movement` is deliberately **not** a dependency. Measured against version 0.17.0 on
Python 3.12.13:

- it requires Python `>=3.12.0`, while this package supports `>=3.11`;
- resolving it alone pulls **119 packages and 720 MB**, including Qt, OpenCV,
  `skia-python`, `imageio-ffmpeg` and `numba`, and pins `netCDF4<1.7.3`;
- `tables` is one of its own core dependencies, so depending on it would not remove
  PyTables from the `behavior` extra;
- its SLEAP reader applies a hardcoded axis permutation and ignores the `dims`
  attribute, so it cannot read the current sleap-io analysis HDF5 that
  `pose_from_sleap_analysis_h5()` reads.

Three things in this boundary have no counterpart in `movement`, and stay here:

- **Ethogram and annotation types.** `movement` covers poses and bounding boxes;
  point events and behavioral intervals are fipha types.
- **Foreign-clock alignment.** `movement` interpolates gaps along a pose's own time
  axis. It has no clock identity, no synchronisation fit and no lineage, so
  `fit_clock_synchronization()` and `BehaviorCovariate.aligned_to()` remain here.
- **Value/mask separation.** `movement` gates confidence by overwriting coordinates
  with `NaN`, and `compute_speed` uses a central difference. On a gated sample that
  combination reports a speed *at* the gated frame while blanking its two
  well-estimated neighbours. `PoseTrajectory.speed()` instead invalidates a step
  when either endpoint fails the threshold and keeps the value beside its mask, as
  [SDR-0033](decisions/0033-retain-validity-masks-without-compressing-time.md)
  requires. Pass the dataset to `pose_from_movement()` *before* running
  `movement.filtering.filter_by_confidence`.

`movement` stores coordinates as `float32`. Values widen to `float64` on import but
carry `float32` precision, so a file read through both paths will not agree
bit-for-bit. See
[SDR-0059](decisions/0059-consume-movement-datasets-without-depending-on-movement.md).

### Keypoint-MoSeq

`annotations_from_moseq()` run-length encodes an in-memory `syllable` sequence.
`annotations_from_moseq_results_h5()` reads the documented recording hierarchy
directly. Each interval retains the full duration of one uninterrupted state.

```python
from fipha.interoperability import annotations_from_moseq_results_h5

states = annotations_from_moseq_results_h5(
    "moseq-project/model-a/results.h5",
    recording="recording-01",
    subject="mouse-07",
    session="day-04",
    fps=30.0,
    labels={0: "pause", 1: "rear"},
)
rear_onsets = states.event_times()["rear"]
```

Syllable numbers are model-specific, may be reindexed, and are not universal
behavior names. A semantic label mapping is therefore optional and provenance of
the fitted MoSeq model remains essential.

### BORIS

`annotations_from_boris()` consumes already-loaded aggregated columns.
`annotations_from_boris_aggregated_file()` reads BORIS aggregated CSV/TSV directly.
`annotations_from_boris_tabular_file()` handles the other common shape: a metadata
preamble followed by START/STOP or point-event rows.

```python
annotations = annotations_from_boris_tabular_file(
    "mouse-07-day-04-boris.csv",
    subject="mouse-07",
    session="day-04",
    source_subject="mouse-07",
)

aggregated = annotations_from_boris_aggregated_file(
    "mouse-07-day-04-aggregated.tsv",
    subject="mouse-07",
    session="day-04",
    source_subject="mouse-07",
)
```

In tabular files, blank or POINT status rows become point events and START/STOP
rows are paired as intervals. In aggregated tables, POINT and STATE types are
handled directly. Invalid, unmatched or unknown rows are rejected.

## From behavior to neural and longitudinal questions

The immediate fipha composition is:

1. transform pose into a declared covariate, such as confidence-gated speed;
2. synchronize it to the photometry clock from explicit matched pulses and retain
   the synchronization artifact;
3. align it without crossing invalid spans and retain the resulting mask;
4. use point events, explicit interval edges, covariate values and masks in an
   `EncodingSession`; the model reports complete-case coverage without compressing
   time; and
5. summarize declared neural estimands at the trial or session level and pass them
   through `prepare_unspool_study()`.

See the [worked interoperability tutorial](tutorials/behavior-tool-interoperability.md)
and the [auditable interval-policy contract](interval-policy.md). The separate
[Unspool contract](unspool-interoperability.md) begins only after declared
neural summaries and across-session comparability evidence exist.

## Gaps exposed by the examples

| Priority | Missing ecosystem capability | Likely home |
|---|---|---|
| P0 | extend the now-complete one-version fixture matrix across a second released version and one real camera-to-photometry synchronization record | adapter validation in fipha |
| P1 | bounded remote `ndx-pose` series access and a real camera-to-photometry synchronization fixture | fipha I/O and validation |
| P1 | broaden interval-policy fixtures to real multi-label annotations and a second source-tool version | fipha interoperability validation |
| P1 | multi-animal identity-switch diagnostics at the neural-alignment boundary | source-tool QC plus fipha preflight |
| P1 | versioned behavioral interchange artifact with hashes and confidence semantics | shared package after a second consumer adopts it |
| P2 | adapters for SimBA, B-SOiD and user-supplied state probabilities | thin fipha adapters |

A gap should become a separate library only when it has an independent object
model, at least two consuming packages, and useful validation outside photometry.
On that test, the new clock transform should move to a shared ecosystem package if
Unspool becomes a second direct consumer. A provenance-rich behavioral interchange
artifact is another plausible shared library. Photometry-specific kernels and
optical QC remain here; longitudinal model families remain in Unspool.

## Sources

- [DeepLabCut output contract](https://github.com/DeepLabCut/DeepLabCut/blob/main/docs/standardDeepLabCut_UserGuide.md) and [Mathis et al. (2018)](https://doi.org/10.1038/s41593-018-0209-y)
- [SLEAP export documentation](https://docs.sleap.ai/latest/tutorial/exporting-the-results/) and [Pereira et al. (2022)](https://doi.org/10.1038/s41592-022-01426-1)
- [Keypoint-MoSeq I/O contract](https://keypoint-moseq.readthedocs.io/en/latest/io.html) and [Weinreb et al. (2024)](https://doi.org/10.1038/s41592-024-02318-2)
- [BORIS aggregated-event export](https://www.boris.unito.it/user_guide/export_events/) and [Friard & Gamba (2016)](https://doi.org/10.1111/2041-210X.12584)
