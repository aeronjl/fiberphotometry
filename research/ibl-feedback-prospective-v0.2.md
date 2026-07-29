# Prospective IBL feedback expansion v0.2

Status: **stopped at the frozen readiness gate** (26 July 2026)

## Outcome-blind cohort lock

The [frozen protocol](https://github.com/aeronjl/fipha/blob/main/benchmarks/protocol-ibl-feedback-prospective-v0.2.md)
required at least 12 eligible animals beyond development animals `fip_13`–`fip_16`
before loading fluorescence outcomes or calculating feedback contrasts.

The reproducible query found 546 public sessions from 22 animals:

- 139 sessions from the four development animals, excluded as specified;
- 407 sessions from 18 nominally new animals;
- zero eligible held-out sessions and zero eligible held-out animals.

Every new session contained labelled 470-nm GCaMP rows and wavelength-0 rows named
`None`, but no labelled 415-nm isosbestic rows. The package's versioned IBL adapter
requires a 415-nm reference for the nine frozen reference-correction universes, so
all 407 new sessions received the same machine-readable exclusion reason:
`adapter_schema_failure`.

The complete session/lab/subject inventory, exclusions, query environment, and
fingerprint are in
[`ibl-feedback-cohort-v0.2.json`](https://github.com/aeronjl/fipha/blob/main/benchmarks/ibl-feedback-cohort-v0.2.json).
It was committed before any dF/F or feedback contrast was calculated.

## Why wavelength 0 was not treated as a reference

IBL's extraction source maps wavelength 0 to `None` / “No additional signal” and
maps 415 nm separately to `Isosbestic`. The public loading guide likewise instructs
users to select frames by the recorded wavelength. Although ROI columns contain
finite values on wavelength-0 rows, neither metadata nor official semantics
identify those values as a control channel. Relabelling them after the gate failure
would be an outcome-adjacent schema amendment and could manufacture eligibility.

Sources:

- [IBL photometry extraction source](https://docs.internationalbrainlab.org/_modules/ibllib/pipes/neurophotometrics.html)
- [IBL photometry loading guide](https://docs.internationalbrainlab.org/notebooks_external/loading_photometry_data.html)

## Decision and interpretation

The held-out estimate, confidence interval, multiverse, and specification curve do
not exist for v0.2. This is a readiness failure, not a null scientific result.
The apparent increase from four to 22 public animals did not increase the eligible
population for the frozen paired-signal analysis.

Any analysis of the 18 new animals requires a v0.3 protocol with one of two forms:

1. provenance establishes that another stored field is genuinely the isosbestic
   measurement, permitting an updated adapter; or
2. a declared signal-only estimand uses experimental control-free preprocessing,
   clearly separated from the paired-reference v0.1/v0.2 analysis.

The second option cannot be described as a held-out replication of the original
nine-universe analysis because it changes every correction workflow and its
identifiability assumptions.

The subsequent [channel-provenance audit](ibl-new-cohort-channel-provenance-v0.1.md)
found that the study methods explicitly describe 470-nm-only acquisition and that
the producing extractor maps wavelength 0 to no-LED frames. The first route is
therefore closed on current evidence. A
[signal-only v0.3 design](drafts/ibl-feedback-signal-only-v0.3-design.md) is being
developed separately and has not yet been frozen or executed.
