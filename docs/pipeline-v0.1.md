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

Version 0.1 deliberately supports reference-based preprocessing and scalar
acquired-sample summaries. It does not yet model filtering, resampling,
time-resolved inference, exclusion policies, multiple comparisons, or missing
outcomes. Those should enter as new tagged operations and validation rules, not
as miscellaneous optional fields on the existing types.

The automated fixture runs the full path across four synthetic animals and
checks that the animal remains the aggregation unit. A second fixture injects
missingness and verifies that a QC failure blocks inference without shrinking
the observation table. The public IBL builder also runs this API and asserts
that its table is identical to the frozen direct calculation.
