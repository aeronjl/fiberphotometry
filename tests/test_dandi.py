import io
import json
import os
from types import SimpleNamespace

import pytest

from fiberphotometry.io import dandi


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


def test_response_series_discovery_covers_acquisition_and_processing() -> None:
    response_type = type("FiberPhotometryResponseSeries", (), {})
    raw = response_type()
    processed = response_type()
    other = SimpleNamespace()
    nwbfile = SimpleNamespace(
        acquisition={"raw": raw, "other": other},
        processing={
            "ophys": SimpleNamespace(
                data_interfaces={"dff": processed, "segmentation": other}
            )
        },
    )

    discovered = list(dandi._response_series(nwbfile))

    assert discovered == [
        ("acquisition/raw", raw),
        ("processing/ophys/dff", processed),
    ]


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
