# SDR-0044: Require comparability evidence before longitudinal handoff

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

A trial table can be structurally valid while its neural column changes meaning
across sessions. Sensor, implant site, units, normalization, preprocessing, data
coverage, hardware, reference coupling, or raw fluorescence scale may differ.
Unspool can model a trajectory through those values but cannot determine whether
they still represent the same photometry measurement.

Automatically harmonizing sessions would hide measurement changes. Rejecting every
numerical shift would also be inappropriate because bleaching, expression, motion,
and hardware differences can change outcome-blind diagnostics without invalidating
normalized estimands.

## Decision

fipha owns a typed, outcome-blind across-session comparability preflight.

- Analysts declare one record per subject, session, and logical neural series.
- Sensor, site, output-variable, and unit changes are refusal states.
- Preprocessing changes refuse by default and can be prospectively downgraded to a
  warning.
- Finite fraction and event coverage receive per-session thresholds.
- Raw-baseline fold change, reference-correlation range, and sampling-rate ratio
  receive explicit warning and refusal thresholds.
- Missing diagnostics remain visible and can be made mandatory prospectively.
- The complete report is fingerprinted and can be required by the Unspool export.
- Export refuses failed evidence and sessions absent from the report. Warnings are
  retained and may be allowed or refused explicitly.

No neural outcomes enter the assessment.

## Alternatives considered

- **Let Unspool diagnose measurement drift.** Rejected because longitudinal model
  fit cannot distinguish biological change from an altered optical measurement.
- **Silently normalize each session.** Rejected because it changes the estimand and
  can erase real longitudinal variation.
- **Use a single universal pass/fail threshold.** Rejected because diagnostics have
  different meanings and tolerances depend on the declared analysis.
- **Refuse every hardware or baseline change.** Rejected because these can be
  legitimate while still requiring explicit review.

## Consequences

Longitudinal handoffs can carry machine-checkable evidence that the neural series
was reviewed on a common operational basis. Thresholds and missingness policies are
visible rather than embedded in plotting code. Warning-bearing analyses remain
possible, but the warning is part of the fingerprinted handoff.

The v0.1 thresholds are product defaults, not validated field-wide scientific
cutoffs. They must remain configurable and cannot substitute for histology,
sensor-specific diagnostics, or a measurement-error model.

## Revisit trigger

Revisit after two external longitudinal datasets provide independently reviewed
session exclusions, or after sensor/isobestic validity and calibration metadata can
support more specific preflight rules.
