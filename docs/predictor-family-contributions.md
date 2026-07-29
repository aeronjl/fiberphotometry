# Ask whether a predictor family improves held-out prediction

*Applies to v0.1.*

!!! warning "Experimental predictive sensitivity"
    A full-versus-reduced score difference is not a causal effect, unique variance,
    model-free importance, or proof that a neural signal represents the omitted
    variable. It is conditional on two declared models and their validation data.

<figure markdown="span">
  <img src="../assets/predictor-family-contributions.svg" alt="A full cue, reward, and movement model branches to literal models omitting reward or movement, then rejoins as paired animal-level held-out R-squared differences with an uncalibrated dispersion range.">
  <figcaption>Conceptual workflow. Positive deltas mean the full model predicted held-out animals better than the literal drop-family model.</figcaption>
</figure>

## Scientific question

Given a defensible full encoding model, does one prespecified family—events,
movement, trial history, or normalized progress—improve prediction of observations
from animals or sessions that were not used to fit that fold?

Recent photometry work has used cross-validated leave-predictor-out analyses to
ask this kind of conditional predictive question—for example,
[Touponse et al. (2025)](https://www.nature.com/articles/s41586-025-10046-6)
combine lagged behavioral kernels, cross-validation, and leave-predictor-out
analysis. The package implements the comparison as a strict layer over an existing
[encoding multiverse](event-kernel-multiverse.md), because silently rebuilding
models would sever the result from its declared alternatives and failure ledger.
See the motivating literature synthesis in the
[capability audit](https://github.com/aeronjl/fiberphotometry/blob/main/planning/literature-capability-audit-v0.2.md#3-which-overlapping-events-and-behaviors-explain-the-continuous-signal).

## Declare literal drops

```python
from fiberphotometry.encoding_contributions import (
    PredictorFamilyContributionSpec,
    PredictorFamilyDropSpec,
    assess_predictor_family_contributions,
)

contribution_spec = PredictorFamilyContributionSpec(
    full_model="cue-reward-motion",
    families=(
        PredictorFamilyDropSpec(
            family="movement",
            reduced_model="cue-and-reward",
            removed_predictors=("motion",),
            rationale="Ask whether movement improves held-out prediction.",
        ),
        PredictorFamilyDropSpec(
            family="reward events",
            reduced_model="cue-motion",
            removed_predictors=("reward",),
            rationale="Ask whether reward timing improves held-out prediction.",
        ),
    ),
)

result = assess_predictor_family_contributions(multiverse_result, contribution_spec)
```

The caller names the full model, reduced model, scientific family, exact predictor
names expected to disappear, and rationale. The package verifies that each reduced
model is a literal subset of the full model. It rejects:

- a changed lag window, basis, modulation, or source under a shared predictor name;
- predictors added only to the nominally reduced model;
- a changed ridge grid, grouping, fold count, sampling tolerance, or coverage rule;
- an inaccurate list of removed predictors; and
- a model name absent from the retained multiverse ledger.

This is deliberately stricter than the general multiverse, where changing several
modeling choices can be scientifically legitimate. A family-drop label is only
honest when the named family is the complete computational difference.

## Common evidence and paired groups

Both fits must retain the same timestamp fingerprints. If a movement-confidence
mask removes rows only from the full model, both model scores remain visible but
the comparison becomes `descriptive_only`; no delta or dispersion range is emitted.

For eligible comparisons, the primary value is

\[
\Delta R^2 = R^2_{\text{full}} - R^2_{\text{reduced}},
\]

using each model's selected ridge penalty and mean cross-validation score. Positive
values favour the full model predictively. The artifact also pairs out-of-fold
\(R^2\) within each held-out animal or session, retaining group identities and
observation counts.

The Student-*t* range calculated across those paired group deltas is reported as
`group_dispersion`, a `PredictorFamilyDeltaDispersion` labelled
`paired_group_t_dispersion_uncalibrated`. **These bounds are uncalibrated and are
not a confidence interval.** The held-out groups share overlapping training sets,
so their delta scores are positively correlated; the Student-*t* arithmetic
therefore understates the variance of the mean delta and the range under-covers
it. No unbiased estimator of k-fold cross-validation variance exists
(Bengio & Grandvalet 2004), so the range is published as a dispersion summary at
the requested nominal level, with `calibrated=False` recorded on the artifact.

The range is also not simultaneous across families — `simultaneous_comparisons`
records how many families were declared so a reader can divide the complement of
`nominal_level` explicitly — and it is conditional on the declared models,
selected penalties, grouping, and available groups. With few animals or
heterogeneous group scores it can be wide or unstable; inspect the complete
`group_deltas` rather than reducing the result to whether the range crosses zero.

## Read the result without overclaiming

| Result | Defensible interpretation | Not supported |
| --- | --- | --- |
| Positive delta | The full specification transported better to held-out groups | The predictor caused or is uniquely encoded by the fluorescence |
| Near-zero delta | The family added little held-out score under these paired specifications | The biological variable is irrelevant |
| Negative delta | The reduced model transported better under this validation | The family suppresses the neural signal |
| Descriptive only | Denominators differ; inspect both fits separately | A numerical family contribution |
| Failed | A declared full or reduced model could not be fitted | Removing the failed model from the analysis set |

Correlated families can substitute for one another, and their leave-one-family-out
deltas do not add to total model performance. Comparing many families after seeing
the outcome is exploratory multiplicity, not confirmatory discovery. A useful
workflow prespecifies a small set of scientifically coherent families, reports all
failures and group deltas, and tests any resulting hypothesis in new data.

## Run the worked simulation

```bash
uv run python examples/event_kernel_multiverse.py
```

The seeded eight-animal example writes both
`event-kernel-multiverse-result.json` and
`predictor-family-contribution-result.json`. The latter retains the declaration,
stable full/reduced universe IDs, selected penalties and scores, paired animal
deltas, uncalibrated `group_dispersion` range, eligibility status, and failure or
comparison reason.
