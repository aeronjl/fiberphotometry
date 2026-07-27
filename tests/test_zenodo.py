import hashlib
import json
from pathlib import Path

import pytest

from fiberphotometry.archive import create_archive_package
from fiberphotometry.cli import main
from fiberphotometry.zenodo import create_zenodo_draft


def _deposit(tmp_path: Path) -> Path:
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    analysis = json.dumps({"artifact_type": "event_analysis_result"}).encode()
    (bundle / "analysis.json").write_bytes(analysis)
    manifest = {
        "schema_version": "1",
        "fiberphotometry_version": "test",
        "project": {"name": "project.toml", "sha256": "a" * 64},
        "status": "complete",
        "artifacts": {
            "analysis.json": {"sha256": hashlib.sha256(analysis).hexdigest()}
        },
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "artifact_type": "fiberphotometry_archive_metadata",
                "schema_version": "1",
                "title": "Reward photometry evidence",
                "description": "A reproducible analysis deposit.",
                "creators": [
                    {"name": "Laffere, Aeron", "affiliation": None, "orcid": None}
                ],
                "publication_date": "2026-07-27",
                "publisher": "Zenodo",
                "license": "cc-by-4.0",
                "keywords": ["fiber photometry"],
                "related_identifiers": [],
                "resource_type": "Dataset",
                "language": "en",
            }
        )
    )
    output = tmp_path / "deposit.zip"
    create_archive_package(bundle, metadata=metadata, output=output)
    return output


def test_creates_and_validates_unpublished_sandbox_draft(tmp_path, monkeypatch) -> None:
    archive = _deposit(tmp_path)
    monkeypatch.setenv("ZENODO_SANDBOX_TOKEN", "secret-test-token")
    calls = []

    def request(method, url, token, *, payload=None, expected):
        calls.append((method, url, token, payload, expected))
        if method == "POST":
            assert payload["metadata"]["title"] == "Reward photometry evidence"
            return {
                "id": 123,
                "links": {
                    "bucket": "https://sandbox.zenodo.org/api/files/bucket-id",
                    "self": "https://sandbox.zenodo.org/api/deposit/depositions/123",
                    "html": "https://sandbox.zenodo.org/deposit/123",
                },
            }
        return {
            "submitted": False,
            "state": "inprogress",
            "metadata": {"title": "Reward photometry evidence"},
        }

    def upload(url, path, token):
        assert url.endswith("/deposit.zip")
        assert token == "secret-test-token"
        return {"filename": path.name, "filesize": path.stat().st_size}

    monkeypatch.setattr("fiberphotometry.zenodo._request_json", request)
    monkeypatch.setattr("fiberphotometry.zenodo._upload_file", upload)

    receipt = create_zenodo_draft(archive)

    assert receipt.deposition_id == 123
    assert receipt.environment == "sandbox"
    assert receipt.submitted is False
    assert receipt.project_sha256 == "a" * 64
    assert [call[0] for call in calls] == ["POST", "GET"]
    assert all("secret-test-token" not in call[1] for call in calls)


def test_rejects_untrusted_upload_link_before_sending_file(
    tmp_path, monkeypatch
) -> None:
    archive = _deposit(tmp_path)
    monkeypatch.setenv("ZENODO_SANDBOX_TOKEN", "secret-test-token")
    monkeypatch.setattr(
        "fiberphotometry.zenodo._request_json",
        lambda *args, **kwargs: {
            "id": 123,
            "links": {
                "bucket": "https://attacker.example/api/files/stolen",
                "self": "https://sandbox.zenodo.org/api/deposit/depositions/123",
            },
        },
    )

    with pytest.raises(ValueError, match="untrusted URL"):
        create_zenodo_draft(archive)


def test_cli_requires_token_and_production_is_explicit(tmp_path, capsys) -> None:
    archive = _deposit(tmp_path)

    assert main(["zenodo-draft", str(archive)]) == 2
    assert "ZENODO_SANDBOX_TOKEN" in capsys.readouterr().err
    assert main(["zenodo-draft", str(archive), "--production"]) == 2
    assert "ZENODO_TOKEN" in capsys.readouterr().err
