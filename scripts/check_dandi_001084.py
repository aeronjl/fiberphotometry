"""Check the DANDI 001084 NWB benchmark asset without downloading 18 GB."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen

API = "https://api.dandiarchive.org/api/dandisets/001084/versions/draft/assets/"
EXPECTED_PATH = "sub-DL18/sub-DL18_ses-211110_image+ophys.nwb"


def main() -> None:
    query = urlencode({"path": EXPECTED_PATH})
    with urlopen(f"{API}?{query}", timeout=30) as response:
        payload = json.load(response)
    if payload["count"] != 1:
        raise RuntimeError(f"expected one benchmark asset, found {payload['count']}")
    asset = payload["results"][0]
    if asset["path"] != EXPECTED_PATH or asset["size"] <= 0:
        raise RuntimeError("DANDI benchmark asset metadata is invalid")
    print(
        json.dumps(
            {
                "asset_id": asset["asset_id"],
                "path": asset["path"],
                "size_bytes": asset["size"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
