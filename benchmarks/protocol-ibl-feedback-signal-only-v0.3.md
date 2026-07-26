# Prospective IBL feedback signal-only protocol v0.3

Status: **frozen after readiness, before photometry-outcome access** (26 July
2026)

This protocol supersedes the non-normative v0.3 design draft for the held-out IBL
cohort. It does not amend or rescue the failed paired-reference v0.2 protocol.

## Estimand and interpretation

Estimate the animal-level correct-minus-incorrect difference in feedback-aligned
DMS fluorescence response. Trials are nested in sessions and sessions in animals;
session contrasts are equally weighted within animal. The intent is exploratory
description, not causal inference.

Only explicitly labelled 470-nm samples enter the recording. Wavelength-0 no-LED
rows are ignored and no reference channel is constructed. Results therefore remain
vulnerable to motion, haemodynamic, and other signal-only confounds.

## Frozen cohort gate

The outcome-blind query excludes development animals `fip_13`–`fip_16`, requires a
DMS ROI, at least 20 usable correct and 20 usable incorrect events per session, and
at least 12 eligible animals. Usability conservatively requires the entire widest
event window to lie inside a full 60-second rolling-baseline interval. Timestamp
gaps split intervals.

The query read photometry timestamps, wavelength/include flags, ROI labels, and
behavioural event labels/counts. It did not load ROI fluorescence values or compute
condition-specific fluorescence summaries.

The gate passed with 383 sessions from all 18 held-out animals. Twenty-four
sessions failed the event-count rule; 139 development-animal sessions remained
excluded. The complete manifest is
[`ibl-feedback-cohort-v0.3.json`](ibl-feedback-cohort-v0.3.json), SHA-256
`38197a26ab4804131423a9650a473a11e2b14f09ac2877875b574f2770d894e6`.

## Frozen multiverse

Cross three event windows with these preprocessing families:

- double-exponential baseline with divisive dF/F and subtractive delta-F;
- rate-aware AsLS baseline with divisive dF/F and subtractive delta-F;
- the published centred 60-second rolling baseline with divisive dF/F only.

The windows are standard (-0.5–0 s, 0–0.5 s), early (-0.5–0 s, 0–0.25 s), and
displaced baseline (-1.0–-0.2 s, 0–0.5 s). This yields 15 executable universes.
Three rolling/subtractive combinations are materialized and retained as explicitly
incompatible, because the published workflow was declared only as divisive dF/F.

Divisive and subtractive estimates have different units. They must be displayed in
separate panels and must not be pooled into one estimate distribution, median, or
direction fraction. The published rolling/standard universe is a display and
leave-one-animal-out reference only; it is not a preferred or confirmatory method.

Retain every successful, blocked, failed, and incompatible universe. Report
animal-level intervals, leave-one-animal-out direction changes, estimator/window
decisions, QC warnings, sampling rates, retained events, and baseline failures.

## Stop and amendment rules

Do not select a workflow from its observed magnitude or p-value. Do not silently
drop failed universes or animals. Any change to eligibility, the 15 workflows,
event windows, hierarchy, gap/edge policy, or reporting separation requires a new
version and a dated statement of what outcomes had already been accessed.

The complete typed specification and materialization are in
[`ibl-feedback-protocol-v0.3.json`](ibl-feedback-protocol-v0.3.json), SHA-256
`abcec0a742a20869b7522c1cd700391371764afb9fa60778e16579a7876f05fc`.
