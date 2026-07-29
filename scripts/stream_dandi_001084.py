"""Run the bounded DANDI 001084 NWB integration validation."""

from fipha.io.dandi import validate_remote_nwb_asset

ASSET_ID = "e766feb5-f2e6-449a-a960-9562bf60d498"


def main() -> None:
    result = validate_remote_nwb_asset(ASSET_ID, max_samples=1_000)
    print(result.to_json())


if __name__ == "__main__":
    main()
