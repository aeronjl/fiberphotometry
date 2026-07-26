# Sharp-transient and missing-run benchmark results v0.1.1

## Status and amendment

The frozen benchmark executed 620 scenarios. Version 0.1 exposed an ill-defined
relative-error denominator for simulated event contrasts near zero. The original
result is retained. Version 0.1.1 disclosed aggregate inspection and changed only
that denominator to known peak amplitude before re-execution. Its protocol SHA-256
is `5a3eea425b041c6bd31115bc4c12f165e496fbbea0269eb1119bfd3dcc994efc`;
the result SHA-256 is
`3804b795aaf30bc7c1db5f1eaf22603837471f8992a388f2d79a44dd509586b2`.

## Results

Median-rate linear regularization passed all 40 timestamp-jitter scenarios. Nearest
sample selection failed 4 of 40, all ordinary biphasic cases whose response-window
mean exceeded the 1% error limit. It is therefore unsuitable as the default value
regularizer even when peak timing appears unchanged.

For an isolated sample missing at or immediately beside the event, linear
interpolation passed 50 of 60 scenarios and previous-value duplication passed 48
of 60. Failures concentrated in narrow Gaussian and biphasic responses; linear
interpolation could underestimate a narrow event-centred peak by about 20%.
Protected missingness classified all 60 affected events, but those are structural
passes—not recovered scientific observations.

Naive linear interpolation across contiguous gaps failed 82 of 180 scenarios.
There was no shape-independent safe length: even two missing samples failed 10 of
60 cases overall and 7 of 20 gaps centred on the event. Five-sample gaps failed 28
of 60 and twenty-sample gaps failed 44 of 60. All 180 protected-gap scenarios were
retained with an explicit baseline, response, or event-inside-gap disposition.

The deliberately condition-imbalanced fixture emitted the required warning.

## Product rules

- Small timestamp jitter may be regularized linearly at the session median rate,
  while retaining interpolation-distance and coverage provenance.
- Nearest-sample selection is not an inferential substitute for regularization.
- An isolated dropout inside an inferential window is not automatically repaired.
  Linear interpolation may be offered as a declared sensitivity universe; the
  protected-missing result remains visible.
- Previous-value duplication is not recommended for fluorescence inference.
- Contiguous missing runs are protected gaps. The package does not silently bridge
  them, regardless of length.
- Any missing value in a baseline or response window makes that channel-event
  summary incomplete. Partial finite samples are not silently averaged.
- Reports expose baseline and response finite fractions, reconstructed fractions,
  event disposition, and condition-dependent exclusion or reconstruction warnings.

These rules concern inference. Display-only interpolation may be offered later with
an explicit purpose tag and must never be serialized as observed data.

## Scope boundary

The benchmark covers synthetic transient shape, small clock jitter, isolated
dropouts, and protected gaps at 20 and 50 Hz. It does not yet validate block-mean or
anti-aliased downsampling, behavior-to-photometry clock mapping, trial warping,
noise-dependent artifact detection, or real held-out recordings.
