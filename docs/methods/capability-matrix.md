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
| Hemodynamic and spectral crosstalk correction | **Gap** | Requires wavelength-aware mixing model and controls |
| Multi-color spectral unmixing | **Gap** | Extend channel metadata and mixing diagnostics |
| Event alignment and window summaries | **Supported** | Retains events, sessions and animals |
| Animal-level scalar inference | **Supported/experimental** | t intervals supported; resampling and mixed models experimental |
| Whole-waveform intervals | **Supported** | Animal-level pointwise and simultaneous bands |
| Trial-level functional mixed models | **Planned** | `fastFMM` bridge and numerical-parity fixtures |
| Behavioral/event-kernel GLMs | **Experimental** | FIR event kernels, continuous covariates and group-held-out ridge selection; uncertainty and public-data validation remain |
| Longitudinal learning trajectories | **Gap** | Session/time hierarchy and varying effects |
| Tonic/phasic long-duration analysis | **Gap** | Multiscale baseline and transient representations |
| Spontaneous transient detection | **Gap** | Local baselines, event definitions and validation fixtures |
| Multi-site/multi-color coupling | **Gap** | Cross-channel lag, partial association and shared-event models |
| Optogenetic-stimulation artifact handling | **Gap** | Pulse masks, recovery windows and negative controls |
| Sensor-kinetic deconvolution | **Gap / caution** | Sensor-specific forward models and identifiability diagnostics |
| Robustness multiverses | **Supported** | Named alternatives, compatibility, failures and provenance |
| NWB evidence and archival publication | **Supported** | Export, verification, signing and draft DOI handoff |

“Gap” means the question is common enough to deserve either implementation or a
clear interoperability route. It does not mean the safest response is necessarily
to add another algorithm; some capabilities require new validation data first.
