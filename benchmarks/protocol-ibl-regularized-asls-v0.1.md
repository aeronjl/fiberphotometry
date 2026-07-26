# Held-out IBL regularized-AsLS comparison v0.1

Status: **frozen before held-out fluorescence access** (26 July 2026).

## Held-out cohort

The benchmark uses the 24 sessions excluded from the IBL v0.3 cohort solely
because they lacked the minimum event count in both feedback conditions. Their
timestamps, include flags, and behavioral counts were inspected during cohort
construction, but the v0.3.2 analysis loaded fluorescence only for the 383
eligible sessions. Exact signal, ROI, and trial files are checksum-frozen in the
executable JSON protocol before signal columns are opened.

These sessions are intentionally unsuitable for population inference. They are an
independent engineering set for preprocessing execution, fidelity, coverage, and
downstream scalar-summary sensitivity.

## Frozen comparison

The primary method is division-normalized AsLS after linear median-rate
regularization with a 1.5-times-median protected-gap boundary. Double exponential
and the published rolling baseline run both on raw timestamps and after the same
regularization. Their raw-versus-regularized agreement isolates interpolation
effects from baseline-method disagreement.

Event deltas use `[-1.0, 0.0)` seconds for baseline and `[0.0, 0.5)` seconds for
response, applied to the exact usable feedback events in the frozen cohort rows.
No minimum condition count is imposed and no population effect is estimated.

## Prospective gates

- Every source matches its frozen digest and every method executes every session.
- Every fitted baseline and method-specific event set is at least 99% complete.
- Maximum target-to-source distance is at most 0.25 median source intervals.
- For each raw-compatible comparator, median raw-versus-regularized trace
  correlation is at least 0.995, every case is at least 0.95, and median
  normalized trace RMSE is at most 0.10.
- Raw-versus-regularized pooled event-delta correlation is at least 0.99 and its
  normalized median absolute difference is at most 0.05.

AsLS-versus-comparator agreement is descriptive only. Agreement is not truth;
disagreement may arise from either baseline. Every session and failure is retained,
and thresholds will not be tuned after aggregate access.

The machine-readable contract and source manifest are
[`ibl-regularized-asls-protocol-v0.1.json`](ibl-regularized-asls-protocol-v0.1.json).
