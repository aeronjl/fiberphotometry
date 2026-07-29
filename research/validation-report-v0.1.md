# Real-data validation report v0.1

## DANDI 001084: archived dF/F reproduction

The validator streamed 1,000 samples × 103 channels from the raw fluorescence,
archived baseline and archived dF/F series. Applying the conventional fitted
baseline formula

```text
(raw - baseline) / baseline
```

gave an overall correlation of 0.9551 with archived dF/F, RMSE 0.01174 and mean
bias +0.01098. This initially appeared to be a dynamic mismatch.

Channel-wise analysis resolved it: every channel has correlation effectively 1.0,
and subtracting each channel's constant offset reduces RMSE to 1.22×10⁻¹⁶. Thus
the archived dF/F is the conventional formula followed by channel-wise additive
zeroing. That zeroing operation is not recorded in the series descriptions or
comments inspected by the validator.

Implications:

- numerical reproduction requires provenance beyond variable names;
- FiberPhotometry should represent zeroing as a separate transformation;
- additive zeroing does not alter within-channel event differences, but it does
  affect absolute baselines and cross-channel comparisons;
- a high pooled correlation concealed a perfectly systematic discrepancy.

Machine-readable result:
[`dandi-dff-reproduction.json`](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/dandi-dff-reproduction.json).

## IBL: real session and legacy-output reproduction

Session `7a867587-aba3-48da-ace9-3f4ac7082b6f` from subject `fip_13` contains
74,681 signal-wavelength samples, 320 trials and DMS, NAcc and DLS channels. The
estimated signal rate is 20.0011 Hz. The manual inclusion mask retains 78.28% of
signal frames; interpolated reference coverage is 78.28%.

The new adapter plus acquired-sample event summaries reproduce the archived
`latent-state-belief-models` stimulus-window deltas to machine precision across
all three regions (maximum absolute discrepancy < 1.9×10⁻¹⁴). This validates:

- 470/415 nm demultiplexing;
- interpolation of the reference onto signal timestamps;
- preservation of manual inclusion masks as missing samples;
- ROI-to-region mapping;
- half-open pre/post event-window semantics.

The general interpolated event tensor is close but not identical to acquired-
sample summaries: correlations range 0.9824–0.9923 and RMSE ranges
1.60×10⁻⁵–1.91×10⁻⁵. Interpolation changes temporal sample weighting. Therefore
the library now exposes both operations explicitly; one must not silently stand
in for the other.

The fitted reference slopes also vary markedly (DMS 4.41 versus approximately
0.84 for NAcc/DLS). This is not itself an error—the channels can differ in scale—
but it motivates channel-level fit diagnostics before reference correction is
treated as routine.

Machine-readable result:
[`ibl-session-validation.json`](https://github.com/aeronjl/fiberphotometry/blob/main/benchmarks/ibl-session-validation.json).

## Scope limits

These validations establish structural and numerical compatibility for one DANDI
slice and one IBL session. They do not establish biological validity of the
reference channel, generalisation across acquisition systems, or calibrated
multi-animal inference.
