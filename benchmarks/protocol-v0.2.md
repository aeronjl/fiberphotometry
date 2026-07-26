# Frozen preprocessing benchmark protocol v0.2

**Frozen:** 2026-07-26, before aggregate v0.2 execution.

This repository-frozen protocol responds to v0.1 and the first DANDI/IBL
validations. Changes require a new protocol version; expected and unexpected
failures remain in the report.

## Primary questions

1. Does IRLS reduce baseline distortion from large neural transients without
   degrading clean linear recovery?
2. Do missing intervals change estimates beyond loss of precision?
3. Do event-correlated motion, nonlinear coupling, lag and reference biological
   contamination produce detectable degradation rather than plausible-looking
   corrected traces?

## Fixed design

- 20 deterministic seeds per scenario.
- 120 seconds at 20 Hz; events every 15 seconds.
- Neural transient scale 0.40 for adequate recovery above measurement noise.
- OLS and Huber IRLS fitted-reference dF/F.
- No scenario-specific parameter tuning after execution.

## Scenarios

1. `clean_linear`: shared linear artefact and uncontaminated reference.
2. `large_transients`: clean model with doubled neural amplitude.
3. `dropout_blocks`: clean model with three fixed missing intervals totalling 15%.
4. `event_locked_motion`: shared artefact includes an event-shaped component,
   violating separability between behaviour, biology and motion.
5. `nonlinear_coupling`: signal contains a quadratic artefact absent from the
   linear fit.
6. `lagged_reference`: the reference artefact is delayed by 250 ms.
7. `reference_contamination`: reference contains half the neural transient scale.

## Metrics

- correlation and RMSE against known ground-truth neural dF/F;
- recovered versus true mean event amplitude and absolute amplitude bias;
- RMS corrected signal during ground-truth-null periods;
- shared-artifact slope error where the linear model is valid;
- QC warnings emitted for each scenario.

## Acceptance thresholds

- Clean IRLS ground-truth correlation ≥ 0.90.
- Clean IRLS absolute event-amplitude bias ≤ 0.005.
- IRLS null RMS at least 25% below OLS for large transients.
- Dropout IRLS correlation no more than 0.03 below clean IRLS.
- Dropout event-amplitude bias no more than 0.005 above clean IRLS.
- Event-locked, nonlinear, lagged and contaminated scenarios must each either
  emit a relevant QC warning or show ≥ 20% degradation in correlation/RMSE
  relative to clean. They are diagnostic challenges, not eligible for a generic
  pass based only on a plausible trace.

These thresholds validate only this simulator. They do not establish biological
validity or a universal correction default.
