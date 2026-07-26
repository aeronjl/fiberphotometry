# Prospective IBL feedback signal-only protocol v0.3.1

Status: **frozen before photometry-outcome access** (26 July 2026)

This is a narrow pre-outcome amendment to
[v0.3](protocol-ibl-feedback-signal-only-v0.3.md). The cohort, eligibility gate,
preprocessing methods, normalization families, event windows, incompatibility
rules, reference role, and reporting requirements are unchanged.

## Reason for amendment

The v0.3 prose required session contrasts to be equally weighted within animal.
Its typed `Estimand`, however, declared only `aggregation_unit = "animal"`. The
implemented paired estimator therefore pooled events within animal, implicitly
giving sessions with more retained events more weight.

This mismatch was identified during the execution audit. No v0.3 photometry
values, condition-specific fluorescence summaries, contrasts, intervals, or
p-values had been accessed. The v0.3 files remain unchanged as an audit record.

## Corrected typed estimand

v0.3.1 adds `contrast_unit = "session"`. For every universe:

1. calculate correct-minus-incorrect from event summaries within each session;
2. average complete session contrasts equally within each animal;
3. estimate and test the mean across the 18 animals.

An unbalanced fixture verifies that this differs from trial-count-weighted pooling.
No incomplete session may be silently dropped.

The frozen machine-readable protocol is
[`ibl-feedback-protocol-v0.3.1.json`](ibl-feedback-protocol-v0.3.1.json). Its hash
is recorded inside that file and must be verified before execution.

All interpretation and stop rules from v0.3 continue to apply. In particular,
divisive and subtractive outcomes remain separate evidence lanes, every failure
class is retained, and the published rolling workflow is not promoted to a
confirmatory or preferred analysis.
