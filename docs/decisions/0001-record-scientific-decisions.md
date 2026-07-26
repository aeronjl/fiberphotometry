# SDR-0001: Record consequential scientific decisions

- Status: Accepted
- Date: 2026-07-26
- Decision owners: project maintainers
- Related protocol/report: none

## Context

Fiber-photometry workflows contain reasonable but consequential choices. Source
code and final reports reveal what was implemented, but not necessarily when a
default was withheld, why a metric changed, or which alternatives were considered.
Retrospective explanations can accidentally make exploratory choices look planned.

## Decision

Maintain numbered scientific decision records for changes to recommended methods,
defaults, estimands, benchmark interpretation, inference policy, compatibility and
deprecation. Record negative and deferred decisions as carefully as additions.

Keep working designs in `docs/drafts/`, frozen pre-execution rules in benchmark
protocols, complete outcomes in machine-readable artifacts, and post-execution
interpretation in reports. Each document must link to the adjacent layers.

## Consequences

Users can audit both the evidence and project judgment. Maintainers incur a small
documentation cost and must resist silently editing historical rationale.

## Alternatives considered

- Git history alone: rejected because intent is difficult to discover and commits
  mix scientific and implementation details.
- Reports alone: rejected because they are written after observing results.
- One continuously edited design document: retained for drafts, but insufficient as
  a chronological decision trail.

## Revisit trigger

Reconsider the format if external contributors find it burdensome or if a formal
governance system replaces repository-local review.

## Evidence added later

None.
