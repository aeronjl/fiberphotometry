# SDR-0018: Summarize robustness within complete unit lanes

- Status: Accepted
- Date: 2026-07-27
- Decision owners: project maintainers
- Related schema:
  [multiverse lane summary v1](../../schemas/multiverse-lane-summary-v1.schema.json)

## Context

Separating divisive and subtractive estimates visually prevents an obvious unit
error, but HTML alone is insufficient for reproducible downstream work. A global
practical-effect threshold cannot express meaningful minima on distinct scales,
and summaries calculated only over successful workflows reward pipeline failure.

## Decision

Allow one practical-effect threshold and direction per declared unit lane. When a
per-lane policy is present, require exactly one threshold for every lane and reject
simultaneous use of the legacy global threshold.

Emit a versioned machine-readable lane-summary artifact. Calculate ranges and
medians only from successful finite estimates, but use every compatible universe
in that lane—including failed and blocked workflows—as the denominator for sign
and practical-effect stability fractions. Retain explicit universe membership in
each summary.

## Consequences

Scientists and external tools can reproduce the report's unit-local claims without
scraping presentation markup. Failure cannot inflate a robustness fraction. A lane
with no successful workflows has null magnitude summaries while retaining its
declared threshold and failure counts.

## Alternatives considered

- Store thresholds by preprocessing label: rejected because multiple labels may
  share units and should occupy one interpretable lane.
- Omit failed workflows from fractions: rejected because fragility would improve
  the apparent result.
- Add fields only to the HTML: rejected because the scientific summary requires a
  stable machine interface.

## Revisit trigger

Revisit the denominator policy if user research demonstrates that scientists need
both conditional-on-success and all-declared-workflow fractions. If both are
added, label them explicitly rather than changing the v1 meaning.

## Evidence added later

None yet.
