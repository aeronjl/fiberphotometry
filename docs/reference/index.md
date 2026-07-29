# Python API

The root package exposes a curated core: ingest, preprocessing, dF/F,
resampling, quality control, event alignment and summarisation, the pipeline
runner, and the evidence, archive and publication surface built on them. Every
name below is declared `supported` or `experimental` — see the
[API stability policy](../api-stability.md) before depending on either.

Advanced method families are **not** re-exported at the root. They keep their
full public API in their own module, so `from fipha.spectral import
welch_psd` rather than `from fipha import welch_psd`. Those modules
are listed under [namespaced modules](#namespaced-modules).

## Root namespace

::: fipha

## Namespaced modules

Anything in these modules that is not re-exported above is importable and tested
but sits outside the declared stability surface, and may change without a
deprecation cycle.

### Acquisition and interchange

| Module | Contents |
| --- | --- |
| `fipha.io` | Re-exports every acquisition adapter below under one namespace |
| `fipha.io.acquisition` | Shared guarantees and inspection types for native adapters |
| `fipha.io.tabular` | CSV/TSV schemas, loaders, and inspection results |
| `fipha.io.tdt` | Adapter from official TDT Python SDK structures |
| `fipha.io.doric` | Doric HDF5 `.doric` reader |
| `fipha.io.pyphotometry` | Versioned pyPhotometry `.ppd` binary reader |
| `fipha.io.neurophotometrics` | Neurophotometrics Bonsai CSV and parquet reader |
| `fipha.io.nwb` | [`ndx-fiber-photometry` reader and writer](../nwb-data-model.md) |
| `fipha.io.nwb_project` | Provenance-complete NWB export for executed projects |
| `fipha.io.dandi` | Bounded streaming validation of public DANDI assets |
| `fipha.io.dandi_000351`, `fipha.io.dandi_000971` | Pinned dataset-specific adapters |
| `fipha.io.ibl` | International Brain Laboratory photometry tables |
| `fipha.io.ndx_pose` | Native ndx-pose inspection, import, and export |
| `fipha.behavio` | [Behavio study export](../behavio-interoperability.md) |

### Signal and method families

| Module | Contents |
| --- | --- |
| `fipha.spectral` | [Gap-aware time, frequency, and state analysis](../spectral-state-analysis.md) |
| `fipha.cross_spectral` | Coherence and phase for declared signal pairs |
| `fipha.multisignal` | [Paired-signal association and crosstalk diagnostics](../multisite-multicolor-analysis.md) |
| `fipha.spatial_network` | [Coordinate-aware multi-fiber networks](../spatial-network.md) |
| `fipha.optical_mixing` | [Wavelength-aware optical unmixing](../optical-unmixing.md) |
| `fipha.sensor_kinetics` | [Sensor forward models and deconvolution](../sensor-kinetic-modeling.md) |
| `fipha.sensor_validity` | [Sensor profiles and isosbestic validity](../optical-validity.md) |
| `fipha.optogenetics` | [Artifact masks and recovery diagnostics](../optical-validity.md) |
| `fipha.multiscale` | [Multiscale long-duration summaries](../multiscale-long-duration.md) |
| `fipha.transients`, `fipha.transient_product` | [Spontaneous transient detection and quantification](../spontaneous-transients.md) |

`fipha.interoperability` and `fipha.interval_policy` no longer exist. The pose,
ethogram, clock-synchronization, and interval-policy surface is now
[`behavio.pose`](https://aeronjl.github.io/behavio/pose/), [`behavio.ethograms`](https://aeronjl.github.io/behavio/ethograms/),
[`behavio.covariates`](https://aeronjl.github.io/behavio/covariates/), [`behavio.sync`](https://aeronjl.github.io/behavio/clock-synchronization/) and
[`behavio.interval_policy`](https://aeronjl.github.io/behavio/interval-policy/),
installed through `fipha[behavior]`. `fipha.io.ndx_pose` still lives here and
imports Behavio's `PoseTrajectory` lazily.

### Encoding and multiverse

| Module | Contents |
| --- | --- |
| `fipha.encoding` | [Event-kernel encoding models](../event-kernel-encoding.md) and their bases |
| `fipha.encoding_multiverse` | [Named event-kernel model comparison](../event-kernel-multiverse.md) |
| `fipha.encoding_contributions` | [Predictor-family contributions](../predictor-family-contributions.md) |
| `fipha.multiverse` | [Pipeline multiverse execution and robustness](../multiverse-contract.md) |
| `fipha.compatibility` | [Structural compatibility checks](../pipeline-compatibility.md) |

### Inference and study design

| Module | Contents |
| --- | --- |
| `fipha.inference` | [Design-driven scalar inference](../inference-design.md) beyond the root primitives |
| `fipha.design` | Design report and issue types returned by `validate_design` |
| `fipha.planning` | [Analysis plans and power sensitivity](../inference-design.md) |
| `fipha.mixed` | [Scalar mixed-model sensitivity summaries](../scalar-mixed-model.md) |
| `fipha.timecourse` | [Peri-event interactions](../peri-event-inference.md) beyond the root contrast |
| `fipha.population` | [Population contrasts and interactions](../population-inference.md) |
| `fipha.population_workflows` | [Population workflow adapters](../population-workflow-adapters.md) |
| `fipha.association_inference` | [Animal-level association inference](../multisite-multicolor-analysis.md) |
| `fipha.transient_inference` | [Animal-level transient rate and kinetics](../spontaneous-transients.md) |

### Projects, evidence, and reporting

| Module | Contents |
| --- | --- |
| `fipha.project` | Session sources and multiverse project configuration |
| `fipha.metadata` | [Metadata completeness assessment](../metadata-completeness.md) |
| `fipha.comparability` | [Across-session comparability](../session-comparability.md) |
| `fipha.report` | Self-contained HTML evidence reports |
| `fipha.qc`, `fipha.event_qc` | QC result types returned by the root entry points |
| `fipha.simulate` | Small ground-truth simulations for tests and examples |
| `fipha.validation` | Numerical validation against independently processed signals |
