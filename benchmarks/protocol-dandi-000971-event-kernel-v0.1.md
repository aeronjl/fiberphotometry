# DANDI 000971 behavioral event-kernel protocol v0.1

Status: **frozen before event-kernel model execution** (27 July 2026)

## Product question

Can the experimental encoding API express and execute a literature-shaped model
on immutable public raw NWB recordings, separate the response common to active
nose pokes from the incremental response associated with reward, and report
generalization to completely held-out animals?

This is a descriptive reanalysis of Seiler et al. (2022), not an independent
replication or a causal model of reward. The public fluorescence outcomes were
already accessed for the repository's earlier scalar DANDI 000971 tutorial. This
protocol is therefore not outcome-blind with respect to those recordings. It is
frozen before inspecting any event-kernel coefficients, selected penalties, or
cross-validated encoding scores.

## Frozen source and cohort

- Immutable DANDI:000971 version `0.260213.1851`, DOI
  `10.48324/dandi.000971/0.260213.1851`, CC-BY-4.0.
- The same six NWB assets and checksums pinned in
  [`dandi-000971-tutorial-manifest-v0.1.json`](dandi-000971-tutorial-manifest-v0.1.json):
  two animals from each published PR, DPR, and PS family.
- One RI60-family session per animal, containing DMS and DLS calcium signals,
  their matched 405-nm references, active nose-poke times, and reward times.
- Published phenotype families describe cohort selection only. They are not
  predictors, strata, or outcomes in this small model.
- Cached files must match their pinned byte sizes and SHA-256 checksums. Source
  failures are retained and no animal is replaced after execution.

## Frozen preprocessing

For each asset:

1. Validate the four expected DMS/DLS calcium/reference columns.
2. Block-average the approximately 1-kHz source recording to approximately 20 Hz,
   retaining achieved rate and discarded-tail provenance.
3. Apply a fourth-order 3-Hz zero-phase Butterworth filter to signal and reference.
4. Fit the filtered 405-nm reference to each calcium signal with robust Huber IRLS.
5. Use fitted-reference dF/F as the continuous response.

This matches the reference preprocessing from the completed public-data tutorial.
It is fixed here to isolate the encoding-model question; preprocessing alternatives
are deferred to a later event-kernel multiverse.

## Frozen event design and estimand

Every active nose poke contributes an impulse to `active_poke`. Every reward time
contributes an impulse to `reward_increment`. The NWB conversion records each
reward timestamp as exactly one active-poke timestamp, and the adapter must validate
that relation.

The joint Gaussian FIR model is fitted separately to DMS and DLS across each full
recording:

- `active_poke` lag window: **−1.0 to +3.0 seconds**;
- `reward_increment` lag window: **−1.0 to +3.0 seconds**;
- sample grid: the achieved approximately 20-Hz grid;
- intercept: one pooled intercept per region;
- no continuous covariates, because movement or video measurements are absent
  from these pinned files;
- overlapping predictors and nearby trials are retained rather than censored.

The `active_poke` kernel estimates the response associated with an unrewarded
active poke. The `reward_increment` kernel estimates the additional response for
a rewarded poke, conditional on the common active-poke kernel. These are pooled
descriptive coefficients in dF/F units, not causal effects and not animal-level
confidence intervals.

## Frozen validation

- Ridge candidates: `0`, `0.1`, `1`, `10`, `100`, and `1000`.
- Six folds, each holding out one complete animal and its complete session.
- Continuous scaling policy remains training-fold-only, although this design has
  no continuous covariates.
- Select the candidate with the largest mean animal-wise held-out R²; ties prefer
  the smaller penalty.
- Retain every fold's animal identity, observation count, and R².
- Fit the selected model once to all six animals for descriptive kernels.

No minimum R² or expected kernel direction is an acceptance gate. Negative held-out
R² is a valid scientific result showing that the sparse declared event design does
not predict a new animal better than its held-out mean. Product acceptance instead
requires deterministic execution, complete group isolation, finite retained
results, and agreement between reruns.

## Frozen interpretation and deliverables

Report event denominators, selected penalties, all held-out scores, DMS and DLS
kernels, and explicit limitations. Do not:

- call the reward increment a reward-prediction error;
- infer DMS-versus-DLS population differences without animal-level uncertainty;
- interpret held-out R² as coefficient significance;
- claim motion correction from the isosbestic channel;
- describe reuse of the source recordings as independent confirmation.

The executable writes one versioned JSON evidence artifact and a checksum manifest.
The documentation must connect this example to the method contract and expose any
product limitation encountered during real-data execution.

## Sources available at freeze time

- Seiler et al. (2022), [source study](https://doi.org/10.1016/j.cub.2022.01.055).
- Seiler et al. (2026), [immutable DANDI dataset](https://doi.org/10.48324/dandi.000971/0.260213.1851).
- DANDI, [official example notebook](https://docs.dandiarchive.org/example-notebooks/000971/lernerlab/seiler_2024/fiber_photometry_example_notebook/).
- Simpson et al. (2024), [fiber-photometry analysis primer](https://pmc.ncbi.nlm.nih.gov/articles/PMC10939905/).
- [Event-kernel method contract](../docs/event-kernel-encoding.md).
