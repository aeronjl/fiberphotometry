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
  baselines; prospective optogenetic-pulse masks with separate recovery/control
  diagnostics; open versioned sensor profiles with wavelength, detector, reference,
  lag, and event-validity evidence; independently identified wavelength-aware
  linear optical unmixing with rank, conditioning, missing-pattern, residual, and
  channel-holdout evidence.
- **Planned:** automatic artifact correction, nonlinear or time-varying optical
  mixing, and stronger validated lag diagnostics.

See [preprocessing and QC](../pipeline-v0.1.md) and
[irregular sampling](../irregular-sampling-v0.1.md). For stimulation and optical
interpretation safeguards, see [optogenetic artifacts and sensor validity](../optical-validity-v0.1.md).
For calibrated multi-wavelength or multi-color source separation, see
[wavelength-aware optical unmixing](../optical-unmixing-v0.1.md).

## Ask event-related questions

- **Supported:** event alignment retaining every trial; explicit baseline and
  response windows; candidate/gated/complete event accounting; animal-level
  contrasts; pointwise and simultaneous peri-event intervals.
- **Experimental:** design-aware hierarchical bootstrap, permutation procedures,
  and scalar mixed-model sensitivity summaries.
- **Planned:** trial-level functional mixed models through `fastFMM`.
- **Experimental:** typed point/interval annotations, explicit onset/offset and
  duration modulation, and first-class normalized-progress kernels.
- **Gap:** interval merge/split/filter, contextual-label, and overlap policies.

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

Candidate detection is now separate from quantification on non-z-scored dF/F, with
named GuPPY-, PASTa-, and prominence-compatible families, compound-event metadata,
exposure-adjusted session summaries, and animal-aware rate/kinetic contrasts.
Detector-bound baseline/control threshold objects, native gap-bounded waveform
cutouts, explicit boundary/rail/flat-step/neighbor QC, and optional pre-quantification
refusal are available. Broader raw-signal/manual validation remains a gap. Long-window
bins are descriptive and do not label slow fluorescence as a biological tonic
component.

## Explain overlapping events and behavior

**Experimental:** behavioral event-kernel encoding jointly estimates overlapping
event responses and continuous covariates, with complete animals or sessions held
out during ridge selection. See the [method contract](../event-kernel-encoding-v0.1.md)
and [worked simulation](../tutorials/event-kernel-simulation.md).
The [public DANDI reproduction](../tutorials/dandi-000971-event-kernel.md)
retains weak animal-held-out prediction and shows why the method remains
experimental. It now includes conditional grouped-jackknife kernel intervals and
session-safe held-out residual diagnostics. The
[model-multiverse workflow](../event-kernel-multiverse-v0.1.md) compares named
whole-design alternatives, retains failures, and permits score deltas only on
identical retained timestamps.

Full-FIR and raised-cosine bases, explicit within-session event history, duration
modulation, and normalized-progress kernels are available as named alternatives.
The [predictor-family contribution workflow](../predictor-family-contributions-v0.1.md)
adds strictly paired full-versus-reduced held-out comparisons while rejecting
changed predictors, tuning policies, or denominators. Simultaneous kernel intervals
remain opt-in after the first
[480-study calibration](../event-kernel-interval-calibration-v0.1.md) missed its
normalized-progress gate; pointwise group sensitivity remains the default. See the
[previous-outcome tutorial](../tutorials/event-kernel-history.md) and
[variable-duration tutorial](../tutorials/variable-duration-kernels.md).

## Ask long-duration, state, longitudinal, or network questions

Gap-aware single-signal analysis is now an **experimental first-class workflow**:

- autocorrelation retains within-run pair counts at every lag;
- Welch PSD aggregates complete windows across continuity runs;
- spectrograms retain window bounds and edge distances without padding;
- user-supplied state epochs remain separate analysis partitions; and
- band-power contrasts aggregate sessions before animal-level inference.

Physical-time long-duration analysis is also an **experimental first-class
workflow**. Named seconds-to-hours windows expose temporal coverage, acquired
samples, gap and epoch boundaries, sample- versus time-weighted observables, and
window→session→animal contrasts without assigning biological tonic/phasic labels.

See [gap-aware time, frequency, and state analysis](../spectral-state-analysis-v0.1.md)
and [multiscale long-duration summaries](../multiscale-long-duration-v0.1.md).

Guarded multi-site and multi-color analysis is also an **experimental first-class
workflow**. It adds explicit pair/site/sensor/optical metadata, shared-clock and
joint-validity evidence, lagged association with declared event/behavior
residualization, blocked within-session nulls, crosstalk review flags,
state-conditioned coherence/phase, and session-to-animal inference. See
[multi-site and multi-color association](../multisite-multicolor-analysis-v0.1.md).

Coordinate-aware dense arrays are an **experimental first-class workflow**. Three
or more channels in one declared geometry produce a complete edge/exclusion
ledger, physical-distance summaries, a node-label spatial null, and fixed
edge→session→mouse inference. See
[coordinate-aware dense multi-fiber networks](../spatial-network-v0.1.md).

The remaining questions are scientifically important but **not yet first-class
workflows**:

- native behavioral learning-trajectory models; use the experimental
  [Unspool interoperability contract](../unspool-interoperability-v0.1.md) instead;
- across-session photometry comparability before handing summaries to Unspool;
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
