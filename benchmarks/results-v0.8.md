# Preprocessing-sequence benchmark results v0.8

Protocol: [`protocol-v0.8.md`](protocol-v0.8.md). Executed 2026-07-26.

| Criterion | Result | Status |
|---|---:|---|
| Resampling RMSE outside gap < 0.01 | 0.00963 | Pass |
| Interpolated samples strictly inside gap = 0 | 0 | Pass |
| Source array retained exactly | true | Pass |
| Low-frequency reconstruction RMSE < 0.03 | 0.02143 | Pass |
| 20 Hz attenuation ≥ 95% | 99.85% | Pass |
| Pre-filter array retained exactly | true | Pass |
| Required operation provenance present | present | Pass |

The filter reported 15 edge-padding samples and no finite segments too short to
filter. The resampler recorded linear interpolation, a 20 Hz target rate, a 0.1
second maximum bridgeable gap, 192 source samples, and 200 output samples.

The resampling error passes narrowly. These results support the implementation
contract only for the frozen deterministic scenarios. They do not justify 20 Hz,
5 Hz, fourth order, or any other parameter as a scientific default.
