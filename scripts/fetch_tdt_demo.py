"""Fetch and verify the official TDT SDK demo used by the opt-in integration test."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

URL = "https://www.tdt.com/files/examples/TDTExampleData.zip"
SHA256 = "8af3a76fafb595b938fd3e5c8a8f16423bfd24bbc50d5f5f10bcc9ed2790a147"
BLOCK = "FiPho-180416"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path(".cache/tdt-demo"))
    args = parser.parse_args()
    cache = args.cache.resolve()
    archive = cache / "TDTExampleData.zip"
    destination = cache / "extracted"
    cache.mkdir(parents=True, exist_ok=True)

    if not archive.exists():
        temporary = archive.with_suffix(".zip.part")
        with urllib.request.urlopen(URL) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(archive)

    digest = _sha256(archive)
    if digest != SHA256:
        raise SystemExit(f"unexpected archive SHA-256: {digest}")

    with zipfile.ZipFile(archive) as source:
        members = [
            member
            for member in source.infolist()
            if member.filename.startswith(f"{BLOCK}/")
            and ".." not in Path(member.filename).parts
        ]
        source.extractall(destination, members=members)

    print(destination / BLOCK)


if __name__ == "__main__":
    main()
