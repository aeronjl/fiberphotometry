# Literature and capability audit v0.2

**Audit date:** 2026-07-27
**Question:** Does fipha cover the analyses contemporary
neuroscientists actually use and need?

## Executive conclusion

**Not yet.** fipha already has a differentiated and unusually rigorous
core for event-locked, multi-animal analysis: labelled identity, gap-aware
preprocessing, animal-level inference, whole-waveform uncertainty, multiverse
robustness, NWB provenance, and publication evidence. That remains the right
product foundation.

The first audit nevertheless made three mistakes:

1. it treated broad method labels as coverage even when the implementation only
   covered one member of a contested method family;
2. it underweighted continuous-state, time/frequency, and variable-duration
   behavior analyses that appear in both established tools and current papers;
3. it did not separate *detection* of spontaneous events from quantification on
   an interpretable signal scale.

The package is therefore credible for one important scientific question—how a
signal changes around discrete events across animals—but is not yet a
field-comprehensive photometry analysis product.

## How this audit was conducted

This is a structured, purposive coverage review rather than a systematic review
or meta-analysis. Sources were selected across four strata:

- field primers and statistical/method papers;
- established open-source tool papers;
- recent applications spanning evoked, spontaneous, longitudinal, naturalistic,
  multi-site, multi-sensor, and sleep/state experiments;
- recent COSYNE programmes as a horizon scan, not as validation evidence.

The audit asks of each method family:

1. Is it used to answer a recurring scientific question?
2. Is it implemented, merely representable in the data model, or absent?
3. Does the implementation preserve the animal/session hierarchy?
4. Are choices, failure modes, and units explicit?
5. Is there public or controlled validation and a worked example?

“Supported” requires all five. A function existing in the source tree is not by
itself coverage.

## Papers read and what they changed

