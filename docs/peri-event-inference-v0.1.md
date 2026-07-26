# Animal-level peri-event inference v0.1

FiberPhotometry can add a time-resolved evidence lane to the existing scalar event
contrast without treating events as independent replicates.

```python
from fiberphotometry import EventAnalysis, PeriEventInferenceSpec

study = EventAnalysis(
    sessions,
    numerator="correct",
    denominator="incorrect",
    channel="DMS",
    preprocessing=preprocessing,
    timecourse=PeriEventInferenceSpec(
        window=(-1.0, 2.0),
        rate_hz=20,
        confidence=0.95,
        draws=2_000,
        seed=7,
    ),
)
```

## Experimental unit and aggregation

The input remains event-level so individual observations and missing windows stay
visible. Inference does not operate on events directly:

1. Events are averaged within each session and condition.
2. Session-condition means are averaged equally within each animal.
3. The numerator-minus-denominator curve is formed for each animal.
4. Only those animal contrast curves are resampled.

Duplicating events within a session therefore leaves the estimate, standard error,
and interval unchanged. An animal must contribute both contrast conditions, and at
least two animals must support a time point.

## Two different uncertainty statements

The pointwise percentile interval describes uncertainty separately at each
relative time. It does not cover a scientist scanning the entire curve for an
interesting time point.

The simultaneous band uses the bootstrap distribution of the maximum absolute
standardized deviation over the declared window. Its critical value expands a
single band around the animal-level estimate, providing a whole-window confidence
statement under the declared bootstrap assumptions. For small samples, the
critical value cannot fall below the ordinary two-sided animal-level t critical
value; this conservative floor prevents a sparse empirical bootstrap from making
the simultaneous band misleadingly narrow. This is not a cluster-based test and
does not infer a privileged onset or duration.

The result records both bands, pointwise animal support, seed, draw count, critical
value, and warnings for changing support or zero-variance points. The HTML report
draws the simultaneous band behind the pointwise interval and states their
different interpretations. JSON retains the complete numeric arrays.

## Scope and limitations

- This v0.1 method addresses a within-animal categorical contrast.
- Equal session weighting is the only supported within-animal policy.
- Missing values are retained; support may vary by time and is reported.
- The band reflects between-animal uncertainty, conditional on the observed
  sessions and preprocessing workflow.
- It does not replace functional mixed models, cluster permutation tests, or a
  prespecified scalar estimand when those answer a different question.

The low-level `infer_peri_event_contrast` API accepts an event-by-time matrix plus
animal, session, and condition labels for integrations outside `EventAnalysis`.
