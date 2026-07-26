# Pseudoreplication benchmark results v0.4

The [frozen protocol](protocol-v0.4.md) was executed across 100 deterministic
true-null studies. Compact results are in [`results-v0.4.json`](results-v0.4.json),
and the complete run can be regenerated with
`uv run python scripts/run_pseudoreplication_benchmark.py`.

| Method | False-positive rate |
| --- | ---: |
| Event-row percentile bootstrap | 79% |
| Nested animal/event bootstrap, animal-level estimand | 12% |

All pre-specified criteria passed. Treating 1,200 events as independent produced
severe pseudoreplication: animal random intercepts were mistaken for a condition
effect in most simulated studies. Declaring the 12 animals as the population
units reduced false positives by 67 percentage points.

The remaining 12% is still above the nominal 5%. With six animals per group,
ordinary percentile intervals are imperfectly calibrated. The result supports
explicit animal-level inference over event-level resampling; it does not yet
justify percentile bootstrap as a release-quality default. Next comparators
should include studentized/BCa intervals, randomization inference, and an
independently implemented mixed model.
