# Multiverse-engine benchmark results v0.9

Protocol: [`protocol-v0.9.md`](protocol-v0.9.md). Executed 2026-07-26.

## Engine behavior

The two decision nodes expanded to eight universes. Universe identifiers were
identical across repeated materialization. Six universes succeeded, the
deliberately invalid cutoff failed and was retained, and its declared
incompatible window combination was retained without execution. Separate tests
retain QC-blocked universes and distinguish them from failures.

Robustness fractions use all compatible universes as the denominator. The one
deliberate execution failure therefore counts as not supporting a claim; it
cannot disappear and inflate robustness. Incompatible universes are excluded
from that denominator because the contract declares that they are not
scientifically defensible workflows.

## Simulation outcomes

| Scenario | Successful estimate range | Positive fraction | Practical positive fraction | Reference estimate |
|---|---:|---:|---:|---:|
| Stable positive effect | 0.0486 to 0.0550 | 6/7 | 6/7 | 0.0550 |
| True null | -0.00158 to 0.00040 | 3/7 | 0/7 | 0.00040 |
| Reference contamination | -0.1022 to -0.0737 | 0/7 | 0/7 | -0.0997 |
| One influential animal | 0.0246 to 0.0288 | 6/7 | 6/7 | 0.0288 |

The nominal smallest positive effect was 0.01. Fractions include the retained
compatible failure in their denominator.

For the stable positive scenario, OLS and IRLS decision medians were both about
0.0541; filtering before IRLS reduced the median to 0.0499. Reference
leave-one-animal-out estimates ranged from 0.0532 to 0.0569.

The true-null scenario never crossed the practical-effect threshold, despite
half of the six successful estimates being numerically positive.

Reference contamination reversed the known positive effect for every successful
workflow. OLS, IRLS, and filtered-IRLS medians were -0.0762, -0.1009, and
-0.0948. This is a retained warning: robustness across methods sharing an invalid
reference assumption does not imply validity.

In the influential-animal scenario, the multiverse alone looked directionally
stable. Omitting the influential animal reduced the reference estimate from
0.0288 to 0.00031, whereas the other omissions produced 0.0324 to 0.0331. The
leave-one-unit-out diagnostic therefore exposed fragility that the specification
distribution did not.

These deterministic simulations validate engine behavior and demonstrate
failure modes; they do not calibrate inferential coverage or establish a
preferred robustness threshold.
