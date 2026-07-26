# IBL new-cohort channel provenance v0.1

Status: **paired-reference route closed; signal-only design required** (26 July
2026)

## Question

The prospective IBL v0.2 query found 407 held-out sessions with alternating
470-nm rows and wavelength-0 rows named `None`, but no labelled 415-nm reference.
This audit asked whether the zero-labelled rows could be recovered as a genuine
isosbestic channel from primary acquisition provenance.

No fluorescence outcome, feedback contrast, or condition-specific result from the
held-out cohort was inspected during this audit.

## Evidence

### Acquisition methods

The dataset tag `2024_Q3_Pan_Vazquez_et_al` corresponds to Pan-Vazquez et al.,
*Pre-existing visual responses in a projection-defined dopamine population
explain individual learning trajectories*. Its methods state that GCaMP6f was
recorded with a Neurophotometrics FP3002 using **470-nm excitation**: 464 of 476
sessions at 50 Hz and 12 at 20 Hz. The published processing used a ±30 s rolling
average as `F0` and calculated `(F - F0) / F0`. No second optical reference channel
is described.

- [Open-access article and methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11579926/)
- [PubMed record](https://pubmed.ncbi.nlm.nih.gov/39413788/)

This is direct study-level evidence that the recordings are signal-only.

### Historical extraction semantics

The public dataset records identify `ibllib` 2.38.0 as the producing version. In
that version's extractor, wavelength 0 is explicitly `None` / “No LED ON”, while
415 nm is separately `Isosbestic` and 470 nm is `GCaMP`. The extractor reads LED
states through the acquisition channel map and writes the corresponding wavelength
and name into the processed table. Exact zero/`None` values therefore represent a
matched no-LED state under the producing code, not an unlabelled 415-nm state.

- [`ibllib` 2.38.0 fibre-photometry extractor](https://github.com/int-brain-lab/ibllib/blob/2.38.0/ibllib/io/extractors/fibrephotometry.py)
- [IBL photometry loading guide](https://docs.internationalbrainlab.org/notebooks_external/loading_photometry_data.html)

### Public asset boundary

Representative held-out and development sessions expose
`photometry.signal.pqt` and `photometryROI.locations.pqt`, but not the raw
Neurophotometrics table or per-session channels CSV expected by the historical
extractor. Consequently, the public archive does not permit an independent
frame-by-frame reconstruction from raw LED states. That limitation does not
create positive evidence for a hidden reference channel; it bounds the audit.

## Conclusion

The convergent acquisition paper and historical extractor establish the most
plausible and documented interpretation: these are 470-nm signal-only recordings
interleaved with no-LED camera frames. The wavelength-0 rows must not be used as an
isosbestic reference. The paired-reference v0.2 readiness failure stands, and the
407 sessions may be reconsidered only under a separately frozen signal-only
protocol.

This conclusion should be revisited only if raw acquisition files or corrected
primary metadata are published.
