# Frozen extended scalar-calibration protocol v0.6

**Frozen:** 2026-07-26, before aggregate execution.

Five hundred deterministic studies per scenario and effect state, with 500
animal-stratified bootstrap draws per study. Between-animal designs contain 12
animals split equally by condition. Scenarios are Gaussian, Student-t(3),
heteroscedastic treatment noise, unequal event counts, and outcome-dependent
missingness. Each runs under a true null and an effect of 0.8 animal SD.

The benchmark records percentile, basic, and BCa null coverage, power, and median
interval width. Its vectorized unit-mean implementation is algebraically
equivalent to the public animal-stratified scalar estimand and is checked against
that implementation in unit tests.

## Acceptance and policy

- Each method must have 90–99% null coverage in at least four of five scenarios.
- Every scenario must have at least one method with 88–100% coverage.
- Power for effect 0.8 must exceed 50% in Gaussian and unequal-count scenarios.
- No default is selected unless one method meets 90–99% coverage in all five
  scenarios without having the greatest median width in all five.

These simulations remain stylized and cannot validate informative-missingness
assumptions or substitute for design-specific randomization inference.
