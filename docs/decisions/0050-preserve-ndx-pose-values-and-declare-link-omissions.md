# SDR-0050: Preserve ndx-pose values and declare link omissions

- **Status:** Accepted
- **Date:** 2026-07-28
- **Related decisions:** [SDR-0006](0006-require-explicit-nwb-session-metadata.md), [SDR-0032](https://github.com/aeronjl/behavio/blob/main/docs/decisions/0032-preserve-external-behavior-semantics.md)

## Context

`ndx-pose` provides a common NWB representation for pose output from DeepLabCut,
SLEAP, Keypoint-MoSeq, NeuroConv, movement, and other tools. Its series can store
2D or 3D coordinates, confidence, timestamps or rate, physical conversion and
offset, reference frames, skeletons, source software, camera devices, and formal
video links.

fipha's initial pose boundary stored only x/y and admitted only two source
literals. Reading extension data through it would silently discard z and could
confuse raw stored values with coordinates in the declared unit. Recreating formal
NWB links from a device name or video path would encode relationships not present in
the destination file.

## Decision

Extend `PoseTrajectory` with optional z, reference-frame, and confidence-definition
fields, and permit any non-empty external source identity. Three-dimensional speed
uses every present axis and invalidates a step if any endpoint coordinate is missing.

Implement native `ndx-pose` 0.3 inspection, import, and export with these rules:

- Inspect every `PoseEstimation` before selection and retain file SHA-256 plus
  container/series metadata without reading complete coordinate arrays.
- Require a file selector to resolve exactly one estimator when several exist.
- Require declared subject, session, and clock identity; never infer clock alignment
  from co-location in an NWB file.
- Convert stored coordinates to declared physical values using
  `stored × conversion + offset`.
- Preserve 2D versus 3D, confidence, confidence definition, reference frame,
  skeleton order/edges, scorer, source software/version, and path metadata.
- Represent absent confidence as `NaN`, not one or zero. Refuse finite extension
  confidence outside `[0, 1]`.
- Require identical timestamps across child series in one estimator.
- Write schema-valid `Skeletons` and `PoseEstimation` objects. Because the 0.3.0
  schema requires confidence even though the Python docstring describes it as
  optional, write an all-`NaN` confidence dataset when it is unknown.
- Accept destination `Device` and `ImageSeries` links explicitly. If imported links
  are not supplied, report them as omissions and omit dependent video/dimension
  metadata rather than synthesizing objects or incomplete relationships.

## Alternatives considered

- **Read x/y and drop z:** rejected because a syntactically successful import would
  change three-dimensional distance and speed.
- **Keep raw stored values:** rejected because NWB's unit contract requires applying
  conversion and offset for physical interpretation.
- **Treat missing confidence as one:** rejected because it would claim certainty and
  make confidence-gated validity silently permissive.
- **Choose the first PoseEstimation:** rejected because files may contain multiple
  cameras, individuals, or algorithms and dictionary order is not scientific intent.
- **Recreate cameras from names:** rejected because device descriptions, models,
  serials, and ownership by the destination file would be invented or incomplete.
- **Depend on a complete behavior framework:** rejected because direct extension
  interoperability is small, standardized, and does not require pose discovery.

## Consequences

The NWB extra now includes `ndx-pose>=0.3.0`. Pose trajectories can represent 3D
coordinates without changing existing 2D adapters. Scientists must provide identity,
clock, reference frames, and destination links rather than relying on guesses.

The round trip is exact for copied arrays and supported metadata, while object links
are exact only when their destination objects are supplied. The result types make
this distinction inspectable.

## Revisit trigger

Add bounded remote series access when a public DANDI workflow needs it. Revisit
multi-individual files only if the extension standard changes its single-subject
design or a community convention supplies explicit identity semantics. Add training
objects only if a neural-analysis use case requires them.

## Evidence added later

`PoseTrajectory` — including the optional z, reference-frame, and
confidence-definition fields added by this record — moved out of fipha with the
rest of the general behaviour surface and is now
[`behavio.pose.PoseTrajectory`](https://aeronjl.github.io/behavio/pose/).
`fipha.io.ndx_pose` stays here and imports the type lazily behind the `behavior`
extra, so the inspection, import, export, and link-omission rules decided above are
unchanged; only the package that owns the value type has changed.
