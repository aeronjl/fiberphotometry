import numpy as np

from fiberphotometry import align_events, make_recording


def test_align_events_retains_events_and_metadata() -> None:
    time = np.arange(0, 10.1, 0.1)
    recording = make_recording(
        time=time,
        signal=time,
        subject="mouse-1",
        session="session-1",
    )

    aligned = align_events(
        recording,
        [2, 8],
        window=(-1, 1),
        rate=10,
        variable="signal",
        event_ids=["a", "b"],
    )

    assert aligned.dims == ("event", "relative_time", "channel")
    assert aligned.sizes["event"] == 2
    assert np.isclose(aligned.sel(event="a", relative_time=0).item(), 2)
    assert aligned.attrs["subject"] == "mouse-1"
