import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from fiberphotometry import make_recording

pynwb = pytest.importorskip("pynwb")
ndx_fiber_photometry = pytest.importorskip("ndx_fiber_photometry")

from fiberphotometry.io.nwb import (  # noqa: E402
    NWBAcquisitionMetadata,
    NWBChannelMetadata,
    NWBDeviceMetadata,
    NWBIndicatorMetadata,
    add_recording_to_nwb,
    from_nwb_series,
    series_provenance,
)

DLIGHT = NWBIndicatorMetadata(
    name="dLight1_3b",
    label="dLight1.3b",
    description="Dopamine sensor expressed in dorsal striatum",
)
FIBER = NWBDeviceMetadata(name="fiber_0", description="400 um implanted fiber")
GREEN_LED = NWBDeviceMetadata(name="led_470", description="470 nm excitation LED")
ISOSBESTIC_LED = NWBDeviceMetadata(name="led_415", description="415 nm isosbestic LED")
DETECTOR = NWBDeviceMetadata(name="photodetector_0", description="Femtowatt receiver")


def _channel(location: str, excitation: float) -> NWBChannelMetadata:
    return NWBChannelMetadata(
        location=location,
        excitation_wavelength_nm=excitation,
        emission_wavelength_nm=525.0,
        indicator=DLIGHT,
        optical_fiber=FIBER,
        excitation_source=GREEN_LED if excitation > 450 else ISOSBESTIC_LED,
        photodetector=DETECTOR,
    )


def _recording():
    return make_recording(
        time=[0.0, 0.1, 0.2],
        signal=[[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]],
        reference=[[0.5, 0.6], [0.5, 0.6], [0.5, 0.6]],
        channel_names=["DMS", "DLS"],
        subject="mouse-1",
        session="session-1",
    )


def _nwbfile():
    return pynwb.NWBFile(
        session_description="round-trip fixture",
        identifier="fixture",
        session_start_time=datetime.now(UTC),
    )


def _write(nwbfile, path: Path) -> Path:
    with pynwb.NWBHDF5IO(path, "w") as io:
        io.write(nwbfile)
    return path


def test_core_nwb_roundtrip(tmp_path) -> None:
    recording = make_recording(
        time=[0.0, 0.1, 0.2],
        signal=[[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]],
        channel_names=["DMS", "DLS"],
        subject="mouse-1",
        session="session-1",
    )
    nwbfile = _nwbfile()
    add_recording_to_nwb(recording, nwbfile)
    path = tmp_path / "roundtrip.nwb"

    with pynwb.NWBHDF5IO(path, "w") as io:
        io.write(nwbfile)
    with pynwb.NWBHDF5IO(path, "r") as io:
        restored = from_nwb_series(io.read().acquisition["FiberPhotometrySignal"])

    assert restored.channel.values.tolist() == ["DMS", "DLS"]
    assert restored.attrs["subject"] == "mouse-1"
    assert np.array_equal(restored.signal.values, recording.signal.values)
    assert np.array_equal(restored.time.values, recording.time.values)

    with pynwb.NWBHDF5IO(path, "r") as io:
        bounded = from_nwb_series(
            io.read().acquisition["FiberPhotometrySignal"], max_samples=2
        )
    assert bounded.signal.shape == (2, 2)


def test_recordings_are_written_as_community_response_series(tmp_path) -> None:
    nwbfile = _nwbfile()
    series = add_recording_to_nwb(_recording(), nwbfile)

    assert isinstance(series, ndx_fiber_photometry.FiberPhotometryResponseSeries)
    assert series.fiber_photometry_table_region is None
    assert "no optical acquisition metadata was supplied" in series.description
    assert "fiberphotometry-core-nwb-v1" not in str(series.comments)

    path = _write(nwbfile, tmp_path / "bare.nwb")
    assert pynwb.validate(path=str(path)) == []


