# SDR-0035: Compare event-kernel models only on common evidence

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related protocol/report: [event-kernel multiverse contract](../event-kernel-multiverse-v0.1.md)

## Context

Event-kernel conclusions can depend on which events, lag windows and continuous
behavioral covariates enter the design matrix. Comparing one selected model with
no visible alternatives encourages researcher degrees of freedom. Naively ranking
several models is also unsafe: adding a covariate with missing values can change
the fitted timestamps, and changing animal/session grouping changes the prediction
target.

The existing general multiverse contract requires named alternatives, stable
identities and failure retention. Event-kernel models additionally require a
comparison rule for group-held-out prediction and temporally masked observations.

## Decision

Represent each event-kernel alternative as a unique name, scientific rationale and
complete `EncodingModelSpec`. Require an explicit reference and freeze intent as
confirmatory, exploratory or descriptive.

Alternatives in one multiverse must share grouping, fold count, sampling tolerance
and coverage thresholds. They may vary event families, lag windows, continuous
covariates and ridge grids. Assign stable computational IDs before fitting.

Retain every fit failure. Do not replace a failed reference or automatically
select the highest-scoring model.

Record a fingerprint of the exact retained sample indices for every session. Emit
a held-out mean-R² delta only when the alternative and reference have identical
fingerprints under the common validation policy. When sample indices differ,
retain both scores but label the comparison descriptive-only. Equal sample counts
do not establish common evidence.

## Consequences

Scientists can expose plausible design choices without turning the workflow into
an outcome-driven winner search. Predictive deltas have a clear denominator, and
behavioral missingness cannot silently make two scores appear directly comparable.
Failed or inadmissible designs remain part of the declared analysis record.

The first API is verbose because it enumerates full model specifications. It does
not yet factor choices into nodes, compare coefficients across unlike bases, or
provide nested model tests. Result artifacts become larger because successful
universes retain their full fit evidence.

The event-kernel fit artifact advances to schema v4 to add exact retained-index
fingerprints.

## Alternatives considered

- **Report only the best held-out model:** rejected because it hides the declared
  decision space and encourages outcome-dependent selection.
- **Compare scores whenever row counts match:** rejected because equal counts can
  correspond to different timestamps.
- **Force every model onto the union of available rows:** rejected because it
  requires imputing predictors that are explicitly invalid.
- **Force every model onto the intersection of every candidate predictor mask:**
  deferred because unused covariates would unnecessarily discard data; a frozen
  common-mask sensitivity lane can be added explicitly later.
- **Allow grouping and fold policy to vary:** rejected because those choices alter
  the validation target rather than the model design alone.

## Revisit trigger

Revisit when basis, history, duration or progress predictors require a factorial
decision graph; when nested resampling is added; or when a validated common-mask
comparison policy is needed. Preserve names, rationales, stable IDs, exact evidence
checks and failure retention in any successor.

## Evidence added later

None.
