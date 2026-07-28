# Multi-signal and spatial analysis

Use this category for simultaneous sites, colors, sensors, or coordinate-defined
fiber arrays. Signal identity, shared time, joint validity, and optical review must
be established before association is interpreted.

## Choose the workflow

| Geometry | Workflow | Output |
|---|---|---|
| Two or more named sites or colors | [Multi-site and multi-color association](../multisite-multicolor-analysis-v0.1.md) | lagged association, coherence, phase, and crosstalk review |
| Three or more fibers with physical coordinates | [Coordinate-aware dense arrays](../spatial-network-v0.1.md) | edge ledger, distance summaries, spatial null, animal contrast |
| Overlapping optical channels measuring known components | [Optical unmixing](../optical-unmixing-v0.1.md) | conditionally unmixed component signals |

## Coverage gaps this category exposes

- nonlinear and time-varying crosstalk estimation;
- directed or causal network models with defensible temporal nulls;
- population-level dynamic connectivity and graph inference;
- joint photometry–electrophysiology workflows; and
- public multi-site/multi-color benchmarks with independent optical calibration.

Zero-lag association is particularly vulnerable to shared motion, bleaching, and
instrumental contamination. The package therefore treats residualization,
blocked nulls, state partitions, and crosstalk flags as evidence—not decoration.
