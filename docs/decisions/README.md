# Scientific decision records

This directory records consequential scientific and API decisions, including
decisions to defer or reject a method. It is an audit trail, not a claim that every
decision is permanent.

## Status vocabulary

- **Draft:** proposed and open to change; not normative.
- **Accepted:** current project policy.
- **Rejected:** considered but not adopted.
- **Superseded:** replaced by a later numbered record, which must link back.

Decision records state their date, evidence available at that date, alternatives,
consequences and an explicit revisit trigger. Later evidence is appended or linked;
the original reasoning is not silently rewritten.

## Relationship to other documents

- `docs/drafts/` contains working designs and questions. Drafts may change freely
  and must not be cited as package guarantees.
- `benchmarks/protocol-*.md` freezes hypotheses, scenarios and thresholds before
  aggregate execution.
- benchmark JSON files retain complete machine-readable outcomes.
- reports describe results after execution and link to the governing decisions.

## Index

| Record | Status | Decision |
| --- | --- | --- |
| [SDR-0001](0001-record-scientific-decisions.md) | Accepted | Record consequential scientific decisions |
| [SDR-0002](0002-control-free-methods-remain-experimental.md) | Accepted | Keep initial control-free methods experimental |
| [SDR-0003](0003-separate-subtraction-and-division.md) | Accepted | Represent subtraction and division as different transformations |
| [SDR-0004](0004-require-explicit-derived-data-alignment.md) | Accepted | Require explicit alignment for externally derived data |
| [SDR-0005](0005-do-not-infer-photometry-channel-identity.md) | Accepted | Do not infer photometry channel identity from row position |
| [SDR-0006](0006-require-explicit-nwb-session-metadata.md) | Accepted | Require explicit NWB session metadata and avoid invented hardware |
| [SDR-0007](0007-require-explicit-tdt-store-mapping.md) | Accepted | Require explicit TDT stream, channel, and epoc semantics |
| [SDR-0008](0008-open-metadata-versioned-readiness-profile.md) | Accepted | Preserve open metadata while versioning readiness profiles |
| [SDR-0009](0009-separate-structural-incompatibility-from-scientific-failure.md) | Accepted | Preflight structural incompatibility without accessing outcomes |
| [SDR-0010](0010-mixed-models-are-sensitivity-summaries.md) | Accepted | Report scalar mixed models as secondary sensitivity summaries |
| [SDR-0011](0011-regularize-irregular-clocks-prospectively.md) | Accepted | Regularize irregular clocks only through prospective, auditable policy |
| [SDR-0012](0012-protect-missing-event-windows.md) | Accepted | Protect missing event windows instead of silently reconstructing them |
| [SDR-0013](0013-report-event-selection-before-preprocessing.md) | Accepted | Report event selection before and after preprocessing |
| [SDR-0014](0014-resample-animals-for-peri-event-bands.md) | Accepted | Resample animals for peri-event uncertainty |
| [SDR-0015](0015-use-a-frozen-public-nwb-golden-path.md) | Accepted | Use a frozen public NWB golden path |
| [SDR-0016](0016-require-named-multiverse-alternatives.md) | Accepted | Require named, justified multiverse alternatives |
| [SDR-0017](0017-couple-preprocessing-outputs-and-separate-units.md) | Accepted | Couple preprocessing outputs and separate incompatible units |

Use four-digit monotonically increasing identifiers. Copy
[`template.md`](template.md), fill every heading, and add the record to this index.
