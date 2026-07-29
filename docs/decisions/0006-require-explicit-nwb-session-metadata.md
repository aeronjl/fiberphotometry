# SDR-0006: Require explicit NWB session metadata

- Status: Accepted
- Date: 2026-07-26
- Decision owners: project maintainers
- Related protocol/report: [CLI v0.1](../cli.md)

## Context

The configuration-first CLI can now export tabular analyses to NWB. A valid NWB
file requires session description, identifier, and start time, while
`ndx-fiber-photometry` can additionally represent indicators, excitation sources,
photodetectors, optical fibers, and commanded versus measured wavelengths. Generic
CSV files frequently contain none of that acquisition hardware metadata.

## Decision

NWB export is opt-in. Require a declared session description and timezone-aware
start time rather than deriving them from filenames, filesystem timestamps, or the
current clock. Write raw and processed signals as valid core-NWB `TimeSeries`
objects when extension hardware metadata are unavailable. Preserve channel names,
source hashes, operations, events, QC, project configuration, and analysis results
inside the file. Do not construct `ndx-fiber-photometry` hardware objects from
guesses.

Validate every file before publication and hash it in the CLI artifact manifest.

## Consequences

Scientists receive portable, valid, provenance-complete NWB files from ordinary
tabular projects. The files can be shared and re-opened without implying knowledge
of optical hardware that was never recorded. Export requires a small amount of
additional configuration, and core `TimeSeries` output is less semantically rich
than a fully populated extension file.

## Alternatives considered

- Use the current time as `session_start_time`: rejected because it would describe
  export time as acquisition time.
- Use file modification time: rejected because copying or editing changes it.
- Invent generic extension devices and indicators: rejected because valid object
  structure would still encode false experimental metadata.
- Disable NWB writing until all extension metadata exist: rejected because core
  NWB can faithfully represent the available signal, event, and provenance data.

## Revisit trigger

Add extension-native writing when a typed acquisition schema can require and
validate the relevant `ndx-fiber-photometry` metadata, with round-trip fixtures
from real acquisition systems.

## Evidence added later

On 2026-07-27, NWB export was extended to multiverse projects without inventing
additional acquisition metadata. The storage boundary for processed workflows is
governed by
[SDR-0020](0020-store-one-reference-signal-and-the-complete-multiverse-ledger.md).

On 2026-07-28, the revisit trigger was satisfied. `NWBAcquisitionMetadata` is the
typed acquisition schema that requires and validates the fields
`ndx-fiber-photometry` marks required, so extension-native writing is now
available. Signals are always written as `FiberPhotometryResponseSeries` rather
than core `TimeSeries`, and channel labels and preprocessing provenance moved from
a private JSON document in `comments` to two documented scratch `DynamicTable`
objects. The prohibition in the decision is unchanged: without declared metadata
the writer emits no `FiberPhotometryTable` at all. See the
[NWB data model](../nwb-data-model.md).
