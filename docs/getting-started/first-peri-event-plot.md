# Your first peri-event plot

The event-aligned mean trace with an uncertainty band is the standard figure in
fiber photometry. This page draws one end to end.

It needs the [base install](install.md) plus the `plots` extra:

```bash
pip install "fipha[plots] @ git+https://github.com/aeronjl/fipha.git"
```

## The whole thing

```python
import matplotlib.pyplot as plt
import numpy as np
from fipha import align_events, make_recording, reference_dff

# One synthetic session: events 25 s apart, response amplitude varying
# trial to trial, on shared photobleaching.
rng = np.random.default_rng(0)
time = np.arange(0.0, 300.0, 0.01)
event_times = np.arange(20.0, 300.0, 25.0)
bleach = 0.6 * np.exp(-time / 250.0)
amplitudes = 0.06 * (1.0 + 0.35 * rng.standard_normal(event_times.size))
response = sum(
    amplitude * np.exp(-np.clip(time - onset, 0.0, None) / 1.5) * (time >= onset)
    for onset, amplitude in zip(event_times, amplitudes, strict=True)
)

recording = make_recording(
    time=time,
    signal=2.0 + bleach + response + rng.normal(0.0, 0.002, time.size),
    reference=2.0 + bleach + rng.normal(0.0, 0.002, time.size),
    channel_names=["DMS"],
    subject="mouse-01",
    session="day-01",
)
corrected = reference_dff(recording)

# Cut a window around every event. Events stay a dimension.
epochs = align_events(corrected, event_times, window=(-2.0, 6.0), rate=100.0)
trace = epochs.sel(channel="DMS")

lag = trace["relative_time"].values
mean = trace.mean("event").values
sem = trace.std("event", ddof=1).values / np.sqrt(trace.sizes["event"])

fig, ax = plt.subplots(figsize=(4.2, 2.8), constrained_layout=True)
ax.axhline(0.0, color="0.8", linewidth=0.8)
ax.axvline(0.0, color="0.5", linewidth=1.0, linestyle="--")
ax.fill_between(lag, mean - sem, mean + sem, alpha=0.25, linewidth=0)
ax.plot(lag, mean, linewidth=1.5)
ax.set_xlabel("Time from event (s)")
ax.set_ylabel("dF/F")
ax.set_title(f"DMS, {trace.sizes['event']} events, 1 session")
fig.savefig("first-peri-event-plot.png", dpi=200)
```

<figure class="doc-figure">
  <img src="../../assets/first-peri-event-plot.png" alt="Mean dF/F rises sharply at the dashed event marker at time zero and decays over roughly four seconds; a narrow shaded band shows the standard error across twelve events.">
  <figcaption><strong>Output of the code above.</strong> Synthetic data with a
  known response, aligned to twelve events in one session. The shaded band is the
  standard error <em>across events within one session</em>, which is not an
  animal-level uncertainty statement.</figcaption>
</figure>

## What `align_events` returns

```python
>>> epochs.dims
('event', 'relative_time', 'channel')
>>> epochs.shape
(12, 801, 1)
```

Events are a labelled dimension, not something already averaged away. The
`relative_time` coordinate is time from event onset, so zero is the event. The
original `event_time` stays attached as a coordinate, so any window can be traced
back to the sample it came from.

Two arguments matter more than they look:

- `window=(-2.0, 6.0)` is in seconds relative to the event. The pre-event part
  is your baseline; make it long enough to be a baseline and short enough not to
  overlap the previous event.
- `rate=100.0` is the resampling rate for the aligned window. Set it from your
  acquisition rate — `assess_recording(recording).estimated_rate_hz` reports it.

Pass `max_gap_s=` to refuse windows that span a dropout instead of silently
interpolating across it.

## A one-line diagnostic version

The package ships a ready-made three-panel diagnostic — the raw and fitted
channels, the corrected trace with event markers, and the event-aligned mean.
It needs the `plots` extra for matplotlib:

```python
from fipha import plot_event_diagnostics

fig, axes = plot_event_diagnostics(
    corrected,
    event_times,
    channel="DMS",
    window=(-2.0, 6.0),
)
fig.savefig("event-diagnostics.png", dpi=200)
```

`plot_specification_curve` is exported alongside it, for
[robustness multiverses](../multiverse-contract.md).

## Getting a number out of it

A figure is not a result. `summarize_event_windows` reduces each event to a
baseline mean, a response mean, and their difference, without interpolating or
averaging events away:

```python
from fipha import summarize_event_windows

summary = summarize_event_windows(
    corrected,
    event_times,
    baseline=(-2.0, 0.0),
    response=(0.0, 2.0),
    variable="dff",
)
delta = summary["delta"].sel(channel="DMS")
print(f"mean delta dF/F = {float(delta.mean()):.4f} over {delta.sizes['event']} events")
```

```text
mean delta dF/F = 0.0143 over 12 events
```

## The limit of this page

This is one animal, one session, one condition. The band above describes
variability across trials within that session. Trials are not independent
replicates of an animal, so a band like this cannot support a claim about a group
of mice — that is the pseudoreplication failure the package is built to avoid.

For a real result you need a contrast between named conditions, several animals,
and inference that keeps the animal as the experimental unit:

- [First event analysis](../product-workflow.md) — the scientist-facing
  `EventAnalysis` workflow, from labelled sessions to an auditable contrast and
  an HTML evidence report.
- [Peri-event inference](../peri-event-inference.md) — animal-level pointwise and
  whole-window simultaneous bands, which is what the figure above should become.
- [Animal estimates and population contrasts](../population-inference.md) — the
  shared boundary that materializes session and animal estimates before any
  population claim.
