# SDR-0027: Hold out complete groups for event-kernel models

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related evidence: [event-kernel method contract](../event-kernel-encoding.md)

## Context

Samples within a photometry session and sessions within an animal are dependent.
Randomly splitting time points can put near-identical temporal context and the same
animal on both sides of validation, producing an optimistic score that does not
answer whether the model generalizes to a new biological unit.

## Decision

Select ridge penalties with cross-validation that holds out complete animals by
default. Permit complete-session holdout when the intended prediction target is a
new session, while preserving compound animal/session identity. Construct FIR
predictors separately inside every recording. Learn continuous-predictor scaling
from the training fold only. Retain every held-out identity and score in the result.

Treat held-out \(R^2\) as predictive validation, not coefficient uncertainty or a
causal estimand.

## Consequences

Validation is harder and may expose poor cross-animal generalization, but its unit
matches the usual population claim. Unequal group sizes are balanced greedily by
observation count, while the reported fold score gives each nonconstant held-out
group equal weight. Datasets with fewer than two eligible groups are rejected.

## Alternatives considered

- Random time-point folds: rejected because temporal and animal leakage is severe.
- Random trial folds: rejected as a default because trials from one animal remain
  dependent; a future blocked within-session mode may support a narrower target.
- One global fit without predictive validation: rejected because fit quality alone
  cannot demonstrate transport across animals or sessions.

## Revisit trigger

Revisit when nested hyperparameter selection, blocked time-series validation, or a
hierarchical encoding model is added, or when public-data benchmarks show that the
current group-balanced score has undesirable selection behavior.
