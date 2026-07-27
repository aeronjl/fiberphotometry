# Spontaneous transients and long recordings

!!! warning "Experimental method family"

    There is no field-wide spontaneous-event definition. Report the complete
    specification and show whether conclusions survive plausible alternatives.

`detect_transients()` detects local maxima inside uninterrupted finite acquisition
runs. It then defines amplitude relative to an adaptive pre-peak baseline, applies
a named inclusion threshold, and measures half-height width and area. It retains
rejected candidates and uses acquired duration—not wall-clock duration across
gaps—for rates.

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

The defaults are close to common published choices, but are not endorsed as
universally optimal. PASTa motivates adaptive pre-peak baselines and reports event
amplitude, duration, AUC, frequency, and inter-event intervals. GuPPy motivates a
15-second moving window and MAD-based detection. Individual studies also use
fixed z-score or prominence rules, underscoring the need to record alternatives.

## Current boundaries

This increment does not yet identify compound events, deconvolve sensor kinetics,
assign events to neurotransmitter release episodes, or infer a biological
tonic/phasic decomposition. Those require separate ground truth and interpretation
tests.

## Sources

- Bruno et al., [PASTa: flexible photometry analysis including spontaneous
  transients](https://pmc.ncbi.nlm.nih.gov/articles/PMC12224222/)
- Sherathiya et al., [GuPPy: a Python toolbox for fiber photometry
  analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC8688475/)
- Markowitz et al., [Wideband dopamine dynamics](https://pmc.ncbi.nlm.nih.gov/articles/PMC11526850/)
