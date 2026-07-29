# Previous-outcome event kernels

!!! warning "Experimental"
    This example validates recovery and grouped prediction for a declared history
    term. It does not establish that previous outcome modulates a particular neural
    signal in biological data.

## Question

Does the response to the current cue differ according to the immediately previous
trial outcome, after retaining the average cue response?

This is an event-wise interaction. It is not a longitudinal learning model: the
history resets at every session boundary, while cross-session trajectories remain
the responsibility of [Unspool](../unspool-interoperability.md).

## Declare rather than infer the history

Each cue has a caller-supplied `outcome_code`. Here rewarded and unrewarded trials
are coded +0.5 and −0.5, so zero represents their midpoint. The first cue has no
previous outcome and deliberately receives the declared unavailable value of zero.

```python
from fipha.encoding import EncodingSession

session = EncodingSession.from_arrays(
    subject="mouse-1",
    session="day-1",
    time=time,
    response=corrected_signal,
    events={"cue": cue_times},
    event_values={"cue": {"outcome_code": outcome_code}},
)
```

The values must be finite and match cue occurrences one-for-one. fipha
does not guess trial order, carry history across sessions, or silently discard a
trial with missing metadata.

## Fit a main kernel and a history kernel

```python
from fipha.encoding import (
    EncodingModelSpec,
    EventKernelSpec,
    EventModulationSpec,
    fit_event_kernel_model,
)

spec = EncodingModelSpec(
    event_kernels=(
        EventKernelSpec("cue", (-1.0, 3.0)),
        EventKernelSpec(
            "cue-by-previous-outcome",
            (-1.0, 3.0),
            source_event="cue",
            modulation=EventModulationSpec(
                value="outcome_code",
                lag_events=1,
                unavailable_value=0.0,
            ),
        ),
    ),
    group_by="animal",
)

result = fit_event_kernel_model(sessions, spec)
```

The `cue` kernel is the expected response when `outcome_code` is zero. The
`cue-by-previous-outcome` kernel is the response-unit change per one unit of that
coding. With −0.5/+0.5 coding, its curve is the rewarded-minus-unrewarded previous
outcome contrast. Both terms are estimated jointly with every other declared event
and covariate.

## Robustness workflow

History should normally be a named model alternative, not added after viewing the
pooled curve. Compare a cue-only model with a cue-plus-history model through
`run_encoding_multiverse()`. Direct held-out R² differences are reported only when
the exact retained observations match; failures remain in the ledger.

The executable simulation in
[`examples/event_kernel_history.py`](https://github.com/aeronjl/fipha/blob/main/examples/event_kernel_history.py)
recovers a known previous-outcome curve while holding out complete animals.

## What this does not do

- It does not estimate latent learning state or cross-session behavioral change.
- It does not decide how reward, choice, or duration should be coded.
- It does not make a conditional kernel causal.
- It does not rescue a model that fails group-held-out prediction.

The serialized result records the source event, lag, value name, unavailable-value
rule, basis, fitted curve, uncertainty, and grouped diagnostics.