| Source | What it establishes for the product |
|---|---|
| [Simpson et al. (2024), *Neuron* primer](https://pmc.ncbi.nlm.nih.gov/articles/PMC10939905/) | Raw and intermediate inspection, operation order, sensor-specific filtering and controls, time warping, event-kernel regression, and animal-level inference are distinct requirements. |
| [Jean-Richard-dit-Bressel and McNally (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11957252/) | Low-pass filtering, IRLS reference fitting, and fitted-reference dF/F perform well in their tests; invalid periods must be removed first; local rebaselining and null-relative normalization are materially different from session z-scoring. |
| [Jean-Richard-dit-Bressel et al. (2020)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7017714/) | Whole-waveform bootstrap/permutation analysis avoids arbitrary scalar windows, but temporal multiplicity and the independent unit must be explicit. |
| [Loewinger et al. (2025)](https://elifesciences.org/articles/95802) | Trial-level functional mixed models preserve the full time course, nested variation, and covariate effects that subject averages discard. |
| [Wallace et al. (2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC13245556/) | Session z-scoring can erase or distort pharmacological changes in spontaneous dopamine kinetics; candidate detection and kinetic quantification should be separable, with final measurements made on non-z-scored dF/F. |
| [Donka et al. (2025), PASTa](https://pmc.ncbi.nlm.nih.gov/articles/PMC12224222/) | Local mean/minimum/last-minimum baselines, control- or baseline-derived thresholds, compound events, cut waveforms, and event-defined bins are part of practical transient analysis. |
| [Bruno et al. (2021), pMAT](https://pmc.ncbi.nlm.nih.gov/articles/PMC7853640/) | Batch ingestion, inspectable intermediate traces, event heatmaps, configurable peak/AUC windows, and a spike-count workflow remain common user expectations. |
| [Sherathiya et al. (2021), GuPPY](https://pmc.ncbi.nlm.nih.gov/articles/PMC8688475/) | Its spontaneous detector removes high-amplitude points before estimating a moving MAD baseline; a generic rolling MAD is not method parity. |
| [Murphy et al. (2023), PhAT](https://pmc.ncbi.nlm.nih.gov/articles/PMC10246504/) | Interactive comparison of raw, reference, corrected, and alternative-baseline traces is scientific QC, not cosmetic UI; cross-trace similarity is used for both QC and exploratory multi-region work. |
| [Bridge et al. (2024), FiPhA](https://pmc.ncbi.nlm.nih.gov/articles/PMC10885510/) | Scientists use interval-event filters, coalescing/bout rules, PSD, autocorrelation, spectrograms, video-derived states, and spectral unmixing in addition to peri-event averages. |
| [Conlisk et al. (2023), Pyfiber](https://pmc.ncbi.nlm.nih.gov/articles/PMC10545777/) | Complex operant experiments require named intervals, contextual event rules, multi-session extraction, and configuration-driven behavior/photometry fusion. |
| [Drakopoulos et al. (2025), FiPhoPHA](https://pmc.ncbi.nlm.nih.gov/articles/PMC12363645/) | Accessible whole-waveform bootstrap and permutation inference remains an adoption need even when a package offers a different valid inferential estimand. |
| [Markowitz et al. (2018)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6026065/) | Naturalistic behavioral motifs have variable duration; photometry has been linearly time-normalized to motif progress and used with held-out decoding. Behavior discovery belongs elsewhere, but aligned state/progress inputs belong here. |
| [Mohebi et al. (2024)](https://www.nature.com/articles/s41593-023-01566-3) | Application papers combine spontaneous autocorrelation, event kinetics, reward-history integrators, regression, and reinforcement-learning-derived covariates. |
| [Touponse et al. (2025)](https://www.nature.com/articles/s41586-025-10046-6) | A current high-impact application uses lagged behavioral kernels, subject random effects, cross-validation, and leave-one-predictor-out contribution analysis. |
| [Bouabid et al. (2025)](https://www.nature.com/articles/s41467-025-60462-5) | High-density chronic photometry requires spatial coordinates, component-specific features, learning trajectories, and mouse-aware mixed models across tens of sites. |
| [Jang et al. (2026)](https://www.nature.com/articles/s41593-026-02227-x) | Current experiments combine video pose, multi-channel sensor/control metadata, TMAC correction, event discrimination, and simultaneous dopamine/acetylcholine measurements. |
| [Potter et al. (2026)](https://www.nature.com/articles/s41386-026-02351-z) | Dual-signal applications use cross-correlation, multitaper coherence, phase offset, Hilbert phase, and state-conditioned comparisons. |

The source list is intentionally broader than package papers. Tool papers show
what interfaces users expect; application papers show what they actually need to
publish.

## Coverage verdict by scientific question

### 1. Can I trust and inspect the corrected signal?

**Status: strong core, incomplete scientific contract.**

Supported today: sampling/gap QC, filtering, OLS and IRLS reference fitting,
subtractive and divisive outputs, experimental signal-only baselines, operation
provenance, and initial raw/corrected diagnostics.

Missing or partial:

- an enforced/reported processing-order contract;
- null-relative and local-rebaseline normalization families;
- sensor/isobestic-aware validity checks rather than a generic “reference” role;
- control-animal/control-sensor roles and negative-control comparison reports;
- saturation, bleed-through, hemodynamic, and optogenetic-crosstalk diagnostics;
- a scientist-facing full-session/zoomed comparison of every intermediate.

The immediate need is not ten more detrenders. It is a typed normalization and
control contract that prevents scientifically incompatible operations from
looking interchangeable.

### 2. What changes around a discrete event?

**Status: strongest supported family.**

Event retention, explicit denominators, animal-level scalar inference,
pointwise/simultaneous waveform intervals, and multiverse reporting are real
strengths. They exceed several established packages in hierarchy and provenance.

Still missing:

- exact documented parity examples for the published waveform
  bootstrap/permutation approach;
- the `fastFMM` trial-level functional mixed-model bridge;
- interval-valued behaviors with minimum/maximum duration, coalescing,
  refractory, contextual, and first/last-occurrence filters;
- onset, offset, and normalized-progress alignment for variable-duration bouts;
- first-class event heatmaps and individual-animal/trial diagnostics in the
  scientist-facing report.

Time normalization must be declared and sensitivity-tested; it must not silently
replace real duration with an apparently physical time axis.

### 3. Which overlapping events and behaviors explain the continuous signal?

**Status: experimental, correctly started, not complete.**

The FIR event-kernel implementation, continuous covariates, animal/session-held-
out ridge selection, jackknife sensitivity, and residual diagnostics cover the
minimum credible encoding-model skeleton.

Needed next:

- basis alternatives (FIR and splines) in the multiverse;
- event amplitudes, durations, interactions, and explicit trial-history/RL
  covariates;
- lagged or basis-expanded continuous covariates;
- leave-one-predictor-family-out contribution analysis;
- simultaneous kernel bands and formal coverage calibration;
- conditional mixed-effects kernels or a documented route to them;
- a public application with useful held-out prediction, while retaining the
  existing negative result.

Nonlinear models can remain an extension boundary until the linear design,
validation, and interpretation contract is mature.

### 4. Are there spontaneous transients, and how do their kinetics change?

**Status: experimental product family with important validation gaps.**

The product API now separates candidate detection from quantification, retains
gap boundaries, and provides named GuPPY two-threshold MAD, PASTa local-baseline,
and Wallace-style z-height/prominence families. Prominence timestamps can be
quantified on non-z-scored dF/F; PASTa includes last-local-minimum baselines; and
nearby accepted events receive compound-group metadata.

Missing:

- thresholds learned from a declared baseline epoch, control session, or control
  cohort and then frozen across conditions;
- maximum fall-search rules, incomplete/compound status, T80/decay and slope
  measures, and exported cut waveforms;
- behavior-defined bins/epochs;
- manual/biological ground truth across sensors and acquisition systems.

Animal-level rate and kinetic contrasts are now available: count/exposure is
pooled within animal, kinetics are summarized session-to-animal, and resampling
or condition randomization operates on animals rather than detected events.

The existing public dLight result predates the separated detector families. It
remains evidence that the method family matters, not validation that one detector
is correct.

### 5. How does activity vary over long recordings or physiological states?

**Status: major gap omitted by v0.1.**

The field uses whole-session autocorrelation, power spectra, spectrograms,
state/epoch summaries, and relationships to EEG/EMG, pupil, movement, sleep, and
circadian phase. Dual-signal studies also use coherence and phase.

Needed:

- gap-aware PSD/autocorrelation with explicit detrending and frequency units;
- spectrogram/time-frequency results with edge and missing-data flags;
- user-supplied state/epoch tables and state-conditioned summaries;
- multiscale baseline/tonic descriptions that do not equate a filter band with a
  biological mechanism;
- hierarchical comparisons of spectral/state summaries across animals;
- cross-spectral methods only after single-signal spectral validation.

This family should precede an ambitious “tonic dopamine” abstraction. Tonic and
phasic are biological claims; trend, band-limited power, and detected events are
observable analysis objects.

### 6. How do signals relate across sites, sensors, or cell classes?

**Status: data-model-compatible, analysis gap.**

Recent work ranges from two-color recordings to more than 50 chronic sites. A
pairwise Pearson correlation is not sufficient: shared movement, task events,
bleaching, spectral crosstalk, and common controls can create coupling.

Needed in stages:

1. paired channel/site metadata, alignment QC, and crosstalk/control diagnostics;
2. zero-lag and lagged association with blocked or animal-level uncertainty;
3. event- and behavior-residualized association;
4. coherence/phase for scientifically justified bands;
5. spatial-coordinate covariates and animal-aware site models for dense arrays.

Granger-causal or generic network claims should remain out of scope until sampling,
stationarity, common-driver, and model-identification assumptions can be defended.

### 7. How does the signal change across learning or days?

**Status: interoperable, with a photometry-specific gap.**

The validated Unspool handoff is the right boundary for longitudinal behavioral
and learning models. fipha should not duplicate that package.

fipha must still own:

- session/channel identity and acquisition comparability;
- expression, illumination, coupling, and baseline-normalization diagnostics;
- within-session estimands and uncertainty passed to Unspool;
- explicit flags when across-day amplitude comparison is not identified;
- literature-shaped examples linking a photometry result bundle to an Unspool
  study.

### 8. Can I connect photometry to rich behavior without rebuilding my task?

**Status: basic timestamps supported; interval workflow incomplete.**

Pose estimation, video tracking, and behavioral state discovery remain outside
core. The package should consume their outputs through stable event, interval,
continuous-covariate, and normalized-progress schemas.

The practical gap is a behavior-table contract supporting:

- point events and start/stop intervals;
- contextual labels and nested task phases;
- bout merge/split/filter rules;
- frame/TTL clock-alignment evidence;
- continuous pose, speed, pupil, and latent-state probabilities;
- direct handoffs from common tabular outputs and Unspool.

## Revised product boundary

### Core product

- inspectable, sensor-aware preprocessing and QC;
- discrete-event and interval/bout alignment;
- hierarchical event-waveform inference;
- spontaneous-event method families;
- encoding models with held-out validation;
- single-signal time/frequency/state analysis;
- guarded multi-signal/site association;
- reproducible multiverses, reports, NWB, and publication evidence.

### Interoperability rather than duplication

- behavior/pose discovery: DeepLabCut, SLEAP, Keypoint-MoSeq, BORIS, Unspool;
- longitudinal behavioral inference: Unspool;
- acquisition/demodulation: vendor and open acquisition tools;
- specialized RL model fitting: consume declared latent variables and histories;
- Raman and instrument-specific optical models: extensions;
- arbitrary nonlinear prediction and causal network discovery: extensions.

## Revised priority order

### P0 — correct claims and make method families explicit

1. update the capability matrix and methods navigation;
2. distinguish supported, experimental, representable, and gap;
3. document detector non-parity and detection-versus-quantification risk;
4. add a literature-to-capability traceability table to release review.

### P1 — close scientific-validity gaps in existing families

1. transient detection/quantification separation, published detector families,
   cut-waveform QC, and hierarchical rate/kinetic inference;
2. interval/bout filtering plus onset/offset/progress alignment;
3. `fastFMM` bridge and a numerical reproduction;
4. encoding basis/history/contribution multiverses and interval calibration;
5. typed normalization/control/sensor contracts and richer intermediate QC.

### P2 — add the missing mainstream analysis family

1. single-signal autocorrelation, PSD, spectrogram, and state epochs;
2. multiscale/long-duration summaries with non-biological names;
3. public sleep/state or long-duration tutorial with animal-level inference.

### P3 — multi-signal and optical breadth

1. paired channel/site workflows and confound-aware association;
2. state-conditioned coherence/phase with blocked uncertainty;
3. spatial mixed models for dense multi-fiber studies;
4. spectral unmixing, hemodynamic correction, and optogenetic crosstalk masks;
5. native Doric, Neurophotometrics, and pyPhotometry adapters.

## Field-coverage acceptance rule

A method family is not complete until it has:

- a named scientific estimand and units;
- typed inputs and explicit invalid states;
- method alternatives represented as a reproducible multiverse where contested;
- animal/session-aware uncertainty;
- simulation or numerical parity plus an independent public/controlled fixture;
- diagnostic figures and a scientist-facing result report;
- a literature-shaped worked example with limitations;
- machine-readable provenance and round-trip evidence.

This rule deliberately prevents breadth-by-API. The goal is not to accumulate
functions; it is to make the main analyses in contemporary photometry defensible,
discoverable, and reproducible.

## Bottom line

The package is still aimed at the right product. Its advantage is not that it can
eventually contain every algorithm; it is that it can unify the field's recurring
analysis families under one evidential contract. The literature supports that
opportunity. It also shows that the next work should deepen spontaneous and
behavior-interval validity, add functional mixed models, and introduce
time/frequency/state analysis before claiming comprehensive field coverage.
