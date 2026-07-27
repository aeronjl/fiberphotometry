# Project evidence reader v0.1

`read_project_evidence` provides one supported interface for a CLI artifact
directory or a standalone exported NWB file. It returns `ProjectEvidenceBundle`,
with common accessors for primary analysis, multiverse result, unit-local
robustness summary, metadata, preflight, and normalized project provenance.

## Directory verification

The reader requires manifest schema v1 and checks every declared artifact before
exposing JSON records. Artifact paths must be relative descendants of the bundle;
parent traversal, absolute paths, and symlinks resolving outside the bundle are
rejected. Every observed SHA-256 must equal the manifest value. A successful read
sets `manifest_verified = True` and every `EvidenceFile.verified = True`.

Failed or blocked bundles remain readable when their manifest is internally
complete. Their `kind` may be `incomplete` when execution stopped before an
analysis result was written; preflight and metadata remain available.

## Standalone NWB trust boundary

The reader recovers FiberPhotometry JSON scratch datasets through PyNWB and
requires project provenance plus either a primary analysis or multiverse result.
It computes the file SHA-256 for identification, but cannot compare it with an
external authority. Consequently `manifest_verified` and `EvidenceFile.verified`
are `None`. Reading means the HDF5/NWB structure and embedded JSON are usable, not
that an independently published checksum has been verified.

To obtain verified NWB checksums, read the complete artifact directory containing
the NWB files and its manifest.

Manifest checksum verification establishes internal bundle integrity; it does not
authenticate a publisher. Use `verify_publication_manifest` with an independently
maintained `allowed_signers` file for publisher authentication.

## Stability

`EvidenceFile`, `ProjectEvidenceBundle`, and `read_project_evidence` are supported
v0.1 APIs. Unknown manifest schema versions and malformed record types are rejected
rather than guessed. The reader returns decoded JSON mappings rather than
reconstructing mutable execution objects, keeping archival inspection separate
from rerunning an analysis.

Use `compare_project_evidence(left, right)` to compare two loaded bundles. A
directory and an NWB file can be scientifically equivalent even though byte
identity is undefined across formats.
