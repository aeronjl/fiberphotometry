# Frozen preprocessing-sequence benchmark protocol v0.8

**Frozen:** 2026-07-26 before aggregate numerical execution, after implementation
and unit-level examples were inspected.

## Scenarios

1. Resample a known 1.3 Hz sine from a deterministic irregular time grid to 20
   Hz. Remove source samples strictly between 4 and 5 seconds and set the maximum
   bridgeable source gap to 0.1 seconds.
2. Low-pass a 100 Hz signal containing a unit-amplitude 1 Hz component and a
   0.5-amplitude 20 Hz component with a fourth-order 5 Hz zero-phase Butterworth
   filter.

## Acceptance criteria

- Resampling RMSE outside the declared gap is below 0.01.
- No interpolated samples occur strictly inside the declared gap.
- Source and pre-filter arrays are retained exactly.
- Low-frequency reconstruction RMSE is below 0.03.
- The 20 Hz component is attenuated by at least 95%.
- Provenance reports the interpolation method, gap limit, filter implementation,
  and edge-padding samples.

All criteria are retained whether they pass or fail. This numerical benchmark
tests implementation behavior, not biological validity or optimal parameter
selection.