def test_declared_acquisition_metadata_builds_the_extension_objects(tmp_path) -> None:
    recording = _recording()
    nwbfile = _nwbfile()
    signal_metadata = NWBAcquisitionMetadata(
        channels=(_channel("DMS", 470.0), _channel("DLS", 470.0)),
        description="Dual-site dLight recording",
    )
    reference_metadata = NWBAcquisitionMetadata(
        channels=(_channel("DMS", 415.0), _channel("DLS", 415.0)),
        description="Dual-site dLight recording",
    )
    add_recording_to_nwb(
        recording,
        nwbfile,
        variable="signal",
        name="RawFiberPhotometrySignal",
        acquisition_metadata=signal_metadata,
    )
    add_recording_to_nwb(
        recording,
        nwbfile,
        variable="reference",
        name="RawFiberPhotometryReference",
        acquisition_metadata=reference_metadata,
    )

    path = _write(nwbfile, tmp_path / "extension.nwb")
    assert pynwb.validate(path=str(path)) == []

    with pynwb.NWBHDF5IO(path, "r") as io:
        read = io.read()
        metadata = read.lab_meta_data["fiber_photometry"]
        table = metadata.fiber_photometry_table
        assert isinstance(table, ndx_fiber_photometry.FiberPhotometryTable)
        assert len(table) == 4
        assert list(table["location"][:]) == ["DMS", "DLS", "DMS", "DLS"]
        assert list(table["excitation_wavelength_in_nm"][:]) == [
            470.0,
            470.0,
            415.0,
            415.0,
        ]
        assert list(table["emission_wavelength_in_nm"][:]) == [525.0] * 4
        indicators = metadata.fiber_photometry_indicators.indicators
        assert [item.label for item in indicators.values()] == ["dLight1.3b"]
        assert set(read.devices) == {"fiber_0", "led_470", "led_415", "photodetector_0"}

        signal = read.acquisition["RawFiberPhotometrySignal"]
        reference = read.acquisition["RawFiberPhotometryReference"]
        assert list(signal.fiber_photometry_table_region.data[:]) == [0, 1]
        assert list(reference.fiber_photometry_table_region.data[:]) == [2, 3]

        restored = from_nwb_series(signal)

    assert restored.channel.values.tolist() == ["DMS", "DLS"]
    rows = json.loads(restored.attrs["ndx_fiber_photometry_channels"])
    assert [row["location"] for row in rows] == ["DMS", "DLS"]
    assert {row["indicator"] for row in rows} == {"dLight1_3b"}
    assert {row["excitation_source"] for row in rows} == {"led_470"}
    assert {row["photodetector"] for row in rows} == {"photodetector_0"}


def test_repeated_writes_reuse_identical_table_rows(tmp_path) -> None:
    recording = _recording()
    nwbfile = _nwbfile()
    metadata = NWBAcquisitionMetadata(
        channels=(_channel("DMS", 470.0), _channel("DLS", 470.0))
    )
    add_recording_to_nwb(
        recording,
        nwbfile,
        name="RawFiberPhotometrySignal",
        acquisition_metadata=metadata,
    )
    module = nwbfile.create_processing_module("fiberphotometry", "derived signals")
    processed = add_recording_to_nwb(
        recording,
        nwbfile,
        name="ProcessedFiberPhotometrySignal",
        unit="dF/F",
        processing_module=module,
        acquisition_metadata=metadata,
    )

    table = nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table
    assert len(table) == 2
    assert list(processed.fiber_photometry_table_region.data[:]) == [0, 1]
    assert pynwb.validate(path=str(_write(nwbfile, tmp_path / "reused.nwb"))) == []


def test_prebuilt_ndx_ophys_devices_objects_are_written_unchanged(tmp_path) -> None:
    ndx_ophys_devices = pytest.importorskip("ndx_ophys_devices")
    fiber_model = ndx_ophys_devices.OpticalFiberModel(
        name="MFC_400_model",
        manufacturer="Doric",
        numerical_aperture=0.48,
        core_diameter_in_um=400.0,
    )
    fiber = ndx_ophys_devices.OpticalFiber(
        name="fiber_0",
        model=fiber_model,
        fiber_insertion=ndx_ophys_devices.FiberInsertion(
            insertion_position_ap_in_mm=0.8,
            insertion_position_ml_in_mm=1.5,
            insertion_position_dv_in_mm=-4.2,
        ),
    )
    nwbfile = _nwbfile()
    nwbfile.add_device_model(fiber_model)
    channel = NWBChannelMetadata(
        location="DMS",
        excitation_wavelength_nm=470.0,
        emission_wavelength_nm=525.0,
        indicator=DLIGHT,
        optical_fiber=fiber,
        excitation_source=GREEN_LED,
        photodetector=DETECTOR,
        coordinates_mm=(0.8, 1.5, -4.2),
        notes="Single-fiber pilot recording",
    )
    recording = make_recording(
        time=[0.0, 0.1, 0.2],
        signal=[[1.0], [1.5], [2.0]],
        channel_names=["DMS"],
        subject="mouse-2",
        session="session-2",
    )
    add_recording_to_nwb(
        recording,
        nwbfile,
        acquisition_metadata=NWBAcquisitionMetadata(channels=(channel,)),
    )

    path = _write(nwbfile, tmp_path / "prebuilt.nwb")
    assert pynwb.validate(path=str(path)) == []

    with pynwb.NWBHDF5IO(path, "r") as io:
        read = io.read()
        table = read.lab_meta_data["fiber_photometry"].fiber_photometry_table
        assert table["optical_fiber"][0].model.numerical_aperture == pytest.approx(0.48)
        assert np.allclose(table["coordinates"][0], [0.8, 1.5, -4.2])
        assert table["notes"][0] == "Single-fiber pilot recording"


