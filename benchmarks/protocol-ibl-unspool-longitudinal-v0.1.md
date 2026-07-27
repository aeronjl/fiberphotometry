# IBL FiberPhotometry–Unspool longitudinal benchmark v0.1

Status: **frozen before the new longitudinal aggregate comparison** (27 July 2026).

This is a post-hoc predictive benchmark. Photometry and feedback outcomes were
already accessed in the disclosed IBL v0.3 analyses; no confirmatory claim is
available. The new element frozen here is the lagged cross-package prediction rule.

## Question

Does the immediately previous session's DMS correct-minus-incorrect feedback
response improve prediction of correctness in one future session, beyond stationary
behavior and linear session progress?

## Cohort and chronology

Use the 18-animal checksum-frozen IBL v0.3 cohort. Retain at most one eligible
session per animal and ISO date; when two session UUIDs share a date, retain the
lexicographically smallest UUID without inspecting outcomes. Assign session order by
ISO date. Do not infer chronology from filesystem or row order.
Only selected session orders 0–11 are accessed: order 0 supplies the first lagged
predictor, orders 1–10 train, and order 11 is held out.

## Neural summary

Use the previously declared 470-nm-only `published_rolling / divide_standard`
workflow: rolling baseline, divided fractional dF/F, −0.5–0 s baseline, and 0–0.5 s
response. Within each session calculate mean correct minus mean incorrect feedback
delta. The predictor for session *t* is the summary from session *t−1*, divided by a
fixed 0.01 fractional-dF/F scale. The first session has no predictor and is excluded.

## Candidate models

All are Unspool Bernoulli history GLMs with one within-session correctness lag and
L2 penalty `1e-6`:

1. stationary;
2. fixed linear session progress (`session_order / 20`);
3. session progress plus the prior-session neural contrast.

No candidate or penalty is selected after aggregate inspection.

## Validation and inference

Use one cohort-forward-session fold: the first ten retained predictor-bearing
sessions train each model and the next session is held out for every eligible animal.
Compare animal-balanced log loss. Use 5,000 paired animal-bootstrap draws with seed
`20260727`. The primary contrast is session-progress log loss minus
session-progress-plus-neural log loss; positive favors the neural model.

## Claim boundary

The benchmark can establish only incremental predictive association in one future
session under this cohort, preprocessing path, lag, and model set. It cannot establish
causality, reproduce the source paper's encoding models, validate 470-nm-only signal
correction, or show transport to new animals or laboratories.

The normative machine-readable protocol is
[`ibl-unspool-longitudinal-protocol-v0.1.json`](ibl-unspool-longitudinal-protocol-v0.1.json).
