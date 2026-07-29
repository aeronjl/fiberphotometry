# Behavior and longitudinal integration

FiberPhotometry consumes behavior; it does not duplicate pose estimation,
behavioral segmentation, or longitudinal learning models. This category makes
those boundaries explicit and preserves enough provenance for the ecosystem to
remain reproducible.

## Choose the workflow

| Need | Workflow | Boundary |
|---|---|---|
| Import pose, states, events, and intervals from specialist tools | [Behavioral ecosystem interoperability](../ecosystem-interoperability.md) | DeepLabCut, SLEAP, Keypoint-MoSeq, and BORIS remain upstream |
| Round-trip standardized pose in NWB | [Native ndx-pose interoperability](../ndx-pose-interoperability.md) | unsupported video/device links remain named omissions |
| Put independent device clocks on one time coordinate | [Clock synchronization](../clock-synchronization.md) | explicit matched pulses only; no implicit interpolation |
| Check whether session summaries are comparable | [Across-session comparability](../session-comparability.md) | incompatible sessions are reported, not pooled |
| Model learning or change across sessions | [Longitudinal behavior with Unspool](../unspool-interoperability.md) | Unspool owns longitudinal behavior models |

## Coverage gaps this category exposes

- validated direct adapters for additional annotation and pose ecosystems;
- uncertainty propagation from pose/state estimation into photometry models;
- richer standardized NWB links among video, pose, behavior, and photometry;
- drift-aware synchronization beyond affine pulse matching; and
- stable cross-package schemas for longitudinal model outputs.

The worked [behavior-tool interoperability tutorial](../tutorials/behavior-tool-interoperability.md)
shows the handoff. Interval transformation remains auditable through the
[bout-policy workflow](../interval-policy.md).
