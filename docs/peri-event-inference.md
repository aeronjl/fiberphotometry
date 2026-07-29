# Animal-level peri-event inference v0.1

fipha can add a time-resolved evidence lane to the existing scalar event
contrast without treating events as independent replicates. The result retains the
complete session-to-animal evidence chain rather than only the final population
curve.

<figure class="doc-figure doc-figure--wide">
  <img src="../assets/peri-event-inference.svg" alt="Eight animal-level peri-event contrast curves are summarized by a mean with a narrower pointwise interval and a wider simultaneous whole-window band around an event at time zero.">
  <figcaption><strong>Animal-level curves support two uncertainty statements.</strong> The synthetic illustration distinguishes pointwise uncertainty from simultaneous coverage across the declared window.</figcaption>
</figure>

```python
from fipha import EventAnalysis, PeriEventInferenceSpec

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

The serialized result includes every session-condition curve with event counts,
every animal-condition curve with source sessions and pointwise support, incomplete
animal identifiers, and a leave-one-animal-out population curve for each included
animal. This makes unequal trial yield and influential animals inspectable without
turning them into population replicates.

## Paired and independent populations

The default `design="paired"` answers a within-animal contrast. Only complete
animal pairs enter the population curve; incomplete animals remain visible in the
result ledger.

For a between-animal experiment, conditions must be constant at the animal level
and animal identifiers must be disjoint. Declare that design rather than asking the
software to infer it from the observed labels:

```python
study = EventAnalysis(
    sessions,
    numerator="drug",
    denominator="control",
    channel="DMS",
    preprocessing=preprocessing,
    factor_assignment_unit="animal",
    timecourse=PeriEventInferenceSpec(
        design="independent",
        window=(-1.0, 2.0),
        draws=2_000,
        seed=7,
    ),
)
```

Independent inference forms one curve per animal, contrasts the two group means,
uses a pointwise Welch standard error, and resamples animals separately within
group. Each group requires at least two animals.

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

The result records both bands, group-specific pointwise animal support, seed, draw
count, critical value, Hedges standardized effects, and warnings for changing
support or zero-variance points. The HTML report draws the simultaneous band behind
the pointwise interval and summarizes the largest leave-one-animal-out change. JSON
retains the complete numeric arrays and ledgers.

## Scope and limitations

- This v0.1 method addresses paired within-animal and independent between-animal
  two-level contrasts.
- Equal session weighting is the only supported within-animal policy.
- Missing values are retained; support may vary by time and is reported.
- The band reflects between-animal uncertainty, conditional on the observed
  sessions and preprocessing workflow.
- Factorial interactions, continuous covariates, generalized outcomes, and
  functional mixed models are not yet supported.
- It does not replace functional mixed models, cluster permutation tests, or a
  prespecified scalar estimand when those answer a different question.

The low-level `infer_peri_event_contrast` API accepts an event-by-time matrix plus
animal, session, and condition labels for integrations outside `EventAnalysis`.
Its `design` argument is required whenever the intended design is independent.

When two independent groups each contribute both repeated conditions, use
`infer_peri_event_interaction()` rather than running separate group analyses. The
[group-by-condition interaction contract](population-interactions.md) retains
the same session and animal evidence while directly estimating the difference in
differences.

The shared result semantics are described in
[Animal estimates and population contrasts](population-inference.md).
