"""Deterministic, repository-ready archives for verified evidence bundles."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fiberphotometry.publication import ATTESTATION_NAME, SIGNATURE_NAME
from fiberphotometry.results import read_project_evidence

ARCHIVE_METADATA_NAME = "archive-metadata.json"
ARCHIVE_MANIFEST_NAME = "archive-manifest.json"
DATACITE_NAME = "datacite.json"
ZENODO_NAME = ".zenodo.json"
_ORCID = re.compile(r"^(?:https://orcid\.org/)?(\d{4}-\d{4}-\d{4}-[\dX]{4})$")
_DOI = re.compile(r"^(?:https?://doi\.org/)?10\.\d{4,9}/\S+$", re.IGNORECASE)


@dataclass(frozen=True)
class ArchiveCreator:
    """One archive creator, optionally identified by ORCID."""

    name: str
    affiliation: str | None = None
    orcid: str | None = None


@dataclass(frozen=True)
class ArchiveRelatedIdentifier:
    """A typed relationship from the archive to another resource."""

    identifier: str
    relation: Literal[
        "Cites", "IsCitedBy", "IsDerivedFrom", "IsSupplementTo", "References"
    ]


@dataclass(frozen=True)
class ArchiveMetadata:
    """Repository-neutral metadata used to derive deposit-specific records."""

    title: str
    description: str
    creators: tuple[ArchiveCreator, ...]
    publication_date: str
    publisher: str
    license: str
    keywords: tuple[str, ...] = ()
    related_identifiers: tuple[ArchiveRelatedIdentifier, ...] = ()
    resource_type: Literal["Dataset", "Software"] = "Dataset"
    language: str = "en"
    artifact_type: Literal["fiberphotometry_archive_metadata"] = (
        "fiberphotometry_archive_metadata"
    )
    schema_version: str = "1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class ArchivePackage:
    """Description of a completed deterministic deposit archive."""

    path: Path
    sha256: str
    project_sha256: str
    files: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(
            {
                "files": list(self.files),
                "path": str(self.path),
                "project_sha256": self.project_sha256,
                "schema_version": "1",
                "sha256": self.sha256,
                "status": "complete",
            },
            indent=2,
            sort_keys=True,
        )


def load_archive_metadata(path: str | Path) -> ArchiveMetadata:
    """Strictly load and validate repository-neutral archive metadata."""
    source = Path(path).resolve()
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read archive metadata: {source}") from error
    if not isinstance(value, dict):
        raise ValueError("archive metadata must be a JSON object")
    expected = {
        "title",
        "description",
        "creators",
        "publication_date",
        "publisher",
        "license",
        "keywords",
        "related_identifiers",
        "resource_type",
        "language",
        "artifact_type",
        "schema_version",
    }
    if set(value) != expected:
        raise ValueError("archive metadata fields are invalid")
    if value.get("artifact_type") != "fiberphotometry_archive_metadata":
        raise ValueError("archive metadata artifact_type is invalid")
    if value.get("schema_version") != "1":
        raise ValueError("unsupported archive metadata schema_version")
    for key in ("title", "description", "publisher", "license", "language"):
        _nonempty(value.get(key), f"archive metadata {key}")
    try:
        date.fromisoformat(value["publication_date"])
    except (TypeError, ValueError) as error:
        raise ValueError(
            "archive metadata publication_date must be YYYY-MM-DD"
        ) from error
    if value.get("resource_type") not in {"Dataset", "Software"}:
        raise ValueError("archive metadata resource_type is invalid")
    creators_value = value.get("creators")
    if not isinstance(creators_value, list) or not creators_value:
        raise ValueError("archive metadata needs at least one creator")
    creators = tuple(_creator(item) for item in creators_value)
    keywords_value = value.get("keywords")
    if not isinstance(keywords_value, list):
        raise ValueError("archive metadata keywords must be an array")
    keywords = tuple(_unique_strings(keywords_value, "archive metadata keywords"))
    related_value = value.get("related_identifiers")
    if not isinstance(related_value, list):
        raise ValueError("archive metadata related_identifiers must be an array")
    related = tuple(_related(item) for item in related_value)
    return ArchiveMetadata(
        value["title"],
        value["description"],
        creators,
        value["publication_date"],
        value["publisher"],
        value["license"],
        keywords,
        related,
        value["resource_type"],
        value["language"],
    )


def create_archive_package(
    bundle: str | Path,
    *,
    metadata: ArchiveMetadata | str | Path,
    output: str | Path,
    overwrite: bool = False,
) -> ArchivePackage:
    """Create a deterministic ZIP after validating evidence and deposit metadata."""
    root = Path(bundle).resolve()
    evidence = read_project_evidence(root)
    if evidence.source_format != "directory" or evidence.manifest_verified is not True:
        raise ValueError("archival packaging requires a verified artifact directory")
    if evidence.status != "complete":
        raise ValueError("archival packaging requires a complete evidence bundle")
    if evidence.kind == "incomplete":
        raise ValueError("archival packaging requires analysis or multiverse evidence")
    record = (
        load_archive_metadata(metadata)
        if not isinstance(metadata, ArchiveMetadata)
        else metadata
    )
    destination = Path(output).resolve()
    if destination.suffix.lower() != ".zip":
        raise ValueError("archive output must use the .zip extension")
    if destination.exists() and not overwrite:
        raise ValueError("archive output already exists; use overwrite explicitly")
    evidence_paths = [root / "manifest.json", *(item.path for item in evidence.files)]
    optional_paths = [root / ATTESTATION_NAME, root / SIGNATURE_NAME]
    if sum(path.exists() for path in optional_paths) == 1:
        raise ValueError("publication attestation and signature must appear together")
    for candidate in optional_paths:
        if candidate.exists():
            if not candidate.is_file() or candidate.is_symlink():
                raise ValueError(f"unsafe publication artifact: {candidate.name}")
            evidence_paths.append(candidate)
    generated = {
        ARCHIVE_METADATA_NAME: record.to_json().encode(),
        DATACITE_NAME: _datacite(record).encode(),
        ZENODO_NAME: _zenodo(record).encode(),
    }
    source_entries: dict[str, Path] = {}
    for path in evidence_paths:
        if path.is_symlink():
            raise ValueError(
                f"archive evidence must not be a symbolic link: {path.name}"
            )
        source_entries[f"evidence/{path.name}"] = path
    inventory = {
        name: {"sha256": digest, "size": size}
        for name, (digest, size) in (
            (name, _file_sha256_size(path))
            for name, path in sorted(source_entries.items())
        )
    }
    inventory.update(
        {
            name: {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
            for name, content in sorted(generated.items())
        }
    )
    manifest = (
        json.dumps(
            {
                "artifact_type": "fiberphotometry_archive_manifest",
                "files": inventory,
                "project_sha256": evidence.project_sha256,
                "schema_version": "1",
            },
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    generated[ARCHIVE_MANIFEST_NAME] = manifest
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in sorted(set(source_entries) | set(generated)):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                if name in generated:
                    archive.writestr(info, generated[name], compresslevel=9)
                else:
                    with (
                        source_entries[name].open("rb") as source_handle,
                        archive.open(info, "w", force_zip64=True) as target_handle,
                    ):
                        shutil.copyfileobj(source_handle, target_handle, 1024 * 1024)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return ArchivePackage(
        destination,
        _file_sha256(destination),
        evidence.project_sha256,
        tuple(sorted(set(source_entries) | set(generated))),
    )


def verify_archive_package(path: str | Path) -> ArchivePackage:
    """Verify safe paths, checksums, sizes, metadata, and evidence in an archive."""
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"archive does not exist: {source}")
    try:
        archive_handle = zipfile.ZipFile(source)
    except zipfile.BadZipFile as error:
        raise ValueError("archive is not a valid ZIP file") from error
    with archive_handle as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("archive contains duplicate paths")
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise ValueError("archive contains an unsafe path")
        try:
            manifest = json.loads(archive.read(ARCHIVE_MANIFEST_NAME))
            metadata_bytes = archive.read(ARCHIVE_METADATA_NAME)
        except (KeyError, json.JSONDecodeError) as error:
            raise ValueError(
                "archive metadata or manifest is missing or invalid"
            ) from error
        _validate_archive_manifest(manifest)
        declared = manifest["files"]
        if set(names) != set(declared) | {ARCHIVE_MANIFEST_NAME}:
            raise ValueError("archive contents do not match archive manifest")
        for name, declaration in declared.items():
            digest, size = _zip_sha256_size(archive, name)
            if size != declaration["size"] or digest != declaration["sha256"]:
                raise ValueError(f"archive checksum mismatch for: {name}")
        optional = {f"evidence/{ATTESTATION_NAME}", f"evidence/{SIGNATURE_NAME}"}
        if len(optional & set(names)) == 1:
            raise ValueError("archived publication signature pair is incomplete")
    with tempfile.TemporaryDirectory() as temporary_dir:
        temporary_root = Path(temporary_dir)
        metadata_path = temporary_root / ARCHIVE_METADATA_NAME
        metadata_path.write_bytes(metadata_bytes)
        load_archive_metadata(metadata_path)
        evidence_root = temporary_root / "evidence"
        evidence_root.mkdir()
        with zipfile.ZipFile(source) as archive:
            for name in names:
                if name.startswith("evidence/") and len(Path(name).parts) == 2:
                    with (
                        archive.open(name) as source_handle,
                        (evidence_root / Path(name).name).open("wb") as target_handle,
                    ):
                        shutil.copyfileobj(source_handle, target_handle, 1024 * 1024)
        evidence = read_project_evidence(evidence_root)
        if evidence.status != "complete":
            raise ValueError("archived evidence bundle is not complete")
        if evidence.project_sha256 != manifest["project_sha256"]:
            raise ValueError("archive project fingerprint does not match evidence")
    return ArchivePackage(
        source, _file_sha256(source), manifest["project_sha256"], tuple(sorted(names))
    )


def _creator(value: Any) -> ArchiveCreator:
    if not isinstance(value, dict) or set(value) != {"name", "affiliation", "orcid"}:
        raise ValueError("archive metadata creator fields are invalid")
    _nonempty(value.get("name"), "archive metadata creator name")
    affiliation = value.get("affiliation")
    if affiliation is not None:
        _nonempty(affiliation, "archive metadata creator affiliation")
    orcid = value.get("orcid")
    if orcid is not None:
        if not isinstance(orcid, str) or not _valid_orcid(orcid):
            raise ValueError("archive metadata creator ORCID is invalid")
        orcid = _ORCID.fullmatch(orcid).group(1)  # type: ignore[union-attr]
    return ArchiveCreator(value["name"], affiliation, orcid)


def _related(value: Any) -> ArchiveRelatedIdentifier:
    if not isinstance(value, dict) or set(value) != {"identifier", "relation"}:
        raise ValueError("archive related identifier fields are invalid")
    _nonempty(value.get("identifier"), "archive related identifier")
    allowed = {"Cites", "IsCitedBy", "IsDerivedFrom", "IsSupplementTo", "References"}
    if value.get("relation") not in allowed:
        raise ValueError("archive related identifier relation is invalid")
    identifier = value["identifier"]
    if identifier.lower().startswith(
        ("10.", "http://doi.org/", "https://doi.org/")
    ) and not _DOI.fullmatch(identifier):
        raise ValueError("archive related DOI is invalid")
    return ArchiveRelatedIdentifier(identifier, value["relation"])


def _datacite(record: ArchiveMetadata) -> str:
    creators = []
    for creator in record.creators:
        value: dict[str, Any] = {"name": creator.name}
        if creator.affiliation:
            value["affiliation"] = [{"name": creator.affiliation}]
        if creator.orcid:
            value["nameIdentifiers"] = [
                {
                    "nameIdentifier": f"https://orcid.org/{creator.orcid}",
                    "nameIdentifierScheme": "ORCID",
                    "schemeUri": "https://orcid.org",
                }
            ]
        creators.append(value)
    attributes: dict[str, Any] = {
        "creators": creators,
        "descriptions": [
            {"description": record.description, "descriptionType": "Abstract"}
        ],
        "language": record.language,
        "publicationYear": int(record.publication_date[:4]),
        "publisher": {"name": record.publisher},
        "rightsList": [{"rightsIdentifier": record.license}],
        "subjects": [{"subject": item} for item in record.keywords],
        "titles": [{"title": record.title}],
        "types": {
            "resourceType": "Fiber photometry evidence bundle",
            "resourceTypeGeneral": record.resource_type,
        },
    }
    if record.related_identifiers:
        attributes["relatedIdentifiers"] = [
            {
                "relatedIdentifier": item.identifier,
                "relatedIdentifierType": "DOI"
                if _DOI.fullmatch(item.identifier)
                else "URL",
                "relationType": item.relation,
            }
            for item in record.related_identifiers
        ]
    return (
        json.dumps(
            {"data": {"type": "dois", "attributes": attributes}},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _zenodo(record: ArchiveMetadata) -> str:
    creators = []
    for creator in record.creators:
        value = {"name": creator.name}
        if creator.affiliation:
            value["affiliation"] = creator.affiliation
        if creator.orcid:
            value["orcid"] = creator.orcid
        creators.append(value)
    payload: dict[str, Any] = {
        "access_right": "open",
        "creators": creators,
        "description": record.description,
        "keywords": list(record.keywords),
        "license": record.license,
        "publication_date": record.publication_date,
        "title": record.title,
        "upload_type": "dataset" if record.resource_type == "Dataset" else "software",
    }
    if record.related_identifiers:
        payload["related_identifiers"] = [
            {
                "identifier": item.identifier,
                "relation": item.relation[0].lower() + item.relation[1:],
            }
            for item in record.related_identifiers
        ]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _valid_orcid(value: str) -> bool:
    match = _ORCID.fullmatch(value)
    if match is None:
        return False
    digits = match.group(1).replace("-", "")
    total = 0
    for character in digits[:-1]:
        total = (total + int(character)) * 2
    result = (12 - total % 11) % 11
    return digits[-1] == ("X" if result == 10 else str(result))


def _nonempty(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _unique_strings(values: list[Any], name: str) -> list[str]:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicates")
    return values


def _validate_archive_manifest(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "artifact_type",
        "files",
        "project_sha256",
        "schema_version",
    }:
        raise ValueError("archive manifest fields are invalid")
    if (
        value.get("artifact_type") != "fiberphotometry_archive_manifest"
        or value.get("schema_version") != "1"
    ):
        raise ValueError("archive manifest type or version is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("project_sha256", "")):
        raise ValueError("archive manifest project fingerprint is invalid")
    files = value.get("files")
    if not isinstance(files, dict):
        raise ValueError("archive manifest files are invalid")
    for declaration in files.values():
        if (
            not isinstance(declaration, dict)
            or set(declaration) != {"sha256", "size"}
            or not re.fullmatch(r"[0-9a-f]{64}", declaration.get("sha256", ""))
            or not isinstance(declaration.get("size"), int)
            or declaration["size"] < 0
        ):
            raise ValueError("archive manifest file declaration is invalid")


def _file_sha256(path: Path) -> str:
    return _file_sha256_size(path)[0]


def _file_sha256_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _zip_sha256_size(archive: zipfile.ZipFile, name: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with archive.open(name) as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size
