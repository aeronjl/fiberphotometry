# SDR-0028: Retain weak event-kernel validation and keep the API experimental

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related evidence: [public event-kernel reproduction](../tutorials/dandi-000971-event-kernel.md)

## Context

The first frozen public-data event-kernel model executed on six DANDI:000971
animals. DMS and DLS both selected the strongest declared ridge penalty. Mean
animal-held-out R² remained slightly negative, with one animal contributing most
of the poor generalization. Pooled kernels nevertheless contained visually
structured event-related coefficients.

Displaying pooled kernels without equally prominent validation would invite users
to mistake an in-sample descriptive pattern for a model that transports across
animals. Changing the penalty grid, analysis support, predictors, or cohort after
seeing these outcomes would also invalidate the frozen comparison.

## Decision

Retain the complete result as a weak predictive-validation outcome. Keep the
event-kernel API experimental. Present held-out scores beside pooled kernels and
make no claim of coefficient significance, causal reward coding, or regional
difference.

Do not amend this run. Define future penalty grids, added behavioral predictors,
analysis-support choices, and preprocessing alternatives prospectively as new
versioned designs. Add animal-level kernel uncertainty and residual diagnostics
before considering API promotion.

## Consequences

The public example demonstrates honest failure handling and reveals missing
product capabilities rather than serving as a showcase of a positive biological
result. Users can reproduce every fold and inspect the influential animal. The
package does not yet answer whether a population reward-increment kernel differs
from zero or between regions.

## Alternatives considered

- Expand the ridge grid immediately: rejected for this version because the
  selected boundary was learned from its outcomes.
- Restrict scoring to event neighborhoods: deferred as a distinct estimand and
  validation target that must be declared in advance.
- Drop the influential animal: rejected because it passed the frozen structural
  criteria and excluding it based on prediction would be outcome-dependent.
- Lead with pooled kernel shapes: rejected because their apparent structure does
  not override weak cross-animal prediction.

## Revisit trigger

Revisit experimental status after a new prospectively specified public benchmark
adds coefficient uncertainty and diagnostics and demonstrates acceptable behavior
across more than one dataset or laboratory.
