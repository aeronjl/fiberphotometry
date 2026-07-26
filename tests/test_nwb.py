from datetime import UTC, datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from fiberphotometry import make_recording

pynwb = pytest.importorskip("pynwb")

from fiberphotometry.io.nwb import add_recording_to_nwb, from_nwb_series  # noqa: E402


def test_core_nwb_roundtrip(tmp_path) -> None:
    recording = make_recording(
        time=[0.0, 0.1, 0.2],
        signal=[[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]],
        channel_names=["DMS", "DLS"],
        subject="mouse-1",
        session="session-1",
    )
    nwbfile = pynwb.NWBFile(
        session_description="round-trip fixture",
        identifier="fixture",
        session_start_time=datetime.now(UTC),
    )
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


def test_extension_shaped_series_retains_channel_metadata() -> None:
    table = pd.DataFrame(
        {
            "location": ["DMS"],
            "excitation_wavelength_in_nm": [470.0],
            "emission_wavelength_in_nm": [525.0],
            "indicator": [SimpleNamespace(name="dLight1.3b")],
            "optical_fiber": [SimpleNamespace(name="fiber-0")],
        }
    )

    class RegionTable:
        def __getitem__(self, rows: np.ndarray) -> pd.DataFrame:
            return table.iloc[rows]

    region = SimpleNamespace(table=RegionTable(), data=np.asarray([0]))
    series = SimpleNamespace(
        name="FiberPhotometryResponseSeriesGreen",
        data=np.asarray([[1.0], [2.0], [3.0]]),
        timestamps=None,
        rate=20.0,
        starting_time=1.0,
        comments="",
        fiber_photometry_table_region=region,
    )

    restored = from_nwb_series(series, subject="mouse", session="session")

    assert restored.channel.item() == "DMS"
    assert "dLight1.3b" in restored.attrs["ndx_fiber_photometry_channels"]
    assert np.allclose(restored.time.values, [1.0, 1.05, 1.1])
