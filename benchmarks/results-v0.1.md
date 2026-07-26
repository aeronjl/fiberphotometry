# Preprocessing benchmark results v0.1

**Executed:** 2026-07-26 against the frozen
[`protocol-v0.1.md`](protocol-v0.1.md), using seeds 0–19.

| Scenario | Method | Median slope error | Median neural correlation | Median null RMS |
|---|---:|---:|---:|---:|
| linear shared artefact | OLS | 0.004728 | 0.628774 | 0.007670 |
| linear shared artefact | IRLS | 0.005006 | 0.628773 | 0.007507 |
| large neural transients | OLS | 0.006066 | 0.964490 | 0.013957 |
| large neural transients | IRLS | 0.010697 | 0.964360 | 0.008119 |
| reference contamination | OLS | 0.003557 | 0.237457 | 0.007399 |
| reference contamination | IRLS | 0.003487 | 0.237209 | 0.007394 |

## Threshold decisions

- **Pass:** IRLS median slope error is below 0.08 in the clean and
  large-transient scenarios.
- **Pass:** IRLS median neural correlation exceeds 0.80 with large transients.
- **Pass:** IRLS slope error is less than 0.02 worse than OLS in the clean case.
- **Fail:** IRLS does not improve median slope error by 25% with large
  transients. Its error is larger, although still small in absolute terms.
- **Diagnostic failure retained:** adding biological signal to the reference
  reduces median neural correlation from approximately 0.63 to 0.24 for the
  modest-transient simulation. Neither regression method detects or repairs this.

## Interpretation

The initial hypothesis was too broad. In these simulations the transients are
mostly uncorrelated with the shared artefact, so OLS estimates its slope well.
IRLS materially reduces null-period RMS when transients are large, consistent
with resisting their influence on the fitted baseline, but this is not the same
as improving slope recovery. A future protocol should pre-specify fitted-baseline
error and event-amplitude bias, and vary event–artefact correlation directly.

This result does not justify selecting IRLS or OLS as a universal default.

