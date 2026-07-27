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
- [x] New held-out real-data regularized-AsLS comparison (retained gate failure; no promotion)
- [x] Filter API with edge-effect reporting
- [ ] Bleaching models and control-free baseline comparators
  - [x] Experimental double-exponential and AsLS signal-only APIs
  - [x] Frozen v0.1 benchmark with retained partial failure
  - [x] v0.2 baseline-fidelity, normalization, and sampling-rate benchmark
  - [x] First independent real-data-control pilot (mixed; no promotion)
  - [ ] Broader independent-control validation before typed-pipeline promotion
- [x] Event-correlated reference diagnostic benchmarked against confounds
- [ ] Reliable reference-lag diagnostic (v0.3 derivative scan failed)
- [ ] Wavelength-aware hemodynamic correction and spectral-unmixing contract
- [ ] Optogenetic-pulse artifact masks and recovery-window diagnostics
- [ ] Sensor registry with kinetic, saturation, and interpretation constraints
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
- [ ] Native Doric, Neurophotometrics, and pyPhotometry adapters
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
- [x] Animal-level peri-event pointwise and simultaneous interval reporting
- [ ] Behavioral/event-kernel GLMs with grouped cross-validation
  - [x] Typed Gaussian FIR model for overlapping events and continuous covariates
  - [x] Leakage-safe animal/session-held-out ridge selection
  - [x] Ground-truth recovery fixture and executable simulation tutorial
  - [x] Public-data literature reproduction with a frozen design and retained weak validation
  - [x] Conditional grouped-jackknife kernel intervals and out-of-fold residual diagnostics
  - [ ] Formal interval-coverage calibration and simultaneous kernel bands
  - [ ] Design-matrix alternatives in reproducible robustness multiverses
- [ ] Longitudinal learning-trajectory and session-within-animal models
- [ ] Long-duration tonic/phasic analysis
- [ ] Spontaneous transient detection with local-baseline sensitivity analysis
- [ ] Multi-site/multi-color paired and conditional association workflows

## Phase 4 — adoption

- [x] Publishable MkDocs site with strict link and API-reference builds
- [x] Scientist-task methods catalog and supported/experimental/planned matrix
- [ ] Literature-shaped worked examples for each major method family
  - [x] Public-data evidence atlas linking figures to estimands, units, and limitations
  - [x] Event-locked public IBL analysis
  - [x] Raw-NWB animal-level robustness analysis
  - [ ] Behavioral event-kernel GLM
    - [x] Ground-truth implementation tutorial
    - [x] Public-data literature reproduction with retained negative held-out R²
  - [ ] Trial-level functional mixed model
  - [ ] Long-duration tonic/phasic and spontaneous events
  - [ ] Multi-site/multi-color association
  - [ ] Spectral or hemodynamic correction with controls

- [x] First scientist-facing event-analysis workflow
- [x] Self-contained HTML evidence report with animal/QC/provenance views
- [x] Declarative TOML configuration for no-code-rewrite analysis choices
- [x] CLI from tabular project configuration to preflight, JSON, and HTML artifacts
- [x] CLI export of raw/processed signals, events, QC, and provenance to NWB
- [x] Unit-safe grouped report for complete multiverse robustness results
- [x] Configuration-driven multiverse preflight, execution, and evidence bundle
- [x] Extend project multiverses to signal-only preprocessing recipe families
- [x] Add per-unit-lane practical-effect thresholds and machine-readable summaries
- [x] Add declarative method-specific baseline parameters and compatibility rules
- [x] Add multiverse-aware NWB provenance and result export
- [x] Add a project-level result reader for JSON and NWB evidence bundles
- [x] Add cross-bundle comparison and reproducibility-diff reporting
- [x] Add signed publication manifests and detached verification
- [x] Add release/DOI deposition packaging and archival metadata validation
  - [x] Add a sandbox-first Zenodo draft upload and validation adapter
- [x] First-class candidate-to-gated-to-complete event coverage API and report panel
- [x] Public IBL tutorial from import to fingerprinted JSON/HTML report
- [x] Canonical raw-NWB to animal-level robustness tutorial
  - [x] Freeze the DANDI 000971 cohort, estimand, and eight-universe protocol
  - [x] Add the executable workflow and synthetic end-to-end regression fixture
  - [x] Execute the frozen public cohort and publish the retained result narrative
- [ ] Usability review with practicing photometry scientists
  - [x] Freeze v0.1 protocol, stimulus generator, response sheet, and scoring key
  - [ ] Run five moderated sessions and publish the de-identified synthesis
- [ ] External reproduction by two laboratories
- [ ] Stable schema and deprecation policy
  - [x] Declare prospective v0.1 supported and experimental API surfaces
  - [x] Version the primary JSON result and package its normative JSON Schema
  - [x] Add deprecation, migration, changelog, and security policies
  - [x] Complete clean-install and canonical-artifact release audit
- [x] First versioned public benchmark protocol and results
- [x] Scientific decision records and method review guidance
- [ ] External contributor governance
- [ ] 1.0 release and archival DOI
