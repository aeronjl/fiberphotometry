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

### Scientific status

- Signal-only double-exponential and AsLS baselines remain experimental.
- Held-out regularized-AsLS validation retained its failed aggregate gate.
- Scalar mixed models remain opt-in sensitivity summaries.

[Unreleased]: https://github.com/aeronjl/fiberphotometry/compare/main...HEAD
