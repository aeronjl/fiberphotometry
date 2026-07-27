# Native acquisition import v0.1

FiberPhotometry reads Doric, Neurophotometrics, and pyPhotometry acquisition
outputs into the same labelled recording boundary used by TDT, NWB, and tabular
projects. Install file-format dependencies with:

```bash
pip install "fiberphotometry[acquisition]"
```

The importer discovers structure, not biological meaning. Inspect a file first,
then explicitly map detector/ROI inputs to anatomical channels and signal or
reference roles. Every loaded recording retains the mapping and a SHA-256 hash
of the complete source file.

## Identify a source

```python
from fiberphotometry import detect_acquisition_format

detect_acquisition_format("session.doric")  # "doric"
detect_acquisition_format("subject.ppd")  # "pyphotometry"
detect_acquisition_format("photometryData.csv")  # "neurophotometrics"
```

Detection is deliberately conservative. An ordinary CSV remains `tabular`, and
an ambiguous parquet file remains `unknown` until the caller chooses an adapter.

## Doric `.doric`

Doric Neuroscience Studio v6 stores acquisition data in HDF5. Dataset paths
vary with the hardware and acquisition mode, so inspect the real tree and map
the selected series:

```python
from fiberphotometry import (
    DoricChannel,
    DoricSchema,
    DoricSeries,
    inspect_doric,
    load_doric_input,
)

inspection = inspect_doric("Console_Acq_0000.doric")
for field in inspection.fields:
    print(field.key, field.sample_count, field.units)

base = "DataAcquisition/FPConsole/Signals/Series0003/AnalogIn"
loaded = load_doric_input(
    "Console_Acq_0000.doric",
    DoricSchema(
        channels=(
            DoricChannel(
                "NAc",
                signal=DoricSeries(f"{base}/AIN01", f"{base}/Time"),
            ),
        )
    ),
    subject="mouse-01",
    session="2026-07-27",
)
```

Lock-in outputs commonly use paths ending in
`AIN#xAOUT#-LockIn/Values` with a sibling `Time` dataset. The importer does not
assume that an AOUT wavelength is a biological reference. Reference series may
have their own timestamps; they are interpolated onto signal timestamps and
remain `NaN` outside observed support. Different signal-channel clocks are
rejected rather than silently resampled.

Threshold crossings in a declared `DoricDigitalEvents` series can be retained
as rising, falling, or both event edges.

## Neurophotometrics

Neurophotometrics exports contain ROI columns sampled on alternating LED rows.
The adapter supports the established column layouts:

- `Timestamp` plus `Flags`;
- `Timestamp` plus `LedState`;
- `SystemTimestamp` plus `LedState`, including IBL-style parquet exports.

```python
from fiberphotometry import (
    NeurophotometricsChannel,
    NeurophotometricsSchema,
    load_neurophotometrics_input,
)

loaded = load_neurophotometrics_input(
    "photometryData.csv",
    NeurophotometricsSchema(
        channels=(
            NeurophotometricsChannel(
                "DMS",
                roi_column="Region0G",
                signal_wavelength=470,
                reference_wavelength=415,
            ),
        )
    ),
    subject="mouse-01",
    session="2026-07-27",
)
```

The 415, 470, and 560 nm excitation bits are decoded from `Flags`/`LedState`.
Rows with simultaneous excitation LEDs are not assigned to a single wavelength.
Reference samples are interpolated to the signal-frame clock. Higher acquisition
flag bits can be exposed as typed transitions with
`NeurophotometricsDigitalEvents`; excitation bits cannot be reused as event
masks.

## pyPhotometry `.ppd`

`.ppd` is a packed binary format containing its acquisition JSON header,
analog inputs, and digital states. Biological channel identity is not stored
authoritatively, so the analog mapping is explicit:

```python
from fiberphotometry import (
    PyPhotometryChannel,
    PyPhotometryDigitalEvents,
    PyPhotometrySchema,
    load_pyphotometry_input,
)

loaded = load_pyphotometry_input(
    "subject.ppd",
    PyPhotometrySchema(
        channels=(PyPhotometryChannel("NAc", signal_analog=1, reference_analog=2),),
        digital_events=(PyPhotometryDigitalEvents(1, "cue"),),
    ),
    subject="mouse-01",
    session="2026-07-27",
)
```

Import is raw: it does not apply the filtering options used by pyPhotometry's
analysis helper. For current v1.1 pulsed files, the adapter preserves raw LED-on
and LED-off baseline arrays, their baseline-subtracted values, and clipping
masks. It also supports the legacy v0.x/v1.0 layout and retains raw digital state
plus declared rising-edge events.

## Validation scope

- Doric: checksum-pinned parity against Doric's published
  `Console_Acq_0000.doric`, plus synthetic lock-in, reference-clock, and TTL
  coverage.
- pyPhotometry: checksum-pinned parity against the real legacy `1.0V.ppd` in
  the official manuscript archive, plus a byte-level v1.1 pulsed fixture.
- Neurophotometrics: versioned `Flags`, `LedState`, ROI, alternating-clock, and
  event-bit fixtures aligned with the current IBL reader contract.

These checks establish format semantics, not the biological identity of an
arbitrary detector, ROI, wavelength, or digital line.

## Primary format references

- [Doric's official readDoric examples](https://github.com/doriclenses/readDoric)
- [Doric Neuroscience Studio v6 format statement](https://neuro.doriclenses.com/products/doric-neuroscience-studio)
- [pyPhotometry importing-data guide](https://pyphotometry.readthedocs.io/en/latest/user-guide/importing-data/)
- [pyPhotometry current import implementation](https://github.com/pyPhotometry/code/blob/master/tools/data_import.py)
- [IBL Neurophotometrics reader](https://github.com/int-brain-lab/ibl-photometry/blob/main/src/iblphotometry/neurophotometrics.py)
