# API stability policy for v0.1

Status: **release-candidate boundary**. This policy takes effect for the first
published `0.1.x` release; the current `0.1.0.dev0` build remains developmental.

## Two states, no third

**Every name in `fipha.__all__` is declared `supported` or
`experimental`.** There is no unclassified state. The declarations are
`fipha.stability.SUPPORTED_API_V0_1` and `EXPERIMENTAL_API_V0_1`, and
`tests/test_stability.py` fails the build if a root export is missing from both,
appears in both, or is declared without being exported.

The root namespace is deliberately small. Names reachable only from their own
module — `fipha.spectral.welch_psd`,
`fipha.encoding.fit_event_kernel_model`,
`fipha.multiverse.run_multiverse` — are outside the declared surface
entirely. They are importable and tested, but carry no compatibility promise and
may be renamed, restructured, or removed without a deprecation cycle.

## Supported surface

The supported surface is the scientific core path plus the evidence and
deposition machinery built on it:

- ingest through the canonical recording boundary: `make_recording`,
  `validate_recording`, acquisition-format detection and validation, and the
  tabular and TDT schemas and loaders;
- preprocessing and normalization: `reference_dff`, `baseline_dff`,
  `lowpass_filter`, and `resample_recording`;
- quality control: `assess_recording`, `assess_signal_recording`, and
  `assess_event_confounds`;
- event alignment and summarisation: `align_events` and `summarize_event_windows`;
- the pipeline runner `run_pipeline` with its declared specification and
  operation types;
- the `EventAnalysis`, `EventSession`, `Preprocessing`, configuration, result,
  coverage, and peri-event inference workflow types;
- project configuration and NWB export;
- verified project evidence reading from manifest directories and NWB files;
- semantic cross-bundle comparison and reproducibility reporting;
- detached OpenSSH publication signing and allowed-signers verification;
- validated, deterministic archival packaging and verification;
- sandbox-first creation and validation of unpublished Zenodo draft deposits.

Within a `0.1.x` line, supported names will not be removed or have required
arguments added without defaults. Bug fixes may tighten validation when existing
behavior could silently produce an invalid scientific result.

## Experimental surface

The experimental root exports are the study-design and inference primitives, the
native acquisition-format readers, the NWB, DANDI and IBL interchange functions,
the typed [`ndx-fiber-photometry` acquisition metadata](nwb-data-model.md) types
`NWBAcquisitionMetadata`, `NWBChannelMetadata`, `NWBDeviceMetadata` and
`NWBIndicatorMetadata`, spontaneous transient detection, the optional matplotlib
figures, and the multiverse NWB export. Their names are listed in
`EXPERIMENTAL_API_V0_1`.

Whole method families live in their own module and are experimental as families:
optical unmixing, spatial networks, sensor kinetics, multiscale summaries,
spectral and state analysis, event-kernel encoding and its multiverse, predictor
family contributions, interval policy, behavioral ecosystem adapters,
matched-pulse clock synchronization, scalar mixed models, transient products, and
the population inference variants. Experimental APIs retain provenance and tests
but may change between minor releases when validation exposes a scientific
problem.

## Deprecation

Supported APIs receive a `DeprecationWarning`, migration text, and at least one
minor release of overlap before removal. Serialized v1 artifacts are not silently
rewritten: readers must reject unknown major schema versions and migrations must
produce a new artifact with recorded source version.

Security fixes and corrections preventing scientifically invalid output may bypass
the overlap period. Such changes require release notes and a scientific decision
record explaining the risk.

## Versioning interpretation

Before 1.0, Python package minor versions may contain deliberate experimental API
changes. Patch releases preserve supported interfaces and v1 artifact schemas.
The eventual 1.0 boundary will be based on usability and external reproduction,
not simply elapsed development time.
