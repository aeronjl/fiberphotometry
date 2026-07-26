# IBL channel-QC cohort v0.1

The public IBL adapter and channel diagnostics were run on a frozen cohort of 12
sessions: four animals (`fip_13`–`fip_16`) sampled at early, middle, and late
points. This gives 36 region channels. Session identifiers and the executable
selection are preserved in `scripts/validate_ibl_qc_cohort.py`; no raw data are
committed.

Coverage was high: median paired finite fraction was 99.05% (range 95.12–100%).
Median absolute signal/reference correlation was 0.392 and median relative
OLS/IRLS slope difference was 2.65%. Twelve channels emitted at least one
warning:

- 12 had more than 1% exactly flat consecutive signal steps;
- 3 had absolute signal/reference correlation below 0.1;
- 2 were fit-method sensitive, with OLS/IRLS slope differences of 28.0% and
  44.9%.

The two fit-sensitive channels were both DMS in `fip_13` (middle and late). Their
signal/reference correlations were 0.0045 and -0.0090. In the late session, OLS
estimated a slope of -3.734 versus -2.057 for IRLS. These should be treated as
poor candidates for reference-based correction, not silently processed.

Flat steps clustered by session (all channels in two `fip_13` and two `fip_16`
sessions), reaching 13.1% in one NAcc channel. This may reflect quantisation,
clipping, repeated acquisition values, or upstream processing; the metric is a
screening flag rather than a diagnosis. Sampling interval CV ranged from 0.00075
to 0.00538.

The aggregate machine-readable result is
[`benchmarks/ibl-qc-cohort-v0.1.json`](../benchmarks/ibl-qc-cohort-v0.1.json).
Regenerate the full per-channel output with:

```bash
uv run --group ibl-validation python scripts/validate_ibl_qc_cohort.py
```
