# DANDI 000971 end-to-end tutorial result v0.1

Status: **completed descriptive product demonstration** (27 July 2026)

## What was executed

The [prospectively frozen protocol](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-dandi-000971-tutorial-v0.1.md)
was committed as `b004b8f` before the selected fluorescence outcomes were accessed.
All six files from immutable DANDI:000971 version `0.260213.1851` matched their
frozen byte sizes and SHA-256 digests. No asset was replaced and no source,
schema, or event preflight failed.

The committed [evidence bundle](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/dandi-000971-tutorial-v0.1/) contains
the preflight, primary result, complete multiverse, self-contained HTML report,
and checksum manifest. The executable source remains
[`examples/dandi_000971_reward_tutorial.py`](https://github.com/aeronjl/fiberphotometry/blob/main/examples/dandi_000971_reward_tutorial.py).

## Event denominator

| Animal | Published family | Active pokes | Rewarded | Unrewarded | Boundary exclusions |
|---|---|---:|---:|---:|---:|
| 028-392 | PR | 87 | 32 | 55 | 0 |
| 048-392 | PR | 124 | 25 | 99 | 0 |
| 272-396 | DPR | 149 | 39 | 110 | 0 |
| 333-393 | DPR | 246 | 49 | 197 | 0 |
| 112-283 | PS | 42 | 7 | 35 | 0 |
| 113-283 | PS | 311 | 48 | 263 | 0 |

The 959 events are observations, not 959 independent replicates. Every analysis
first reduces them to within-animal rewarded and unrewarded summaries; six animal
contrasts determine the inferential uncertainty. The large count imbalance is
visible rather than repaired by subsampling or trial-level weighting tricks.

## Primary result

### Bounded source-panel reproduction

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/dandi-000971-source-figure-bounded-v0.1.svg" alt="Rewarded and unrewarded nose-poke time courses for DMS and DLS are shown separately for PR, DPR, and PS phenotypes, with two individual animals per phenotype and a final panel showing each animal's rewarded-maximum minus unrewarded-minimum peak score.">
  <figcaption><strong>Partial reproduction of Seiler et al. Figures 3E–F and 4E–F.</strong> Thin traces are animals; heavy traces are animal-equal phenotype means; shading is SEM across two animals and is descriptive. The right panels use the source paper's maximum rewarded minus minimum unrewarded PSTH value from 0–1.5 s. Unlike the source figures, this checksum-pinned teaching cohort has one session from only two animals per phenotype and cannot reproduce training-stage effects or the full-cohort statistics. Processing matches the source OLS fitted-reference dF/F and session z-score, with this tutorial's declared 3 Hz zero-phase filter.</figcaption>
</figure>

This figure deliberately mirrors the source panel's estimand and visual grammar
before introducing the package's alternative robustness analysis. It is a
**partial source-panel reproduction**, not numerical parity with the full study.
See the [paper-figure correspondence register](tutorials/paper-figure-roadmap.md)
and regenerate it from the six pinned NWB assets with:

```bash
uv run --extra nwb --extra plots python scripts/plot_dandi_000971_source_figure.py
```

The frozen reference workflow—3 Hz zero-phase filtering, robust IRLS reference
fit, fitted-reference dF/F, and a 0-1.5 second response—estimated:

- rewarded minus unrewarded DMS response: **0.00693 ΔF/F**;
- 95% paired Student interval: **−0.00731 to 0.02118 ΔF/F**;
- descriptive paired-test p-value: **0.266**.

The point estimate is positive, but the interval contains both negative and
positive population values. This six-animal demonstration therefore does not
establish a non-zero population contrast. That is not a product failure: the
report correctly prevents hundreds of events from creating spurious precision.

Individual animal contrasts were heterogeneous, ranging from approximately
−0.00454 to 0.03322 ΔF/F. Two of six were slightly negative. The published PR,
DPR, and PS labels were deliberately not modeled, so this result says nothing
about phenotype differences.

## Robustness result

All eight frozen universes executed successfully:

- estimate range: **0.00676 to 0.00694 ΔF/F**;
- median estimate: **0.00686 ΔF/F**;
- fraction positive: **8/8**;
- blocked, failed, or incompatible universes: **0**.

Median estimates were almost unchanged across unfiltered OLS, unfiltered IRLS,
filtered OLS, and filtered IRLS. The 0-0.5 second window produced a slightly lower
median (0.00678) than the 0-1.5 second window (0.00693), but this shift was tiny
relative to animal-level uncertainty.

Leave-one-animal-out reference estimates remained positive from 0.00168 to
0.00923 ΔF/F. The direction is therefore not created by one animal, although
omitting animal 112-283 substantially attenuates the estimate and exposes its
influence.

## Product interpretation

This result demonstrates why the product needs both a primary workflow and a
multiverse. The primary interval answers how uncertain the animal-level estimate
is; the multiverse answers whether reasonable analysis choices materially move
that estimate. Here those answers differ:

- **method robustness is high**—filtering, reference estimator, and response
  window barely alter the point estimate;
- **population precision is low**—six heterogeneous animals permit a wide
  interval.

A conventional event-level analysis could obscure that distinction. The evidence
bundle instead shows the event denominator, independent-unit boundary,
preprocessing provenance, complete decision space, and influence diagnostic in
one rerunnable result.

## Limits

- This is a deliberately balanced six-animal teaching cohort, not a representative
  sample of the source population.
- The same public recordings underlie the source paper, so qualitative agreement
  is a reanalysis rather than independent replication.
- The source-panel reproduction is limited to one session from two animals per
  phenotype; its SEM is descriptive and must not be read as full-cohort precision.
- The scalar mean-window contrast is not the source paper's peak-based statistic.
- The isosbestic measurement is a reference channel, not guaranteed motion-only
  or biologically inert ground truth.
- Robustness across eight specified workflows does not imply robustness to every
  scientifically plausible preprocessing or inferential model.

## Sources

- Seiler et al. (2022), [source study](https://doi.org/10.1016/j.cub.2022.01.055).
- Seiler et al. (2026), [immutable public data](https://doi.org/10.48324/dandi.000971/0.260213.1851).
- DANDI, [official example notebook](https://docs.dandiarchive.org/example-notebooks/000971/lernerlab/seiler_2024/fiber_photometry_example_notebook/).
- CatalystNeuro, [NWB conversion provenance](https://github.com/catalystneuro/lerner-lab-to-nwb).
