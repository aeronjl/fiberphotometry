# Roadmap

## Phase 0 — scientific foundation

- [x] Canonical labelled recording prototype
- [x] Robust and OLS reference-fit prototype with provenance
- [x] Event alignment retaining individual events
- [x] Initial landscape and extraction audits
- [x] Ground-truth simulation seed
- [x] Freeze benchmark scenarios and acceptance thresholds in-repository
- [ ] Confirm package name with likely users before first public release

## Phase 1 — trustworthy preprocessing

- [x] Channel-level validity, dropout, repeated-extreme, and flat-step QC
- [x] Sampling-rate and gap diagnostics
- [x] Resampling with explicit interpolation provenance
- [x] Session-adaptive median-rate regularization and gap diagnostics
- [x] Frozen smooth-signal irregular-clock fidelity benchmark
- [x] Sharp-transient, missing-run, and event-boundary resampling benchmark
- [x] Outcome-blind real-data event-coverage and selection audit across 383 IBL sessions
- [ ] New held-out real-data regularized-AsLS comparison
- [x] Filter API with edge-effect reporting
- [ ] Bleaching models and control-free baseline comparators
  - [x] Experimental double-exponential and AsLS signal-only APIs
  - [x] Frozen v0.1 benchmark with retained partial failure
  - [x] v0.2 baseline-fidelity, normalization, and sampling-rate benchmark
  - [x] First independent real-data-control pilot (mixed; no promotion)
  - [ ] Broader independent-control validation before typed-pipeline promotion
- [x] Event-correlated reference diagnostic benchmarked against confounds
- [ ] Reliable reference-lag diagnostic (v0.3 derivative scan failed)
- [x] Initial three-scenario benchmark report with retained failure
- [x] Seven-scenario v0.2 benchmark with retained failures
- [x] Twelve-session, four-animal IBL channel-QC audit
- [x] Initial raw/peri-event/corrected diagnostic plot API

## Phase 2 — interoperability

- [x] Core NWB round trip and `ndx-fiber-photometry` response-series read path
- [x] DANDI 001084 bounded remote-stream integration fixture
- [x] DANDI archived dF/F numerical reproduction and provenance discrepancy report
- [x] DANDI 001084 API metadata contract and bounded-streaming plan
- [x] Pinned DANDI 000971 raw calcium/isobestic adapter and frozen pilot
- [x] DANDI 000351 raw-to-processed parity audit (retained failure)
- [ ] Recover DANDI 000351 raw-to-dF/F transformation provenance
- [x] IBL table adapter with alternating-wavelength interpolation and masks
- [x] Real IBL session reproduction against archived analysis outputs
- [x] TDT and generic tabular adapters
  - [x] Schema-first wide CSV/TSV recording and event adapter
  - [x] Explicit TDT stream/epoc adapter through the same canonical boundary
  - [x] Checksum-pinned official real-block TDT integration fixture
- [x] Versioned metadata completeness and analysis/NWB/publication readiness report

## Phase 3 — inference

- [x] Typed, versioned experimental-design representation
- [x] Experimental animal-level hierarchical bootstrap
- [x] Experimental design-aware sign-flip and label permutations
- [x] Frozen pseudoreplication benchmark contrasting trial and animal resampling
- [x] Initial independent MixedLM point-estimate parity
- [x] Independent interval and unbalanced mixed-model plumbing parity
- [x] Extended non-Gaussian, heteroscedastic, unequal-count calibration
- [x] Condition-stratified hierarchical resampling
- [x] Four-animal IBL event-table/design integration
- [x] Animal-level Welch and paired-t interval comparators
- [x] Frozen conditional power grid from 6–30 animals per condition
- [x] Conservative design-aware scalar inference recommender
- [x] Independent SciPy parity for Welch and paired intervals
- [x] Versioned analysis plans with explicit assumption acknowledgement
- [x] Result provenance with package version, timestamp, input fingerprint, and seed
- [x] Seeded Monte Carlo plan execution
- [x] First frozen descriptive IBL analysis plan and result
- [x] Typed preprocessing-to-inference pipeline with non-destructive QC gates
- [x] Typed multiverse expansion with stable IDs and compatibility rules
- [x] Failure-retaining robustness and decision summaries
- [x] Reference-pipeline leave-one-animal-out diagnostics
- [x] First frozen descriptive public-data multiverse
- [x] Specification-curve plot API and frozen IBL figure
- [x] Prospective, new-animal-gated IBL expansion protocol
- [x] Refresh held-out IBL manifest (gate failed: no labelled reference channels)
- [x] Resolve new-cohort IBL channel provenance (470-nm-only acquisition)
- [x] Implement the published rolling baseline with 20/50-Hz and gap fixtures
- [x] Freeze signal-only IBL v0.3 (18 animals; 15 executable universes)
- [x] Execute and report the amended signal-only IBL v0.3.2 multiverse
- [x] Pilot power sensitivity ranges
- [x] Opt-in scalar mixed-model sensitivity summaries
- [ ] `fastFMM` bridge and numerical-parity fixtures
- [ ] Pointwise versus simultaneous interval reporting

## Phase 4 — adoption

- [x] First scientist-facing event-analysis workflow
- [x] Self-contained HTML evidence report with animal/QC/provenance views
- [x] Declarative TOML configuration for no-code-rewrite analysis choices
- [x] CLI from tabular project configuration to preflight, JSON, and HTML artifacts
- [x] CLI export of raw/processed signals, events, QC, and provenance to NWB
- [x] Unit-safe grouped report for complete multiverse robustness results
- [x] First-class candidate-to-gated-to-complete event coverage API and report panel
- [x] Public IBL tutorial from import to fingerprinted JSON/HTML report
- [ ] Usability review with practicing photometry scientists
  - [x] Freeze v0.1 protocol, stimulus generator, response sheet, and scoring key
  - [ ] Run five moderated sessions and publish the de-identified synthesis
- [ ] External reproduction by two laboratories
- [ ] Stable schema and deprecation policy
- [x] First versioned public benchmark protocol and results
- [x] Scientific decision records and method review guidance
- [ ] External contributor governance
- [ ] 1.0 release and archival DOI
