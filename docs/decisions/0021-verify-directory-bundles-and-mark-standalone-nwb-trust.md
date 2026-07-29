# SDR-0021: Verify directory bundles and mark standalone NWB trust

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Project evidence reader v0.1](../evidence-reader.md)

## Context

Scientists need to reopen completed analyses without knowing whether results came
from JSON sidecars or an NWB archive. A directory manifest provides expected
checksums, while a standalone NWB file carries embedded provenance but cannot
authenticate its own bytes. Treating both as implicitly verified would overstate
the available evidence.

## Decision

Provide one normalized project evidence reader. For directories, require manifest
schema v1, constrain artifact paths to the bundle, verify every declared SHA-256,
and reject the entire read on any mismatch or missing artifact. For standalone NWB
files, require readable embedded project provenance and an analysis or multiverse
result, compute the observed checksum, but mark manifest verification as unknown.

Return decoded archival records rather than reconstructing executable pipeline
objects. Preserve complete, blocked, failed, and incomplete statuses.

## Consequences

Consumers can inspect both storage formats through common accessors and can tell
whether integrity was externally checked. Tampered or path-traversing manifests
fail before record use. Rerunning a serialized workflow remains an explicit future
operation rather than an accidental side effect of reading evidence.

## Alternatives considered

- Mark every readable NWB file verified: rejected because self-contained bytes do
  not establish correspondence with a published artifact.
- Ignore manifest hashes for convenience: rejected because provenance without
  integrity checking cannot establish which evidence was reviewed.
- Rehydrate every dataclass automatically: rejected because schema evolution and
  execution semantics require explicit migrations.

## Revisit trigger

Add detached checksum or signature verification for standalone files when the
project defines a publication/signing workflow and trust-store policy.

## Evidence added later

None yet.
