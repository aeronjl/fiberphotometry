# Frozen descriptive IBL multiverse specification v0.1

**Frozen:** 2026-07-26 before executing the aggregate dF/F multiverse, after the
four sessions and correctness contrast had already been examined in the earlier
post-hoc analysis. This is not a preregistration.

## Fixed scientific structure

- The same four public IBL sessions (`fip_13`–`fip_16`).
- DMS channel, aligned to feedback.
- Within-animal correct-minus-incorrect contrast.
- Animal as the aggregation unit.
- Descriptive paired-t interval; correctness is observed, not randomized.
- Trials retained by the frozen raw-data availability rule used in v0.1.

## Decision nodes

Correction family:

1. OLS reference dF/F.
2. Robust IRLS reference dF/F (declared reference workflow).
3. Resample to 20 Hz without bridging gaps over 0.25 s, fourth-order 3 Hz
   zero-phase low-pass filtering, then robust IRLS reference dF/F.

Event summary:

1. Baseline -0.5–0 s; response 0–0.5 s (declared reference workflow).
2. Baseline -0.5–0 s; response 0–0.25 s.
3. Baseline -1.0–-0.2 s; response 0–0.5 s.

This yields nine compatible dF/F universes. All outputs are dimensionless dF/F
changes and share one estimand declaration. The earlier raw-fluorescence result
is reported separately because combining estimates with different units into
one robustness distribution would be misleading.

## Reporting

Retain universe IDs, complete pipelines, estimates, intervals, failures, QC
blocks, correction/window decision medians, and reference leave-one-animal-out
estimates. Report direction descriptively. No smallest effect of interest or
causal interpretation is introduced after viewing these data.
