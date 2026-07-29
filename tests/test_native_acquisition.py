import json

import numpy as np
import pytest

from fipha import (
    DoricChannel,
    DoricDigitalEvents,
    DoricSchema,
    DoricSeries,
    NeurophotometricsChannel,
    NeurophotometricsDigitalEvents,
    NeurophotometricsSchema,
    PyPhotometryChannel,
    PyPhotometryDigitalEvents,
    PyPhotometrySchema,
    detect_acquisition_format,
    inspect_doric,
    inspect_neurophotometrics,
    inspect_pyphotometry,
    load_doric_input,
    load_neurophotometrics_input,
    load_pyphotometry_input,
)


def _write_ppd(path, *, version="1.1") -> None:
    header = {
        "subject_ID": "mouse-01",
        "date_time": "2026-01-01T12:00:00",
        "mode": "2 colour pulsed",
        "sampling_rate": 10,
        "volts_per_division": [0.001, 0.001],
        "version": version,
        "n_analog_signals": 2,
        "n_digital_signals": 2,
        "ADC_max_value": 32767,
    }
    encoded = json.dumps(header).encode()
    words = []
    digital_1 = [0, 0, 1, 1, 0]
    digital_2 = [0, 0, 0, 1, 1]
    for index in range(5):
        words.extend(
            [
                ((1000 + index) << 1) | digital_1[index],
                900 << 1,
                ((2000 + index) << 1) | digital_2[index],
                1800 << 1,
            ]
        )
    path.write_bytes(
        len(encoded).to_bytes(2, "little")
        + encoded
        + np.asarray(words, dtype="<u2").tobytes()
    )


def test_pyphotometry_ppd_preserves_raw_baselines_clipping_and_digital_events(
    tmp_path,
) -> None:
    source = tmp_path / "mouse.ppd"
    _write_ppd(source)
    schema = PyPhotometrySchema(
        channels=(PyPhotometryChannel("NAc", 1, 2),),
        digital_events=(
            PyPhotometryDigitalEvents(1, "cue"),
            PyPhotometryDigitalEvents(2, "reward"),
        ),
    )

    loaded = load_pyphotometry_input(
        source, schema, subject="mouse-01", session="session-01"
    )

    assert loaded.recording.signal[:, 0].values == pytest.approx(
        [0.1, 0.101, 0.102, 0.103, 0.104]
    )
    assert loaded.recording.reference[:, 0].values == pytest.approx(
        [0.2, 0.201, 0.202, 0.203, 0.204]
    )
    assert loaded.recording.signal_raw_led_on[:, 0].values[0] == pytest.approx(1)
    assert loaded.recording.signal_raw_baseline[:, 0].values[0] == pytest.approx(0.9)
    assert loaded.recording.digital_state.values[:, 0].tolist() == [0, 0, 1, 1, 0]
    assert loaded.event_times == pytest.approx((0.2, 0.3))
    assert loaded.columns["event"] == ("cue", "reward")
    assert loaded.recording.attrs["source_format"] == "pyPhotometry_ppd"
    inspection = inspect_pyphotometry(source)
    assert [field.key for field in inspection.fields] == [
        "analog_1",
        "analog_2",
        "digital_1",
        "digital_2",
    ]


def test_neurophotometrics_alternating_rows_and_flags_are_native(tmp_path) -> None:
    source = tmp_path / "photometryData.csv"
    source.write_text(
        "FrameCounter,Timestamp,Flags,Region0G,Region1G\n"
        "0,0.0,1,10,20\n"
        "1,0.0,2,100,200\n"
        "2,0.5,9,11,21\n"
        "3,0.5,10,101,201\n"
        "4,1.0,9,12,22\n"
        "5,1.0,10,102,202\n"
        "6,1.5,1,13,23\n"
        "7,1.5,2,103,203\n"
    )
    schema = NeurophotometricsSchema(
        channels=(
            NeurophotometricsChannel("DMS", "Region0G"),
            NeurophotometricsChannel("NAc", "Region1G"),
        ),
        digital_events=(NeurophotometricsDigitalEvents("output_1", 8, "both"),),
    )

    loaded = load_neurophotometrics_input(
        source, schema, subject="mouse", session="session"
    )

    assert loaded.recording.time.values.tolist() == [0, 0.5, 1, 1.5]
    assert loaded.recording.signal.values[:, 0].tolist() == [100, 101, 102, 103]
    assert loaded.recording.reference.values[:, 1].tolist() == [20, 21, 22, 23]
    assert loaded.event_times == (0.5, 1.5)
    assert loaded.columns["edge"] == ("rising", "falling")
    assert loaded.recording.attrs["led_state_column"] == "Flags"
    inspection = inspect_neurophotometrics(source)
    assert dict(inspection.metadata)["detected_layout"] == "version_1"
    assert detect_acquisition_format(source) == "neurophotometrics"


