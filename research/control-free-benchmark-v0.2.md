# Control-free bleaching benchmark v0.2

All frozen v0.2 acceptance gates passed. The protocol was committed before
aggregate execution in
[`benchmarks/protocol-control-free-v0.2.md`](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/protocol-control-free-v0.2.md),
and all 440 runs are retained in
[`benchmarks/control-free-v0.2.json`](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/control-free-v0.2.json).

## Baseline fidelity

| Scenario | Method | Baseline relative RMSE at 10/20/40 Hz | Pass all rates |
| --- | --- | --- | :---: |
| Single exponential | Double exponential | 0.090% / 0.092% / 0.089% | yes |
| Single exponential | AsLS | 0.507% / 0.510% / 0.511% | yes |
| Double exponential | Double exponential | 0.089% / 0.091% / 0.089% | yes |
| Double exponential | AsLS | 0.805% / 0.801% / 0.805% | yes |
| Slow drift | Double exponential | 2.074% / 2.074% / 2.075% | no |
| Slow drift | AsLS | 0.724% / 0.722% / 0.724% | yes |

Event-amplitude median absolute bias remained below 1.7% in every cell. Scaling the
AsLS penalty by `(rate / 20)^4` made its baseline error nearly invariant from 10 to
40 Hz. Full-trace correlations remain in the artifact but are descriptive: their
lower values in small-transient cases still reflect residual acquisition noise.

The methods are complementary rather than interchangeable. A constrained
double-exponential model is substantially more accurate when its bleaching shape
is correct. Its failure on sinusoidal slow drift is structural. AsLS is less
accurate on exponential baselines but flexible enough to pass the slow-drift case.

## Subtraction versus division

| Bleaching mechanism | Division: late-vs-early change | Subtraction: late-vs-early change | Matched choice |
| --- | ---: | ---: | --- |
| Indicator fluorescence | -0.2% | -25.9% | division |
| Additive autofluorescence | +34.4% | -0.4% | subtraction |

This is not a cosmetic normalization choice. Division yields dF/F and is stable
when baseline and physiological amplitude scale together. Subtraction retains
fluorescence units and is stable when the bleaching component is additive. The API
semantics and alternatives are recorded in
[`SDR-0003`](../docs/decisions/0003-separate-subtraction-and-division.md).

## Decision

v0.2 resolves the metric defect identified in v0.1 and supports both experimental
implementations under their stated assumptions. It does not satisfy the independent
real-data-control requirement in
[`SDR-0002`](../docs/decisions/0002-control-free-methods-remain-experimental.md), so neither
method is promoted to the recommended typed pipeline yet.

The next validation should compare control-free baseline estimates against a real
recording with an independent stable fluorophore or acquisition control, while
keeping motion correction conceptually separate.
