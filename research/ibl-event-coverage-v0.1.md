# IBL structural event-coverage audit v0.1

Status: **passed the prospectively frozen product-readiness gate** (26 July
2026).

## Result

The median-rate, 1.5-times-gap regularization policy retained all 224,272 events
selected by the frozen IBL v0.3 cohort across 383 sessions and 18 animals. Both
feedback conditions retained 100%, their retention difference was zero, every
animal-level difference was zero, and no protected gap was bridged.

This is a structural compatibility result, not a fluorescence result. The audit
loaded only timestamps, wavelengths, `include` flags, feedback times, and feedback
condition. Exact signal and trial file hashes were verified against the archived
v0.3.2 execution. No ROI fluorescence column or biological effect estimate was
accessed.

| Stage | Correct | Incorrect | Total |
| --- | ---: | ---: | ---: |
| Boundary-eligible feedback events | 141,559 | 84,325 | 225,884 |
| Retained by frozen 60-second cohort gate | 140,606 | 83,666 | 224,272 |
| Complete after regularization | 140,606 | 83,666 | 224,272 |

The existing cohort gate retained 99.33% of correct and 99.22% of incorrect
boundary-eligible events: 1,612 events were removed before regularization. This
small aggregate difference does not imply uniform session behavior. The worst
session retained 88.1% overall, and the largest session-level condition-retention
difference was 8.44 percentage points. These upstream losses are therefore part
of the selection audit even though they do not count against the prospectively
defined incremental regularization gate.

## What the pass does—and does not—establish

The 383 eligible sessions contained 387,034 source rows marked `include=false`
across 328 sessions. They produced 386,443 unobservable regular-grid points at
recording edges, but no internal protected target-grid gaps. The rolling-validity
cohort gate kept every selected event away from those edges. Consequently:

- the pass shows that regularizing the real IBL timestamp jitter does not itself
  discard or differentially select the frozen event sample;
- it shows that protected missingness is compatible with this cohort and never
  silently bridges excluded edge regions;
- it does **not** provide a real-data test of events adjacent to internal missing
  runs, because this eligible cohort has none;
- synthetic missing-run validation remains the evidence for internal-gap
  classification, and a held-out real dataset with internal dropouts is still
  required.

## Product consequence

Coverage reporting must begin before preprocessing. A workflow should expose the
candidate, eligibility-gated, and post-preprocessing denominators by condition,
session, and animal. A single final “events analyzed” count would hide the
session-level imbalance observed here. The regularizer itself is ready for a
held-out real-data AsLS comparison; this audit does not promote AsLS or reopen the
previously observed fluorescence outcomes.

The governing contract is
[`protocol-ibl-event-coverage-v0.1.md`](https://github.com/aeronjl/fipha/blob/main/benchmarks/protocol-ibl-event-coverage-v0.1.md),
the complete machine-readable output is
[`ibl-event-coverage-results-v0.1.json`](https://github.com/aeronjl/fipha/blob/main/benchmarks/ibl-event-coverage-results-v0.1.json),
and the result fingerprint is
`c63dbfe7bafee999f5ff00a2e3db2c22bb28f543a36ef80ccc6c6a08aa88bbef`.
