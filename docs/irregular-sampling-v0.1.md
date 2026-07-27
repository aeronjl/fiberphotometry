# Irregular sampling and prospective regularization v0.1

The pipeline now supports a session-adaptive regularization declaration:

```python
ResampleOperation(rate_hz="median", max_gap_factor=1.5)
```

Placed before `BaselineDFFOperation("asls")`, this converts timestamp jitter from
a structural incompatibility into an explicit, auditable workflow choice. It does
not alter the completed IBL v0.3.2 analysis.

Every resampling operation records its requested and resolved rate, source interval
CV, median and maximum source intervals, target/source rate ratio, resolved gap
threshold, fraction of target samples protected as gaps, and maximum and 95th
percentile distance to a source sample. Original timestamps and values remain on
the `source_time` dimension.

The frozen smooth-signal benchmark is
[`irregular-resampling-v0.1.json`](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/irregular-resampling-v0.1.json).
Across 20 and 50 Hz sampling, three signal frequencies, and 0.5% timestamp jitter,
all six scenarios passed the prospectively stated 1% normalized-RMSE threshold.
The worst result was 0.248% at a 3 Hz signal sampled at 20 Hz.

This is an engineering acceptance test, not proof that interpolation preserves all
photometry features. Sharp event transients, discontinuities, missing runs, event
coverage near protected gaps, and a new held-out real-data comparison remain
required before regularized AsLS is promoted beyond experimental status.

The subsequent sharp-transient and missing-run study is reported in
[transient-gap results v0.1.1](transient-gap-results-v0.1.1.md). It supports
median-rate linear jitter regularization but rejects silent interpolation across
missing event-window samples.

The governing rationale is
[SDR-0011](decisions/0011-regularize-irregular-clocks-prospectively.md).
