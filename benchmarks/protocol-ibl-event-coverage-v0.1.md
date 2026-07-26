# IBL event-coverage audit v0.1

Status: **frozen before aggregate execution** (26 July 2026).

This outcome-blind audit asks whether the prospective irregular-clock policy can
retain event windows in the 383-session IBL feedback cohort without bridging
missing observations. It may read only 470-nm timestamps, wavelength/include
flags, feedback times, and feedback condition. It must not load fluorescence
values or calculate a biological effect.

## Why there are three denominators

1. **Boundary eligible:** finite correct/incorrect feedback events whose nominal
   `[-1.0, 0.5]` second window lies within the recorded timestamp range.
2. **Frozen-cohort eligible:** the exact events retained by the already-frozen
   60-second rolling-validity gate in cohort v0.3.
3. **Regularization complete:** frozen-cohort events whose baseline and response
   remain structurally observable after median-rate regularization.

This separation reports selection already imposed by the cohort gate instead of
mislabeling it as a consequence of the newer regularization policy.

## Frozen structural policy

For each session, use every 470-nm timestamp to estimate the median source
interval and construct a grid beginning at the first source timestamp. Linear
interpolation is permitted only inside contiguous runs of `include=true` source
rows. An excluded row, or a timestamp interval greater than 1.5 times the
session median, splits a run. No value may be bridged across the split.

Baseline is `[-1.0, 0.0)` seconds and response is `[0.0, 0.5)` seconds relative
to feedback. An event is complete only when every target-grid point in both
windows is structurally observable. Noncomplete events are classified, in
priority order, as event inside a gap, baseline intersects a gap, or response
intersects a gap.

## Prospective product-readiness thresholds

- At least 99% of frozen-cohort events remain complete overall and within each
  feedback condition.
- The absolute correct-versus-incorrect retention difference is at most 0.5
  percentage points at cohort level.
- The corresponding difference is at most 5 percentage points for every animal.
- Every noncomplete event is explicitly classified and no protected gap is
  bridged.

These are engineering release criteria, not universal scientific-validity
thresholds. All session- and animal-level rates and all failures remain visible.
The executable JSON contract is
[`ibl-event-coverage-protocol-v0.1.json`](ibl-event-coverage-protocol-v0.1.json).
