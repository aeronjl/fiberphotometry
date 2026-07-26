import os
from pathlib import Path

import numpy as np
import pytest

from fiberphotometry import (
    TDTBlockSchema,
    TDTEpocEvents,
    TDTEpocValue,
    TDTStreamChannel,
    load_tdt_input,
)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("FIBERPHOTOMETRY_TDT_DEMO_BLOCK"),
    reason="set FIBERPHOTOMETRY_TDT_DEMO_BLOCK to the official FiPho demo block",
)
def test_official_tdt_fipho_block() -> None:
    block = Path(os.environ["FIBERPHOTOMETRY_TDT_DEMO_BLOCK"])
    schema = TDTBlockSchema(
        channels=(TDTStreamChannel("fiber", "4654", 1, "4054", 1),),
        events=TDTEpocEvents(
            "PtAB",
            "pulse_code",
            tuple(
                TDTEpocValue(value, str(int(value)))
                for value in (64959.0, 65023.0, 65535.0)
            ),
        ),
    )

    loaded = load_tdt_input(
        block,
        schema,
        subject="official-demo",
        session="FiPho-180416",
    )

    assert loaded.recording.sizes == {"time": 593_920, "channel": 1}
    assert loaded.recording.attrs["tdt_sdk_version"] == "0.7.3"
    assert loaded.recording.attrs["tdt_sampling_rate_hz"] == pytest.approx(
        1017.2526245117188
    )
    assert loaded.recording.signal.values[[0, -1], 0] == pytest.approx(
        [0.2702181339263916, 87.60558319091797]
    )
    assert loaded.recording.reference.values[[0, -1], 0] == pytest.approx(
        [0.9975791573524475, 11.528764724731445]
    )
    assert (
        loaded.recording.attrs["source_sha256"]
        == "7a66293d14318c91c6030f34e028df62bd47f0eb3cc7661d482ecbfbff6b072a"
    )
    assert len(loaded.event_times) == 30
    assert loaded.event_times[0] == pytest.approx(87.4921984)
    values, counts = np.unique(loaded.columns["tdt_epoc_value"], return_counts=True)
    assert values.tolist() == [64959.0, 65023.0, 65535.0]
    assert counts.tolist() == [10, 10, 10]
    assert loaded.columns["tdt_epoc_offset"][-1] == float("inf")
