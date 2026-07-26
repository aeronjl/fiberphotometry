# SDR-0007: Require explicit TDT store mapping

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

The TDT Python SDK exposes block data as named stream and epoc stores. Stream
names and channel meanings are acquisition-specific: a wavelength-like store
name does not establish whether its data are signal, reference, or something
else. Epoc numeric values likewise require experiment-specific interpretation.

The SDK documents stream `data`, `fs`, and `start_time` fields, one-indexed
channel selection, and epoc `onset`, `offset`, and `data` arrays:

- <https://www.tdt.com/docs/sdk/offline-data-analysis/offline-data-python/>
- <https://tdt.com/docs/sdk/offline-data-analysis/offline-data-python/examples/00_Intro/>

## Decision

TDT import requires a versioned schema that explicitly maps:

- each canonical channel to a stream store and one-indexed SDK channel;
- each reference channel, when present, to its store and SDK channel;
- one epoc store to an analysis factor;
- every accepted numeric epoc value to a categorical label.

The adapter does not infer semantics from store names. All mapped streams must
already have the same sampling rate, start time, and sample count. It rejects
misalignment instead of silently resampling. Resampling remains a separate,
provenance-recorded preprocessing operation.

The imported source fingerprint covers the declared schema and the selected
stream-channel and epoc arrays. It does not claim to fingerprint unselected
stores in the block.

## Alternatives considered

- **Infer conventional stores such as 465/405.** Rejected because conventions
  are not scientific metadata and vary across rigs and experiments.
- **Automatically align or resample stores.** Rejected because it would hide a
  consequential transformation at the acquisition boundary.
- **Retain epoc values without labels.** Rejected because numeric acquisition
  codes do not communicate experimental meaning.

## Consequences

Configuration is more verbose, but it is reviewable and reproducible. Unsupported
or ambiguous blocks fail before analysis. A real-block integration fixture is
still required before claiming broad compatibility with TDT acquisitions.

## Revisit trigger

Revisit if validated TDT metadata provide an authoritative, machine-readable
semantic mapping, or if real-block validation demonstrates that strict temporal
identity prevents common scientifically valid imports.
