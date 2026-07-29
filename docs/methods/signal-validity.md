# Signal formation and validity

Use this category before interpreting fluorescence as neural activity. It answers
whether samples share a usable clock, whether correction is identifiable, and
whether optical or stimulation artifacts invalidate a biological claim.

## Choose the workflow

| Need | Workflow | Status | Important boundary |
|---|---|---|---|
| Inspect sampling, dropouts, flat steps, and channel health | [Preprocessing and QC](../pipeline.md) | Supported | QC can refuse analysis; it does not silently delete observations |
| Make irregular recordings safe for downstream methods | [Irregular sampling](../irregular-sampling.md) | Supported | gaps remain gaps; resampling is explicit |
| Mask declared stimulation and assess sensor/reference validity | [Optogenetic artifacts and sensor validity](../optical-validity.md) | Experimental | masking is not artifact correction |
| Account for indicator response dynamics | [Sensor-kinetic modeling](../sensor-kinetic-modeling.md) | Experimental | deconvolution is conditional on a calibrated model |
| Separate known fluorophores measured in overlapping channels | [Optical unmixing](../optical-unmixing.md) | Experimental | the mixing matrix must be independently identified |

## Coverage gaps this category exposes

- validated automatic motion-artifact correction beyond declared reference fits;
- nonlinear and time-varying spectral mixing;
- preparation-specific, independently measured sensor and optical calibrations;
- prospective ground-truth benchmarks for control-free baselines; and
- validated correction of stimulation transients rather than conservative masks.

These are product gaps, not invitations to hide uncertainty. Until they are
validated, outputs should expose the unresolved condition and narrow the claim.

## Continue to

After the signal contract is fixed, choose an [event-locked](event-locked.md),
[continuous](continuous-dynamics.md), or [multi-signal](multisignal-spatial.md)
analysis. Finish with [population inference and robustness](inference-robustness.md).