def test_neurophotometrics_rejects_implicit_unknown_wavelength(tmp_path) -> None:
    source = tmp_path / "recording.csv"
    source.write_text(
        "FrameCounter,Timestamp,LedState,Region0G\n0,0,1,1\n1,0,2,2\n2,1,1,3\n3,1,2,4\n"
    )
    schema = NeurophotometricsSchema(
        channels=(NeurophotometricsChannel("NAc", "Region0G", 465, 405),)
    )
    with pytest.raises(ValueError, match="415, 470, or 560"):
        load_neurophotometrics_input(source, schema, subject="mouse", session="session")


def test_doric_hdf5_inventory_mapping_interpolation_and_ttl(tmp_path) -> None:
    h5py = pytest.importorskip("h5py")
    source = tmp_path / "Console_Acq_0000.doric"
    with h5py.File(source, "w") as file:
        root = file.create_group("DataAcquisition/FPConsole/Signals/Series0001")
        signal = root.create_group("AIN01xAOUT01-LockIn")
        signal.create_dataset("Time", data=[0.0, 0.5, 1.0, 1.5])
        signal.create_dataset("Values", data=[10.0, 11.0, 12.0, 13.0])
        reference = root.create_group("AIN01xAOUT02-LockIn")
        reference.create_dataset("Time", data=[0.0, 0.75, 1.5])
        reference.create_dataset("Values", data=[1.0, 1.75, 2.5])
        digital = root.create_group("DigitalIO/DIO01")
        digital.create_dataset("Time", data=[0.0, 0.5, 1.0, 1.5])
        digital.create_dataset("Values", data=[0.0, 1.0, 1.0, 0.0])
    base = "DataAcquisition/FPConsole/Signals/Series0001"
    schema = DoricSchema(
        channels=(
            DoricChannel(
                "NAc",
                DoricSeries(
                    f"{base}/AIN01xAOUT01-LockIn/Values",
                    f"{base}/AIN01xAOUT01-LockIn/Time",
                ),
                DoricSeries(
                    f"{base}/AIN01xAOUT02-LockIn/Values",
                    f"{base}/AIN01xAOUT02-LockIn/Time",
                ),
            ),
        ),
        digital_events=(
            DoricDigitalEvents(
                "cue",
                DoricSeries(
                    f"{base}/DigitalIO/DIO01/Values",
                    f"{base}/DigitalIO/DIO01/Time",
                ),
                edge="both",
            ),
        ),
    )

    loaded = load_doric_input(source, schema, subject="mouse", session="session")

    assert loaded.recording.signal[:, 0].values.tolist() == [10, 11, 12, 13]
    assert loaded.recording.reference[:, 0].values == pytest.approx([1, 1.5, 2, 2.5])
    assert loaded.event_times == (0.5, 1.5)
    assert loaded.columns["edge"] == ("rising", "falling")
    inspection = inspect_doric(source)
    assert any(field.key.endswith("LockIn/Values") for field in inspection.fields)
    assert detect_acquisition_format(source) == "doric"


def test_generic_csv_remains_tabular(tmp_path) -> None:
    source = tmp_path / "ordinary.csv"
    source.write_text("time,signal,reference\n0,1,1\n1,2,1\n")
    assert detect_acquisition_format(source) == "tabular"
