# Event-locked responses and encoding

Use this category when events or intervals are supplied independently of the
fluorescence outcome. First decide whether the estimand is an average response,
a jointly estimated response to overlapping predictors, or predictive value.

## Choose the workflow

| Scientific question | Workflow | Output |
|---|---|---|
| What is the response around one event definition? | [Peri-event inference](../peri-event-inference-v0.1.md) | auditable session estimates and paired or independent animal-level time course |
| Does a repeated event/condition contrast differ between animal groups? | [Group-by-condition interactions](../population-interactions-v0.1.md) | animal-level peri-event difference in differences |
| What is associated with each of several overlapping events? | [Event-kernel encoding](../event-kernel-encoding-v0.1.md) | regularized kernels with complete-group validation |
| Does the result survive plausible design choices? | [Event-kernel model multiverses](../event-kernel-multiverse-v0.1.md) | paired design alternatives and failure ledger |
| Does one predictor family add held-out information? | [Predictor-family contributions](../predictor-family-contributions-v0.1.md) | paired full-minus-reduced held-out score |
| Are time-course intervals calibrated? | [Interval calibration](../event-kernel-interval-calibration-v0.1.md) | scenario-wise coverage evidence |
| How should bouts be filtered, merged, split, or overlapped? | [Interval and bout policies](../interval-policy-v0.1.md) | transformed intervals and lineage ledger |

## Interpretation boundaries

- A peri-event average is not a unique causal response when events overlap.
- A kernel coefficient is conditional on all included predictors and basis choices.
- In-sample fit does not establish transport to a new animal.
- Pointwise intervals do not cover an entire time course simultaneously.
- Separate significance tests within each group do not test a group-by-condition
  interaction.
- Full-versus-reduced prediction measures conditional predictive contribution,
  not biological necessity.

## Coverage gaps this category exposes

- production-ready functional mixed models for whole time courses;
- calibrated selective inference after tuning and model selection;
- richer nonlinear and interaction bases with group-safe validation; and
- reference reproductions of commonly used published event-analysis figures.

See the [event-locked worked examples](../tutorials/index.md) for simulations,
public data, duration-varying behavior, and retained negative validation results.
