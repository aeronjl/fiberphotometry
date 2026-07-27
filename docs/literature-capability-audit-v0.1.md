# Literature and capability audit v0.1

**Audit date:** 2026-07-27  
**Question:** Does FiberPhotometry cover the analyses a contemporary
neuroscientist is likely to need, and can a scientist discover that coverage?

## Conclusion

Not yet comprehensively. The package has an unusually strong foundation for
auditable **event-locked, multi-animal analysis**: explicit data identity,
preprocessing alternatives, event denominators, animal-aware inference,
whole-waveform uncertainty, multiverse robustness, NWB evidence, and publication
provenance. That is a coherent and valuable product core.

The field, however, uses photometry for more than event-triggered contrasts.
Contemporary work increasingly asks encoding-model, longitudinal, spontaneous,
multi-region, multi-sensor, and long-duration questions. Those workflows are
either absent or only representable as raw channels today. The old documentation
also obscured the strong core because it was organized by implementation history
rather than scientific question.

## What the field expects

### 1. Inspectable preprocessing, not a hidden corrected trace

The 2024 Neuron primer describes filtering, bleaching correction, movement
correction, normalization, raw/intermediate inspection, behavioral regression,
and group inference as distinct stages. It stresses that preprocessing varies
substantially across studies and that trials must not be treated as independent
animals ([Simpson et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10939905/)).
The 2025 artifact-correction study specifically motivates filtering, robust
reference fitting, and fitted-reference dF/F while warning that operation order
matters ([Jean-Richard-dit-Bressel and McNally,
2025](https://doi.org/10.1117/1.NPh.12.2.025003)).

**Coverage:** strong for common single-signal/reference workflows; experimental
for signal-only baselines. Missing wavelength-aware hemodynamic correction,
spectral unmixing, optogenetic-pulse artifacts, and native lock-in/demodulation.

### 2. Event-related inference without arbitrary peak/AUC fishing

Waveform bootstrap and permutation methods were developed to avoid uncorrected
pointwise testing and fragile post-hoc summaries
([Jean-Richard-dit-Bressel et al.,
2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7017714/)). Functional linear mixed
models go further by preserving trial-level time courses, modeling nested random
effects, and providing joint intervals
([Loewinger et al., 2025](https://elifesciences.org/articles/95802)). FiPhoPHA's
2025 Python workflow reflects continued demand for accessible bootstrap and
permutation analysis ([Martins et al.,
2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12363645/)).

**Coverage:** strong animal-level pointwise/simultaneous intervals and explicit
resampling units; partial scalar mixed models; missing the promised `fastFMM`
trial-level bridge. The package should also document exactly how its animal-level
estimand differs from FLMM's trial-level conditional estimands.

### 3. Behavioral encoding models and trial history

Modern photometry studies often estimate overlapping contributions of cues,
actions, rewards, movement, and latent behavioral variables rather than selecting
one alignment event. The 2024 primer explicitly discusses regression with
event-related kernels. At COSYNE 2024, Sanchez Araujo et al. modeled three
striatal photometry signals across learning with a Gaussian GLM containing task
events, alongside a hierarchical behavioral GLM
([COSYNE 2024 program, abstract 2-005](https://www.cosyne.org/s/Cosyne2024_program_book.pdf)).
The same program includes multiple-linear-regression analyses of current and past
outcomes/actions and RL-linked photometry analyses.

**Coverage:** missing. This is the largest mainstream analysis gap. A first-class
encoding workflow needs lagged event kernels, continuous covariates, trial-history
features, regularization, grouped cross-validation, coefficient uncertainty, and
animal/session hierarchy. A generic array regression helper would not be enough.

### 4. Learning and long-duration recordings

The COSYNE example analyzes acquisition trajectories across animals, not merely
stationary sessions. Long-duration photometry adds different questions: tonic
baseline dynamics, phasic transients, circadian structure, discontinuous sessions,
and correction choices operating at different time scales. A 2025 review
explicitly separates tonic and phasic analytical modes
([Pourmir et al., 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12663613/)); a
2026 workflow emphasizes revisitable correction and event analysis at both
multiday and session scales ([Pourmir et al.,
2026](https://doi.org/10.64898/2026.04.21.719944)).

**Coverage:** missing beyond ordinary multi-session provenance. Add an explicit
longitudinal data axis, across-session normalization diagnostics, multiscale
tonic summaries, locally defined phasic events, and nested time/session/animal
models. Do not force long-duration data through peri-event windows.

### 5. Spontaneous transient analysis

Many calcium, astrocyte, sleep, circadian, pharmacology, and disease studies ask
about transient frequency, amplitude, duration, area, or inter-event intervals
without an external trigger. PASTa identifies this as a recurring gap and uses
local-baseline peak detection rather than one absolute session threshold
([PASTa protocol, 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12224222/)).

**Coverage:** missing. This needs definition/versioning of detected events,
negative controls, sensitivity analysis over local baseline and refractory
choices, and animal-aware inference on event-derived outcomes.

### 6. Multi-site, multi-color, and network questions

Photometry can now record multiple regions, pathways, sensors, or cell classes.
Spectrally resolved systems explicitly unmix green and red indicators
([Meng et al., 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC5957785/)), while
recent work measures astrocyte-neuron relationships across regions
([Liu et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11566604/)). COSYNE
2024 reported simultaneous measurement of four neuromodulators in amygdala, and
COSYNE 2025 featured whole-striatum multi-fiber dopamine measurements for a
distributional-RL question
([Matias et al., 2025](https://world-wide.org/conf/cosyne-25/broadly-projecting-mesolimbic-dopamine-f2b72b4a)).

**Coverage:** the labelled data model can hold multiple channels/sites, but the
scientist-facing workflow chooses one analysis channel. Missing capabilities
include spectral mixing/crosstalk diagnostics, paired channel contrasts,
cross-correlation with lag uncertainty, partial associations controlling shared
behavior, and hierarchical network summaries. Naive correlation should not become
the default because shared events and slow drift can create apparent coupling.

### 7. Sensor-aware interpretation

Fluorescent sensors differ in affinity, dynamic range, kinetics, saturation,
photostability, pH sensitivity, and relation to the biological quantity. Bulk
calcium photometry may primarily reflect nonsomatic calcium and is not a direct
spike count ([Legaria et al.,
2022](https://www.nature.com/articles/s41593-022-01152-z)). The field now spans
calcium, dopamine, acetylcholine, serotonin, norepinephrine, peptides, voltage,
metabolic signals, and even spectroscopic measurements.

**Coverage:** metadata can record sensor identity, but analysis is not yet
sensor-aware. Needed features are a sensor registry with citations and declared
kinetic/interpretive constraints, saturation warnings, optional forward-model
or deconvolution adapters, and explicit refusal to translate fluorescence into
concentration or firing without calibration.

### 8. Hemodynamics and emerging optical modalities

Hemoglobin absorption can distort fluorescence differently across wavelengths;
spectrally resolved measurements can estimate and correct this contamination
([Zhang et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9243291/)). Recent
directions include spectral photometry and 2025 vibrational/Raman fiber photometry
([Pisano et al., 2025](https://www.nature.com/articles/s41592-024-02557-3)).

**Coverage:** absent and not all of it belongs in the core. The core should define
an extensible wavelength/spectrum representation and transformation provenance;
specialized modality packages can implement Raman or instrument-specific models.

## Documentation audit

Before this audit, the repository contained over 60 substantial Markdown files
but no site configuration, landing page, task-oriented navigation, methods index,
or supported-versus-planned matrix. Strong evidence was therefore difficult to
discover, and benchmark/decision records competed with introductory guidance.

The new documentation architecture separates:

1. **Start here** — choose by scientific question and input;
2. **Methods** — what each analysis answers, assumes, and supports;
3. **Worked examples** — executable literature-shaped analyses;
4. **Data and interoperability** — formats, metadata, and evidence;
5. **Publication** — comparison, signing, and DOI deposition;
6. **Evidence and rationale** — benchmarks, decisions, limitations;
7. **Reference** — Python API and stability contracts.

The current two tutorials demonstrate the core event-analysis product, but they
do not establish comprehensive field coverage. Five literature-shaped examples
should become acceptance fixtures for the missing method families.

## Recommended capability programme

### P0 — make the existing product legible

- publish and continuously validate the documentation site;
- complete task-oriented method pages with assumptions and failure modes;
- add small copyable examples for every supported public API family;
- clearly badge supported, experimental, planned, and out-of-scope methods.

### P1 — mainstream scientific coverage

1. behavioral/event-kernel GLMs with grouped validation;
2. `fastFMM` bridge and Loewinger numerical reproduction;
3. spontaneous transient detection with local-baseline sensitivity analysis;
4. longitudinal tonic/phasic representation and hierarchical summaries;
5. multi-site/multi-color paired and conditional association workflows.

### P2 — acquisition and optical breadth

- native Doric, Neurophotometrics, and pyPhotometry adapters;
- spectral unmixing and wavelength-aware hemodynamic correction;
- optogenetic pulse/artifact masks;
- sensor registry and sensor-aware diagnostics.

### Deliberate extension boundaries

Do not make raw video tracking, behavioral pose estimation, acquisition control,
Raman spectral modeling, or arbitrary machine-learning models core dependencies.
Provide stable tables, timestamps, covariates, and plugin boundaries so specialist
tools can interoperate without weakening the evidential contract.

## Audit maintenance

Review this matrix at least once per minor release and after major methods papers
or conference programmes. A capability moves from planned to supported only when
it has an explicit estimand, validated failure behavior, public or controlled
fixtures, a worked example, and documentation of assumptions.
