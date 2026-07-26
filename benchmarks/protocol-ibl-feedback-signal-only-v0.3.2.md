# IBL feedback signal-only protocol v0.3.2

Status: **frozen after limited, disclosed outcome access** (26 July 2026)

This amendment corrects a product/preflight failure in
[v0.3.1](protocol-ibl-feedback-signal-only-v0.3.1.md). It does not reinterpret an
observed effect.

## What went wrong

v0.3 classified all 15 non-rolling/subtractive universes as executable without
running an outcome-blind structural compatibility check. The first real session
has a nominal 50 Hz clock but interval CV 0.00569. The declared AsLS operation
requires a regular time axis and therefore failed before fitting a baseline.

Timestamp regularity is acquisition structure, not a fluorescence outcome. This
should have been identified before either v0.3 or v0.3.1 was frozen. Treating the
failure as scientific evidence against AsLS would be incorrect.

## Outcome-access disclosure

The smoke test and interrupted v0.3.1 runner downloaded 19 sessions. They computed some
session-level summaries in memory, but no cohort estimate, interval, p-value,
specification curve, or leave-one-animal-out result was produced or inspected.
The only inspected result was the structural AsLS error from the first session.

## Amendment

All six AsLS universes are retained as **mechanically incompatible**, with the
reason that the protocol lacks an explicit timestamp-regularization operation.
They are not counted as failed scientific analyses. The six double-exponential
and three published-rolling universes remain eligible. All other v0.3.1 choices,
including equal session weighting within animal, are unchanged.

A future AsLS protocol must predeclare and validate a resampling policy; it cannot
be introduced into this result after outcome access.

The machine-readable protocol is
[`ibl-feedback-protocol-v0.3.2.json`](ibl-feedback-protocol-v0.3.2.json). The
package now exposes outcome-blind pipeline and multiverse compatibility reports so
this class of error can be detected during product preflight.
