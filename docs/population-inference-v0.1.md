# Animal estimates and population contrasts v0.1

FiberPhotometry separates the measurements used to estimate an animal from the
animals used to estimate a population. This boundary is reusable across scalar
responses and vector outcomes such as peri-event curves.

## The evidence chain

```text
events, windows, or detected features
  -> session-condition estimates
  -> animal-condition estimates
  -> declared paired or independent population contrast
```

Every `PopulationUnitEstimate` contains an animal identifier, contrast level,
estimate, source-session identifiers, observation count, and pointwise source
support. `infer_population_contrast()` receives only these materialized animal
estimates. It never treats their contributing events or windows as independent
population replicates.

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/population-inference-boundary.svg" alt="Events and windows become session estimates, then equally weighted animal estimates, and only then a paired or independent population contrast; an evidence ledger preserves support and influence throughout.">
  <figcaption><strong>The inferential boundary is a stored product, not an implicit average.</strong> Domain-specific rules construct animal estimates; the common population layer operates only after that boundary is inspectable.</figcaption>
</figure>

## Supported designs

### Paired

Use a paired design when every included animal contributes both levels. The
population estimate is the mean within-animal difference. Animals missing either
level are listed in `excluded_units`; they are not silently treated as independent
observations.

### Independent

Use an independent design for a between-animal comparison. Animal identifiers must
be disjoint across levels, and each level needs at least two animals. Group means
are contrasted with a Welch standard error, while bootstrap draws resample animals
separately within each group.

```python
from fiberphotometry import (
    PopulationContrastSpec,
    PopulationUnitEstimate,
    infer_population_contrast,
)

animals = (
    PopulationUnitEstimate(
        unit_id="control-01",
        level="control",
        estimate=(0.12,),
        support=(2,),
        source_units=("session-01", "session-02"),
        observation_count=18,
    ),
    # Additional animals from both disjoint groups...
)

result = infer_population_contrast(
    animals,
    PopulationContrastSpec(
        numerator="drug",
        denominator="control",
        design="independent",
        draws=2_000,
        seed=7,
    ),
)
```

Scalar outcomes use a one-element `estimate`. Curves, spectra, and other ordered
outcomes use longer tuples with a common shape.

## What the result makes inspectable

- the population estimate in the original measurement units;
- pointwise standard errors and Hedges standardized effects;
- pointwise bootstrap intervals and a simultaneous max-*t* band;
- numerator, denominator, and contrast support at every outcome point;
- included and incomplete animals;
- the complete animal-estimate ledger; and
- the population curve after leaving out each animal, plus its maximum deviation.

The simultaneous band is a whole-outcome uncertainty statement under the declared
bootstrap design. It is not a cluster test and does not identify a response onset.
Pointwise standardized effects are secondary descriptions, not permission to scan
for the largest effect without accounting for selection.

## Where domain rules still belong

The common layer starts only after animal estimates exist. Analysis-specific code
must still decide how to form them. For example, transient rates pool counts over
finite exposure, while peri-event kinetics average session-condition curves equally
within animal. A generic population function must not erase those denominators.

## Current boundary

Version 0.1 supports two-level paired and independent contrasts. Factorial designs,
group-by-condition interactions, continuous covariates, generalized count models,
crossed effects, and functional mixed models remain explicit gaps. Those extensions
require estimand-specific simulations rather than a formula-only interface.

The test suite includes seeded small-sample Gaussian coverage regressions for both
designs. These guard against obvious interval regressions; they are not a claim of
calibration under skew, heteroscedasticity, informative missingness, or
preprocessing selection. Broader scenario calibration remains required before
promoting the resampling API beyond its current experimental boundary.

The governing rationale is recorded in
[SDR-0055](decisions/0055-materialize-animal-estimates-before-population-inference.md).
