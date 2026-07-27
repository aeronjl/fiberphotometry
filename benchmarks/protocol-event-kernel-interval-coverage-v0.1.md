# Frozen event-kernel interval-coverage protocol v0.1

**Frozen:** 2026-07-27, before aggregate execution.

## Question

Can grouped event-kernel uncertainty provide a useful whole-model simultaneous
band without understating repeated-sampling uncertainty across realistic
animal-level photometry designs?

The target is the population-mean generating curve. The independent unit is the
animal. Coverage is evaluated against the complete generating curve, not merely at
its peak or at lags selected after viewing a fit.

## Candidate procedure

Retain the current delete-one-group jackknife pointwise sensitivity interval. For
the candidate simultaneous band:

1. convert each delete-one-group curve into a jackknife pseudo-curve;
2. concatenate every evaluated point from every event and progress kernel in the
   fitted model into one prespecified family;
3. draw 2,000 seeded Gaussian multipliers over the centered group pseudo-curves;
4. take the 95th percentile of the maximum absolute standardized deviation across
   that complete family; and
5. apply the finite-group Student-*t*/Gaussian critical-value ratio before forming
   bands around the bias-corrected jackknife estimate.

The package output must retain the method name, seed, draw count, family size,
critical value, group identities, selected ridge penalty, and both pointwise and
simultaneous bounds. Zero-standard-error points remain zero-width and are excluded
from the standardized maximum. The procedure is conditional on the selected ridge
penalty and is not selective inference.

## Deterministic simulation matrix

Run 80 independently seeded studies in each scenario. Each study uses regularly
sampled 10 Hz sessions, six repeated events or ten repeated bouts per animal, and
the same model API used by scientists.

1. **Balanced Gaussian:** eight animals, one five-lag FIR event kernel, fixed
   unpenalized fit, independent Gaussian residuals.
2. **Kernel heterogeneity:** eight animals, one five-lag FIR event kernel with
   mean-one random animal amplitudes, independent Gaussian residuals.
3. **Autocorrelated residuals:** eight animals, one five-lag FIR event kernel and
   stationary AR(1) residuals with coefficient 0.65.
4. **Overlapping selected model:** eight animals, overlapping cue and reward FIR
   kernels plus a continuous movement covariate; ridge penalty selected from
   `(0.0, 0.1, 1.0)` by animal-held-out cross-validation.
5. **Blockwise missingness:** eight animals, one five-lag FIR kernel, with a
   deterministic random block of response samples masked in every session and a
   declared 70% coverage floor.
6. **Normalized progress:** six animals, ten variable-duration bouts, a four-term
   linear progress basis evaluated at 31 progress points, and independent Gaussian
   residuals.

Generating curves, noise scales, event times, interval bounds, masks, model
specifications, and seeds are fixed in the executable benchmark. No scenario or
threshold may be changed after aggregate outcomes are inspected without creating a
new protocol version.

## Recorded outcomes

For every study retain:

- fit success or complete error text;
- selected ridge penalty and held-out mean \(R^2\);
- marginal pointwise coverage across the complete kernel family;
- whole-family pointwise-band coverage for diagnostic comparison;
- whole-family simultaneous-band coverage;
- median pointwise and simultaneous widths; and
- whether every simultaneous width is at least its pointwise counterpart.

Aggregate by scenario and retain all study-level rows in machine-readable JSON.

## Acceptance gates

The candidate may be exposed as an **experimental conditional simultaneous
sensitivity band** only if:

- at least 85% of studies in every scenario cover the complete generating family;
- marginal pointwise coverage is at least 90% in every scenario;
- every declared study fits successfully;
- every bound is finite; and
- no simultaneous band is narrower than its corresponding pointwise interval.

Overcoverage and excessive width are reported rather than hidden. Passing does not
promote the encoding model or interval to a general confidence guarantee: the
matrix is finite, the multiplier approximation is conditional on the fitted
specification, and the public DANDI example already shows temporal
misspecification. A failed gate is retained and the candidate simultaneous output
must remain unavailable by default.
