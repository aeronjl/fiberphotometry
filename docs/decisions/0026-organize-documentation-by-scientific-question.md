# SDR-0026: Organize documentation by scientific question

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related evidence: [Literature and capability audit](https://github.com/aeronjl/fiberphotometry/blob/main/planning/literature-capability-audit-v0.2.md)

## Context

The repository accumulated detailed contracts, benchmarks, validation reports,
and decision records, but filenames and chronology did not help a scientist find
an analysis for a particular question. Documentation breadth could therefore be
mistaken for product breadth, while unsupported method families were not visible
from the entry point.

## Decision

Publish the Markdown documentation as a searchable site organized around
scientific tasks: getting started, methods, worked examples, data and
interoperability, publication, evidence, and reference. Maintain one capability
matrix that labels method families as supported, experimental, planned, or
out-of-scope.

Require a worked scientific example, assumptions, failure behavior, and an
explicit estimand before a major method family is presented as supported. Keep
benchmarks and decision records accessible as evidence without placing them in
the primary learning path.

## Consequences

Scientists can determine quickly whether the package answers their question, and
missing coverage becomes a product roadmap rather than an implicit promise. Site
builds fail on broken internal links or API documentation. Existing Markdown
continues to render on GitHub and remains the source of truth.

## Alternatives considered

- Publish the existing `docs/` directory without curated navigation: rejected
  because it reproduces the discoverability problem in a different renderer.
- Organize primarily by Python module: rejected because neuroscientists begin
  with experimental questions, not package architecture.
- Hide planned methods: rejected because transparent boundaries help users avoid
  forcing unsupported analyses through the event workflow.

## Revisit trigger

Revise the taxonomy after moderated usability sessions or when a new supported
method family no longer fits the current scientific-task structure.
