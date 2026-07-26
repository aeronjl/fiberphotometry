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

Use four-digit monotonically increasing identifiers. Copy
[`template.md`](template.md), fill every heading, and add the record to this index.
