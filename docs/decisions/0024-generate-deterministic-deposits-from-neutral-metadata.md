# SDR-0024: Generate deterministic deposits from neutral metadata

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract: [Archival deposition v0.1](../archive-deposition-v0.1.md)

## Context

A scientifically complete evidence bundle is not yet repository-ready. DOI
services require discovery and citation metadata, while repository-specific
records can drift if authors maintain DataCite and Zenodo descriptions separately.
Ordinary ZIP creation also embeds incidental timestamps and may include unrelated
files, preventing stable deposit fingerprints.

## Decision

Maintain one strict, versioned, repository-neutral archive metadata record.
Generate DataCite and Zenodo projections from it, package only manifest-verified
evidence plus paired publication signature files, and inventory every deposited
file by byte length and SHA-256. Create ZIP entries in a canonical order with
fixed timestamps, permissions, and compression settings.

Keep upload and DOI publication outside this command. Repository credentials,
record reservation, embargo policy, and the irreversible act of publishing need
an explicit later workflow and human review.

## Consequences

The same inputs yield the same deposit bytes, repository metadata shares one
authorship source, and a recipient can verify an archive offline. The neutral v1
schema intentionally supports the shared, high-value subset; repository-specific
features such as communities, grants, and embargoes remain future extensions.

## Alternatives considered

- Treat `.zenodo.json` as canonical: rejected because it couples the product to
  one repository and weakens direct DataCite interoperability.
- Archive the entire output directory: rejected because undeclared files and
  platform metadata would enter deposits silently.
- Upload directly from the analysis command: rejected because deposition and
  especially DOI publication have different authorization and review boundaries.

## Revisit trigger

Add a repository adapter when an authenticated sandbox deposition demonstrates a
stable need. Preserve the neutral record and deterministic package as the review
boundary.
