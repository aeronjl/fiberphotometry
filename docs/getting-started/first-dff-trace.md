# Your first dF/F trace

This page produces a reference-corrected dF/F trace from scratch. It needs no
data files, no repository checkout, and no optional extras — only the
[base install](install.md).

## The whole thing

```python
import numpy as np
from fiberphotometry import assess_recording, make_recording, reference_dff

# A five-minute, 100 Hz synthetic recording: shared photobleaching and motion in
# both channels, plus a signal-only response every 25 s.
rng = np.random.default_rng(0)
time = np.arange(0.0, 300.0, 0.01)
bleach = 0.6 * np.exp(-time / 250.0)
motion = 0.02 * np.sin(2 * np.pi * 0.05 * time)
response = sum(
    0.06 * np.exp(-np.clip(time - onset, 0.0, None) / 1.5) * (time >= onset)
    for onset in np.arange(20.0, 300.0, 25.0)
)

recording = make_recording(
    time=time,
    signal=2.0 + bleach + motion + response + rng.normal(0.0, 0.002, time.size),
    reference=2.0 + bleach + motion + rng.normal(0.0, 0.002, time.size),
    channel_names=["DMS"],
    subject="mouse-01",
    session="day-01",
)

corrected = reference_dff(recording)
dff = corrected["dff"].sel(channel="DMS")

print(f"peak dF/F  {float(dff.max()):.4f}")
print(f"baseline   {float(dff.isel(time=slice(0, 500)).mean()):+.5f}")
```

```text
peak dF/F  0.0279
baseline   -0.00035
```

The photobleaching decay and the 0.05 Hz motion artefact are gone; the
signal-only response survives. That is the whole point of the reference channel.

## What each step does

**`make_recording`** builds the canonical representation: an
`xarray.Dataset` with a `time` coordinate, a named `channel` coordinate, and the
subject and session attached as attributes. Nothing downstream has to guess which
column was the signal, which was the isosbestic reference, or which animal a trace
came from.

```python
>>> recording
<xarray.Dataset> Size: 720kB
Dimensions:    (time: 30000, channel: 1)
Coordinates:
  * time       (time) float64 0.0 0.01 0.02 ... 299.98 299.99
  * channel    (channel) <U3 'DMS'
Data variables:
    signal     (time, channel) float64 ...
    reference  (time, channel) float64 ...
Attributes:
    subject:           mouse-01
    session:           day-01
    processing_stage:  raw
```

Pass `reference=None` if you have no control channel. You then need
`fiberphotometry.baseline_dff` instead, which is experimental — see
[Preprocessing and QC](../pipeline.md).

**`reference_dff`** fits the reference channel to the signal channel and forms
`(signal - fitted_reference) / fitted_reference`. It defaults to iteratively
reweighted least squares (`method="irls"`), which is less distorted by large
transients than ordinary least squares. It adds four variables and keeps the raw
ones:

```python
>>> list(corrected.data_vars)
['signal', 'reference', 'fitted_reference', 'dff', 'reference_fit_coefficient']
```

Raw data is never overwritten, and the fit coefficients stay attached to the
result, so a reviewer can see what the correction actually did.

## Check the recording before you trust it

`assess_recording` runs outcome-blind quality control — it looks only at the
signals, never at your experimental conditions or your result.

```python
qc = assess_recording(recording)

print(f"{qc.estimated_rate_hz:.1f} Hz, {qc.samples} samples")
for channel in qc.channels:
    print(
        f"{channel.channel}: "
        f"signal-reference r = {channel.signal_reference_correlation:.3f}, "
        f"warnings = {channel.warnings or 'none'}"
    )
```

```text
100.0 Hz, 30000 samples
DMS: signal-reference r = 0.996, warnings = none
```

The fields worth reading first:

| Field | Why it matters |
|---|---|
| `estimated_rate_hz`, `sampling_interval_cv` | A high interval CV means an irregular clock. See [Irregular sampling](../irregular-sampling.md). |
| `large_gap_count`, `longest_valid_segment_s` | Dropouts break windowed analyses; they are reported, not silently bridged. |
| `signal_reference_correlation` | Very low correlation suggests the reference is not tracking a shared artefact. Very high correlation with a slope near 1 can mean the "reference" contains biological signal. |
| `flat_step_fraction`, `extreme_repeat_fraction` | Detector rails and stuck values. |
| `warnings` | Populated only when a channel trips a threshold. |

QC never deletes samples and never rewrites your data. It tells you what is
there so you can decide.

## Using your own data

`make_recording` is the direct route when you already have arrays in memory. If
your data is in a file, use the typed import boundary instead so that channel
roles, units, and event semantics are declared rather than inferred:

- [Import tabular data](../tabular-import.md) — CSV/TSV exports.
- [Import TDT data](../tdt-import.md) — TDT blocks.
- [Import native acquisition files](../native-acquisition-import.md) — Doric,
  Neurophotometrics, pyPhotometry.

## Next

[Your first peri-event plot](first-peri-event-plot.md) aligns this trace to event
times and draws the standard event-locked figure.
