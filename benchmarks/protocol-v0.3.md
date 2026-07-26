# Frozen event-aware diagnostic benchmark protocol v0.3

**Frozen:** 2026-07-26, before aggregate v0.3 execution.

This protocol tests diagnostics introduced in response to the retained v0.2
event-locked-motion failure. No thresholds or scenarios may change after the
aggregate run; changes require a new version.

## Fixed design

- The seven v0.2 scenarios, parameters, duration, rate, and 20 seeds are reused.
- Event QC uses a -0.5–0 second baseline, 0–0.5 second response, and ±1 second
  derivative cross-correlation lag scan.
- A reference event response at least 0.5 reference standard deviations from
  baseline warns as `event_correlated_reference`.
- A best derivative lag of at least 100 ms that improves absolute correlation
  by at least 0.05 warns as `signal_reference_lag`.

## Acceptance thresholds

- At least 18/20 event-locked-motion runs emit `event_correlated_reference`.
- At least 18/20 lagged-reference runs emit `signal_reference_lag`.
- At least 18/20 reference-contamination runs emit
  `event_correlated_reference`.
- No more than 2/20 clean-linear runs emit either warning.
- Every v0.2 numerical result remains unchanged to floating-point tolerance.

Passing these simulator criteria does not establish that an event-correlated
reference response is motion, biological contamination, or causal. It establishes
only that the library exposes the violated separability assumption.
