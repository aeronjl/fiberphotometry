# SDR-0014: Resample animals for peri-event uncertainty

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

Peri-event plots often display uncertainty computed across trials, even though
trials are nested within sessions and animals. Pointwise intervals are also easily
misread as controlling error across an entire time series. Both practices can make
evidence look much more precise than the experimental design supports.

## Decision

The first time-course inference API forms equal-weighted session-condition means,
then animal condition means, and resamples only animal contrast curves. It reports
pointwise percentile intervals and a distinct simultaneous max-deviation band over
the complete declared window. The simultaneous critical value is conservatively
floored by the two-sided animal-level t critical value for small samples. Reports
explicitly state that pointwise intervals are local and cannot be used as
whole-window inference.

Event duplication must not change inferential precision. Missing animal support is
reported per time point, and bands remain undefined where fewer than two animal
contrasts are finite. Time-course inference is a separate evidence lane and does
not silently replace a prespecified scalar estimand.

## Consequences

Bands will generally be wider than trial-level standard errors and simultaneous
bands wider than pointwise intervals. This is intentional. Repeated sessions are
weighted equally rather than implicitly weighting animals by trial yield. The
initial method does not claim functional mixed-model or cluster-test semantics.

## Revisit trigger

Add alternative aggregation or functional models only with explicit estimands,
calibration fixtures, and report language that keeps their uncertainty statements
distinct. Revisit fixed observed standard-error studentization if simulation under
strongly varying support or heteroscedasticity shows poor simultaneous coverage.
