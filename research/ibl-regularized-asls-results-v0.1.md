# Held-out IBL regularized-AsLS comparison v0.1

Status: **completed; frozen aggregate gate failed; no method promotion** (26 July
2026).

## Result

All 24 checksum-frozen held-out sessions loaded and all five declared method paths
executed. The benchmark retained all 5,920 frozen event windows for every method.
Nevertheless, the overall prospective gate failed, so regularized AsLS remains
experimental.

The held-out sessions had been excluded from the earlier IBL v0.3 analysis solely
because they lacked enough events in both feedback conditions. Their fluorescence
values had not been loaded before the
[`v0.1 protocol`](https://github.com/aeronjl/fipha/blob/main/benchmarks/protocol-ibl-regularized-asls-v0.1.md) and exact
source hashes were frozen.

## Regularization fidelity

Double exponential and the published rolling baseline were applied both before
and after regularization, isolating interpolation effects from baseline-method
choice.

| Raw versus regularized method | Median trace r | Minimum trace r | Median normalized trace RMSE | Event-delta r | Event normalized median change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Double exponential | 0.9964 | 0.9620 | 0.1136 | 0.9990 | 0.0146 |
| Published rolling | 0.9973 | 0.9612 | 0.1029 | 0.9990 | 0.0143 |

Trace correlations and every event-level gate passed. The prospective median
normalized trace-RMSE threshold of 0.10 failed narrowly for both comparators. This
is not relabelled a pass because downstream event summaries were stable: the
contract explicitly required both.

The maximum target-to-source distance was 0.525 median sample intervals, exceeding
the frozen 0.25 threshold. The target grid begins at the first source sample, but
small interval errors accumulate phase relative to later acquired samples; almost
all regularized targets are therefore interpolated rather than exact timestamp
matches. Median-rate regularization is mechanically sound here, but interpolation
provenance remains scientifically relevant.

## Missingness and coverage

Every method retained all 5,920 selected event windows. Whole-recording finite
coverage was different:

| Method | Minimum fitted-baseline fraction |
| --- | ---: |
| Raw double exponential | 97.46% |
| Regularized double exponential | 97.46% |
| Regularized AsLS | 97.46% |
| Raw published rolling | 77.66% |
| Regularized published rolling | 77.31% |

The 99% frozen gate therefore failed. Double exponential and AsLS preserve
manually excluded recording edges as missing. The rolling baseline additionally
requires a complete centred 60-second window; one short session consequently had
only about 77% fitted coverage. The event-selection intervals kept every analyzed
event away from these regions. This distinction validates the product decision to
report candidate, gated, and complete denominators separately from global trace
coverage.

## AsLS sensitivity

| Regularized comparison | Median baseline r | Median baseline normalized RMSE | Event-delta r | Event normalized median difference | Contrast sign agreement* |
| --- | ---: | ---: | ---: | ---: | ---: |
| AsLS vs double exponential | 0.9776 | 2.109 | 0.9997 | 0.0140 | 100% |
| AsLS vs published rolling | 0.9816 | 2.863 | 0.9996 | 0.0199 | 100% |

\*Only six sessions contained usable events in both conditions; these are
descriptive session contrasts, not population inference.

AsLS and the comparators produce highly correlated slow baselines but materially
different baseline magnitudes relative to within-trace scale. Those differences
mostly cancel in the short baseline-versus-response event contrast. This supports
AsLS as an explicit sensitivity universe, not as a validated default: agreement
on one short-window estimand cannot establish baseline truth or generalize to
slower outcomes.

## Decision

Regularization successfully makes AsLS executable on real irregular clocks and
preserves these selected short-window event summaries. It did not pass the frozen
whole-trace fidelity and coverage contract, and AsLS baseline identity remains
method-dependent. SDR-0002 and SDR-0011 therefore remain conservative: expose the
method and provenance, retain it as experimental, and do not promote it into a
recommended default.

The complete machine-readable result is
[`ibl-regularized-asls-results-v0.1.json`](https://github.com/aeronjl/fipha/blob/main/benchmarks/ibl-regularized-asls-results-v0.1.json),
with fingerprint
`ed8ec3dc071957093790599f95122e5c4b30a738c6334c06d92a232fde6b365a`.
