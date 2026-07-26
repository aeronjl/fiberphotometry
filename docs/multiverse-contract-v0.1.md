# Multiverse scientific contract v0.1

A FiberPhotometry multiverse evaluates multiple defensible workflows for one
fixed dataset, scientific estimand, and experimental-unit declaration. It is a
robustness analysis, not a search over outcomes or a substitute for replication.

## Invariants

- Every universe has the same `Estimand`, including outcome meaning, contrast,
  and aggregation unit. Changing the estimand creates a different multiverse.
- Decision nodes and their alternatives have stable names and scientific
  rationales. Confirmatory nodes are frozen before inspecting final contrasts.
- A named reference selection is required; it is not silently treated as the
  uniquely correct workflow.
- Compatibility rules exclude incoherent combinations before execution and
  retain the exclusion reason.
- Every valid universe receives an identifier derived from its canonical choices
  and complete materialized pipeline specification.
- Successful, QC-blocked, incompatible, non-finite, and failed universes are all
  retained. Execution failure cannot improve the reported robustness fraction.
- Random seeds remain part of the materialized analysis plan.

## Interpretation

Primary summaries concern estimates: range, median, direction, practical-effect
stability, the reference estimate, and which choices shift the median estimate.
The fraction of nominally significant results is not a primary robustness
measure because universes are dependent specifications, not random independent
samples.

When requested and structurally possible, leave-one-aggregation-unit-out results
are computed for the declared reference universe. They diagnose dependence on a
single animal or other population unit; they do not repair a small sample.

An exploratory multiverse may help identify influential decisions, but must not
be relabelled confirmatory. Any revised decision space should receive a new
specification and be validated on independent data.

## Methodological context

This contract adapts multiverse analysis and specification-curve principles to
nested photometry workflows:

- Steegen et al. (2016), [Increasing Transparency Through a Multiverse
  Analysis](https://doi.org/10.1177/1745691616658637).
- Simonsohn et al. (2020), [Specification Curve
  Analysis](https://doi.org/10.1038/s41562-020-0912-z).
- Carp (2012), [On the Plurality of (Methodological)
  Worlds](https://doi.org/10.3389/fnins.2012.00149).
- Botvinik-Nezer et al. (2020), [Variability in the Analysis of a Single
  Neuroimaging Dataset by Many Teams](https://doi.org/10.1038/s41586-020-2314-9).
