# NWB data model

fipha reads and writes the community NWB data model for fiber
photometry: [`ndx-fiber-photometry`](https://github.com/catalystneuro/ndx-fiber-photometry)
from CatalystNeuro, which is registered in the NWB Extensions Catalog, layered on
[`ndx-ophys-devices`](https://github.com/catalystneuro/ndx-ophys-devices), and
which deprecates the older `ndx-photometry`. The package does not define a private
photometry schema and does not encode structured metadata into any free-text field.

Install the optional dependencies with `pip install 'fipha[nwb]'`.

## What is written

Every recording written by `add_recording_to_nwb()`, by the CLI, and by
`export_project_nwb()` becomes an `ndx_fiber_photometry.FiberPhotometryResponseSeries`.
The extension type is emitted whether or not optical hardware metadata is
available, so files are discoverable by NWB Inspector, DANDI and NeuroConv.

When acquisition metadata is supplied, the writer additionally builds:

| Emitted object | Source |
|---|---|
| `FiberPhotometry` (`LabMetaData`, named `fiber_photometry`) | created once per file |
| `FiberPhotometryTable` (named `fiber_photometry_table`) | one row per declared channel |
| `FiberPhotometryIndicators` with `ndx_ophys_devices.Indicator` objects | `NWBIndicatorMetadata` |
| `OpticalFiber`, `ExcitationSource`, `Photodetector` devices | `NWBDeviceMetadata` |
| `DynamicTableRegion` named `fiber_photometry_table_region` on each series | the channels of the written variable |

Table rows are deduplicated by content, so a signal series and its processed
derivative reference the same rows, while a 470 nm signal and a 415 nm isosbestic
reference reference different rows of the same table.

## What the extension requires, and who supplies it

`FiberPhotometryTable` marks these columns required: `location`,
`excitation_wavelength_in_nm`, `emission_wavelength_in_nm`, `indicator`,
`optical_fiber`, `excitation_source` and `photodetector`. A CSV, `.ppd`, `.doric`
or TDT import carries none of them.

**The package supplies no default for any of these.** Excitation wavelength,
emission wavelength and indicator identity are experimental facts; a defaulted
470 nm or a defaulted `GCaMP6f` would be a fabricated measurement in a file whose
purpose is provenance. Instead the metadata is a **required argument at write
time**: pass `NWBAcquisitionMetadata` and the extension objects are built; omit it
and the response series is written with no `fiber_photometry_table_region` at all.
Both outcomes pass `pynwb.validate()`, because the extension marks the region
optional.

So, compared with earlier releases, a user who wants a fully described photometry
file must now supply, per channel: brain location, excitation wavelength in
nanometres, emission wavelength in nanometres, an indicator name and label, and a
name for the optical fiber, excitation source and photodetector. A user who
supplies nothing gets the same signals, timestamps, channel labels and provenance
as before, in the community neurodata type, with no acquisition table.

## Declaring acquisition metadata

```python
from datetime import datetime, timezone

import numpy as np
from pynwb import NWBFile

from fipha import (
    NWBAcquisitionMetadata,
    NWBChannelMetadata,
    NWBDeviceMetadata,
    NWBIndicatorMetadata,
    add_recording_to_nwb,
    make_recording,
)

recording = make_recording(
    time=np.arange(600) / 20.0,
    signal=np.random.default_rng(0).normal(size=(600, 2)),
    channel_names=["DMS", "DLS"],
    subject="mouse-01",
    session="day-04",
)

dlight = NWBIndicatorMetadata(name="dLight1_3b", label="dLight1.3b")
fiber = NWBDeviceMetadata(name="fiber_0", description="400 um implanted fiber")
led = NWBDeviceMetadata(name="led_470", description="470 nm excitation LED")
detector = NWBDeviceMetadata(name="photodetector_0", description="Femtowatt receiver")

channels = tuple(
    NWBChannelMetadata(
        location=location,
        excitation_wavelength_nm=470.0,
        emission_wavelength_nm=525.0,
        indicator=dlight,
        optical_fiber=fiber,
        excitation_source=led,
        photodetector=detector,
    )
    for location in ("DMS", "DLS")
)

nwbfile = NWBFile(
    session_description="Cue-evoked dopamine release",
    identifier="mouse-01-day-04",
    session_start_time=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
    session_id="day-04",
)
add_recording_to_nwb(
    recording,
    nwbfile,
    name="RawFiberPhotometrySignal",
    acquisition_metadata=NWBAcquisitionMetadata(channels=channels),
)
```

`NWBChannelMetadata` also accepts `coordinates_mm` and `notes`, which populate the
extension's optional columns. `coordinates_mm` is all-or-none across a file,
because a partly-populated coordinate column would imply a measurement that was
never made.

`ndx-ophys-devices` has moved manufacturer and model number onto `DeviceModel`
objects, which require further facts this package cannot invent (numerical
aperture, detector type, excitation mode). `NWBDeviceMetadata` therefore carries
only a name and description. When those values *are* known, pass a fully populated
`ndx_ophys_devices` container — `OpticalFiber`, `ExcitationSource`, `Photodetector`
or `Indicator` — directly in place of the dataclass:

```python
from ndx_ophys_devices import FiberInsertion, OpticalFiber, OpticalFiberModel

model = OpticalFiberModel(
    name="MFC_400_model",
    manufacturer="Doric",
    numerical_aperture=0.48,
    core_diameter_in_um=400.0,
)
nwbfile.add_device_model(model)
fiber = OpticalFiber(
    name="fiber_0",
    model=model,
    fiber_insertion=FiberInsertion(
        insertion_position_ap_in_mm=0.8,
        insertion_position_ml_in_mm=1.5,
        insertion_position_dv_in_mm=-4.2,
    ),
)
```

## Package metadata the extension has no slot for

Channel labels and preprocessing provenance are written to two scratch
`DynamicTable` objects rather than into `comments`:

| Scratch table | Columns | Contents |
|---|---|---|
| `fipha_series_channels` | `series_name`, `channel_index`, `channel_name` | package channel labels, which are not the same thing as `location` when two wavelengths share one fiber |
| `fipha_series_attributes` | `series_name`, `key`, `value` | recording attributes, including source hashes, `processing_stage`, the operation ledger and `source_variable` |

`fipha.io.nwb.series_provenance(nwbfile, series_name)` returns the second
table as a dictionary. Subject and session are read from `NWBFile.subject` and
`NWBFile.session_id` first, and only then from these tables.

## Reading

`from_nwb_series()` accepts an `ndx-fiber-photometry` response series or a core
`TimeSeries`. Channel labels are resolved in this order: the
`fipha_series_channels` scratch table, the `location` column of the linked
`FiberPhotometryTable`, then positional defaults. When a table region is present,
the full row contents are retained on the returned dataset as
`attrs["ndx_fiber_photometry_channels"]`.

`fipha.io.dandi.validate_remote_nwb_asset()` discovers response series by
`isinstance` against the imported extension class, not by class name.

## Validation

Exported files are checked against the ecosystem's own validators, not only
against this package's reader:

- `pynwb.validate()` returns no errors for files written with and without
  acquisition metadata; `export_project_nwb()` validates every file before
  publishing it and deletes any file that fails;
- an NWB Inspector test runs when `nwbinspector` is installed and asserts that no
  message of critical, error or validation importance is raised.
