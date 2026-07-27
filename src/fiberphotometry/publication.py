"""Detached OpenSSH signatures for publication evidence manifests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fiberphotometry.results import read_project_evidence

PUBLICATION_NAMESPACE = "fiberphotometry-publication@aeronjl.github.io"
ATTESTATION_NAME = "publication-attestation.json"
SIGNATURE_NAME = "publication-attestation.json.sig"


@dataclass(frozen=True)
class PublicationAttestation:
    """Canonical claim binding one project manifest to a signer identity."""

    manifest_sha256: str
    project_sha256: str
    signer_identity: str
    signed_at_utc: str
    namespace: str = PUBLICATION_NAMESPACE
    signature_method: Literal["openssh"] = "openssh"
    artifact_type: Literal["publication_manifest_attestation"] = (
        "publication_manifest_attestation"
    )
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class PublicationVerification:
    """Successful verification of a detached publication attestation."""

    status: Literal["verified"]
    signer_identity: str
    manifest_sha256: str
    project_sha256: str
    signed_at_utc: str
    namespace: str
    attestation_path: str
    signature_path: str
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def sign_publication_manifest(
    bundle: str | Path,
    *,
    key: str | Path,
    signer_identity: str,
    overwrite: bool = False,
) -> PublicationAttestation:
    """Sign a verified complete directory manifest using an OpenSSH identity."""
    source = Path(bundle).resolve()
    evidence = read_project_evidence(source)
    if evidence.source_format != "directory" or evidence.manifest_verified is not True:
        raise ValueError("publication signing requires a verified artifact directory")
    if evidence.status != "complete":
        raise ValueError("publication signing requires a complete evidence bundle")
    identity = signer_identity.strip()
    if not identity or any(character.isspace() for character in identity):
        raise ValueError("signer_identity must be non-empty and contain no whitespace")
    key_path = Path(key).expanduser().resolve()
    if not key_path.is_file():
        raise ValueError(f"OpenSSH signing key does not exist: {key_path}")
    _require_ssh_keygen()
    attestation_path = source / ATTESTATION_NAME
    signature_path = source / SIGNATURE_NAME
    if not overwrite and (attestation_path.exists() or signature_path.exists()):
        raise ValueError(
            "publication signature already exists; use overwrite explicitly"
        )
    manifest_path = source / "manifest.json"
    attestation = PublicationAttestation(
        _file_sha256(manifest_path),
        evidence.project_sha256,
        identity,
        datetime.now(UTC).isoformat(),
    )
    payload = attestation.to_json().encode()
    completed = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(key_path),
            "-n",
            PUBLICATION_NAMESPACE,
        ],
        input=payload,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        message = completed.stderr.decode(errors="replace").strip()
        raise ValueError(f"OpenSSH publication signing failed: {message}")
    _atomic_write(attestation_path, payload)
    _atomic_write(signature_path, completed.stdout)
    return attestation


def verify_publication_manifest(
    bundle: str | Path,
    *,
    allowed_signers: str | Path,
) -> PublicationVerification:
    """Verify signer authorization, signature bytes, and exact manifest binding."""
    source = Path(bundle).resolve()
    evidence = read_project_evidence(source)
    if evidence.source_format != "directory" or evidence.manifest_verified is not True:
        raise ValueError("publication verification requires an artifact directory")
    allowed_path = Path(allowed_signers).expanduser().resolve()
    if not allowed_path.is_file():
        raise ValueError(f"allowed signers file does not exist: {allowed_path}")
    attestation_path = source / ATTESTATION_NAME
    signature_path = source / SIGNATURE_NAME
    attestation = _read_attestation(attestation_path)
    if not signature_path.is_file():
        raise ValueError("publication detached signature is missing")
    observed_manifest = _file_sha256(source / "manifest.json")
    if attestation.manifest_sha256 != observed_manifest:
        raise ValueError("publication attestation does not match manifest bytes")
    if attestation.project_sha256 != evidence.project_sha256:
        raise ValueError("publication attestation does not match project fingerprint")
    _require_ssh_keygen()
    payload = attestation_path.read_bytes()
    completed = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(allowed_path),
            "-I",
            attestation.signer_identity,
            "-n",
            PUBLICATION_NAMESPACE,
            "-s",
            str(signature_path),
        ],
        input=payload,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode(errors="replace").strip()
        raise ValueError(f"OpenSSH publication verification failed: {message}")
    return PublicationVerification(
        "verified",
        attestation.signer_identity,
        attestation.manifest_sha256,
        attestation.project_sha256,
        attestation.signed_at_utc,
        attestation.namespace,
        str(attestation_path),
        str(signature_path),
    )


def _read_attestation(path: Path) -> PublicationAttestation:
    if not path.is_file():
        raise ValueError("publication attestation is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("publication attestation is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("publication attestation must be a JSON object")
    expected = {
        "manifest_sha256",
        "project_sha256",
        "signer_identity",
        "signed_at_utc",
        "namespace",
        "signature_method",
        "artifact_type",
        "schema_version",
    }
    if set(value) != expected:
        raise ValueError("publication attestation fields are invalid")
    if value.get("artifact_type") != "publication_manifest_attestation":
        raise ValueError("publication attestation artifact_type is invalid")
    if value.get("schema_version") != "1":
        raise ValueError("unsupported publication attestation schema_version")
    if value.get("signature_method") != "openssh":
        raise ValueError("publication attestation signature_method is invalid")
    if value.get("namespace") != PUBLICATION_NAMESPACE:
        raise ValueError("publication attestation namespace is invalid")
    for key in ("manifest_sha256", "project_sha256"):
        _validate_sha256(value.get(key), f"publication attestation {key}")
    for key in ("signer_identity", "signed_at_utc"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"publication attestation {key} is invalid")
    try:
        parsed_time = datetime.fromisoformat(value["signed_at_utc"])
    except ValueError as error:
        raise ValueError("publication attestation signed_at_utc is invalid") from error
    if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
        raise ValueError("publication attestation signed_at_utc needs a timezone")
    return PublicationAttestation(**value)


def _require_ssh_keygen() -> None:
    if shutil.which("ssh-keygen") is None:
        raise ValueError("OpenSSH ssh-keygen is required for publication signatures")


def _validate_sha256(value: Any, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256")


def _atomic_write(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
