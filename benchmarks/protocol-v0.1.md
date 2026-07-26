# Frozen preprocessing benchmark protocol v0.1

**Frozen:** 2026-07-26, before examining the aggregate benchmark outcomes.

This is a repository-frozen protocol, not a claim of registration in an external
registry. Any changes to scenarios or thresholds require a new versioned file;
failed scenarios remain visible.

## Primary question

Does Huber IRLS recover a linearly shared reference contribution more faithfully
than OLS when neural transients are large, without materially degrading recovery
in the clean linear case?

## Fixed scenarios

Each scenario uses 20 deterministic seeds, 120 seconds at 20 Hz, events every 15
seconds, Gaussian measurement noise, a sinusoidal shared artefact, and a slowly
decaying common component.

1. `linear_shared_artifact`: modest neural transient, uncontaminated reference.
2. `large_neural_transients`: fivefold larger neural transient, uncontaminated
   reference; tests whether OLS absorbs positive transients.
3. `reference_contamination`: reference contains half the signal-channel neural
   amplitude; a deliberate assumption violation and expected failure case.

## Methods

- OLS fit of signal on intercept plus reference.
- Huber IRLS using median absolute-deviation scale and tuning constant 1.345.
- Identical fitted-reference dF/F calculation after fitting.

## Metrics

- absolute error in the known shared-artifact slope (true value 1.4);
- Pearson correlation of corrected dF/F with the neural ground truth;
- RMS corrected signal where the ground-truth neural component is zero.

## Acceptance thresholds

These thresholds govern only the current simulation family:

- median IRLS slope error below 0.08 in the linear and large-transient scenarios;
- median IRLS neural correlation above 0.80 in the large-transient scenario;
- median IRLS slope error no more than 0.02 worse than OLS in the linear scenario;
- IRLS must improve median slope error by at least 25% over OLS with large
  transients;
- the reference-contamination scenario is not eligible to pass. It must be
  reported as an assumption-violation diagnostic, not hidden or optimised away.

Passing does not validate the method for experimental data. The next protocol
must add nonlinear, lagged, bleaching, dropout and event-locked motion artefacts.

