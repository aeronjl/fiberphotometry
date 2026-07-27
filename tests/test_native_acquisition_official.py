import os
from pathlib import Path

import pytest

from fiberphotometry import (
    DoricChannel,
    DoricSchema,
    DoricSeries,
    PyPhotometryChannel,
    PyPhotometrySchema,
    load_doric_input,
    load_pyphotometry_input,
)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("FIBERPHOTOMETRY_DORIC_DEMO_FILE"),
    reason="set FIBERPHOTOMETRY_DORIC_DEMO_FILE to Doric's Console_Acq_0000.doric",
)
def test_official_doric_console_file() -> None:
    source = Path(os.environ["FIBERPHOTOMETRY_DORIC_DEMO_FILE"])
    base = "DataAcquisition/FPConsole/Signals/Series0003/AnalogIn"
    loaded = load_doric_input(
        source,
        DoricSchema(
            (
                DoricChannel(
                    "AIN01",
                    DoricSeries(f"{base}/AIN01", f"{base}/Time"),
                ),
            )
        ),
        subject="vendor-demo",
        session="Console_Acq_0000",
    )

    assert loaded.recording.sizes == {"time": 60_244, "channel": 1}
    assert loaded.recording.time.values[[0, -1]] == pytest.approx([12, 17.000169])
    assert loaded.recording.signal.values[[0, -1], 0] == pytest.approx(
        [-0.09735405, 0.10788293]
    )
    assert (
        loaded.recording.attrs["source_sha256"]
        == "68d76e7e16d59acafe4fe9ff0edea60625596a1af35375dccb9f35ccc637f404"
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("FIBERPHOTOMETRY_PPD_DEMO_FILE"),
    reason="set FIBERPHOTOMETRY_PPD_DEMO_FILE to manuscript board-1/1.0V.ppd",
)
def test_official_legacy_pyphotometry_file() -> None:
    source = Path(os.environ["FIBERPHOTOMETRY_PPD_DEMO_FILE"])
    loaded = load_pyphotometry_input(
        source,
        PyPhotometrySchema((PyPhotometryChannel("analog_1", 1),)),
        subject="board-1",
        session="1.0V",
    )

    assert loaded.recording.sizes == {
        "time": 11_800,
        "channel": 1,
        "digital_input": 2,
    }
    assert loaded.recording.signal.values[[0, -1], 0] == pytest.approx(
        [0.991571044921875, 0.9920745849609375]
    )
    assert loaded.recording.attrs["pyphotometry_version"] == "0.1"
    assert (
        loaded.recording.attrs["source_sha256"]
        == "58d3e264ccbc8a9b8ac8236683385655d7b46ca51aed428b427b2a0d6f2361a4"
    )
