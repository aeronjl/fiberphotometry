# DANDI 000971 independent-control pilot v0.1

Status: **completed; mixed descriptive result; no method promotion** (26 July 2026)

## Question

Do experimental signal-only bleaching baselines recover approximately the same
slow trend as an independently acquired 405-nm isosbestic channel in real
dual-site recordings?

The [protocol](https://github.com/aeronjl/fipha/blob/main/benchmarks/protocol-dandi-000971-control-v0.1.md) and exact
[asset manifest](https://github.com/aeronjl/fipha/blob/main/benchmarks/dandi-000971-pilot-manifest-v0.1.json) were frozen
before aggregate signal execution. The compact, machine-readable
[result](https://github.com/aeronjl/fipha/blob/main/benchmarks/dandi-000971-control-v0.1.json) retains every case.

## Data and execution

One animal was selected from each of four session families in immutable published
DANDI:000971 version `0.260213.1851`. Each NWB contributed DMS and DLS calcium plus
matched isosbestic channels: eight region-level cases and sixteen method-case
comparisons. All four downloads matched their recorded byte sizes and SHA-256
digests. All exposed the expected schema, and every fitted baseline was fully
finite after block averaging to approximately 20 Hz.

The executable runner is
[`scripts/run_dandi_000971_control_pilot.py`](https://github.com/aeronjl/fipha/blob/main/scripts/run_dandi_000971_control_pilot.py).
It caches raw assets outside the repository, rechecks integrity on reuse, and
generates the JSON result from the frozen manifest.

## Results

| Method | Cases | Median slow-trend correlation | Median relative RMSE | Correlation gate | RMSE gate |
|---|---:|---:|---:|---:|---:|
| Double exponential | 8 | 0.259 | 4.62% | Fail | Pass |
| Rate-aware AsLS | 8 | 0.713 | 5.36% | Fail | Pass |

The low RMSE and modest correlation are not contradictory. Fluorescence trends
have large positive offsets, so two traces can be close in scale while disagreeing
about relatively small within-session changes. The individual correlations were
heterogeneous: double exponential ranged from -0.482 to 0.804 and AsLS from 0.278
to 0.845. One double-exponential DLS fit was nearly flat while its comparator rose
21.6%, producing the negative correlation. In FP-RR20, both methods tracked the
direction and approximate magnitude of decline in both regions.

The corrected-signal/isobestic correlations also varied substantially. They are
reported diagnostically, not treated as a success criterion: residual correlation
can reflect motion, shared bleaching, biological contamination, or other common
structure, and a low value is not by itself proof of valid correction.

## Interpretation and decision

The pilot establishes a reproducible real-NWB path and shows that both methods
produce numerically plausible fluorescence-scale baselines. It does **not** show
reliable recovery of the independently measured slow trend across preparations.
Neither descriptive method gate passed in full, so SDR-0002 remains unchanged:
both signal-only methods stay experimental and outside the recommended typed
pipeline.

The comparator is not ground truth. The affine isosbestic fit can be invalid, the
405-nm channel can carry non-bleaching structure, and wavelength-specific bleaching
can create genuine disagreement. Consequently this result motivates a larger
multiverse across comparator construction and datasets; it does not rank AsLS as
scientifically superior merely because its pilot median correlation was higher.

## Follow-up

1. Reproduce raw-to-archived-dF/F behavior in DANDI:000351, retaining its published
   processing outputs as a parity comparator while clearly marking the Dandiset as
   a mutable draft.
2. Add explicit comparator variants (robust affine, OLS, and slow-scale choices)
   under a frozen multiverse, then report whether conclusions survive those choices.
3. Refresh and execute the prospectively gated IBL analysis on the 18 newly
   available animals, independently of this control-free baseline decision.
4. Seek a larger immutable raw calcium/isobestic cohort before reconsidering
   promotion.
