# Population inference and robustness

This category applies across the signal, event, continuous, and multi-signal
routes. It defines what counts as an independent unit and whether a conclusion
depends on one defensible workflow choice.

## Choose the workflow

| Need | Workflow | Status |
|---|---|---|
| Select the experimental unit, estimand, and resampling design | [Experimental design and inference](../inference-design-v0.1.md) | Supported guidance and APIs |
| Quantify sensitivity to named analytic alternatives | [Robustness multiverses](../multiverse-contract-v0.1.md) | Supported |
| Fit an optional scalar hierarchical sensitivity model | [Scalar mixed models](../scalar-mixed-model-v0.1.md) | Experimental |
| Inspect validation evidence rather than capability claims | [Public-data evidence atlas](public-evidence-atlas.md) | Maintained register |

## Default hierarchy

Repeated samples and trials belong to sessions; sessions belong to animals. A
workflow may model lower levels, but population uncertainty must not pretend those
observations are independent animals. Predictive validation likewise holds out the
complete group at the level of the intended generalization claim.

## Coverage gaps this category exposes

- functional mixed models for complete time courses;
- small-sample corrections across more hierarchical designs;
- calibrated simultaneous inference after model selection;
- Bayesian hierarchical models with inspectable prior sensitivity; and
- meta-analytic evidence across laboratories and acquisition systems.

Robustness is not a vote across arbitrary analyses. Universes must preserve the
estimand and denominator, declare compatibility rules before outcomes, and retain
failures alongside successful results.
