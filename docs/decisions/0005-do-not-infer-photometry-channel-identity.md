# SDR-0005: Do not infer photometry channel identity from row position

- Status: Accepted
- Date: 2026-07-26
- Decision owners: project maintainers
- Related protocol/report:
  [prospective IBL v0.2](../ibl-feedback-prospective-v0.2.md)

## Context

The prospective IBL query found 407 sessions from 18 new animals, but none had
labelled 415-nm isosbestic rows. They instead alternated labelled 470-nm rows with
wavelength-0 rows named `None`. ROI values were finite on both. Official IBL
extraction semantics distinguish wavelength 0 (“No additional signal”) from 415
nm (“Isosbestic”). Treating finite values or alternating position as sufficient
channel identity would pass a readiness gate only by changing the schema after it
failed.

## Decision

Require explicit wavelength/name metadata or primary acquisition provenance before
assigning signal or reference semantics. Do not infer an isosbestic channel from
row alternation, finite values, column position, correlation, or analytical
convenience. Unknown channels remain unknown and must fail adapters that require a
reference.

## Consequences

Some large public cohorts cannot enter paired-reference workflows despite having
apparently regular tables. This reduces immediate sample size but prevents silent
scientific relabelling. Signal-only analyses remain possible only under separately
declared methods and protocols.

## Alternatives considered

- Treat wavelength-0 rows as 415 nm because they alternate with 470 nm: rejected
  because official metadata assigns a different meaning and no primary provenance
  supports the reinterpretation.
- Infer identity from correlation with 470 nm: rejected because correlation cannot
  establish acquisition wavelength or biological inertness.
- Drop the reference requirement and run the frozen multiverse: rejected because
  all nine universes explicitly use reference correction.

## Revisit trigger

Revisit for these assets if IBL publishes corrected metadata or acquisition-level
documentation that identifies the wavelength-0 values as a specific optical
channel.

## Evidence added later

The producing `ibllib` version (2.38.0) explicitly maps wavelength 0 to “No LED
ON”, and the associated study methods describe 470-nm-only acquisition with no
isosbestic channel. The public archive does not expose the raw channel-map files,
but the two independent primary sources agree. The paired-reference route is
therefore closed unless new raw or corrected metadata appear. See the
[channel-provenance audit](../ibl-new-cohort-channel-provenance-v0.1.md).
