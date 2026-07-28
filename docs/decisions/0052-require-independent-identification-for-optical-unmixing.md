# SDR-0052: Require independent identification for optical unmixing

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

Multi-wavelength and multi-color photometry measurements can contain sensor
fluorescence, absorption, autofluorescence, background, and spectral bleed-through.
Channel wavelengths describe the optical acquisition but do not uniquely determine
how latent contributions mix. Factoring one biological recording into an unknown
mixing matrix and unknown source traces is non-unique without additional constraints.

A package that labels an unconstrained regression output “hemodynamic correction”
can produce plausible traces while hiding underidentification, unstable inversion,
missing-channel assumptions, and reuse of the outcome to define its own correction.

## Decision

FiberPhotometry separates matrix identification from matrix application.

- Components, roles, units, measured channels, excitation/emission wavelengths,
  coefficients, offsets, calibration identity, and design version are typed.
- A matrix may come from an independent calibration with known component values or
  be explicitly marked as user-declared. The biological application recording is
  never used to jointly estimate both matrix and sources.
- Known-component calibration refuses insufficient, rank-deficient, or excessively
  conditioned component designs and retains per-channel in-sample fit evidence.
- Before outcomes are accessed, the mixing matrix must have at least as many
  channels as components, full component rank, acceptable conditioning, classified
  channel roles, and—by default—excitation and emission metadata.
- Matrix application is pointwise. It does not interpolate, smooth, refit, or
  compress time across gaps.
- Every missing-channel pattern is assessed separately. Underidentified or
  ill-conditioned samples remain unsolved with a machine-readable reason.
- Reconstructed channels and residuals are retained. Overdetermined designs add
  leave-one-channel-out reconstruction diagnostics; square systems explicitly lack
  that validation.
- Extracted components retain calibration identity, design version, validity, and
  the complete evidence fingerprint.

## Alternatives considered

- **Derive coefficients from wavelengths alone.** Rejected because wavelength
  labels do not encode detector response, optical path, fluorophore spectra,
  absorber concentration, fiber coupling, or acquisition gain.
- **Fit matrix and sources from the same recording.** Rejected as a default because
  the factorization is not uniquely identified and assumptions would be hidden.
- **Use a pseudoinverse for rank-deficient systems.** Rejected because it returns
  one arbitrary solution to an unidentified question.
- **Use ridge regularization to make an underidentified system invertible.**
  Rejected because regularization stabilizes a chosen solution but does not create
  identification.
- **Fill missing channels by temporal interpolation before inversion.** Rejected as
  a default because it replaces absent optical evidence with a signal model.
- **Call low residual error biological validation.** Rejected because reconstruction
  supports the optical model, not source identity, inertness, or concentration.

## Consequences

Many ordinary two-channel systems can be applied but cannot pass leave-one-channel-
out validation. Some missing samples remain unsolved even when neighboring times are
valid. Scientists need calibration artifacts or must declare exploratory
coefficients honestly. Redundant channels become valuable because they permit
out-of-channel reconstruction diagnostics and resilience to channel loss.

The API is composable with existing validity, multiverse, spectral, event, and
animal-level workflows, but inferred components remain experimental processed
signals rather than validated biological quantities.

## Revisit trigger

Revisit after calibration and raw-recording validation across at least two optical
systems and sensor families, or when a nonlinear/time-varying model has independent
identification data, simulation recovery gates, and explicit comparison against
this linear contract.
