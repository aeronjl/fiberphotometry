import numpy as np
import pytest

from fiberphotometry import make_recording


def test_make_recording_preserves_identity_and_shape() -> None:
    recording = make_recording(
        time=[0, 1, 2],
        signal=[1, 2, 3],
        subject="mouse-1",
        session="day-1",
    )

    assert recording.signal.shape == (3, 1)
    assert recording.attrs["subject"] == "mouse-1"


def test_make_recording_rejects_nonmonotonic_time() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        make_recording(time=[0, 2, 1], signal=np.ones(3), subject="m", session="s")
