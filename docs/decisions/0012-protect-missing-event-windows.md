# SDR-0012: Protect missing event windows instead of silently reconstructing them

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

Published photometry workflows variously interpolate isolated dropped frames,
replace selected artifact regions, remove and concatenate segments, or downsample
without reporting consequences for event summaries. The frozen v0.1.1 benchmark
found that reconstruction safety depends on transient shape and gap location: even
one missing event-adjacent sample and two-sample gaps caused retained failures.

## Decision

Linear median-rate regularization is an experimental, declared policy for small
timestamp jitter. Missing fluorescence samples are different: contiguous gaps are
never silently bridged, and isolated samples inside inferential windows default to
protected missingness. Linear isolated-sample reconstruction may appear only as an
explicit sensitivity universe.

Event summaries require complete finite baseline and response windows. They report
finite coverage, reconstructed coverage, and an event disposition. Peri-event
alignment interpolates only within finite contiguous runs. Condition-dependent
exclusion or reconstruction produces a warning.

## Consequences

Some datasets will retain fewer analyzable events, but no partial event is treated
as fully observed. Display interpolation must be separately tagged in any future
implementation. The original values and masks remain available for alternative
prospective policies.

## Revisit trigger

Revisit after validation against real held-out dropouts, sensor-specific transient
libraries, or a reconstruction model that supplies calibrated uncertainty rather
than a single filled trace.
