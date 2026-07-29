# SDR-0033: Retain validity masks without compressing time

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related protocol/report: [behavioral event-kernel method contract](../event-kernel-encoding.md)

## Context

Behavior tools and optical QC can identify samples that should not enter a model:
low-confidence pose, occlusion, acquisition gaps, stimulation artifacts or invalid
response values. The first event-kernel implementation filtered non-finite rows
but could not receive an explicit validity mask or report what it removed.

Simply deleting invalid rows also creates a subtler error. Residual diagnostics
can treat the samples on opposite sides of a missing span as consecutive and thus
invent lag-1 relationships across unobserved time. Filling those spans would make
an even stronger, usually unjustified claim about the missing values.

The evidence available now supports preserving upstream validity decisions and
making the fitted denominator visible. It does not establish a generally valid
imputation model or a missing-at-random assumption for behavioral covariates.

## Decision

Event-kernel sessions accept separate boolean validity masks for the response and
each continuous covariate. For predictors named in a model specification, fitting
uses the intersection of those masks and finite-value checks: an explicit
complete-case policy.

The original regular time grid is retained while predictors are constructed.
Invalid rows are excluded only after event lags have been placed, so time is never
compressed. Residual lag diagnostics restart at every excluded span as well as at
session boundaries.

Each session must satisfy declared minimum retained-observation and retained-
fraction thresholds. Defaults are three observations and 50%, recorded as
guardrails rather than scientific adequacy claims. Fitting fails when masking
removes all support for any requested event lag.

The result records global and per-session total, retained and excluded counts,
invalid response counts, invalid counts for every selected covariate, retained
fractions, and contiguous retained-run counts. Reason counts may overlap; the
excluded count is their union.

## Consequences

Behavioral confidence and optical-validity evidence can flow into inference
without NaN conventions or silent filling. Scientists can audit which animals,
sessions and predictors determine the effective denominator. Temporal diagnostics
no longer bridge gaps, and unsupported coefficients fail instead of appearing as
zero-valued estimates.

Complete-case analysis may change the target population of time points when
missingness is behavior- or signal-dependent. It can discard substantial data and
does not correct informative missingness. A single row set for all selected
predictors favors directly comparable coefficients over maximum predictor-specific
sample size.

The event-kernel artifact schema changes to version 3 to include the validity
report.

## Alternatives considered

- **Continue implicit non-finite filtering:** rejected because it hides upstream
  mask semantics and effective denominators.
- **Interpolate or globally fill invalid spans:** rejected because the package has
  no generally defensible model for occlusion or neural missingness, and filling
  can bridge long gaps.
- **Delete timestamps before building event lags:** rejected because it compresses
  time and moves samples on opposite sides of a gap next to one another.
- **Use a different row set for each coefficient:** rejected for this joint model
  because coefficients would no longer share one fitted likelihood or denominator.
- **Automatically drop unsupported lag columns:** rejected because it silently
  changes a declared event window and produces incomparable model shapes.

## Revisit trigger

Reconsider when a missingness-mechanism model or imputation method has a declared
estimand, validation data representative of photometry and behavioral occlusion,
and group-aware uncertainty calibration. Also revisit the default coverage floors
after empirical failure rates are available across several public datasets.

## Evidence added later

None.
