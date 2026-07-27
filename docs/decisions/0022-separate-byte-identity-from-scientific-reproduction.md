# SDR-0022: Separate byte identity from scientific reproduction

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related contract:
  [Reproducibility comparison v0.1](../reproducibility-comparison-v0.1.md)

## Context

Re-executing an unchanged analysis records a new execution time and may use a new
package version, so byte equality is stronger than scientific reproduction.
Conversely, matching filenames or aggregate estimates do not establish that the
same estimand, data selection, preprocessing, and universe ledger were used.

## Decision

Report byte identity, project fingerprint identity, and scientific equivalence as
separate claims. Treat execution time and package version as visible provenance
differences, not substantive failures by themselves. Compare primary analyses by
their scientific components and align multiverse workflows by stable universe ID.

Use exact numeric comparison by default and require callers to record any absolute
or relative tolerance. Classify every reported change as configuration,
specification, data, quality, outcome, execution, or provenance. A truncated diff
must not claim equivalence.

## Consequences

Independent formats can reproduce scientifically without pretending to share
bytes. Reviewers can distinguish benign regeneration metadata from altered data or
methods. Exact project fingerprints remain conservative: semantically similar but
textually changed project files are reported as different configurations.

## Alternatives considered

- Compare only manifests: rejected because timestamps can change bytes while
  leaving the scientific result intact.
- Compare only final estimates: rejected because different workflows can coincide
  numerically.
- Ignore provenance differences entirely: rejected because version and execution
  context remain important for audit and diagnosis.

## Revisit trigger

Add field-specific tolerances only when validation demonstrates that one global
numeric policy is insufficient. Any defaults must remain zero unless justified by
a documented numerical reproducibility benchmark.

## Evidence added later

None yet.
