import io
import json
import os
from datetime import UTC, datetime

import pytest

from fiberphotometry.io import dandi
from fiberphotometry.io.nwb import from_nwb_series


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def test_resolve_dandi_download_url_prefers_public_s3(monkeypatch) -> None:
    payload = {
        "contentUrl": [
            "https://api.dandiarchive.org/api/assets/id/download/",
            "https://dandiarchive.s3.amazonaws.com/blobs/example",
        ]
    }
    monkeypatch.setattr(
        dandi,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(json.dumps(payload).encode()),
    )

    url = dandi.resolve_dandi_download_url("asset-id")

    assert url == "https://dandiarchive.s3.amazonaws.com/blobs/example"


def test_response_series_discovery_covers_acquisition_and_processing(tmp_path) -> None:
    pynwb = pytest.importorskip("pynwb")
    ndx_fiber_photometry = pytest.importorskip("ndx_fiber_photometry")
    from fiberphotometry import make_recording
    from fiberphotometry.io.nwb import add_recording_to_nwb

    recording = make_recording(
        time=[0.0, 0.1, 0.2],
        signal=[[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]],
        channel_names=["DMS", "DLS"],
        subject="mouse-1",
        session="session-1",
    )
    nwbfile = pynwb.NWBFile(
        session_description="discovery fixture",
        identifier="discovery",
        session_start_time=datetime.now(UTC),
    )
    add_recording_to_nwb(recording, nwbfile, name="RawFiberPhotometrySignal")
    nwbfile.add_acquisition(
        pynwb.TimeSeries(
            name="UnrelatedSeries",
            data=[0.0, 1.0, 2.0],
            timestamps=[0.0, 0.1, 0.2],
            unit="V",
            description="a core TimeSeries that is not photometry",
        )
    )
    module = nwbfile.create_processing_module("fiberphotometry", "derived signals")
    add_recording_to_nwb(
        recording,
        nwbfile,
        name="ProcessedFiberPhotometrySignal",
        unit="dF/F",
        processing_module=module,
    )
    module.add(
        pynwb.TimeSeries(
            name="UnrelatedProcessedSeries",
            data=[0.0, 1.0, 2.0],
            timestamps=[0.0, 0.1, 0.2],
            unit="V",
            description="a core TimeSeries that is not photometry",
        )
    )
    path = tmp_path / "discovery.nwb"
    with pynwb.NWBHDF5IO(path, "w") as handle:
        handle.write(nwbfile)

    with pynwb.NWBHDF5IO(path, "r", load_namespaces=True) as handle:
        read = handle.read()
        discovered = list(dandi._response_series(read))

        assert [name for name, _ in discovered] == [
            "acquisition/RawFiberPhotometrySignal",
            "processing/fiberphotometry/ProcessedFiberPhotometrySignal",
        ]
        assert all(
            isinstance(value, ndx_fiber_photometry.FiberPhotometryResponseSeries)
            for _, value in discovered
        )
        restored = from_nwb_series(discovered[0][1])

    assert restored.channel.values.tolist() == ["DMS", "DLS"]
    assert restored.attrs["subject"] == "mouse-1"


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("FIBERPHOTOMETRY_LIVE_DANDI") != "1",
    reason="set FIBERPHOTOMETRY_LIVE_DANDI=1 for the bounded network test",
)
def test_live_dandi_001084_bounded_stream() -> None:
    result = dandi.validate_remote_nwb_asset(
        "e766feb5-f2e6-449a-a960-9562bf60d498",
        max_samples=10,
        max_series=1,
    )

    assert len(result.response_series) == 1
    assert result.response_series[0].samples_read == 10
    assert result.response_series[0].channels_read == 103
