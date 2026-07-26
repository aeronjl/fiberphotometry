# Frozen pseudoreplication benchmark protocol v0.4

**Frozen:** 2026-07-26, before aggregate v0.4 execution.

## Question

Does treating trials as independent observations inflate false-positive
confidence intervals when treatment is assigned between animals?

## Fixed design

- 100 deterministic null studies.
- 12 animals, six per condition, with 100 events each.
- True treatment effect zero.
- Animal random-intercept SD 1.0 and event noise SD 0.3.
- 400 percentile-bootstrap draws per study.
- Comparator: ordinary event-row bootstrap.
- Proposed method: nested animal/event bootstrap with an animal-level estimand.
- A study is positive when its 95% interval excludes zero.

## Acceptance thresholds

- Event-row bootstrap false-positive rate ≥30%, demonstrating the intended
  pseudoreplication challenge.
- Hierarchical bootstrap false-positive rate ≤15%.
- Hierarchical false-positive rate at least 20 percentage points below the
  event-row result.

This benchmark tests one balanced Gaussian design. Passing does not establish
coverage for small samples, imbalance, missingness, time series, or arbitrary
experimental designs.
