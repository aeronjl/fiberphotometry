# SDR-0055: Materialize animal estimates before population inference

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

Photometry analyses begin with events, windows, detected transients, or spectral
segments, but most biological claims generalize across animals. A method can avoid
literal trial-level testing and still be difficult to audit if it returns only a
population mean. Scientists need to see how sessions became animal estimates,
which animals supported each outcome point, and whether one animal controls the
conclusion.

The package already contained several domain-specific animal-level inference
functions. Their result contracts were similar but not identical, making it harder
to carry the same guarantees across new analysis families.

## Decision

Introduce a reusable population boundary with two explicit stages:

1. Each analysis materializes one estimate per independent unit and contrast
   level. The estimate retains its source sessions, observation count, and
   pointwise support.
2. A population contrast operates only on those unit estimates. It supports a
   paired design over complete units or an independent design over disjoint groups.

Population results retain the complete unit ledger, included and excluded units,
pointwise group support, standardized effect, bootstrap intervals, simultaneous
whole-outcome bands, and one-unit-out influence curves. Scalar outcomes use a
one-element vector and therefore share the same contract as time courses.

Peri-event inference is the reference integration. It first stores
session-condition curves, then forms equal-session animal-condition curves, and
finally calls the reusable population contrast. Event duplication can change the
documented event count but cannot create additional population precision.

The design is never inferred from apparent balance. Users declare `paired` or
`independent`; independent groups must have disjoint animal identifiers.

## Consequences

Results are larger because they include the evidence chain rather than only the
final mean. This is intentional and permits reports, downstream tools, and reviewers
to inspect the actual replication boundary.

The initial implementation handles two-level contrasts. It does not yet support
factorial designs, continuous covariates, crossed effects, generalized outcomes,
or functional mixed models. Hedges standardized effects are descriptive
point-by-point companions to effects in measurement units; they do not replace the
primary estimand.

## Alternatives considered

- **Keep separate inference code in every method family.** Rejected because
  replication, support, and influence semantics would continue to drift.
- **Pass raw trials into a general mixed-model formula.** Deferred because formulas
  alone do not guarantee the intended estimand, exchangeability, or transparent
  session-to-animal aggregation.
- **Store only animal contrast curves.** Rejected because the session-level
  construction and unequal event yield would remain hidden.

## Revisit trigger

Extend the contract when a design has an explicit estimand and calibration suite
for group-by-condition interactions, continuous animal predictors, or hierarchical
functional models. Domain-specific exposure and denominator rules must remain in
the stage that constructs animal estimates.
