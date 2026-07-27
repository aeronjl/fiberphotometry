# Changelog

All notable user-facing changes will be recorded here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) structure and uses
development versions until the first public release.

## [Unreleased]

### Added

- Supported and experimental v0.1 API stability declarations.
- Versioned `event_analysis_result` JSON artifact and packaged JSON Schema.
- Candidate-to-gated-to-complete event coverage in JSON and HTML reports.
- Animal-level peri-event pointwise and simultaneous confidence bands.
- Prospective irregular-clock regularization with protected gaps and provenance.
- Configuration-first CLI output to JSON, HTML, and optional NWB.
- Experimental FIR event-kernel encoding with continuous covariates and
  animal/session-held-out ridge selection.
- Sparse event-kernel fitting and a frozen six-animal public DANDI reproduction
  retaining weak held-out prediction.
- Conditional delete-one-group kernel intervals and group-held-out residual
  diagnostics with session-safe temporal calculations.
- Explicit response and continuous-covariate validity masks for event-kernel
  models, with complete-case coverage ledgers, configurable per-session floors,
  unsupported-lag rejection, and residual diagnostics that do not bridge gaps.
- Experimental typed interoperability for DeepLabCut and SLEAP pose trajectories,
  Keypoint-MoSeq bouts, BORIS point/state annotations, and gap-safe behavioral
  covariates, with an executable ecosystem tutorial.
- Optional DeepLabCut prediction, SLEAP Analysis HDF5, Keypoint-MoSeq results HDF5,
  and BORIS tabular file readers, validated against checksum-pinned official SLEAP
  and BORIS fixtures where upstream artifacts are available.
- Experimental matched-pulse affine clock synchronization with explicit residual,
  drift, pulse-count, span and extrapolation thresholds; pose, covariate and
  annotation transformations retain a stable synchronization evidence ID.
- Experimental named event-kernel model multiverses with stable pre-fit IDs,
  retained failures, exact sample-index fingerprints, and held-out score deltas
  only for models fitted to common evidence.
- Typed full-FIR and lower-dimensional raised-cosine event-kernel bases with
  reconstructed physical-lag curves, reconstructed grouped uncertainty, and
  retained basis functions and weights.
- Typed current and lagged event-value modulation for event-kernel models, with
  session-local history, recovery fixtures, multiverse comparison, and a worked
  tutorial.
- First-class variable-duration behavior encoding with aligned edge/duration
  inputs, normalized-progress bases, full-denominator fitting, grouped uncertainty,
  multiverse comparison, recovery fixtures, and a worked tutorial.

### Scientific status

- Signal-only double-exponential and AsLS baselines remain experimental.
- Held-out regularized-AsLS validation retained its failed aggregate gate.
- Scalar mixed models remain opt-in sensitivity summaries.

[Unreleased]: https://github.com/aeronjl/fiberphotometry/compare/main...HEAD
