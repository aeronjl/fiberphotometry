# DANDI 000351 raw-to-archived dF/F parity protocol v0.1

Status: **frozen before aggregate execution** (26 July 2026)

## Purpose and scope

Test whether explicit ordinary or robust affine reference correction reproduces
the archived dF/F stored beside raw 405/470-nm signals in DANDI:000351. This is an
interoperability and provenance audit, not validation of the archived processing
and not a biological analysis.

DANDI:000351 has no published version. At freezing, its draft reported 428 assets,
98,548,166,664 bytes, and one active upload. Exact asset IDs, paths, sizes, and
SHA-256 digests are pinned in
[`dandi-000351-parity-manifest-v0.1.json`](dandi-000351-parity-manifest-v0.1.json).
The exploratory asset used to understand the schema is excluded from aggregate
execution.

## Frozen extraction

- Require `acquisition/photometry/data_identity == "raw405,raw470"` and a
  two-column raw matrix in that order.
- Require `processing/photometry/dff/data`, raw and archived timestamps, and equal
  sample counts.
- Require raw and archived timestamps to agree within 1 microsecond wherever both
  are finite; do not interpolate misaligned series.
- Retain non-finite samples and report finite fractions rather than silently
  trimming them.
- Verify the exact byte size and SHA-256 digest before signal access.

## Frozen candidate reconstructions

For finite paired raw samples, fit the 405-nm control to the 470-nm signal across
the full session using:

1. ordinary least squares (OLS);
2. Huber iteratively reweighted least squares (IRLS), using the package default.

For both, calculate percentage dF/F as
`100 * (raw470 - fitted405) / fitted405`. Do not filter, detrend, zero, or rescale
either result after fitting. Archived dF/F is a parity target, not ground truth.

## Frozen metrics and gates

For each of four sessions and both candidates, report finite fraction, Pearson
correlation with archived dF/F, RMSE in percentage points, mean signed difference,
and 99th-percentile absolute difference.

Engineering gates:

- all asset digests and required schemas pass;
- timestamps align within 1 microsecond;
- each candidate is finite wherever both raw inputs are finite.

Descriptive exact-parity gate, evaluated per method across all four sessions:

- minimum session correlation at least 0.95; and
- maximum session RMSE at most 0.50 percentage points.

Failure does not imply the archived output is wrong. It indicates that unrecorded
or untested processing choices remain. Do not tune a method after seeing aggregate
results; any follow-up becomes a separately frozen protocol.
