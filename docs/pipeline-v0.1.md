# Typed analysis pipeline v0.1

`run_pipeline()` connects the existing reference correction, recording QC,
acquired-sample event summaries, experimental design, and executable analysis
plans. The composition is intentionally narrow: it supports the validated
scalar path without pretending that every future preprocessing or statistical
model belongs in one permanent configuration type.

The specification has four independent parts:

- `PreprocessingSpec` records the reference-fit method and numerical controls.
- `QualityGateSpec` names warning codes that block inference and declares
  whether only the selected channel or all channels are checked.
- `EventSummarySpec` identifies a channel, source variable, windows, statistic,
  and open output-column name.
- `StudyDesign` and `AnalysisPlan` retain the unit hierarchy, estimand, method,
  assumptions, intent, and random seed.

Per-event metadata remains an open mapping on `RecordingInput`, so a new task
variable or laboratory annotation does not require a library release. The small
typed core covers only semantics used by processing or inference. Specs carry a
schema version; new incompatible meanings require a new schema rather than
silently reinterpreting old JSON.

## QC behavior

QC never deletes observations. If a selected blocking warning occurs, the
pipeline still returns corrected recordings, event summaries, quality reports,
and the complete observation table, but `analysis` is `None`. `blocked_by`
identifies the recording, channel, and warning. An empty blocking-warning tuple
is an explicit choice to report QC without gating inference.

## Current boundaries

Version 1 deliberately supports reference-based preprocessing and scalar
acquired-sample summaries. Version 2 adds filtering and resampling, but neither
schema models time-resolved inference, exclusion policies, multiple comparisons,
or missing outcomes. Those should enter as new tagged operations and validation
rules, not as miscellaneous optional fields on the existing types.

The automated fixture runs the full path across four synthetic animals and
checks that the animal remains the aggregation unit. A second fixture injects
missingness and verifies that a QC failure blocks inference without shrinking
the observation table. The public IBL builder also runs this API and asserts
that its table is identical to the frozen direct calculation.

## Schema v2 operation sequences

Schema v1 remains accepted unchanged. Schema v2 replaces its single
`PreprocessingSpec` with an ordered tuple of tagged operations:

- `ResampleOperation` uses linear interpolation and can prohibit interpolation
  across source gaps larger than a declared duration. Original time-channel
  arrays are retained on a `source_time` axis.
- `LowpassFilterOperation` filters finite runs independently with a zero-phase
  Butterworth SOS implementation. Pre-filter arrays are retained, short runs are
  set to missing rather than filtered across gaps, and the exact edge padding is
  recorded.
- `ReferenceDFFOperation` retains the existing robust/OLS correction behavior.

Every executed operation is appended to the recording's
`fiberphotometry_operations` JSON provenance in execution order. A v1 spec
cannot accidentally receive a v2 tuple, and a v2 spec cannot receive the legacy
object. Frozen numerical behavior is reported in
[`benchmarks/results-v0.8.md`](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/results-v0.8.md).

Time-indexed Boolean acquisition masks are propagated during resampling with
nearest-neighbor labels, retained on the source-time axis, and forced false
inside gaps larger than the declared interpolation limit. They are never
linearly interpolated as numeric signals.
