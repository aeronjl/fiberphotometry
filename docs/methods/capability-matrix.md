# Capability matrix

The target is broad field utility, not a claim that every possible optical
experiment belongs in one package.

| Scientific task | Status | Current route or required work |
|---|---|---|
| Tabular, TDT, NWB and selected public-data ingestion | **Supported** | Explicit schemas and channel roles |
| Doric, Neurophotometrics and pyPhotometry native import | **Experimental** | Typed native readers with format-specific schemas, inspection evidence, digital events and synthetic writer-contract fixtures |
| Sampling, gaps, dropout, saturation-like and flat-step QC | **Supported** | Outcome-blind preflight and report panels |
| Reference-channel correction | **Supported** | OLS and IRLS; subtraction and division remain distinct |
| Signal-only bleaching correction | **Experimental** | AsLS and double exponential need broader controls |
| Processing order, normalization and negative-control contract | **Partial** | Provenance exists; add operation-order validation, local/null-relative normalization, and explicit control roles |
| Sensor/isobestic-aware validity | **Gap** | Add sensor registry, wavelength evidence, bleed-through and saturation diagnostics |
| Hemodynamic and spectral crosstalk correction | **Gap** | Requires wavelength-aware mixing model and controls |
| Multi-color spectral unmixing | **Gap** | Extend channel metadata and mixing diagnostics |
| Event alignment and window summaries | **Supported** | Retains events, sessions and animals |
| Interval/bout alignment and normalized progress | **Experimental / partial** | Typed intervals, explicit onset/offset, aligned duration values, and first-class progress kernels exist; add merge/split/filter and overlap policies |
| Animal-level scalar inference | **Supported/experimental** | t intervals supported; resampling and mixed models experimental |
| Whole-waveform intervals | **Supported** | Animal-level pointwise and simultaneous bands |
| Published waveform bootstrap/permutation parity | **Partial** | Related animal-level resampling exists; add an explicit literature reproduction and estimand comparison |
| Trial-level functional mixed models | **Planned** | `fastFMM` bridge and numerical-parity fixtures |
| Behavioral/event-kernel GLMs | **Experimental** | Full-FIR, raised-cosine, history, duration/progress kernels, grouped validation, pointwise jackknife sensitivity, model multiverses, and paired family drops; the first simultaneous-band calibration failed its normalized-progress gate, so that band is opt-in only |
| Longitudinal learning trajectories | **Interoperable / experimental** | Validated neural-summary handoff to Unspool; public cross-package benchmark still required |
| Across-session photometry comparability | **Experimental** | Typed outcome-blind identity, preprocessing, coverage, baseline, reference-coupling and sampling diagnostics with warning/refusal states bound into the Unspool handoff |
| Single-signal autocorrelation, PSD and spectrograms | **Experimental** | Gap-separated autocorrelation pairs and window-weighted Welch PSD; complete-window spectrograms retain edge and missing-data evidence |
| State/epoch-conditioned spectral summaries | **Experimental** | User-supplied, non-overlapping epochs remain separate partitions; paired band-power inference aggregates sessions within animals |
| Multiscale long-duration summaries | **Gap** | Keep observable summaries distinct from biological “tonic/phasic” claims |
| Spontaneous transient detection | **Experimental** | Separate GuPPY-, PASTa-, and prominence-compatible candidate families; gap-aware detector evidence retained |
| Spontaneous transient quantification | **Experimental** | Non-z-scored amplitude/half-width/AUC, compound groups, exposure-adjusted session summaries; cut traces and frozen control-derived thresholds remain gaps |
| Spontaneous transient animal-level inference | **Experimental** | Paired/independent animal bootstrap and randomization for exposure-adjusted rate, amplitude, width, and AUC contrasts |
| Multi-site/multi-color coupling | **Gap** | Cross-channel lag, partial association and shared-event models |
| Coherence and phase analysis | **Gap** | Implement only after single-signal spectral validation, with state conditioning and blocked uncertainty |
| Dense spatial multi-fiber analysis | **Gap** | Add coordinates and mouse-aware site/spatial models; avoid treating fibers as independent animals |
| Optogenetic-stimulation artifact handling | **Gap** | Pulse masks, recovery windows and negative controls |
| Sensor-kinetic deconvolution | **Gap / caution** | Sensor-specific forward models and identifiability diagnostics |
| Behavior/pose/state discovery | **Experimental interoperability boundary** | Typed file/in-memory adapters and matched-pulse affine clock synchronization; current DeepLabCut, Keypoint-MoSeq, SLEAP and BORIS file fixtures pass with explicit provenance class; `ndx-pose` and real clock fixtures remain gaps; Unspool owns longitudinal models |
| Robustness multiverses | **Supported** | Named alternatives, compatibility, failures and provenance |
| NWB evidence and archival publication | **Supported** | Export, verification, signing and draft DOI handoff |

“Gap” means the question is common enough to deserve either implementation or a
clear interoperability route. It does not mean the safest response is necessarily
to add another algorithm; some capabilities require new validation data first.
