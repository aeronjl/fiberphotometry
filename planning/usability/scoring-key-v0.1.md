# Scoring key v0.1

Keep this document hidden from participants. Award points for scientific meaning,
not exact wording. Assisted answers can receive accuracy points but must be marked
assisted.

## Task 1 — claim and design (2 points)

- 1 point: drug minus control DMS event response (equivalent wording accepted).
- 1 point: animal-level aggregation **and** exploratory intent.

Critical errors: calling events/workflows the population unit; describing the
analysis as confirmatory or randomized.

## Task 2 — unit boundary (2 points)

- 1 point: explicitly rejects one pooled magnitude.
- 1 point: explains that ΔF/F and acquired-fluorescence differences are
  incommensurate; lane magnitudes/ranges must be interpreted locally.

Critical error: pools or directly ranks effect magnitudes across lanes.

## Task 3 — robustness (2 points)

- 1 point: recognizes that successful workflows within both lanes retain the same
  apparent positive direction.
- 1 point: qualifies this as synthetic, exploratory workflow robustness rather
  than proof of a biological effect, and notes the retained execution failure.

Critical error: treats workflow agreement as independent biological replication.

## Task 4 — complete accounting (2 points)

Generate the frozen report before scoring and read its headline counts. Award:

- 1 point: all success/failed/blocked headline counts correct.
- 1 point: incompatible count correct and the failed workflow located in the
  ledger with its reason, rather than assumed to have been dropped.

Critical error: reports only successful workflows or says failure was excluded.

## Task 5 — provenance recovery (2 points)

- 1 point: response-window choice matches the named ledger row.
- 1 point: normalization choice matches the named ledger row.

Use the universe named by the moderator at session time; do not rely on row order
remaining stable across future protocol versions.

## Recurring-error codes

- `E-UNIT`: aggregation unit misunderstood.
- `E-POOL`: incompatible units pooled or compared as magnitudes.
- `E-ROBUST`: workflow agreement overstated as biological replication.
- `E-FAIL`: failed/blocked/incompatible workflow missed or treated as deletion.
- `E-PROV`: choices cannot be recovered from the ledger.
- `E-NAV`: correct evidence exists but is not found.
- `E-LABEL`: wording is found but interpreted incorrectly.
