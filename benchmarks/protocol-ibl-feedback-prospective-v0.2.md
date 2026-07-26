# Prospective IBL feedback robustness protocol v0.2

Status: **frozen but not ready to execute** (26 July 2026)

This protocol defines a held-out expansion of the descriptive feedback analysis
before additional animals' feedback contrasts are examined. The four development
animals (`fip_13`–`fip_16`) informed v0.1 and are excluded from the primary v0.2
estimate. Repeated sessions from those animals cannot satisfy the readiness gate.

## Question and estimand

For public IBL fiber-photometry recordings with a DMS channel, what is the mean
within-animal difference in feedback-aligned dF/F response between correct and
incorrect trials?

- contrast: correct minus incorrect feedback;
- response: mean 0–0.5 s minus mean -0.5–0 s;
- population unit: animal;
- target population: animals satisfying the eligibility rules below;
- intent: descriptive estimation and robustness assessment, not a causal effect of
  correctness.

Correctness is observational. Stimulus, choice, movement, reward, expectation and
trial history may confound the contrast.

## Readiness and cohort lock

Execution is permitted only when a metadata-only query finds at least 12 eligible
animals not used in v0.1. This is a feasibility threshold, not a claim that 12
animals guarantees adequate power. Before fluorescence values or trial-condition
contrasts are loaded, the analysis must commit:

1. query timestamp, ONE server/release identifier and query code;
2. all returned session, subject and laboratory identifiers;
3. exclusions with machine-readable reason codes;
4. a SHA-256 fingerprint of that frozen manifest.

If fewer than 12 new animals are eligible, report the shortfall and stop. Do not
relax criteria after inspecting outcomes. A future amendment must receive a new
protocol version and state whether any outcome data were seen.

## Eligibility fixed before outcome access

Include every public session that has photometry signal, ROI locations, feedback
times and feedback type; contains a DMS-labelled channel; can be converted by the
versioned IBL adapter; and has at least 20 usable correct and 20 usable incorrect
events after fixed boundary/missingness checks. Include every animal with at least
one such session.

Exclude only duplicate session identifiers, missing required objects, absent DMS,
adapter/schema failure, or insufficient usable events. Signal-quality gates remain
non-destructive workflow outcomes: they may block a universe but do not silently
remove an animal from other universes.

## Repeated-session hierarchy

Trials are nested in sessions and sessions in animals. The primary workflow first
computes a condition contrast within each session, then averages session contrasts
with equal weight within animal, then estimates the mean and t interval across
animals. Thus an animal with many sessions is not treated as many independent
animals. Report session counts and contrasts so within-animal heterogeneity remains
visible.

Secondary models may use all trials or sessions only when they include animal-level
clustering/random effects and have an independently validated implementation.
They cannot replace the primary result merely because their interval is narrower.

## Frozen multiverse

Use the same nine universes as v0.1:

- correction: OLS reference dF/F; robust IRLS reference dF/F; or 20 Hz resampling,
  3 Hz fourth-order low-pass filtering, then IRLS;
- window: standard (-0.5–0 s, 0–0.5 s), early (-0.5–0 s, 0–0.25 s), or displaced
  baseline (-1.0–-0.2 s, 0–0.5 s).

The reference universe remains IRLS with the standard window. No smallest effect
of interest is declared. Report every universe, including blocked and failed ones,
the estimate distribution, confidence intervals, decision-wise summaries, and
leave-one-animal-out estimates. The specification curve must be generated from the
complete machine-readable result artifact.

## Interpretation rules

- Emphasize effect sizes, intervals and between-universe dispersion.
- Do not count the nine dependent universes as nine replications.
- Do not select a preferred workflow from its p-value.
- Stable reference-based answers do not validate reference-channel assumptions.
- Label v0.1 plus v0.2 estimates as development/held-out, respectively; show any
  pooled estimate only as a separately labelled secondary analysis.
- Treat direction changes, materially different magnitudes, blocked workflows and
  dependence on one animal as substantive findings rather than nuisances.

## Rationale and methodological context

Multiverse analysis exposes dependence on defensible data-construction choices
([Steegen et al., 2016](https://doi.org/10.1177/1745691616658637)); specification
curves pair ordered estimates with the choices producing them
([Simonsohn et al., 2020](https://doi.org/10.1038/s41562-020-0912-z)). Neither turns
post-hoc alternatives into independent evidence. Fiber-photometry observations are
repeated within animals, and trial pooling without the hierarchy can yield
misleading precision; the primary aggregation therefore preserves the animal as
the population unit (see the trial/session distinction in
[Loewinger et al., 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11903033/)).

## Amendments

None. Any change after this commit requires a dated amendment stating the change,
rationale, and outcome-data access status. Changes to the estimand, eligibility,
readiness threshold, primary hierarchy, or reference universe require v0.3.
