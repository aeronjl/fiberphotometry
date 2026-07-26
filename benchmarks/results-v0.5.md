# Scalar-inference calibration results v0.5

The [frozen protocol](protocol-v0.5.md) was executed across 200 deterministic
true-null studies. Each method used the same 250 nested-bootstrap draws within a
study. Compact results are in [`results-v0.5.json`](results-v0.5.json).

| Scenario | Percentile | Basic | BCa |
| --- | ---: | ---: | ---: |
| Between, 12 balanced animals | 87.5% | 90.0% | 90.0% |
| Between, 24 balanced animals | 95.0% | 95.0% | 95.0% |
| Between, 12 animals split 8:4 | 87.5% | 87.5% | 87.5% |
| Between, 30% events missing | 90.0% | 85.0% | 90.0% |
| Within-animal paired | 97.5% | 97.5% | 100.0% |

All criteria passed and all three methods met the deliberately broad default
eligibility rule. That is not evidence of equivalence or universal calibration:
40 studies per cell give coarse 2.5-percentage-point increments, and the paired
scenario suggests conservative intervals. No default is selected from this
benchmark.

Exact sign-flip tests now enumerate all null assignments for up to 20 paired
units and are tested against direct enumeration. Paired inference raises an error
if any declared unit lacks a contrast level rather than silently dropping it.

An opt-in `statsmodels` MixedLM comparison reproduced the scalar paired estimate
to within 1.7e-16; see
[`statsmodels-parity-v0.1.json`](statsmodels-parity-v0.1.json). This validates the
balanced point estimate, not interval coverage or general mixed-model parity.
