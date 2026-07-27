# Methods catalog

This catalog is organized by scientific task. Method availability and scientific
validation are different claims.

The [public-data evidence atlas](public-evidence-atlas.md) places real outputs
beside their estimands, independent units, and retained negative findings.

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/method-question-map.svg" alt="A central scientific question branches to event contrasts, preprocessing sensitivity, overlapping event kernels, and population effects, each with a distinct method and evidence boundary.">
  <figcaption><strong>Method selection starts with the question.</strong> The surrounding workflow can be standardized while each method retains its own assumptions, estimand, and validation evidence.</figcaption>
</figure>

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
- **Experimental:** typed point/interval annotations, explicit onset/offset
  projection, and normalized progress for variable-duration behavior.
- **Gap:** interval merge/split/filter policies and duration/amplitude kernels.

See [the scientist-facing workflow](../product-workflow-v0.1.md) and
[peri-event inference](../peri-event-inference-v0.1.md).

## Test analytic robustness

- **Supported:** named preprocessing and response-window alternatives, prospective
  compatibility rules, complete failure accounting, practical-effect thresholds,
  leave-one-animal-out diagnostics, and grouped unit-safe reports.

See [robustness multiverses](../multiverse-contract-v0.1.md).

## Detect and quantify spontaneous events

**Experimental:** [spontaneous transient detection and long-window descriptive
summaries](../spontaneous-transients-v0.1.md) expose named threshold and local-
baseline alternatives, protect acquisition gaps, retain rejected candidates, and
have a prospective public three-animal sensitivity audit.

This is not yet parity with the GuPPY, PASTa, or prominence methods. Detection
and quantification cannot yet use separate signal scales; compound events,
control-derived frozen thresholds, cut-waveform QC, and animal-aware rate/kinetic
inference remain gaps. Long-window bins are descriptive and do not label slow
fluorescence as a biological tonic component.

## Explain overlapping events and behavior

**Experimental:** behavioral event-kernel encoding jointly estimates overlapping
event responses and continuous covariates, with complete animals or sessions held
out during ridge selection. See the [method contract](../event-kernel-encoding-v0.1.md)
and [worked simulation](../tutorials/event-kernel-simulation.md).
The [public DANDI reproduction](../tutorials/dandi-000971-event-kernel.md)
retains weak animal-held-out prediction and shows why the method remains
experimental. It now includes conditional grouped-jackknife kernel intervals and
session-safe held-out residual diagnostics.

Basis, trial-history, duration/amplitude, and predictor-family contribution
alternatives remain planned, as do simultaneous kernel intervals and formal
coverage calibration.

## Ask long-duration, state, longitudinal, or network questions

The remaining questions are scientifically important but **not yet first-class
workflows**:

- autocorrelation, power spectra, spectrograms, and state/epoch-conditioned
  summaries;
- native behavioral learning-trajectory models; use the experimental
  [Unspool interoperability contract](../unspool-interoperability-v0.1.md) instead;
- across-session photometry comparability before handing summaries to Unspool;
- multiscale long-duration descriptions without assuming a biological
  tonic/phasic decomposition;
- confound-aware multi-site or multi-color association, coherence, phase, and
  coordinate-aware dense-array models;
- sensor-kinetic deconvolution or concentration calibration.

The [capability matrix](capability-matrix.md) explains why these gaps matter and
which should enter the roadmap.

Behavior/pose/state discovery stays outside core. The experimental
[behavioral ecosystem boundary](../ecosystem-interoperability-v0.1.md) now consumes
native-shaped DeepLabCut, SLEAP, Keypoint-MoSeq and BORIS outputs as typed pose,
continuous-covariate, point-event and interval objects. Unspool remains the peer
package for longitudinal behavioral models.
Explicit paired pulses can establish a shared time coordinate through the
[experimental clock synchronization contract](../clock-synchronization-v0.1.md);
cross-clock interpolation remains forbidden.

## Interpret and publish

The package reads and compares evidence bundles, exports NWB, reports provenance,
signs completed manifests, creates deterministic deposits, and prepares validated
unpublished Zenodo drafts.

See [evidence comparison](../reproducibility-comparison-v0.1.md) and
[archival deposition](../archive-deposition-v0.1.md).
