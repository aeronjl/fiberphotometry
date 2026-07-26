# SDR-0009: Separate structural incompatibility from scientific failure

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

The frozen IBL v0.3 protocol labelled AsLS universes executable even though the
raw timestamp jitter violates the implementation's regular-sampling requirement.
Timestamp structure was available before fluorescence outcomes and should have
been checked at readiness. Calling the later error a failed scientific analysis
would conflate an undeclared preprocessing requirement with evidence about the
method or biological result.

## Decision

Pipeline and multiverse compatibility may be assessed from dimensions, timestamps,
finite/include masks, declared variables, and operation parameters without fitting
or summarizing outcome values. Reports explicitly record
`outcome_values_accessed = false`.

Structural incompatibility is a separate state from blocked QC, runtime failure,
and a successful analysis. A protocol must not label a universe executable until
this preflight passes on the intended acquisition structure.

## Consequences

Changing fluorescence magnitudes cannot alter compatibility. Methods requiring
regular sampling, reference channels, variables, or valid filter rates fail before
outcome access with actionable codes. A structurally incompatible method can be
retained in a multiverse without being misreported as negative scientific evidence.

## Revisit trigger

Revisit when operations acquire additional structural requirements or when a
controlled outcome-masking interface can validate more complex method setup safely.
