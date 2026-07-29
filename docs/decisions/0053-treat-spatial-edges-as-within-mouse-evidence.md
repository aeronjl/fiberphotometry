# SDR-0053: Treat spatial edges as within-mouse evidence

- **Status:** Accepted
- **Date:** 2026-07-28
- **Decision owners:** fipha maintainers
- **Related:** SDR-0046, SDR-0051

## Context

Dense multi-fiber recordings produce many sites and still more pairwise edges per
session. Those edges share nodes, preprocessing, clock, animal and experimental
history. Treating them as independent observations would make uncertainty shrink
with array density even when the number of animals has not changed.

Coordinates also create analysis choices: coordinate space and unit, distance
bins, edge metric, missingness denominator, correlation scale and the spatial
null's exchangeability assumptions. These choices must remain visible if later
geometry or biological knowledge changes.

## Decision

fipha will:

1. require explicit coordinates in one shared named space and unit;
2. estimate each edge through the existing joint-validity, gap-separated paired
   signal contract;
3. retain every candidate edge or a typed exclusion reason;
4. use Fisher-z averaging by default while reporting in correlation units;
5. treat node-label permutation as a within-session spatial sensitivity analysis;
6. reduce edges to a session estimand, sessions equally within mouse and condition,
   and only then contrast mice; and
7. expose support and edge counts as denominators, never as replicate counts.

The API will not label association networks as causal or use graph-edge counts to
set animal-level uncertainty.

## Alternatives considered

### Fit one edge-level mixed model

Rejected as the default. A valid crossed random-effects or covariance model may be
useful for a specified design, but a generic edge model cannot infer the right
node, session, animal and spatial covariance structure from array shape alone.

### Weight session summaries by temporal support or edge count

Rejected. This changes the estimand toward longer sessions and denser or cleaner
arrays. Support remains essential quality evidence but is not biological
replication.

### Permute time series independently across nodes

Rejected for the spatial null. It destroys temporal and network structure. The
implemented null holds observed edges fixed and permutes coordinate labels.

### Freeze one anatomical distance model

Rejected. Named coordinate spaces, explicit bins and serialized specifications
allow later atlas-aware or constrained permutation extensions without silently
changing earlier results.

## Consequences

- Dense arrays yield richer within-session evidence but do not manufacture mice.
- Users can audit which gaps, invalid samples and excluded edges produced each
  summary.
- Unrestricted node-label permutations may be inappropriate for stratified or
  asymmetric implants; the documentation requires users to omit that null when
  its exchangeability assumption fails.
- A scalar mouse contrast sacrifices some edge-level detail. The full session
  networks remain available for future typed spatial models.

## Revisit trigger

Revisit when public raw dense-array datasets with multiple animals and known
geometry support validation of constrained spatial permutations or a prespecified
crossed site/animal model. A new model must preserve the current edge ledger and
must demonstrate calibrated animal-level uncertainty before becoming a default.
