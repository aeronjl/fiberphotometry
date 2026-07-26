# SDR-0008: Preserve open metadata with versioned readiness profiles

- **Status:** Accepted
- **Date:** 2026-07-26

## Context

Acquisition systems, repositories, laboratories, and reporting standards attach
different metadata to fiber-photometry experiments. A closed project ontology
would either discard useful information or require disruptive schema migrations.
An entirely unstructured table, however, cannot tell a scientist what is absent.

## Decision

Project files may contain an open `[metadata]` table. All TOML-native fields are
retained in normalized project provenance, including fields the current package
does not recognize.

A separately versioned `fiberphotometry-metadata-v0.1` profile evaluates a small
set of fields for three distinct targets: executable analysis, NWB export, and
publication/reuse. Checks are explicit and actionable. Unrecognized top-level
fields are reported but never discarded or treated as errors.

Readiness means satisfying this profile only. It is not a claim of compliance
with every journal, repository, ontology, FAIR assessment, or local policy.

## Alternatives considered

- **Closed typed ontology.** Rejected because scientific metadata conventions
  will evolve and lab-specific metadata must survive round trips.
- **Unstructured metadata without assessment.** Rejected because it gives users
  no actionable account of what is missing.
- **One global completeness score.** Rejected because analysis, NWB export, and
  publication have different requirements and a percentage obscures that fact.

## Consequences

The configuration remains extensible while recognized checks are reproducible.
Future profiles can add or refine checks without invalidating preserved metadata.
The v0.1 publication profile is deliberately minimal and must be described as
such in user-facing output.

## Revisit trigger

Revisit when a target repository or community standard is adopted, when metadata
must vary by subject/session/channel, or when mappings to controlled vocabularies
become part of the stable API.
