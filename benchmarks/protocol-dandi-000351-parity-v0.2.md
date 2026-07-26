# DANDI 000351 timestamp-aligned dF/F parity protocol v0.2

Status: **frozen after v0.1 structural audit and before numerical parity execution**
(26 July 2026)

## Rationale

Protocol v0.1 established that archived dF/F is not sample-aligned to raw data.
This follow-up changes exactly one design choice: candidate reconstructions are
linearly interpolated from finite raw timestamps onto finite archived timestamps
within their shared time domain. No extrapolation is permitted.

The dataset, four checksum-pinned assets, raw identity, candidate OLS/IRLS fits,
percentage dF/F formula, metrics, and exact-parity thresholds remain those in
[v0.1](protocol-dandi-000351-parity-v0.1.md).

## Additional extraction rules

- Raw timestamps must be strictly increasing after non-finite rows are excluded.
- Archived timestamps must be strictly increasing after non-finite rows are
  excluded.
- Fit each affine model using all finite raw 405/470 pairs.
- Calculate candidate percentage dF/F at raw samples, then linearly interpolate it
  onto archived timestamps inside the inclusive raw time range.
- Exclude archived samples outside that shared domain and report their count and
  fraction. Do not extrapolate or silently replace archived non-finite values.

## Interpretation

Passing establishes reproducibility of the archived numerical transformation up
to recorded-clock interpolation. Failure means filtering, fitting windows,
resampling implementation, or other unrecorded processing choices remain. It does
not adjudicate which workflow is scientifically preferable.
