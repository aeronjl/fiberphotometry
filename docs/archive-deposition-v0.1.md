# Archival deposition v0.1

FiberPhotometry turns a complete, checksum-verified evidence directory into a
deterministic ZIP suitable for repository or DOI deposition. Packaging is local:
the command never uploads or publishes a record.

## Metadata contract

The input `archive-metadata.json` is repository-neutral and validated against
[`archive-metadata-v1.schema.json`](../schemas/archive-metadata-v1.schema.json).
It requires a title, abstract-like description, at least one creator, publication
date, publisher, license, language, and resource type. Creator ORCIDs are checked
with the ISO 7064 checksum, not merely a text pattern. Keywords and related
identifiers are explicit arrays, including their relation semantics.

From this one source, the package derives:

- `datacite.json`, using DataCite REST API attribute names;
- `.zenodo.json`, using Zenodo deposit metadata names;
- `archive-manifest.json`, recording each packaged path, byte length, SHA-256,
  and the evidence project fingerprint.

The DataCite minimum DOI metadata are creators, title, publisher, publication
year, and general resource type. Zenodo additionally requires deposit type,
description, publication date, and access/license information. The generated
records cover both sets without treating either repository projection as the
canonical scientific record.

## Commands

```bash
uv run fiberphotometry archive artifacts \
  --metadata archive-metadata.json \
  --output reward-analysis-deposit.zip

uv run fiberphotometry verify-archive reward-analysis-deposit.zip
```

Existing output is never replaced without `--force`. Creation admits only a
complete directory whose ordinary evidence manifest verifies. If publication
signing files are present, the attestation and detached signature must appear as
a pair and are preserved under `evidence/`.

## Reproducibility and verification

Entries have sorted paths, fixed timestamps and permissions, fixed compression,
and canonical JSON. Identical evidence and metadata therefore produce identical
ZIP bytes and SHA-256 values across repeated runs of the supported implementation.

Verification rejects duplicate or traversing paths, undeclared files, size or
checksum mismatches, malformed source metadata, incomplete evidence, evidence
manifest failures, and disagreement between archive and project fingerprints.
Signature authorization remains a separate step requiring the verifier's own
`allowed_signers` trust file.