def test_acquisition_metadata_must_describe_every_channel() -> None:
    nwbfile = _nwbfile()
    metadata = NWBAcquisitionMetadata(channels=(_channel("DMS", 470.0),))

    with pytest.raises(ValueError, match="every recording channel"):
        add_recording_to_nwb(_recording(), nwbfile, acquisition_metadata=metadata)


def test_channel_metadata_rejects_invented_wavelengths() -> None:
    with pytest.raises(ValueError, match="positive finite wavelength"):
        _channel("DMS", 0.0)
    with pytest.raises(ValueError, match="at least one channel"):
        NWBAcquisitionMetadata(channels=())
    with pytest.raises(ValueError, match="coordinates_mm for every channel"):
        NWBAcquisitionMetadata(
            channels=(
                _channel("DMS", 470.0),
                NWBChannelMetadata(
                    location="DLS",
                    excitation_wavelength_nm=470.0,
                    emission_wavelength_nm=525.0,
                    indicator=DLIGHT,
                    optical_fiber=FIBER,
                    excitation_source=GREEN_LED,
                    photodetector=DETECTOR,
                    coordinates_mm=(0.5, 2.5, -2.0),
                ),
            )
        )


def test_recording_provenance_is_stored_in_a_structured_scratch_table(
    tmp_path,
) -> None:
    recording = _recording()
    recording.attrs["source_sha256"] = "abc123"
    recording.attrs["processing_stage"] = "baseline_corrected"
    nwbfile = _nwbfile()
    add_recording_to_nwb(recording, nwbfile, name="RawFiberPhotometrySignal")

    path = _write(nwbfile, tmp_path / "provenance.nwb")
    with pynwb.NWBHDF5IO(path, "r") as io:
        read = io.read()
        stored = series_provenance(read, "RawFiberPhotometrySignal")
        restored = from_nwb_series(read.acquisition["RawFiberPhotometrySignal"])

    assert stored["source_sha256"] == "abc123"
    assert stored["source_variable"] == "signal"
    assert stored["subject"] == "mouse-1"
    assert restored.attrs["source_sha256"] == "abc123"
    assert restored.attrs["processing_stage"] == "baseline_corrected"
    assert restored.attrs["session"] == "session-1"


def test_legacy_json_comment_files_still_load(tmp_path) -> None:
    metadata = {
        "schema": "fiberphotometry-core-nwb-v1",
        "channels": ["DMS", "DLS"],
        "subject": "mouse-legacy",
        "session": "session-legacy",
        "source_variable": "signal",
        "recording_attrs": {"processing_stage": "raw"},
    }
    nwbfile = _nwbfile()
    nwbfile.add_acquisition(
        pynwb.TimeSeries(
            name="FiberPhotometrySignal",
            data=np.asarray([[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]]),
            timestamps=np.asarray([0.0, 0.1, 0.2]),
            unit="a.u.",
            description="Fiber photometry signal exported by fiberphotometry",
            comments=json.dumps(metadata, sort_keys=True),
        )
    )

    path = _write(nwbfile, tmp_path / "legacy.nwb")
    with pynwb.NWBHDF5IO(path, "r") as io:
        restored = from_nwb_series(io.read().acquisition["FiberPhotometrySignal"])

    assert restored.channel.values.tolist() == ["DMS", "DLS"]
    assert restored.attrs["subject"] == "mouse-legacy"
    assert restored.attrs["session"] == "session-legacy"
    assert restored.attrs["nwb_neurodata_type"] == "TimeSeries"


def test_written_files_pass_the_nwb_inspector(tmp_path) -> None:
    nwbinspector = pytest.importorskip("nwbinspector")
    nwbfile = _nwbfile()
    nwbfile.subject = pynwb.file.Subject(
        subject_id="mouse-1",
        species="Mus musculus",
        sex="M",
        age="P90D",
    )
    metadata = NWBAcquisitionMetadata(
        channels=(_channel("DMS", 470.0), _channel("DLS", 470.0))
    )
    add_recording_to_nwb(
        _recording(),
        nwbfile,
        name="RawFiberPhotometrySignal",
        acquisition_metadata=metadata,
    )
    path = _write(nwbfile, tmp_path / "inspected.nwb")

    messages = list(nwbinspector.inspect_nwbfile(nwbfile_path=str(path)))
    blocking = [
        message
        for message in messages
        if message.importance.name in {"CRITICAL", "PYNWB_VALIDATION", "ERROR"}
    ]

    assert blocking == [], [message.message for message in blocking]
