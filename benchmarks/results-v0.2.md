# Preprocessing benchmark results v0.2

The unmodified [frozen protocol](protocol-v0.2.md) was executed across 20 seeds
per scenario and method (280 runs). Values below are medians. The compact JSON
artifact is [`results-v0.2.json`](results-v0.2.json); the complete deterministic
output can be regenerated with `uv run python scripts/run_benchmark_v2.py`.

| Scenario / method | Truth correlation | RMSE | Event bias | Null RMS |
| --- | ---: | ---: | ---: | ---: |
| Clean / IRLS | 0.9703 | 0.00983 | -0.005070 | 0.00812 |
| Clean / OLS | 0.9695 | 0.01635 | -0.014925 | 0.01396 |
| Large transients / IRLS | 0.9920 | 0.01108 | -0.007642 | 0.00864 |
| Large transients / OLS | 0.9909 | 0.02934 | -0.032146 | 0.02476 |
| Dropout blocks / IRLS | 0.9670 | 0.00983 | -0.005086 | 0.00777 |
| Event-locked motion / IRLS | 0.9624 | 0.00965 | -0.005418 | 0.00923 |
| Nonlinear coupling / IRLS | 0.9188 | 0.01570 | -0.008176 | 0.01502 |
| Lagged reference / IRLS | 0.9289 | 0.01473 | -0.010562 | 0.01307 |
| Reference contamination / IRLS | 0.7460 | 0.02925 | -0.072044 | 0.00793 |

## Acceptance outcome

Seven of nine criteria passed. The retained failures are:

1. Clean IRLS event bias was -0.005070, missing the absolute 0.005 threshold by
   0.000070. This is a small miss, but the frozen criterion remains failed.
2. Event-locked motion neither triggered current channel QC nor degraded
   correlation/RMSE by 20%. A plausible corrected trace can therefore conceal
   an event-correlated confound. Event-aware diagnostics are required.

IRLS reduced large-transient null RMS by 65% relative to OLS and tolerated the
fixed dropout blocks. Nonlinearity, lag, and reference contamination crossed the
pre-specified degradation criterion, but none emitted a generic channel warning.
The benchmark supports IRLS over OLS for this simulator; it does not support a
universal default or biological validity claim.
