# Behavior and longitudinal integration

fipha consumes behavior; it does not estimate pose, segment behavior, or fit
longitudinal learning models. Most of that surface now lives in the peer package
[Behavio](https://github.com/aeronjl/behavio), which owns the observed-behaviour
boundary (pose, ethograms, intervals, clock synchronization) and the longitudinal
model families. This category makes the split explicit and preserves enough
provenance for the two packages to remain reproducible together.

## What fipha still owns

| Need | Workflow | Boundary |
|---|---|---|
| Round-trip standardized pose in NWB | [Native ndx-pose interoperability](../ndx-pose-interoperability.md) | unsupported video/device links remain named omissions; the trajectory type itself is Behavio's |
| Check whether session summaries are comparable | [Across-session comparability](../session-comparability.md) | incompatible sessions are reported, not pooled |
| Export validated trial-level neural summaries with explicit chronology | [Longitudinal behavior with Behavio](../behavio-interoperability.md) | fipha builds the handoff; Behavio fits the trajectory |
| Model bout onset, duration, and within-bout progress against fluorescence | [Behavioral event-kernel encoding](../event-kernel-encoding.md) | intervals must already be on the photometry clock |

## What Behavio owns

Install it with `pip install 'fipha[behavior]'`, or use it directly.

| Need | Where it lives now |
|---|---|
| Import pose, states, events, and intervals from DeepLabCut, SLEAP, Keypoint-MoSeq, BORIS, or movement | [Behavio pose boundary](https://aeronjl.github.io/behavio/pose/) and [ethograms](https://aeronjl.github.io/behavio/ethograms/) |
| Put independent device clocks on one time coordinate | [Behavio clock synchronization](https://aeronjl.github.io/behavio/clock-synchronization/) |
| Filter, merge, split, or resolve overlapping bouts with an auditable ledger | [Behavio interval and bout policies](https://aeronjl.github.io/behavio/interval-policy/) |
| Model learning or change across sessions | [Behavio longitudinal model families](https://github.com/aeronjl/behavio) |

The worked
[behavior-tool interoperability tutorial](https://aeronjl.github.io/behavio/tutorials/behavior-tool-interoperability/)
in Behavio's documentation shows the complete handoff, from a specialist tool
through synchronization and interval policy into fipha's encoding models.

## Coverage gaps this category exposes

- validated direct adapters for additional annotation and pose ecosystems
  (Behavio);
- uncertainty propagation from pose/state estimation into photometry models
  (shared);
- richer standardized NWB links among video, pose, behavior, and photometry
  (fipha);
- drift-aware synchronization beyond affine pulse matching (Behavio); and
- stable cross-package schemas for longitudinal model outputs (shared).
