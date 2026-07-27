# Reproducibility comparison v0.1

`compare_project_evidence` compares two verified `ProjectEvidenceBundle` objects.
The CLI exposes the same implementation through `fiberphotometry compare`.

## Three distinct claims

- **Byte identity** compares artifact checksum maps for two directories or file
  hashes for two NWB files. It is unknown across storage formats.
- **Same project** requires the exact project-configuration SHA-256.
- **Scientific equivalence** requires comparable result kinds and no substantive
  configuration, specification, data, quality, outcome, or execution differences.

Execution time and package version are retained as `provenance` differences but
do not independently defeat scientific equivalence. Numerical values use exact
comparison by default; callers may declare finite nonnegative absolute and
relative tolerances. The report records those tolerances.

## Domain-aware comparison

Primary analyses compare pipeline specification, preprocessing identity,
configuration fingerprint, data summary, event coverage, quality reports,
processing lineage, time course, blocking state, and analysis outcome. Multiverse
comparisons align universes by stable ID and compare choices, pipelines, statuses,
estimates, intervals, p-values, failures, reference selection, leave-one-out
results, and unit-local robustness summaries.

Differences are typed and addressable by path. Reports are capped at 200 entries by
default; a truncated comparison is conservatively not declared scientifically
equivalent. Markdown values are shortened for review, while JSON retains complete
values for every reported difference.

## Machine artifact

`BundleComparison.to_json()` follows the normative
[`evidence-bundle-comparison-v1` schema](https://github.com/aeronjl/fiberphotometry/blob/main/schemas/evidence-bundle-comparison-v1.schema.json).
`to_markdown()` and `write_markdown()` provide human review artifacts from the
same comparison object.
