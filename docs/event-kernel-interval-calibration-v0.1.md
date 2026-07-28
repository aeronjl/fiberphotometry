# Event-kernel interval calibration v0.1

!!! failure "The candidate simultaneous band did not pass its frozen gate"
    Whole-family coverage reached 82.5% for normalized-progress kernels, below
    the prespecified 85% minimum. The method remains an explicit experimental
    opt-in and ordinary encoding fits continue to report pointwise sensitivity
    intervals only.

<figure markdown="span">
  <img src="../assets/event-kernel-interval-coverage-v0.1.svg" alt="Across six 80-study scenarios, multiplier simultaneous coverage is higher than whole-family coverage from pointwise bands, but normalized-progress coverage is 82.5 percent and falls below the frozen 85 percent gate.">
  <figcaption><strong>Frozen 480-study benchmark.</strong> The dashed line is the prospective whole-family acceptance threshold, not an outcome-selected target.</figcaption>
</figure>

## Why this benchmark exists

The encoding model estimates a curve at many lags or progress positions. A
pointwise interval can behave reasonably at each position while failing to cover
the complete generating curve. That distinction matters when scientists inspect a
whole response shape or select its apparent peak.

The [v0.1 protocol](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-event-kernel-interval-coverage-v0.1.md)
was committed before the 80-study aggregate execution. It evaluated the existing
group-jackknife pointwise interval and a candidate Gaussian-multiplier max-*t*
band. The multiplier family contained every evaluated position from every event
and progress kernel in the fitted model. This follows the general multiplier-
maximum strategy studied by
[Chernozhukov, Chetverikov, and Kato (2014)](https://doi.org/10.1214/14-AOS1230),
but the finite photometry implementation still requires its own empirical
calibration.

## Frozen result

Each scenario contains 80 independently seeded studies. “Marginal pointwise” is
the fraction of individual curve positions covered. The two family columns require
every position in a study to cover simultaneously.

| Scenario | Marginal pointwise | Pointwise family | Candidate simultaneous | Gate |
| --- | ---: | ---: | ---: | --- |
| Balanced Gaussian FIR | 94.5% | 75.0% | 88.8% | Pass |
| Animal kernel heterogeneity | 93.8% | 81.2% | 90.0% | Pass |
| AR(1) residuals, \(\phi=0.65\) | 94.5% | 78.8% | 86.2% | Pass |
| Overlapping cue/reward + movement + selected ridge | 95.6% | 66.2% | 88.8% | Pass |
| Blockwise missing response samples | 96.0% | 80.0% | 91.2% | Pass |
| Six-animal normalized progress | 94.6% | 63.7% | **82.5%** | **Fail** |

All 480 declared fits succeeded, all bounds were finite, and simultaneous widths
were never narrower than their pointwise counterparts. Median simultaneous
critical values ranged from 2.87 to 3.44. The candidate materially improved
whole-family coverage over pointwise bands, especially for the ten-point
overlapping-event family, but improvement is not the same as calibration.

The complete study-level ledger is retained in
[`event-kernel-interval-coverage-v0.1.json`](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/event-kernel-interval-coverage-v0.1.json).
Reproduce it with:

```bash
uv run python scripts/run_event_kernel_interval_calibration.py
uv run --group docs python scripts/plot_event_kernel_interval_calibration.py
```

## Product consequence

The default remains explicit and pointwise:

```python
from fiberphotometry import EncodingModelSpec, KernelUncertaintySpec

model = EncodingModelSpec(
    event_kernels=(cue,),
    uncertainty=KernelUncertaintySpec(confidence_level=0.95),
)
```

Researchers reproducing or developing the candidate can opt in without confusing
it with the default:

```python
from fiberphotometry import MultiplierSimultaneousBandSpec

model = EncodingModelSpec(
    event_kernels=(cue, reward),
    uncertainty=MultiplierSimultaneousBandSpec(
        confidence_level=0.95,
        simultaneous_draws=2_000,
        simultaneous_seed=20_260_727,
    ),
)
```

The result then stores optional `simultaneous_lower` and `simultaneous_upper`
arrays plus method, seed, draws, complete family size, and critical value. The band
is still conditional on the selected ridge penalty and fitted model. It is not
selective inference, a cluster test, or a license to interpret zero exclusion as a
causal effect.

## What happens next

The failure is localized enough to guide the next benchmark rather than invite a
post-hoc threshold change. The next protocol should investigate progress-basis
evaluation and six-animal finite-group behavior, add heterogeneous progress
trajectories, and compare the fixed multiplier approximation with nested group
bootstrap or analytically conservative alternatives. Any replacement needs a new
frozen protocol and independent seeds.

The decision to retain but not promote the candidate is recorded in
[SDR-0040](decisions/0040-keep-simultaneous-kernel-bands-opt-in-after-failed-calibration.md).
