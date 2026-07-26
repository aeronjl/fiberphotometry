# Control-free bleaching benchmark protocol v0.2

Status: **frozen before aggregate execution** (26 July 2026)

This protocol follows the retained partial failure in v0.1 and the design rationale
in [SDR-0002](../docs/decisions/0002-control-free-methods-remain-experimental.md).
It separates baseline estimation from denoising and treats division and subtraction
as distinct transformations.

## Baseline-fidelity experiment

Run robust double-exponential and AsLS estimators over 20 seeds at 10, 20 and 40 Hz
for 300 s under single-exponential bleaching, double-exponential bleaching, and
double-exponential bleaching with slow sinusoidal drift. AsLS uses a nominal
smoothness of `1e8` at 20 Hz, scaled by `(rate / 20)^4` to account for its discrete
second-difference penalty. Other parameters remain those of v0.1.

Report:

- relative baseline RMSE: `sqrt(mean(((estimate - truth) / truth)^2))`;
- corrected-trace RMSE and correlation, retained descriptively from v0.1;
- median event-amplitude relative bias;
- all individual runs and effective AsLS smoothness values.

A method passes a scenario/rate cell when median relative baseline RMSE is at most
1%, corrected event-amplitude absolute bias is at most 10%, and no run fails. A
scenario passes when at least one method passes all three rates and the range of
that method's three median baseline RMSEs is at most 0.5 percentage points.

## Normalization-assumption experiment

At 20 Hz, simulate two mechanisms over 20 seeds with identical neural dF/F:

1. `indicator_bleaching`: baseline and physiological amplitude bleach together;
2. `autofluorescence_bleaching`: an additive autofluorescence component bleaches
   while indicator baseline and physiological amplitude remain constant.

Use the double-exponential baseline estimate, then either divide or subtract. For
division, event amplitude is in dF/F; for subtraction it remains in acquired
fluorescence. Calculate the absolute fractional change between median amplitudes in
the first and last third of events. The mechanism-matched transformation must have
median change at most 10%. The mismatched transformation is expected, but not
required, to exceed 10%; its result is retained rather than optimized.

## Reporting and decision rules

- Do not revise thresholds or simulation noise after aggregate execution.
- Baseline correction is not motion correction or denoising.
- Never label subtractive output dF/F.
- v0.2 passing is necessary but insufficient for typed-pipeline promotion; SDR-0002
  also requires real data with an independent control.
- Any change after execution requires a new protocol and decision-record update.
