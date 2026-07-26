# Existing-code extraction audit

## PyDAP (2021)

Private repository: `aeronjl/PyDAP`, six commits from 8–12 December 2021.

Contents include `photometry.py`, `rigbox.py`, `preprocessing.ipynb`, compiled
data, and committed bytecode. The photometry prototype interpolates alternating
470/415 nm samples, directly subtracts the control, applies a rolling-mean
detrend, and z-scores each channel. Rigbox utilities load laboratory-specific MAT
files and extract task events.

### Decision

Preserve as historical provenance; do not import its history or implementation.
Direct subtraction and pre-normalisation should instead become explicit benchmark
comparators. The event synchronisation intent and Rigbox domain knowledge can
inform a future adapter.

## latent-state-belief-models (2026)

Relevant files:

- `src/latent_state_belief_models/data/ibl_public_photometry.py`
- `src/latent_state_belief_models/experiments/paper_d_ibl_public_photometry.py`
- `scripts/inventory_ibl_public_photometry.py`
- `scripts/analyze_paper_d_ibl_public_photometry.py`
- corresponding data and experiment tests

### Reusable concepts

- IBL dataset discovery and availability flags;
- subject/session coverage summaries;
- balanced longitudinal panel selection;
- ONE/ALF trial, wheel, signal, and ROI loading;
- event-window extraction;
- subject-grouped cross-validation;
- explicit comparison of movement and behavioural-policy covariates.

### Keep in the research repository

- paper-specific policy-compression features;
- named “Paper D” report generation;
- regional residual model ladders;
- claim-specific output tables and prose.

### Extraction rules

1. Reimplement against the new canonical model; do not copy package-internal
   dependencies from the research monorepo.
2. Preserve subject/session/trial/ROI identifiers throughout alignment.
3. Convert the IBL loader into an optional adapter with small fixture tests.
4. Replace fixed pre/post means with an event-aligned tensor plus optional,
   explicitly defined summaries.
5. Retain grouped validation as a benchmark principle, not as preprocessing.
6. Record source dataset IDs, collection names, inclusion masks, and wavelengths.

## Immediate extraction backlog

- [ ] Create an `io.ibl` adapter around `photometry.signal.pqt` and ROI metadata.
- [ ] Add IBL alternating-wavelength demultiplexing fixtures.
- [ ] Port balanced panel inventory as an example/benchmark utility.
- [ ] Express event windows through `align_events` without averaging trials.
- [ ] Add movement-confound benchmark using wheel features.
- [ ] Reproduce one existing local report through the new API before migration.

