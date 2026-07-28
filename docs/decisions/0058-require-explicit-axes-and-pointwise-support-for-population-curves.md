# SDR-0058: Require explicit axes and pointwise support for population curves

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

PSD, autocorrelation, lagged-association, and coherence workflows produce complete
frequency or lag curves. Reducing them to a band or single lag is useful when that
summary is prespecified, but it prevents scientists from asking whole-curve
questions and hides support that changes across lags or missing data.

Combining session curves is unsafe when their axes differ. Silent interpolation or
truncation changes the estimand, while treating pairs, windows, or sessions as
population replicates understates uncertainty.

## Decision

Represent every session curve with explicit subject, session, level, metric, axis,
units, values, pointwise lower-level support, and source method. Materialize animal
curves only when all selected session axes and unit contracts are identical.

Aggregate finite session values pointwise within each animal-level cell. Retain both
session support and summed lower-level observation support at each axis point, but
let animals—not pairs, windows, or sessions—determine population uncertainty.

Use the existing vector population contrast and interaction contracts to provide
pointwise and simultaneous whole-axis intervals and leave-one-animal-out influence.

## Consequences

Complete PSD, autocorrelation, lag-correlation, and coherence curves can now cross
the same auditable population boundary as peri-event curves. Analyses with
incompatible axes fail before outcomes are averaged. Harmonization must be an
explicit upstream operation.

Magnitude-squared coherence is supported. Phase is excluded because arithmetic
averaging is not a valid general circular estimand. Spectrogram matrices remain
outside the one-dimensional contract.

## Alternatives considered

- **Require scalar bands or lags only.** Rejected because whole-curve inference is a
  common scientific need and the population engine already supports vectors.
- **Interpolate every session automatically.** Rejected because grid choice and
  interpolation can change peaks, edges, support, and multiplicity.
- **Weight animals by their pairs or windows.** Rejected because recording yield is
  not biological replication.
- **Average phase angles arithmetically.** Rejected because phase is circular and
  unstable where coherence or cross-power is weak.

## Revisit trigger

Add explicit grid-harmonization or two-dimensional time-frequency population
contracts only with defined estimands, support propagation, boundary behavior, and
calibrated simultaneous uncertainty.
