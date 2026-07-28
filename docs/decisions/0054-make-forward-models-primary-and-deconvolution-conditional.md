# SDR-0054: Make forward models primary and deconvolution conditional

- **Status:** Accepted
- **Date:** 2026-07-28
- **Decision owners:** FiberPhotometry maintainers
- **Related:** SDR-0031, SDR-0047, SDR-0052

## Context

Fluorescent sensors filter, delay and sometimes saturate biological inputs.
Deconvolution can appear to restore hidden dynamics, but its result depends on the
response model, sampling rate, noise, recording boundaries, baseline treatment
and regularization. Similar observed traces can be consistent with different
latent inputs when high frequencies are attenuated or the response is uncertain.

The existing sensor registry records context-specific rise and decay evidence.
Those values do not necessarily define an executable impulse response. Silently
turning descriptive metadata into a kernel would create false precision.

## Decision

FiberPhotometry will:

1. keep descriptive `SensorKinetics` separate from executable response models;
2. version model identity, sensor-profile linkage, units, context, evidence,
   coefficient source and calibration ID;
3. make forward prediction available independently of inversion;
4. reset model state at every timestamp gap or invalid region;
5. require positive, sourced regularization and prospective sampling, duration and
   transfer gates before inversion;
6. retain excluded runs, boundary exposure, reconstruction diagnostics and solver
   evidence on the original clock; and
7. label every recovered input as conditional on the declared model rather than
   ground-truth analyte concentration.

The first implementation supports causal linear time-invariant difference-of-
exponentials and sampled impulse-response models. Other model families must use a
new explicit type and evidence contract rather than overloading these semantics.

## Alternatives considered

### Automatically use profile rise and decay values

Rejected. Published values may use incompatible definitions and contexts. An
executable model requires explicit time constants or a sampled response.

### Offer unregularized inverse filtering

Rejected. Low-pass sensor kernels suppress frequencies and make naive division
unstable or undefined. Positive regularization and its source are required.

### Select regularization from best biological separation

Rejected. This adapts the analysis to the desired outcome. Calibration,
simulation, or a prospectively declared robustness set should govern the choice.

### Carry the fitted state across missing regions

Rejected. The unobserved input inside a gap is unknown. Each continuity run starts
from an explicit zero state and records its boundary-affected region.

### Call an independently calibrated output “concentration”

Rejected as a default. Even a calibrated in-vitro response may change with
expression, temperature, pH, preparation and optical system. Input units remain
those of the declared calibration and the result remains conditional.

## Consequences

- Scientists can use forward simulation without accepting the stronger inverse
  claim.
- Coarse sampling and short runs fail or remain visibly excluded before outcome
  interpretation.
- Regularization changes produce different fingerprints and can be reported as a
  robustness multiverse.
- Linear reconstruction diagnostics cannot validate biological correctness;
  independent model checks remain necessary.
- Nonlinear, saturating and time-varying models require future explicit contracts.

## Revisit trigger

Revisit when public calibration-plus-biological datasets support prospective
regularization calibration, latent-input uncertainty coverage, or validated
nonlinear sensor models across multiple constructs and preparations. Promotion
beyond experimental requires evidence that uncertainty remains calibrated under
model mismatch, gaps and realistic noise.
