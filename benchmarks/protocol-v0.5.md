# Frozen scalar-inference calibration protocol v0.5

**Frozen:** 2026-07-26, before aggregate execution.

## Design matrix

Forty deterministic true-null studies per scenario, 250 bootstrap draws each:

1. Between-animal, 12 balanced animals, 100 events each.
2. Between-animal, 24 balanced animals, 100 events each.
3. Between-animal, 12 animals split 8:4, 100 events each.
4. Between-animal, 12 balanced animals with 30% events missing at random.
5. Within-animal paired assignment, 12 animals and 50 events per condition.

Animal random-intercept SD is 1.0 and event-noise SD is 0.3. Coverage of the
true zero effect is measured for percentile, basic, and BCa 95% intervals using
the same bootstrap distribution.

## Acceptance and default policy

- At least one method must cover zero in 80–100% of studies in every scenario.
- BCa coverage must be at least 80% in every scenario.
- No method becomes a default unless its coverage is 85–100% in every scenario.
- Exact paired sign-flip output must equal full enumeration in unit tests.
- Mixed-model parity is a separate opt-in numerical check and cannot rescue a
  failed coverage criterion.

The small number of studies gives coarse coverage estimates. Results guide the
next benchmark; they do not establish universal calibration.
