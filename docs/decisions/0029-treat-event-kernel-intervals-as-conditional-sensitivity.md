# SDR-0029: Treat grouped event-kernel intervals as conditional sensitivity

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related evidence: [public event-kernel reproduction](../tutorials/dandi-000971-event-kernel.md)

## Context

Ordinary sample-level regression standard errors are inappropriate for densely
sampled photometry because observations are temporally dependent and animals are
the independent population units. The experimental model also selects a ridge
penalty through grouped cross-validation. Uncertainty computed after that selection
may omit selection variability, while pointwise intervals across many lags do not
control simultaneous waveform error.

The first public diagnostic run found substantial held-out residual autocorrelation
and selected the largest declared penalty. Delete-one-animal refits produced broad,
structured pointwise intervals, some of which excluded zero.

## Decision

Report delete-one-group jackknife intervals as sensitivity summaries for the pooled
fixed-penalty estimator. Store the full coefficient, bias-corrected estimate,
standard error, interval, omitted identities, confidence level, and conditioning
penalty. Label the bands pointwise and non-simultaneous.

Do not convert zero-excluding lags into significance claims. Keep held-out residual
diagnostics adjacent to kernel bands. Restart autocorrelation and Durbin–Watson
calculations at each session boundary and use them descriptively, without p-values
or automatic pass/fail thresholds.

## Consequences

Scientists can see animal influence and temporal misspecification without false
sample-level precision. The result remains useful for hypothesis generation and
workflow comparison, but it does not yet provide calibrated population waveform
inference. API schema version 2 makes the added uncertainty and diagnostic ledger
explicit.

## Alternatives considered

- Naive regression standard errors: rejected because they treat autocorrelated
  samples as independent and ignore the animal boundary.
- Trial bootstrap: rejected because trials are not independent population units.
- Present jackknife intervals as conventional confidence intervals: rejected
  because penalty selection and simultaneous-lag multiplicity remain unresolved.
- Suppress all uncertainty until a hierarchical model exists: rejected because
  transparent group-influence sensitivity is already materially useful when
  correctly labelled.

## Revisit trigger

Revisit after repeated-sampling coverage calibration across realistic animal
counts and heterogeneity, selective or nested model-selection treatment, and a
validated simultaneous-band procedure.
