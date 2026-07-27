# SDR-0017: Couple preprocessing outputs and separate incompatible units

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Multiverse scientific contract v0.1](../multiverse-contract-v0.1.md)

## Context

Signal-only preprocessing can produce divisive ΔF/F or subtractive acquired-
fluorescence outcomes. Normalization therefore changes both the ordered processing
operations and the variable summarized around events. Independent decision nodes
would create invalid combinations, while pooling their magnitudes would imply that
incompatible units share a scale.

## Decision

Represent preprocessing operations and their event-summary output as one atomic
typed multiverse choice. Apply response-window choices first and the coupled output
choice last, so another node cannot restore an incompatible variable.

Partition scientist-facing robustness reports by output units. Do not display a
pooled median or range across lanes. Reject a project-wide practical-effect
threshold when preprocessing alternatives span units. Require signal-only project
recipes to remain within a signal-only primary analysis and materialize operations
in the order resampling, filtering, baseline estimation.

## Consequences

Divisive and subtractive workflows can inhabit one transparent robustness analysis
without being numerically conflated. The low-level result retains every universe,
but interpretation of magnitude must occur within report lanes. A future schema is
needed for per-lane practical-effect thresholds and summaries.

## Alternatives considered

- Cross preprocessing and output-variable nodes: rejected because most generated
  combinations would be structurally invalid rather than scientific alternatives.
- Convert subtractive values to ΔF/F after execution: rejected because that changes
  the declared transformation and can conceal baseline assumptions.
- Forbid mixed normalization: rejected because robustness to normalization is a
  substantive methodological question.

## Revisit trigger

Add typed, per-unit-lane effect thresholds and machine-readable lane summaries
before presenting practical-effect stability for mixed-normalization multiverses.

## Evidence added later

On 2026-07-27, the revisit trigger was met with typed per-lane thresholds and the
normative `multiverse_lane_summary` artifact. Denominator and serialization policy
are governed by [SDR-0018](0018-summarize-robustness-within-unit-lanes.md).
