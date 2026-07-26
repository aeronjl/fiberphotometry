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

- [ ] Validity, dropout, discontinuity, and saturation masks
- [ ] Sampling-rate diagnostics and resampling
- [ ] Filter API with edge-effect reporting
- [ ] Bleaching models and control-free baseline comparators
- [ ] Reference contamination and lag diagnostics
- [x] Initial three-scenario benchmark report with retained failure
- [ ] Diagnostic plots that expose rather than conceal failures

## Phase 2 — interoperability

- [x] Core NWB round trip and `ndx-fiber-photometry` response-series read path
- [x] DANDI 001084 bounded remote-stream integration fixture
- [x] DANDI 001084 API metadata contract and bounded-streaming plan
- [x] IBL table adapter with alternating-wavelength interpolation and masks
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
