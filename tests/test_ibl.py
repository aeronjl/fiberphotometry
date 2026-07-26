import numpy as np
import pandas as pd

from fiberphotometry.io.ibl import from_ibl_tables


def test_ibl_adapter_demultiplexes_interpolates_and_retains_mask() -> None:
    table = pd.DataFrame(
        {
            "times": [0.0, 0.05, 0.1, 0.15, 0.2, 0.25],
            "wavelength": [470, 415, 470, 415, 470, 415],
            "Region0G": [10.0, 1.0, 11.0, 2.0, 12.0, 3.0],
            "include": [True, True, False, True, True, True],
        }
    )

    recording = from_ibl_tables(
        signal_table=table,
        roi_locations={"Region0G": "DMS"},
        subject="mouse",
        session="session",
    )

    assert recording.channel.item() == "DMS"
    assert np.isnan(recording.signal.values[1, 0])
    assert np.allclose(recording.reference.values[[1, 2], 0], [1.5, 2.5])
    assert recording.included.values.tolist() == [True, False, True]


def test_ibl_adapter_signal_only_ignores_no_led_rows() -> None:
    table = pd.DataFrame(
        {
            "times": [0.0, 0.02, 0.04, 0.06, 0.08, 0.10],
            "wavelength": [470, 0, 470, 0, 470, 0],
            "Region0G": [10.0, 999.0, 11.0, 998.0, 12.0, 997.0],
            "include": [True, True, False, True, True, True],
        }
    )

    recording = from_ibl_tables(
        signal_table=table,
        roi_locations={"Region0G": "DMS"},
        subject="mouse",
        session="session",
        reference_wavelength=None,
    )

    assert recording.time.values.tolist() == [0.0, 0.04, 0.08]
    assert recording.signal.values[:, 0].tolist()[:1] == [10.0]
    assert np.isnan(recording.signal.values[1, 0])
    assert recording.signal.values[2, 0] == 12.0
    assert "reference" not in recording
    assert recording.attrs["reference_wavelength_nm"] == "none"
