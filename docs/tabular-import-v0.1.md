# Generic tabular import v0.1

FiberPhotometry accepts ordinary wide CSV and TSV files without requiring pandas.
Import is deliberately schema-first: filenames, column order, correlation, and
alternation never establish which values are signal or reference measurements.

## Recording contract

Each recording table represents one subject and session. Rows are samples. One
column contains timestamps and every anatomical channel has an explicitly named
signal column. Reference correction is available only when every channel also has
an explicitly named reference column.

```python
from fiberphotometry import (
    TabularChannel,
    TabularRecordingSchema,
    inspect_tabular_recording,
    load_tabular_recording,
)

recording_schema = TabularRecordingSchema(
    time_column="time_ms",
    channels=(
        TabularChannel("DMS", "dms_470", "dms_405"),
        TabularChannel("NAc", "nac_470", "nac_405"),
    ),
    time_unit="milliseconds",
)

inspection = inspect_tabular_recording(
    "recording.csv",
    recording_schema,
    subject="mouse-01",
    session="session-01",
)
print(inspection.to_json())

recording = load_tabular_recording(
    "recording.csv",
    recording_schema,
    subject="mouse-01",
    session="session-01",
)
```

The canonical recording stores time in seconds and signals as `(time, channel)`.
Empty/`NA`/`NaN` signal cells become explicit missing values; time must remain
finite and strictly increasing. Inspection reports duration, estimated rate,
interval irregularity, per-channel finite fractions, and missingness warnings.

The dataset retains the source filename, SHA-256 fingerprint, original time unit,
and complete mapping schema. It does not store an absolute path.

## Event contract

Event rows remain distinct from signal samples. Event identifiers must be unique
within a session, and metadata conversion is declared rather than guessed.

```python
from fiberphotometry import (
    TabularEventColumn,
    TabularEventSchema,
    inspect_tabular_input,
    load_tabular_input,
)

event_schema = TabularEventSchema(
    time_column="onset_ms",
    event_id_column="event_id",
    columns=(
        TabularEventColumn("condition"),
        TabularEventColumn("rewarded", kind="bool"),
        TabularEventColumn("trial_number", name="trial", kind="int"),
    ),
    time_unit="milliseconds",
)

preflight = inspect_tabular_input(
    "recording.csv",
    recording_schema,
    "events.tsv",
    event_schema,
    subject="mouse-01",
    session="session-01",
)
print(preflight.to_json())

pipeline_input = load_tabular_input(
    "recording.csv",
    recording_schema,
    "events.tsv",
    event_schema,
    subject="mouse-01",
    session="session-01",
)
```

The combined preflight also records event-table identity and coverage, warning when
event timestamps fall before or after the recording clock.

Supported metadata types are `string`, `float`, `int`, and `bool`. Event-source
identity and SHA-256 are attached to the recording provenance so downstream JSON,
HTML, and NWB artifacts can identify their inputs.

## Boundaries

- v0.1 supports one wide recording table and one event table per session.
- Time units are explicitly `seconds` or `milliseconds`; sample indices are not
  silently converted without a declared acquisition rate.
- It does not infer signal/reference semantics or interpolate one channel onto
  another timebase.
- Long-form, interleaved-wavelength, and multiplexed acquisition tables require a
  format-specific adapter because demultiplexing and alignment are scientific
  operations, not generic CSV parsing.

These boundaries implement the existing decisions to
[avoid inferred channel identity](decisions/0005-do-not-infer-photometry-channel-identity.md)
and [require explicit alignment](decisions/0004-require-explicit-derived-data-alignment.md).
