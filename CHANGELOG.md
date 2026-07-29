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
- Paired predictor-family held-out contribution summaries over declared encoding
  multiverses, with literal-subset validation, exact-denominator safeguards,
  per-group deltas, conditional sensitivity intervals, and non-causal guidance.
- A frozen 480-study event/progress kernel interval calibration and retained failed
  normalized-progress gate; seeded whole-model multiplier bands are available only
  through an explicit experimental opt-in while pointwise sensitivity remains the
  default.

### Changed

- **The package is renamed from `fiberphotometry` to `fipha`.** The distribution,
  the importable package (`import fipha as fp`), the console script, the
  documentation site and the repository URL all move; no public API symbol and no
  CLI subcommand changes. The old name claimed the name of the field itself, which
  is both unsearchable and discourteous to the established tools in it.
- Identifiers the package writes into data move with it: the NWB scratch tables
  `fipha_series_channels` and `fipha_series_attributes`, the NWB scratch evidence
  keys and JSON `artifact_type` values (`fipha_analysis`, `fipha_archive_metadata`
  and the rest), the xarray provenance attributes `fipha_operations`,
  `fipha_baseline_dff` and `fipha_reference_dff`, the manifest key `fipha_version`,
  the readiness profile `fipha-metadata-v0.1`, the `ndx-pose` document schema
  `fipha-ndx-pose-v1`, the publication signing namespace
  `fipha-publication@aeronjl.github.io`, and the `FIPHA_*` test environment
  variables. Nothing has been released, so no file, manifest or signature in
  existence carries the former names.

### Removed

- The pre-extension NWB compatibility reader. Recordings are written as
  `ndx-fiber-photometry` objects with two documented scratch tables; the reader no
  longer parses the private `fiberphotometry-core-nwb-v1` JSON document that older
  development builds wrote into a core `TimeSeries` `comments` field, and the CLI
  no longer sniffs that document when choosing a series. The package was never
  released, so no such file can exist outside a developer's working tree.

### Scientific status

- Signal-only double-exponential and AsLS baselines remain experimental.
- Held-out regularized-AsLS validation retained its failed aggregate gate.
- Scalar mixed models remain opt-in sensitivity summaries.
- Simultaneous event-kernel bands remain opt-in after the v0.1 progress-kernel
  calibration gate failed.

[Unreleased]: https://github.com/aeronjl/fipha/compare/main...HEAD
