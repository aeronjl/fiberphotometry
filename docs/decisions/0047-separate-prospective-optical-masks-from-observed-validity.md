# SDR-0047: Separate prospective optical masks from observed validity

- **Status:** Accepted
- **Date:** 2026-07-27

## Context

Optogenetic stimulation can create direct light artifacts, detector saturation, and
post-pulse recovery transients. The duration visible in a recorded signal is tempting
to use as the exclusion duration, but doing so makes sample selection depend on the
outcome. Different sensors, powers, optical paths, and detectors also make a universal
mask duration unsafe.

Sensor and isosbestic labels create a second circularity risk. Wavelength metadata and
correlation can identify inconsistencies, but they cannot prove that a reference is
biologically inert, that a signal is free of hemodynamics, or that fluorescence is a
concentration measurement. Sensor knowledge also changes and is context-specific.

## Decision

Pulse masking and observed optical diagnostics are separate immutable results.

- A stimulation mask is generated only from timestamps, a declared pre/post policy,
  and pre-existing validity. It never inspects signal or control values.
- Expanded pulse intervals may merge, but every source pulse ID is retained. The mask
  reports original, artifact, newly invalid, and retained sample counts plus a stable
  fingerprint.
- Recovery, saturation, and negative-control behavior are assessed separately. A
  subsequent pulse censors recovery assessment; overlap with a prior pulse is explicit.
- Observed recovery never mutates the current mask. It may motivate a prospectively
  declared alternative in a future analysis or multiverse.
- Sensor facts enter through immutable, versioned, user-supplied profiles. The package
  does not silently select the newest version or maintain a closed sensor enum.
- Validity assessment compares explicit channel identity and observed evidence with the
  selected profile, returning retained metrics and pass/warning/fail issues.
- The assessment states that it cannot prove biological inertness, specificity,
  absence of contamination, or concentration calibration.

## Alternatives considered

- **Mask until the observed signal returns to baseline.** Rejected because the outcome
  would determine its own denominator and noise could alter the exclusion.
- **Infer detector rails from observed minima and maxima.** Rejected because repeated
  extrema are useful diagnostics but do not establish hardware limits.
- **Ship one mutable built-in profile per named sensor.** Rejected because constructs,
  preparations, calibrations, and evidence change; silent updates would break
  reproducibility.
- **Treat an excitation wavelength as proof of an isosbestic control.** Rejected because
  a nominal wavelength does not establish in-vivo biological inertness.
- **Automatically regress any channel called reference.** Rejected because reference
  correction changes the signal and can remove biological structure.

## Consequences

Scientists must declare pulse policy and sensor metadata explicitly. The workflow may
produce warnings without offering an automatic correction, and laboratories must own
their profile evidence and versioning. In return, exclusions are outcome-independent,
later knowledge cannot rewrite old analyses, and every interpretive gate is auditable.

Optogenetic interpolation, hemodynamic correction, spectral unmixing, sensor-specific
deconvolution, and concentration calibration remain separate unimplemented methods.

## Revisit trigger

Revisit mask defaults after raw recordings from at least two independent laboratories
span multiple stimulation powers, sensors, acquisition systems, and negative controls.
Revisit profile distribution when a community-maintained, versioned sensor ontology
offers stable identifiers and evidence review without requiring mutable package facts.
