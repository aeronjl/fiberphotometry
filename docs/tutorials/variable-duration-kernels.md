# Variable-duration behavior kernels

!!! warning "Experimental"
    This workflow estimates predictive trajectories for declared behavioral bouts.
    It does not validate the behavior classifier or make a bout effect causal.

## Three distinct questions

For a variable-duration behavior such as rearing, grooming, or approach, keep these
hypotheses separate:

1. **Onset or offset:** is there a transient aligned to a physical edge?
2. **Duration modulation:** does the edge response change per second of bout
   duration?
3. **Normalized progress:** how does the conditional response vary from the start
   to the end of the active state?

Normalized progress supplements physical time. It does not turn a long and short
bout into the same physical process.

<figure class="doc-figure doc-figure--wide">
  <img src="../../assets/variable-duration-kernels.svg" alt="Two bouts retain their physical onset, offset, and unequal durations; both map to one normalized-progress trajectory, while samples outside the bouts remain zero-valued design rows rather than missing observations.">
  <figcaption><strong>Progress is an additional coordinate.</strong> Physical interval bounds remain available, and the continuous-recording denominator is preserved.</figcaption>
</figure>

## Convert typed annotations without losing duration

Adapters for Keypoint-MoSeq and BORIS produce `BehaviorAnnotations`. Convert only
the intervals needed for encoding:

```python
inputs = annotations.interval_encoding_inputs(edge="onset")

session = EncodingSession.from_arrays(
    subject=annotations.subject,
    session=annotations.session,
    time=photometry_time,
    response=corrected_signal,
    events=inputs.events,
    event_values=inputs.event_values,
    intervals=inputs.intervals,
)
```

The bundle keeps onset times and `duration_s` aligned one-for-one and retains every
physical `(start_s, stop_s)` pair. Choose `edge="offset"` explicitly when offset is
the scientific reference. The helper does not synchronize clocks: transform the
annotations to the photometry clock first and retain that synchronization evidence.

## Declare edge, duration, and progress terms

```python
from fiberphotometry.encoding import (
    EncodingModelSpec,
    EventKernelSpec,
    EventModulationSpec,
    LinearProgressBasisSpec,
    ProgressKernelSpec,
)

spec = EncodingModelSpec(
    event_kernels=(
        EventKernelSpec("rear", (-1.0, 2.0)),
        EventKernelSpec(
            "rear-by-duration",
            (-1.0, 2.0),
            source_event="rear",
            modulation=EventModulationSpec("duration_s"),
        ),
    ),
    progress_kernels=(
        ProgressKernelSpec(
            "rear-progress",
            source_interval="rear",
            basis=LinearProgressBasisSpec(functions=5),
        ),
    ),
    group_by="animal",
)
```

The unmodulated edge kernel is the response at zero duration under raw-second
coding, which may be an extrapolated reference. For a more meaningful main effect,
the caller can supply an explicitly centered duration value under another name.
FiberPhotometry does not center event values after seeing outcomes.

## How progress fitting works

Each acquired sample inside a bout is assigned `(time - start) / (stop - start)`.
A piecewise-linear basis spans progress from zero to one. Outside-bout rows contain
zeros for every progress component and remain in the full-session denominator;
they are not marked missing or discarded.

The result reports:

- the physical source interval and total bout count;
- the reconstructed curve on a declared 101-point progress grid;
- basis functions and weights needed for exact reconstruction;
- delete-one-group sensitivity intervals on the progress grid; and
- the same group-held-out prediction and residual diagnostics as event kernels.

Within one modeled interval family, bounds must be ordered, non-overlapping, and
fully supported by the recording. Intervals use half-open sampling `[start, stop)`
so adjacent bouts do not double-count a boundary sample.

## Treat alternatives as a multiverse

Onset-only, onset-plus-duration, and onset-plus-progress models answer different
questions. Compare them as named alternatives with `run_encoding_multiverse()`.
Held-out score deltas are reported only on identical retained timestamps, and a
failed progress model stays in the ledger.

Run the complete simulation:

```bash
uv run python examples/variable_duration_kernels.py
```

See the [behavior-tool tutorial](behavior-tool-interoperability.md) for
DeepLabCut, SLEAP, Keypoint-MoSeq, and BORIS inputs.
