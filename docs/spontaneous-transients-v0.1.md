# Spontaneous transients and long recordings

!!! warning "Experimental method family"

    There is no field-wide spontaneous-event definition. Report the complete
    specification and show whether conclusions survive plausible alternatives.

The preferred product API separates candidate detection from kinetic
quantification. This matters whenever detection uses a normalized representation:
candidate timestamps can come from a z-scored stream while amplitude, width, and
area are measured on non-z-scored dF/F.

```python
from fiberphotometry import (
    ProminenceTransientDetectorSpec,
    TransientQuantificationSpec,
    detect_transient_candidates,
    quantify_transient_candidates,
)

candidates = detect_transient_candidates(
    recording,
    variable="detection_z",
    spec=ProminenceTransientDetectorSpec(
        minimum_height_z=1,
        minimum_prominence_z=2,
        detrend_window_s=100,
    ),
)
result = quantify_transient_candidates(
    recording,
    candidates,
    variable="dff",
    spec=TransientQuantificationSpec(
        baseline_method="mean",
        baseline_start_s=1.0,
        baseline_end_s=0.2,
    ),
)
```

Both stages split the signal at missing acquisition and large timestamp gaps.
Candidate IDs retain the detector family, sample, threshold, and score through
quantification.

## Named detector families

- `PastaTransientDetectorSpec` finds local maxima and tests their amplitude
  relative to a pre-peak mean, minimum, or last local minimum. Its threshold is
  supplied in the same units as the detection stream.
- `GuppyTransientDetectorSpec` implements GuPPY's chunked two-threshold
  procedure: high-amplitude samples are excluded using the first, unscaled MAD
  threshold before the second MAD threshold and local-maximum detection.
- `ProminenceTransientDetectorSpec` optionally removes a gap-local moving mean,
  z-scores within each uninterrupted run, and requires both peak height and
  prominence. Quantification remains a separate call on dF/F.

These are compatibility families, not assertions that one detector is correct.
The exact specification belongs in analysis provenance.

## Legacy combined call

`detect_transients()` remains available for the earlier single-variable workflow:

```python
from fiberphotometry import TransientDetectionSpec, detect_transients

result = detect_transients(
    recording,
    variable="dff",
    spec=TransientDetectionSpec(
        threshold_mode="rolling_mad",
        threshold=3.0,
        noise_window_s=15.0,
        baseline_duration_s=0.9,
        baseline_gap_s=0.1,
        baseline_statistic="median",
        minimum_distance_s=0.2,
        bin_width_s=30.0,
    ),
)
```

## What the outputs mean

- `events` contains peak time, local baseline, amplitude, half-height rise/fall
  timing and width, AUC, and preceding inter-event interval.
- `exclusions` records insufficient baselines, sub-threshold candidates, and
  shapes truncated by acquisition boundaries or gaps.
- `summaries` reports count, rate, and median event properties per channel.
- `bins` provides count, finite exposure, exposure-adjusted rate, and median
  amplitude in long windows.

The bins are descriptive. They are not called a tonic signal: slow fluorescence
variation may combine biology with bleaching, motion, and sensor kinetics.

## A minimum sensitivity analysis

At minimum, compare `global_mad` and `rolling_mad`, more than one defensible MAD
multiplier, and `median` versus `minimum` local baselines. The scientific result
should include changes in event count as well as downstream effect estimates.

For new work, prefer the separated calls. Do not use a z-scored quantification
variable to claim interpretable changes in amplitude or kinetics across
conditions.

## Current boundaries

Quantification now marks nearby events with compound-group/rank metadata. It does
not yet export cut waveforms, freeze thresholds learned from baseline/control
epochs, fit animal-aware rate/kinetic models, deconvolve sensor kinetics, assign
events to neurotransmitter release episodes, or infer a biological tonic/phasic
decomposition.

## Sources

- Donka et al., [PASTa: flexible photometry analysis including spontaneous
  transients](https://pmc.ncbi.nlm.nih.gov/articles/PMC12224222/)
- Sherathiya et al., [GuPPy: a Python toolbox for fiber photometry
  analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC8688475/)
- Wallace et al., [The z-scored data are not the data](https://pmc.ncbi.nlm.nih.gov/articles/PMC13245556/)
- Markowitz et al., [Wideband dopamine dynamics](https://pmc.ncbi.nlm.nih.gov/articles/PMC11526850/)
