# SDR-0020: Store one reference signal and the complete multiverse ledger

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Configuration-first CLI v0.1](../cli-v0.1.md)

## Context

A multiverse may contain dozens of preprocessing workflows. Copying every derived
time series into every per-session NWB file scales signal storage with universe
count, while storing only aggregate estimates would make it impossible to recover
the declared decision space, failures, or reference workflow.

## Decision

For multiverse project export, store raw acquisition signals once and store one
processed time series from the explicitly declared reference universe. Embed the
complete typed multiverse result and the unit-local robustness summary as JSON
scratch datasets in every session file. Also retain project configuration,
metadata readiness, session preflight, reference-workflow QC, stable universe IDs,
choices, statuses, estimates, failure reasons, and practical-effect policies.

Label the NWB identifier as a multiverse export, validate every file before
publication, and include every NWB checksum in the evidence manifest. Do not imply
that the reference universe is uniquely correct.

## Consequences

The archive remains bounded by acquisition size rather than universe count while
preserving the full population-level robustness argument. Reproducing a
non-reference processed trace requires rerunning its serialized pipeline against
the archived raw signal. Population results are intentionally repeated in each
session file so an independently shared file retains its analysis context.

## Alternatives considered

- Store every universe's processed signal: rejected because data volume grows
  linearly and most traces are reproducible derivatives.
- Store no processed signal: rejected because the declared reference workflow is
  a useful inspectable bridge between raw acquisition and population estimates.
- Put the multiverse ledger only in an external sidecar: rejected because detached
  NWB files would lose their scientific interpretation.

## Revisit trigger

Consider optional selected-universe trace export if users demonstrate a concrete
review or archival need that cannot be met by rerunning serialized pipelines. Keep
the default bounded and require explicit universe selection.

## Evidence added later

None yet.
