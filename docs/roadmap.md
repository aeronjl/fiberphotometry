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
- [ ] Resampling with explicit interpolation provenance
- [ ] Filter API with edge-effect reporting
- [ ] Bleaching models and control-free baseline comparators
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
- [x] IBL table adapter with alternating-wavelength interpolation and masks
- [x] Real IBL session reproduction against archived analysis outputs
- [ ] TDT and generic tabular adapters
- [ ] Metadata completeness report

## Phase 3 — inference

- [ ] Typed experimental-design representation
- [ ] Animal-level hierarchical bootstrap
- [ ] Design-aware permutation schemes
- [ ] Scalar mixed-model summaries
- [ ] `fastFMM` bridge and numerical-parity fixtures
- [ ] Pointwise versus simultaneous interval reporting

## Phase 4 — adoption

- [ ] External reproduction by two laboratories
- [ ] Stable schema and deprecation policy
- [x] First versioned public benchmark protocol and results
- [ ] Contributor governance and method review template
- [ ] 1.0 release and archival DOI
