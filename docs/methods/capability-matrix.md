# Capability matrix

The target is broad field utility, not a claim that every possible optical
experiment belongs in one package.

| Scientific task | Status | Current route or required work |
|---|---|---|
| Tabular, TDT, NWB and selected public-data ingestion | **Supported** | Explicit schemas and channel roles |
| Doric, Neurophotometrics and pyPhotometry native import | **Gap** | Add thin adapters with official fixtures |
| Sampling, gaps, dropout, saturation-like and flat-step QC | **Supported** | Outcome-blind preflight and report panels |
| Reference-channel correction | **Supported** | OLS and IRLS; subtraction and division remain distinct |
| Signal-only bleaching correction | **Experimental** | AsLS and double exponential need broader controls |
| Processing order, normalization and negative-control contract | **Partial** | Provenance exists; add operation-order validation, local/null-relative normalization, and explicit control roles |
| Sensor/isobestic-aware validity | **Gap** | Add sensor registry, wavelength evidence, bleed-through and saturation diagnostics |
| Hemodynamic and spectral crosstalk correction | **Gap** | Requires wavelength-aware mixing model and controls |
| Multi-color spectral unmixing | **Gap** | Extend channel metadata and mixing diagnostics |
| Event alignment and window summaries | **Supported** | Retains events, sessions and animals |
| Interval/bout alignment and normalized progress | **Experimental / partial** | Typed intervals, explicit onset/offset and progress exist; add merge/split/filter rules and duration kernels |
| Animal-level scalar inference | **Supported/experimental** | t intervals supported; resampling and mixed models experimental |
| Whole-waveform intervals | **Supported** | Animal-level pointwise and simultaneous bands |
| Published waveform bootstrap/permutation parity | **Partial** | Related animal-level resampling exists; add an explicit literature reproduction and estimand comparison |
| Trial-level functional mixed models | **Planned** | `fastFMM` bridge and numerical-parity fixtures |
| Behavioral/event-kernel GLMs | **Experimental** | FIR kernels, explicit validity masks and coverage, grouped validation, conditional jackknife intervals and gap-safe residual diagnostics; add basis/history/contribution multiverses and formal interval coverage |
| Longitudinal learning trajectories | **Interoperable / experimental** | Validated neural-summary handoff to Unspool; public cross-package benchmark still required |
| Across-session photometry comparability | **Gap** | Add expression/coupling/baseline diagnostics and explicit refusal states before Unspool handoff |
| Single-signal autocorrelation, PSD and spectrograms | **Gap** | Add gap-aware, detrending-explicit time/frequency results and public state fixture |
| State/epoch-conditioned and multiscale long-duration summaries | **Gap** | Consume external state tables; keep observable summaries distinct from biological “tonic/phasic” claims |
| Spontaneous transient detection | **Experimental** | Gap-aware local-baseline prototype and public sensitivity audit; not yet GuPPY/PASTa/Prominence parity |
| Spontaneous transient kinetic/rate inference | **Gap** | Separate detection from quantification; add compound events, cut traces, control-derived thresholds and animal-aware models |
| Multi-site/multi-color coupling | **Gap** | Cross-channel lag, partial association and shared-event models |
| Coherence and phase analysis | **Gap** | Implement only after single-signal spectral validation, with state conditioning and blocked uncertainty |
| Dense spatial multi-fiber analysis | **Gap** | Add coordinates and mouse-aware site/spatial models; avoid treating fibers as independent animals |
| Optogenetic-stimulation artifact handling | **Gap** | Pulse masks, recovery windows and negative controls |
| Sensor-kinetic deconvolution | **Gap / caution** | Sensor-specific forward models and identifiability diagnostics |
| Behavior/pose/state discovery | **Experimental interoperability boundary** | Typed file/in-memory adapters and matched-pulse affine clock synchronization; official SLEAP and BORIS fixtures pass, DeepLabCut and Keypoint-MoSeq remain schema-only; `ndx-pose` is a gap; Unspool owns longitudinal models |
| Robustness multiverses | **Supported** | Named alternatives, compatibility, failures and provenance |
| NWB evidence and archival publication | **Supported** | Export, verification, signing and draft DOI handoff |

“Gap” means the question is common enough to deserve either implementation or a
clear interoperability route. It does not mean the safest response is necessarily
to add another algorithm; some capabilities require new validation data first.
