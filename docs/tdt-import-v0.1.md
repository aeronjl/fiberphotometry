# TDT import contract v0.1

FiberPhotometry reads TDT blocks through the official Python SDK and maps only
declared data into the canonical recording/event boundary. Install the optional
adapter with:

```bash
pip install "fiberphotometry[tdt]"
```

## Mapping contract

The official SDK represents continuous streams with `data`, `fs`, and
`start_time`; multichannel arrays are selected with one-indexed channel numbers.
Epoc stores provide `onset`, `offset`, and numeric `data` arrays. FiberPhotometry
therefore requires these meanings to be explicit rather than assuming common
store names such as `_465A` or `_405A`.

```toml
schema_version = "1"
input_format = "tdt"
output_directory = "artifacts"

[tdt]

[[tdt.channels]]
name = "DMS"
signal_store = "x465A"
signal_channel = 1
reference_store = "x405A"
reference_channel = 1

[tdt.events]
store = "Trl_"
factor_name = "condition"

[[tdt.events.values]]
value = 1
label = "control"

[[tdt.events.values]]
value = 2
label = "drug"

[[sessions]]
subject = "mouse-01"
session = "session-01"
block = "data/Subject-Block-1"
```

The remainder of the project file uses the same analysis, artifact, and optional
NWB-export sections as a tabular project. See
[`examples/tdt-project.template.toml`](../examples/tdt-project.template.toml) for
a fuller editable template.

## Validation and provenance

Import fails when a declared store or channel is absent, reference mappings are
partial, epoc values are undeclared, or mapped streams differ in sampling rate,
start time, or sample count. The adapter deliberately does not interpolate or
resample at import. Time is reconstructed from the SDK's `start_time` and `fs`.

Each imported session records its block name, SDK version, schema, timing, and a
SHA-256 fingerprint of the declared schema plus the selected stream-channel and
epoc arrays. Unselected stores are outside that fingerprint's stated scope.

The implementation is covered by SDK-shaped fixtures. It has not yet been
validated against a bounded, redistributable real TDT block; that remains an
explicit roadmap gate rather than an implied compatibility claim.

## References

- [TDT Python SDK overview](https://www.tdt.com/docs/sdk/offline-data-analysis/offline-data-python/)
- [TDT Python SDK introductory examples](https://tdt.com/docs/sdk/offline-data-analysis/offline-data-python/examples/00_Intro/)
- [TDT data storage formats](https://www.tdt.com/docs/sdk/offline-data-analysis/tdt-data-storage/)
