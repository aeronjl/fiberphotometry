# Public-data evidence atlas

These figures are not a gallery of idealized outputs. Each is generated from a
versioned analysis of public photometry data and paired with the question it can
answer, its experimental unit, and the limitation that controls interpretation.

## Are event contrasts robust to reasonable preprocessing choices?

<figure class="doc-figure doc-figure--wide">
  <img src="../../assets/dandi-000971-reward-multiverse-v0.1.svg" alt="Eight animal-level estimates of rewarded minus unrewarded DMS response from six public DANDI animals. All point estimates are positive and tightly grouped, while every confidence interval crosses zero.">
  <figcaption><strong>Stable direction is not precise population evidence.</strong> Across eight declared preprocessing and response-window universes, the rewarded-minus-unrewarded estimate changes little. The wide intervals reflect the six-animal denominator and all cross zero.</figcaption>
</figure>

- **Public source:** [DANDI:000971](https://doi.org/10.48324/dandi.000971/0.260213.1851), from [Seiler et al. (2022)](https://doi.org/10.1016/j.cub.2022.01.055).
- **Estimand:** within-animal rewarded minus unrewarded DMS response.
- **Independent units:** six animals; events are not treated as replicates.
- **Use it to learn:** reference correction and response windows as named analysis decisions.
- **Do not conclude:** phenotype prevalence, source-study replication, or evidence for a nonzero population effect.

[Run the raw-NWB tutorial](../tutorials/dandi-000971-reward-multiverse.md)
or [read the frozen result](../dandi-000971-tutorial-results-v0.1.md).

## Does a descriptive contrast survive a wider signal-only multiverse?

<div class="evidence-grid" markdown>
<figure class="doc-figure">
  <img src="../../figures/ibl-feedback-signal-only-divide-v0.3.2.svg" alt="Specification curve for six divided dF/F workflows in 18 IBL animals. Every correct-minus-incorrect estimate is positive and every interval excludes zero.">
  <figcaption><strong>Divided dF/F lane.</strong> Six executable universes share fractional dF/F units and remain positive.</figcaption>
</figure>

<figure class="doc-figure">
  <img src="../../figures/ibl-feedback-signal-only-subtract-v0.3.2.svg" alt="Specification curve for three subtractive acquired-fluorescence workflows in 18 IBL animals. Every correct-minus-incorrect estimate is positive and every interval excludes zero.">
  <figcaption><strong>Subtractive lane.</strong> Three executable universes share acquired-fluorescence units; they are deliberately not pooled with divided dF/F.</figcaption>
</figure>
</div>

- **Public source:** 383 IBL sessions from 18 animals associated with [Bimbard et al. (2024)](https://doi.org/10.1038/s41593-024-01750-7).
- **Estimand:** correct minus incorrect feedback response, with sessions weighted equally within animal.
- **Independent units:** 18 animals; 224,272 events contribute within the hierarchy.
- **Use it to learn:** compatible universes, structurally rejected workflows, separate unit lanes, and leave-one-animal-out diagnostics.
- **Do not conclude:** causal effects of correctness or robustness to untested preprocessing families.

[Read the complete frozen result and amendments](../ibl-feedback-signal-only-results-v0.3.2.md).

## Can overlapping behavioral events predict a new animal?

<figure class="doc-figure doc-figure--wide">
  <img src="../../assets/dandi-000971-event-kernels-v0.2.png" alt="DMS and DLS active-poke and reward-increment event kernels with broad grouped-jackknife sensitivity intervals from six DANDI animals.">
  <figcaption><strong>Plausible pooled shapes did not transport.</strong> Both regions selected the largest ridge penalty and mean held-out-animal R² remained negative. The figure is useful because the failed prediction gate is retained beside the attractive kernels.</figcaption>
</figure>

- **Public source:** the same checksum-pinned DANDI:000971 cohort.
- **Estimand:** active-poke kernel plus the conditional reward increment in continuous DMS and DLS signals.
- **Validation unit:** complete held-out animals, not samples from animals used in fitting.
- **Use it to learn:** overlapping-event design matrices, grouped penalty selection, residual diagnostics, and honest negative validation.
- **Do not conclude:** significant time points, regional differences, or useful out-of-animal prediction.

[Read and reproduce the event-kernel analysis](../tutorials/dandi-000971-event-kernel.md).

## How to read this atlas

An empirical figure earns a place here only when its page names the source data,
experimental unit, estimand, preprocessing contract, inferential boundary, and a
machine-readable result. Attractive output without those six items remains an
illustration rather than scientific evidence.
