# Methods catalog

This catalog is organized by scientific task. Method availability and scientific
validation are different claims.

## Prepare and validate signals

- **Supported:** channel validity, dropout/repeated-extreme/flat-step QC, sampling
  and gap diagnostics, explicit resampling, low-pass filtering, OLS and robust
  IRLS reference fitting, subtraction or fitted-reference dF/F.
- **Experimental:** double-exponential and asymmetric least-squares control-free
  baselines.
- **Planned:** hemodynamic correction, spectral unmixing, optogenetic-artifact
  handling, and stronger lag diagnostics.

See [preprocessing and QC](../pipeline-v0.1.md) and
[irregular sampling](../irregular-sampling-v0.1.md).

## Ask event-related questions

- **Supported:** event alignment retaining every trial; explicit baseline and
  response windows; candidate/gated/complete event accounting; animal-level
  contrasts; pointwise and simultaneous peri-event intervals.
- **Experimental:** design-aware hierarchical bootstrap, permutation procedures,
  and scalar mixed-model sensitivity summaries.
- **Planned:** trial-level functional mixed models through `fastFMM`.

See [the scientist-facing workflow](../product-workflow-v0.1.md) and
[peri-event inference](../peri-event-inference-v0.1.md).

## Test analytic robustness

- **Supported:** named preprocessing and response-window alternatives, prospective
  compatibility rules, complete failure accounting, practical-effect thresholds,
  leave-one-animal-out diagnostics, and grouped unit-safe reports.

See [robustness multiverses](../multiverse-contract-v0.1.md).

## Ask continuous, longitudinal, or network questions

**Experimental:** behavioral event-kernel encoding jointly estimates overlapping
event responses and continuous covariates, with complete animals or sessions held
out during ridge selection. See the [method contract](../event-kernel-encoding-v0.1.md)
and [worked simulation](../tutorials/event-kernel-simulation.md).
The [public DANDI reproduction](../tutorials/dandi-000971-event-kernel.md)
retains weak animal-held-out prediction and shows why the method remains
experimental.

The remaining questions are scientifically important but **not yet first-class
workflows**:

- learning trajectories and nested longitudinal models;
- tonic/phasic decomposition across hours or days;
- spontaneous transient detection and rate/amplitude/duration summaries;
- multi-site or multi-color coupling and network analyses;
- sensor-kinetic deconvolution or concentration calibration.

The [capability matrix](capability-matrix.md) explains why these gaps matter and
which should enter the roadmap.

## Interpret and publish

The package reads and compares evidence bundles, exports NWB, reports provenance,
signs completed manifests, creates deterministic deposits, and prepares validated
unpublished Zenodo drafts.

See [evidence comparison](../reproducibility-comparison-v0.1.md) and
[archival deposition](../archive-deposition-v0.1.md).
