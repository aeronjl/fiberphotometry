"""Safe creation of unpublished Zenodo draft deposits."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from fiberphotometry.archive import ZENODO_NAME, verify_archive_package

ZENODO_SANDBOX_API = "https://sandbox.zenodo.org/api"
ZENODO_PRODUCTION_API = "https://zenodo.org/api"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


@dataclass(frozen=True)
class ZenodoDraftReceipt:
    """Non-secret receipt for a validated, unpublished Zenodo draft."""

    deposition_id: int
    environment: Literal["sandbox", "production"]
    filename: str
    file_size: int
    archive_sha256: str
    project_sha256: str
    html_url: str
    submitted: Literal[False] = False
    state: Literal["unsubmitted"] = "unsubmitted"
    artifact_type: Literal["zenodo_draft_receipt"] = "zenodo_draft_receipt"
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def create_zenodo_draft(
    archive: str | Path,
    *,
    token_env: str | None = None,
    production: bool = False,
) -> ZenodoDraftReceipt:
    """Create, populate, and validate a Zenodo draft without publishing it."""
    package = verify_archive_package(archive)
    archive_path = package.path
    selected_token_env = token_env or (
        "ZENODO_TOKEN" if production else "ZENODO_SANDBOX_TOKEN"
    )
    if not selected_token_env.replace("_", "").isalnum():
        raise ValueError("Zenodo token environment-variable name is invalid")
    token = os.environ.get(selected_token_env)
    if token is None or not token.strip():
        raise ValueError(
            f"Zenodo access token is missing from environment: {selected_token_env}"
        )
    base_url = ZENODO_PRODUCTION_API if production else ZENODO_SANDBOX_API
    environment: Literal["sandbox", "production"] = (
        "production" if production else "sandbox"
    )
    metadata = _zenodo_metadata(archive_path)
    draft = _request_json(
        "POST",
        f"{base_url}/deposit/depositions",
        token,
        payload={"metadata": metadata},
        expected={201},
    )
    deposition_id = _positive_int(draft.get("id"), "Zenodo draft id")
    links = _object(draft.get("links"), "Zenodo draft links")
    bucket_url = _trusted_url(links.get("bucket"), base_url, "/api/files/")
    self_url = _trusted_url(links.get("self"), base_url, "/api/deposit/depositions/")
    html_url = _trusted_url(
        links.get("html") or links.get("html_url") or self_url,
        base_url,
        None,
    )
    upload_url = f"{bucket_url.rstrip('/')}/{urllib.parse.quote(archive_path.name)}"
    try:
        upload = _upload_file(upload_url, archive_path, token)
    except ValueError as error:
        raise ValueError(
            f"Zenodo draft {deposition_id} was created but upload failed: {error}"
        ) from error
    _validate_upload(upload, archive_path)
    validated = _request_json("GET", self_url, token, expected={200})
    if validated.get("submitted") is not False:
        raise ValueError("Zenodo response did not confirm an unpublished draft")
    state = validated.get("state")
    if state not in {"unsubmitted", "inprogress"}:
        raise ValueError(f"Zenodo draft state is unexpected: {state!r}")
    validated_metadata = _object(validated.get("metadata"), "Zenodo draft metadata")
    if validated_metadata.get("title") != metadata["title"]:
        raise ValueError("Zenodo draft metadata does not match the deposit package")
    return ZenodoDraftReceipt(
        deposition_id,
        environment,
        archive_path.name,
        archive_path.stat().st_size,
        package.sha256,
        package.project_sha256,
        html_url,
    )


def _zenodo_metadata(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            value = json.loads(archive.read(ZENODO_NAME))
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise ValueError("deposit archive lacks valid Zenodo metadata") from error
    return _object(value, "Zenodo metadata")


def _request_json(
    method: str,
    url: str,
    token: str,
    *,
    payload: dict[str, Any] | None = None,
    expected: set[int],
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=60) as response:
            status = response.status
            content = response.read()
    except urllib.error.HTTPError as error:
        detail = _error_detail(error.read())
        raise ValueError(f"Zenodo API returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise ValueError(f"Zenodo API request failed: {error.reason}") from error
    if status not in expected:
        raise ValueError(f"Zenodo API returned unexpected HTTP {status}")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("Zenodo API returned invalid JSON") from error
    return _object(value, "Zenodo API response")


def _upload_file(url: str, path: Path, token: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Zenodo upload URL must use HTTPS")
    connection = http.client.HTTPSConnection(
        parsed.hostname,
        parsed.port or 443,
        timeout=300,
        context=ssl.create_default_context(),
    )
    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    try:
        connection.putrequest("PUT", target)
        connection.putheader("Authorization", f"Bearer {token}")
        connection.putheader("Content-Type", "application/zip")
        connection.putheader("Content-Length", str(path.stat().st_size))
        connection.putheader("Accept", "application/json")
        connection.endheaders()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                connection.send(chunk)
        response = connection.getresponse()
        content = response.read()
    except (OSError, http.client.HTTPException) as error:
        raise ValueError(f"Zenodo file upload failed: {error}") from error
    finally:
        connection.close()
    if response.status not in {200, 201}:
        raise ValueError(
            f"Zenodo file upload returned HTTP {response.status}: "
            f"{_error_detail(content)}"
        )
    try:
        value = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("Zenodo file upload returned invalid JSON") from error
    return _object(value, "Zenodo upload response")


def _validate_upload(value: dict[str, Any], path: Path) -> None:
    filename = value.get("filename") or value.get("key")
    if filename is not None and filename != path.name:
        raise ValueError("Zenodo uploaded filename does not match local archive")
    size = value.get("filesize") or value.get("size")
    if size is not None and size != path.stat().st_size:
        raise ValueError("Zenodo uploaded file size does not match local archive")
    checksum = value.get("checksum")
    if isinstance(checksum, str) and checksum.startswith("md5:"):
        digest = hashlib.md5(usedforsecurity=False)
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        observed = digest.hexdigest()
        if checksum.removeprefix("md5:") != observed:
            raise ValueError(
                "Zenodo uploaded file checksum does not match local archive"
            )


def _trusted_url(value: Any, base_url: str, required_path: str | None) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Zenodo response lacks a required link")
    parsed = urllib.parse.urlparse(value)
    base = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname != base.hostname:
        raise ValueError("Zenodo response contains an untrusted URL")
    if required_path is not None and not parsed.path.startswith(required_path):
        raise ValueError("Zenodo response contains an unexpected API URL")
    return value


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _error_detail(content: bytes) -> str:
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return "request rejected"
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str) and message:
            return message[:300]
    return "request rejected"
