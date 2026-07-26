# Frozen finite-sample t and power protocol v0.7

**Frozen:** 2026-07-26, before aggregate execution.

Ten thousand Gaussian studies per cell compare animal-level Welch inference at
6, 8, 10, 12, 16, 20, and 30 animals per condition. Animal SD is 1, the true
effect is either 0 or 0.8, and event-level noise is negligible after aggregation.

Acceptance: null coverage must be 94–96% at every sample size; simulated power
must be within three percentage points of the noncentral-t calculation; and the
smallest sample size reaching 80% power must be reported rather than rounded
down. Paired-t behavior is unit-tested separately against exact sign flipping.

This benchmark applies only to approximately Gaussian independent animal means.
