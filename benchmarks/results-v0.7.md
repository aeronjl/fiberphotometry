# Finite-sample t and power results v0.7

The [frozen protocol](protocol-v0.7.md) ran 140,000 Gaussian studies. Welch
coverage remained 94.7–95.8%, and simulated power differed from the independent
noncentral-t calculation by at most 1.3 percentage points. Both criteria passed.

| Animals per condition | Coverage | Power for effect 0.8 SD |
| ---: | ---: | ---: |
| 6 | 95.39% | 22.87% |
| 8 | 95.81% | 30.76% |
| 10 | 95.26% | 39.10% |
| 12 | 95.24% | 46.13% |
| 16 | 95.28% | 59.32% |
| 20 | 95.02% | 69.10% |
| 30 | 94.73% | 86.16% |

Thirty animals per condition was the first tested size exceeding 80% power. This
is not a universal sample-size recommendation: the result assumes independent,
approximately Gaussian animal means, equal allocation, effect 0.8 SD, and a
two-sided 5% test. It does show why adding trials cannot replace adding animals.

The public API now provides Welch and paired-t intervals on declared unit means.
Paired randomized designs should still prefer exact sign flipping when its
exchangeability assumption is justified.

Public Welch and paired results reproduce SciPy estimates, p-values, and
confidence intervals to floating-point precision; see
[`scipy-t-parity-v0.1.json`](scipy-t-parity-v0.1.json).
