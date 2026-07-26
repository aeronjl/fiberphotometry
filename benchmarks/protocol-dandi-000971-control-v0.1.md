# DANDI 000971 independent-control pilot protocol v0.1

Status: **frozen before aggregate signal execution** (26 July 2026)

## Purpose and scope

Test experimental signal-only bleaching baselines against an independently acquired
405-nm isosbestic channel in real dual-site recordings. This is a four-animal
engineering and assumption audit, not population validation and not proof that the
isosbestic channel is biologically inert.

The immutable published Dandiset version is `000971/0.260213.1851`. The asset IDs,
paths, sizes and SHA-256 digests were fixed before signal analysis in
[`dandi-000971-pilot-manifest-v0.1.json`](dandi-000971-pilot-manifest-v0.1.json).
One photometry-bearing NWB is selected from each FP-PR, FP-DPR, FP-PS and FP-RR20
family.

## Frozen extraction

- Require exactly two regions, DMS and DLS, each with a calcium-signal and an
  isosbestic-control column identified from the NWB commanded-voltage series.
- Read the acquired fluorescence without using behavioral outcomes.
- Block-average both channels to approximately 20 Hz; retain source rate, block
  size and achieved rate in provenance.
- Analyze each region separately and retain all failures.

## Frozen methods and comparator

Fit the v0.2 control-free defaults to the calcium channel:

1. robust double-exponential baseline;
2. rate-aware AsLS baseline.

Construct the independent acquisition comparator by robustly fitting an affine map
from the isosbestic channel to calcium, then applying a zero-phase fourth-order
0.05-Hz low-pass filter to the fitted reference. Apply the same low-pass filter to
each control-free fitted baseline before comparison. The comparator is a slow
reference trend, not ground-truth bleaching.

## Frozen metrics and gates

For each of eight session-region cases and both methods, report:

- finite fraction of the fitted baseline;
- Pearson correlation with the slow fitted-isosbestic trend;
- relative RMSE against that trend;
- fractional start-to-end change in both trends;
- correlation between corrected dF/F and the acquired isosbestic channel.

Engineering gates:

- all four assets match their SHA-256 digest;
- all assets expose the required four-column schema;
- every method produces at least 99% finite baseline samples.

Scientific descriptive gates:

- median slow-trend correlation at least 0.90;
- median relative RMSE at most 10%;
- no promotion decision may be based on these gates alone.

## Interpretation rules

- Agreement supports real-data plausibility, not identifiability.
- Disagreement can reflect a poor signal-only baseline, reference contamination,
  wavelength-specific bleaching, or an invalid affine map.
- Do not call the isosbestic channel a stable fluorophore.
- Do not use behavioral labels or select time windows after inspecting agreement.
- Update SDR-0002 with the result; typed-pipeline promotion still requires broader
  real-data validation and explicit user-facing method selection.
