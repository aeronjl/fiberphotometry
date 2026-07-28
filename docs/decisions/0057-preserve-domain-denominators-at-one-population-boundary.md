# SDR-0057: Preserve domain denominators at one population boundary

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

Transient, spectral, and multi-signal workflows already formed animal-level
summaries, but each exposed a separate inferential API. That made it harder to
apply the same support, influence, uncertainty, and group-by-condition semantics
across the package. Directly replacing the domain rules with a generic average
would be worse: a transient rate depends on count and exposure, band power depends
on frequency integration and complete windows, and association depends on valid
pairs or cross-spectral windows.

## Decision

Expose a typed materialization product for each domain. Every product retains its
domain-specific animal estimates and maps them to the common
`PopulationUnitEstimate` boundary. It then provides the same `contrast` and
`interaction` operations.

Lower-level counts are provenance and support, not population weights. Sessions
are aggregated within animal before population inference. A valid zero-event rate
cell is retained with an observation count of zero and positive source-session
support.

The initial common contract remains additive. Existing specialist ratio and
randomization APIs remain available rather than being silently reinterpreted.

## Consequences

Scientists can inspect one consistent animal-level ledger and use the same paired,
independent, or two-group × two-condition machinery across core workflows. New
workflow adapters must document how their cells and denominators are formed before
they can enter the common population layer.

The materializers duplicate neither detection nor signal analysis. They consume
the typed results those workflows already produce.

## Alternatives considered

- **Keep separate inferential APIs only.** Rejected because support, influence,
  interaction, and missing-cell behavior would continue to drift.
- **Pool all lower-level observations in one generic model.** Rejected as a default
  because events, windows, pairs, and sessions are not interchangeable biological
  replicates.
- **Replace specialist APIs immediately.** Rejected because ratio estimands and
  randomization tests are not equivalent to the common additive contract.

## Revisit trigger

Revisit when a generalized hierarchical model has explicit event/count/exposure
likelihoods, estimands, missingness behavior, and calibrated uncertainty across the
designs it claims to support.
