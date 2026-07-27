# DANDI 000251 spontaneous-transient construct-validation protocol v0.1

- Frozen: **2026-07-27, before detector outcomes were inspected**
- Status: **prospective, exploratory external validation**
- Source study: Kim et al. (2020), DOI
  [`10.1016/j.cell.2020.11.013`](https://doi.org/10.1016/j.cell.2020.11.013)

## Question and claim boundary

Can independently defined transient detectors find session-long dLight peaks that
are enriched in a published post-teleport response window, and how much do event
counts and measurements change across defensible detector choices?

This is construct validation against task timing, not manual event ground truth.
The archived signal is already dF/F and has no raw reference channel, so this study
does not validate preprocessing. Detected peaks outside task windows are called
spontaneous only in the operational sense of not being selected from those event
timestamps; they are not proven neurotransmitter-release episodes.

## Frozen cohort

Three dopamine-sensor animals (`213`, `214`, `215`), each contributing one standard
VR session and one three-teleport VR session. This is the complete paired cohort
visible together in the first DANDI API page during schema inspection. The six
assets are pinned by ID, path, byte size, and SHA-256 in
`dandi-000251-transients-manifest-v0.1.json`.

DANDI:000251 currently has only a mutable draft. A changed or missing pinned asset
is a hard failure; substitution from the draft is forbidden.

## Signal and events

- Signal: `processing["ophys"]["fluorescence"]`, described in NWB as ventral
  striatal dLight fluorescence (dF/F), sampled at 100 Hz.
- External events: finite `trials["teleport"]` timestamps in three-teleport sessions.
- Published response window: **0.6–2.1 seconds after teleport**. Kim et al. used
  this window to quantify teleport-response peaks.
- Reward timestamps and standard sessions are retained for descriptive context but
  are not used to tune or pass the external criterion.

## Detector universes

Eight universes cross:

- threshold mode: `global_mad`, `rolling_mad`;
- threshold multiplier: `3`, `5` robust standard deviations;
- pre-peak baseline statistic: `median`, `minimum`.

All other parameters are fixed prospectively: 0.9-s baseline, 0.1-s pre-peak gap,
15-s rolling-noise window, 0.2-s minimum peak distance, maximum timestamp gap of
three median sample intervals, complete half-height shape required, and 30-s
descriptive bins. No universe may be removed after execution.

## Outcomes

For every session and universe retain:

- accepted and excluded candidate counts;
- acquired duration and event rate;
- median amplitude, half-height width, AUC, and inter-event interval;
- teleport hit fraction: proportion of teleports with at least one accepted peak
  in the frozen 0.6–2.1-s window.

External enrichment is evaluated separately for each universe. Within each animal,
teleport times are circularly shifted through 999 deterministic offsets spanning
the session, preserving peak times and event spacing. The group statistic is the
mean hit fraction across the three animals. The Monte Carlo-style tail probability
is `(1 + null >= observed) / 1000`. This small cohort is descriptive: p-values do
not promote the method to supported status.

Across-universe robustness reports the full event-count range, pairwise peak-set
Jaccard agreement using a ±0.1-s matching tolerance, and the range of group teleport
hit fractions. Animal/session is always the repeated-measures boundary.

## Frozen interpretation rules

- Retain every universe, failure, and null result.
- Do not select a preferred detector from these outcomes.
- Enrichment shared by all universes supports task-response construct validity.
- Enrichment limited to some universes is a scientifically material disagreement.
- Absence of enrichment is retained as validation failure, not used to revise the
  response window or cohort.
- Neither enrichment nor agreement validates spontaneous peaks outside task windows.
- No biological “tonic” component will be inferred.

## Sources

- Kim et al., [A unified framework for dopamine signals across
  timescales](https://pmc.ncbi.nlm.nih.gov/articles/PMC7736562/).
- DANDI, [Dandiset 000251](https://dandiarchive.org/dandiset/000251/draft).
- Bruno et al., [PASTa](https://pmc.ncbi.nlm.nih.gov/articles/PMC12224222/).
- Sherathiya et al., [GuPPY](https://pmc.ncbi.nlm.nih.gov/articles/PMC8688475/).
