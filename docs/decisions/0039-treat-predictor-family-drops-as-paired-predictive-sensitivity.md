# SDR-0039: Treat predictor-family drops as paired predictive sensitivity

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related method: [predictor-family contributions](../predictor-family-contributions.md)

## Context

Photometry encoding studies increasingly combine events, movement, behavioral
state, history, and progress predictors. A full model can predict held-out animals
well without revealing which correlated predictor family accounts for that
performance. Leave-one-predictor-family-out comparisons are useful, but “variance
explained” or “importance” language can imply a unique or causal partition that
correlated observational designs do not identify.

The general encoding multiverse permits broadly different plausible models. A
family contribution needs a narrower contract: full and reduced models must differ
only by the declared predictor names, use the same validation and tuning policy,
and be evaluated on exactly the same acquired observations.

## Decision

Add a typed contribution layer over an already executed encoding multiverse. The
caller must declare the full model, reduced model, family label, exact removed
predictor names, and rationale. Verify structurally that every shared predictor is
identical, the reduced design adds nothing, the declared removals exactly equal
the model difference, and all non-predictor model and tuning fields match.

Report full minus reduced held-out mean \(R^2\). Emit a delta only when exact
retained-sample fingerprints match. Pair the selected-model out-of-fold \(R^2\)
within every independent animal or session and report all group deltas. Summarize
them with a non-simultaneous Student-*t* sensitivity interval, explicitly
conditional on model declarations and ridge selection. Retain failed models and
denominator mismatches as `failed` or `descriptive_only` outcomes.

Use predictive language throughout. The result is not a causal effect, unique
variance partition, model-free importance score, or biological selectivity test.
Family deltas need not sum because predictors may be correlated or substitutable.

## Consequences

Users can audit whether event, movement, history, or progress families improve
transport to held-out groups without losing the parent multiverse evidence. Model
substitution, outcome-dependent model choice, denominator drift, and semantic
mislabeling become machine-detectable errors.

The paired group interval makes heterogeneity visible but is not selective
inference, simultaneous multiplicity control, or formal coverage calibration.
Small group counts and unstable group-level \(R^2\) can dominate it. Scientists
must retain the individual group deltas and prespecify or transparently label the
family set as exploratory.

## Alternatives considered

- **Subtract arbitrary multiverse alternatives:** rejected because basis, tuning,
  and predictor changes would be mislabeled as one family's contribution.
- **Refit models inside the contribution function:** rejected because that would
  create an untracked execution path outside the multiverse ledger.
- **Use coefficient magnitude:** rejected because scale, basis dimension,
  collinearity, and ridge shrinkage make it incomparable across families.
- **Call the delta unique variance explained:** rejected because leave-family-out
  prediction does not uniquely allocate shared predictive information.
- **Pool all held-out observations for uncertainty:** rejected because samples
  within animals or sessions are not independent replicates.

## Revisit trigger

Revisit the interval after formal simulation-based coverage calibration. Add
nested-CV or independently frozen penalty-selection modes if empirical benchmarks
show material selection bias. Consider multiplicity-aware simultaneous summaries
only after a prespecified family-set contract is validated.

## Evidence added later

None.
