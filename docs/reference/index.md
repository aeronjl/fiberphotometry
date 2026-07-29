# Python API

The root package exposes a curated core: ingest, preprocessing, dF/F,
resampling, quality control, event alignment and summarisation, the pipeline
runner, and the evidence, archive and publication surface built on them. Every
name below is declared `supported` or `experimental` — see the
[API stability policy](../api-stability.md) before depending on either.

Advanced method families are **not** re-exported at the root. They keep their
full public API in their own module, so `from fiberphotometry.spectral import
welch_psd` rather than `from fiberphotometry import welch_psd`. Those modules
are listed under [namespaced modules](#namespaced-modules).

## Root namespace

::: fiberphotometry

## Namespaced modules

Anything in these modules that is not re-exported above is importable and tested
but sits outside the declared stability surface, and may change without a
deprecation cycle.

### Acquisition and interchange

| Module | Contents |
| --- | --- |
| `fiberphotometry.io` | Re-exports every acquisition adapter below under one namespace |
| `fiberphotometry.io.acquisition` | Shared guarantees and inspection types for native adapters |
| `fiberphotometry.io.tabular` | CSV/TSV schemas, loaders, and inspection results |
| `fiberphotometry.io.tdt` | Adapter from official TDT Python SDK structures |
| `fiberphotometry.io.doric` | Doric HDF5 `.doric` reader |
| `fiberphotometry.io.pyphotometry` | Versioned pyPhotometry `.ppd` binary reader |
| `fiberphotometry.io.neurophotometrics` | Neurophotometrics Bonsai CSV and parquet reader |
| `fiberphotometry.io.nwb` | [`ndx-fiber-photometry` reader and writer](../nwb-data-model.md) |
| `fiberphotometry.io.nwb_project` | Provenance-complete NWB export for executed projects |
| `fiberphotometry.io.dandi` | Bounded streaming validation of public DANDI assets |
| `fiberphotometry.io.dandi_000351`, `fiberphotometry.io.dandi_000971` | Pinned dataset-specific adapters |
| `fiberphotometry.io.ibl` | International Brain Laboratory photometry tables |
| `fiberphotometry.io.ndx_pose` | Native ndx-pose inspection, import, and export |
| `fiberphotometry.interoperability` | [Pose and behavior tool boundaries](../ecosystem-interoperability.md), [clock synchronization](../clock-synchronization.md) |
| `fiberphotometry.unspool` | [Unspool study export](../unspool-interoperability.md) |

### Signal and method families

| Module | Contents |
| --- | --- |
| `fiberphotometry.spectral` | [Gap-aware time, frequency, and state analysis](../spectral-state-analysis.md) |
| `fiberphotometry.cross_spectral` | Coherence and phase for declared signal pairs |
| `fiberphotometry.multisignal` | [Paired-signal association and crosstalk diagnostics](../multisite-multicolor-analysis.md) |
| `fiberphotometry.spatial_network` | [Coordinate-aware multi-fiber networks](../spatial-network.md) |
| `fiberphotometry.optical_mixing` | [Wavelength-aware optical unmixing](../optical-unmixing.md) |
| `fiberphotometry.sensor_kinetics` | [Sensor forward models and deconvolution](../sensor-kinetic-modeling.md) |
| `fiberphotometry.sensor_validity` | [Sensor profiles and isosbestic validity](../optical-validity.md) |
| `fiberphotometry.optogenetics` | [Artifact masks and recovery diagnostics](../optical-validity.md) |
| `fiberphotometry.multiscale` | [Multiscale long-duration summaries](../multiscale-long-duration.md) |
| `fiberphotometry.transients`, `fiberphotometry.transient_product` | [Spontaneous transient detection and quantification](../spontaneous-transients.md) |
| `fiberphotometry.interval_policy` | [Interval policies for external behavior intervals](../interval-policy.md) |

### Encoding and multiverse

| Module | Contents |
| --- | --- |
| `fiberphotometry.encoding` | [Event-kernel encoding models](../event-kernel-encoding.md) and their bases |
| `fiberphotometry.encoding_multiverse` | [Named event-kernel model comparison](../event-kernel-multiverse.md) |
| `fiberphotometry.encoding_contributions` | [Predictor-family contributions](../predictor-family-contributions.md) |
| `fiberphotometry.multiverse` | [Pipeline multiverse execution and robustness](../multiverse-contract.md) |
| `fiberphotometry.compatibility` | [Structural compatibility checks](../pipeline-compatibility.md) |

### Inference and study design

| Module | Contents |
| --- | --- |
| `fiberphotometry.inference` | [Design-driven scalar inference](../inference-design.md) beyond the root primitives |
| `fiberphotometry.design` | Design report and issue types returned by `validate_design` |
| `fiberphotometry.planning` | [Analysis plans and power sensitivity](../inference-design.md) |
| `fiberphotometry.mixed` | [Scalar mixed-model sensitivity summaries](../scalar-mixed-model.md) |
| `fiberphotometry.timecourse` | [Peri-event interactions](../peri-event-inference.md) beyond the root contrast |
| `fiberphotometry.population` | [Population contrasts and interactions](../population-inference.md) |
| `fiberphotometry.population_workflows` | [Population workflow adapters](../population-workflow-adapters.md) |
| `fiberphotometry.association_inference` | [Animal-level association inference](../multisite-multicolor-analysis.md) |
| `fiberphotometry.transient_inference` | [Animal-level transient rate and kinetics](../spontaneous-transients.md) |

### Projects, evidence, and reporting

| Module | Contents |
| --- | --- |
| `fiberphotometry.project` | Session sources and multiverse project configuration |
| `fiberphotometry.metadata` | [Metadata completeness assessment](../metadata-completeness.md) |
| `fiberphotometry.comparability` | [Across-session comparability](../session-comparability.md) |
| `fiberphotometry.report` | Self-contained HTML evidence reports |
| `fiberphotometry.qc`, `fiberphotometry.event_qc` | QC result types returned by the root entry points |
| `fiberphotometry.simulate` | Small ground-truth simulations for tests and examples |
| `fiberphotometry.validation` | Numerical validation against independently processed signals |
