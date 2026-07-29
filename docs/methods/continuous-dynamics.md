# Spontaneous and continuous dynamics

Use this category when no single supplied event train defines the question. The
methods keep acquisition gaps and state boundaries explicit rather than treating a
recording as one uninterrupted stationary signal.

## Choose the workflow

| Need | Workflow | Status |
|---|---|---|
| Detect candidate fluorescence transients, then quantify their rate and kinetics | [Spontaneous transients](../spontaneous-transients.md) | Experimental |
| Estimate autocorrelation, PSD, spectrograms, or state-conditioned band power | [Time, frequency, and state analysis](../spectral-state-analysis.md) | Experimental |
| Summarize seconds-to-hours windows with explicit coverage | [Multiscale long-duration summaries](../multiscale-long-duration.md) | Experimental |

## Required distinctions

- Candidate detection is separate from waveform quantification.
- Missing acquisition time is separate from a low signal value.
- A fluorescence transient is not automatically a neurotransmitter-release event.
- Spectral power is descriptive unless the sampling, window, null, and independent
  unit support the stronger claim.
- “Tonic” and “phasic” are biological interpretations, not labels inferred from a
  timescale alone.

## Coverage gaps this category exposes

- manually adjudicated and synthetic-injection detector benchmarks;
- point-process and marked-event models at the animal level;
- wavelet and cross-frequency workflows with gap-aware nulls;
- change-point and latent-state models that preserve uncertainty; and
- public paper-figure reproductions spanning sensors, tasks, and acquisition systems.

For relationships among simultaneous signals, continue to
[multi-signal and spatial analysis](multisignal-spatial.md).
