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
