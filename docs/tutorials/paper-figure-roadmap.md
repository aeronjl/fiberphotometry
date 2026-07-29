# Paper-figure correspondence

This register prevents a public-data analysis from being described as a paper
reproduction merely because it uses the same recordings. It maps each worked
example to an exact source panel, or states that no such claim is intended.

## Current examples

| Worked example | Source target | Current label | What matches | Material departures |
|---|---|---|---|---|
| [DANDI 000971 reward analysis](https://github.com/aeronjl/fiberphotometry/blob/main/research/dandi-000971-tutorial-results-v0.1.md) | Seiler et al. (2022), Figures 3E–F and 4E–F | **Partial source-panel reproduction plus adapted robustness analysis** | the new panel matches rewarded/unrewarded PSTHs, DMS/DLS, phenotype, session z-score, and the 0–1.5 s maximum-minus-minimum statistic | one checksum-pinned session from two animals per phenotype; no training-stage model; the separate robustness result intentionally uses fractional dF/F, IRLS, and a mean-window estimand |
| [DANDI 000971 event kernels](dandi-000971-event-kernel.md) | no source panel; methodological extension of the same event data | **Adapted reanalysis** | public cohort, events, regions | joint regularized kernels and held-out prediction were not source-paper analyses |
| [DANDI 000251 transient validation](https://github.com/aeronjl/fiberphotometry/blob/main/research/dandi-000251-transient-results-v0.1.md) | Kim et al. (2020), Figure 2E–H, especially teleport-aligned traces and normalized peaks | **Adapted construct-validation analysis** | public standard/three-teleport sessions and the prespecified 0.6–2.1 s response interval | detects peaks across continuous traces; event enrichment tests detector behavior and does not reproduce the source RPE/value model or normalized-peak statistic |
| [Public IBL feedback report](ibl-feedback-report.md) | none | **Product demonstration** | public observations and animal-level report | no source-paper panel is claimed |
| [IBL–Unspool longitudinal forecast](ibl-unspool-longitudinal.md) | none | **Cross-package reanalysis** | public sessions and prospective held-out comparison | new coarse neural summary and forecasting question |
| Simulation tutorials | none | **Method illustration** | known generating truth | synthetic data are implementation evidence, not biological evidence |

The Seiler source figures plot rewarded and unrewarded peri-stimulus time courses
by phenotype and training stage, then quantify a maximum-rewarded minus
minimum-unrewarded peak score. The Kim source figure plots condition-aligned
calcium traces and normalized peak/residual summaries across teleport conditions.
Those panel semantics—not superficial colors or layout—define the reproduction
targets.

## Priority reproductions

The bounded Seiler reproduction is now the first implemented source-aligned
figure. The next priorities are:

1. **Kim Figure 2E–H, DANDI 000251.** Reproduce three-teleport population traces
   and normalized peak summaries before layering detector sensitivity on top.
2. **Published peri-event bootstrap/permutation example.** Choose a public
   animal-level dataset whose source statistic and resampling denominator can be
   matched exactly, then compare the package's simultaneous-band route.
3. **Multi-site or multi-color source panel.** Select data with independent
   optical calibration so association is not mistaken for successful unmixing.

## Acceptance criteria

A reproduction moves from the priority list into the examples only when:

- source assets are immutable or checksum-pinned;
- source methods and code have been read and cited;
- the figure-generating script starts from those assets, not digitized pixels;
- parity fixtures cover intermediate preprocessing and the final statistic;
- the figure shows the correct independent unit and uncertainty denominator;
- every departure is visible beside the figure; and
- a failed or discordant reproduction is retained as evidence.

## Primary sources

- Seiler et al. (2022), [Dopamine signaling in the dorsomedial striatum promotes
  compulsive behavior](https://doi.org/10.1016/j.cub.2022.01.055), especially
  Figures 3E–F, 4E–F, and the fiber-photometry analysis methods.
- Kim et al. (2020), [A unified framework for dopamine signals across
  timescales](https://doi.org/10.1016/j.cell.2020.11.013), especially Figure 2E–H
  and the 0.6–2.1 s normalized-peak definition.
