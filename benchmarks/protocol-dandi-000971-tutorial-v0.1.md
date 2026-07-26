# DANDI 000971 end-to-end tutorial protocol v0.1

Status: **frozen before selected-cohort fluorescence outcomes** (27 July 2026)

## Product question

Can a scientist start with public raw NWB photometry, audit the acquisition and
event denominators, run one declared analysis plus a bounded preprocessing
multiverse, preserve animal-level inference, and obtain a rerunnable evidence
bundle without rewriting analysis code?

This is a product demonstration and descriptive reanalysis, not a reproduction of
every result in Seiler et al. (2022). The source paper analyzed rewarded minus
unrewarded nose-poke responses and reported a DMS-specific relationship with later
punishment resistance. The tutorial fixes the narrower DMS event contrast but does
not test phenotype differences or the paper's predictive claim.

## Frozen source and cohort

- Immutable DANDI:000971 version `0.260213.1851`, DOI
  `10.48324/dandi.000971/0.260213.1851`, licensed CC-BY-4.0.
- Six explicitly pinned NWB assets: two animals from each published PR, DPR, and
  PS phenotype family.
- One raw photometry-bearing RI60-family session per animal, with DMS/DLS calcium
  and matched isosbestic measurements.
- The asset IDs, byte sizes, and SHA-256 digests are fixed in
  [`dandi-000971-tutorial-manifest-v0.1.json`](dandi-000971-tutorial-manifest-v0.1.json).
- Published phenotype labels diversify acquisition and behavioral conditions only.
  They are not an analysis factor and the balanced tutorial sample does not
  estimate phenotype prevalence.
- A structurally invalid asset is retained as a failure and is not replaced after
  fluorescence outcomes are accessed.

The bounded download is 2,202,726,004 bytes. Files are cached outside the
repository and rechecked against their immutable digests.

## Frozen extraction and event audit

1. Require the pinned four-column calcium/isosbestic schema for DMS and DLS.
2. Block-average all fluorescence columns to approximately 20 Hz while preserving
   source rate, block size, achieved rate, and discarded-tail counts.
3. Find the one active nose-poke side that has both nose-poke and reward event
   streams.
4. Require every reward timestamp to match exactly one active nose-poke timestamp;
   rewarded pokes are that subset and all remaining active pokes are unrewarded.
5. Retain only events whose complete `[-5, 1.5]` second window lies inside the
   acquired recording. This is a timestamp-only structural gate, not a signal or
   effect-size gate.
6. Report candidate, boundary-complete, rewarded, and unrewarded counts for every
   animal before preprocessing.

## Frozen estimand and primary workflow

- Outcome: mean DMS corrected fluorescence from 0 to 1.5 seconds after an active
  nose poke, minus its mean from -5 to 0 seconds.
- Contrast: rewarded minus unrewarded active nose pokes.
- Aggregation unit: animal. Events are never treated as independent animals.
- Intent: descriptive; no random assignment of reward labels is claimed.
- Primary inference: paired Student interval across six animal-level contrasts.
- Primary preprocessing: fourth-order 3 Hz zero-phase low-pass filtering of signal
  and reference, followed by robust IRLS reference fitting and fitted-reference
  dF/F.
- Required assumptions are acknowledged explicitly in the versioned analysis plan:
  independent animals, an estimand matching the descriptive question,
  approximately Gaussian animal differences, and complete within-animal pairs.

The source study used zero-phase filtering, an OLS fit of 405 nm to 465 nm, and
fitted-reference dF/F. Robust fitting is the tutorial reference because it reduces
the influence of transient deviations on the reference fit; OLS remains visible as
a defensible sensitivity analysis rather than being silently displaced.

## Frozen multiverse

The estimand, animals, event labels, QC policy, and aggregation unit never change.
Two decision nodes create eight universes:

1. Preprocessing: unfiltered OLS, unfiltered IRLS, 3 Hz filtered OLS, or 3 Hz
   filtered IRLS.
2. Response window: 0-0.5 seconds or 0-1.5 seconds, with the same -5-0 second
   baseline.

The named reference universe is `filtered_irls` with the 1.5-second response.
Every universe uses dF/F units. All successful, blocked, incompatible, non-finite,
and failed outcomes remain in the artifact. Leave-one-animal-out estimates are
computed for the reference universe.

## Interpretation rules

- Lead with animal-level estimates and uncertainty, not event count or the number
  of nominally significant universes.
- Report the reference estimate, full successful estimate range, direction
  stability, decision summaries, and leave-one-animal-out range.
- Do not infer that phenotype causes or moderates the contrast.
- Do not call the isosbestic channel biologically inert or motion-specific.
- Do not describe agreement with the source paper as independent confirmation:
  the same public recordings are being reanalyzed.
- A failed universe is a workflow outcome, not evidence for a null biological
  effect. A structurally rejected asset is a product finding, not an invitation to
  change the cohort after inspecting results.

## Frozen deliverables

The executable tutorial writes `preflight.json`, `primary-analysis.json`,
`multiverse.json`, `report.html`, and a checksum-bearing `manifest.json`. The
Markdown tutorial explains the same run without duplicating implementation logic.
A synthetic NWB regression fixture exercises the complete scientific shape in CI;
the full public cohort remains an explicit network execution.

## Sources available at freeze time

- Seiler et al. (2022), [source study](https://doi.org/10.1016/j.cub.2022.01.055).
- Seiler et al. (2026), [immutable DANDI dataset](https://doi.org/10.48324/dandi.000971/0.260213.1851).
- DANDI, [official example notebook](https://docs.dandiarchive.org/example-notebooks/000971/lernerlab/seiler_2024/fiber_photometry_example_notebook/).
- CatalystNeuro, [NWB conversion source](https://github.com/catalystneuro/lerner-lab-to-nwb).
- Jean-Richard-dit-Bressel & McNally (2025), [artifact-correction comparison](https://doi.org/10.1117/1.NPh.12.2.025003).
