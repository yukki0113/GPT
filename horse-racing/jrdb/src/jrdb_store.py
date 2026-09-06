#!/usr/bin/env python3
"""Resolve JRDB logical artifacts from an external manifest into a verified local cache.

The manifest is the operational locator contract. Live Google Drive file IDs remain
outside Git; consumers ask only for logical names such as ``jrdb://analysis/current``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

MANIFEST_VERSION = "1.0"
RESOLVABLE_STATUSES = {"FINAL", "YTD", "PUBLISHED"}
KNOWN_STATUSES = RESOLVABLE_STATUSES | {"CANDIDATE"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LOGICAL_PART_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class StoreError(RuntimeError):
    """Raised when a store manifest or artifact cannot be resolved safely."""


@dataclass(frozen=True)
class StoredObject:
    provider: str
    file_id: str
    filename: str
    size: int
    sha256: str


@dataclass(frozen=True)
class PayloadSpec:
    compression: str
    member: str | None
    filename: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ArtifactSpec:
    logical_name: str
    artifact_type: str
    schema_version: str
    data_version: str
    period_from: str
    period_to: str
    status: str
    storage: StoredObject
    payload: PayloadSpec

    @property
    def logical_uri(self) -> str:
        return f"jrdb://{self.logical_name}"


@dataclass(frozen=True)
class StoreManifest:
    manifest_version: str
    updated_at: str
    artifacts: dict[str, ArtifactSpec]

    @classmethod
    def from_file(cls, path: Path) -> "StoreManifest":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"Could not read store manifest: {path}: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoreManifest":
        version = str(data.get("manifest_version") or "")
        if version != MANIFEST_VERSION:
            raise StoreError(
                f"Unsupported store manifest version: {version or '<missing>'}"
            )
        updated_at = str(data.get("updated_at") or "")
        raw_artifacts = data.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raise StoreError("Store manifest artifacts must be a list")

        artifacts: dict[str, ArtifactSpec] = {}
        for raw_artifact in raw_artifacts:
            if not isinstance(raw_artifact, dict):
                raise StoreError("Store manifest artifact must be an object")
            artifact = parse_artifact(raw_artifact)
            if artifact.logical_name in artifacts:
                raise StoreError(
                    f"Duplicate logical artifact: {artifact.logical_name}"
                )
            artifacts[artifact.logical_name] = artifact
        return cls(version, updated_at, artifacts)

    def get(self, logical_name: str, allow_candidate: bool = False) -> ArtifactSpec:
        normalized = normalize_logical_name(logical_name)
        artifact = self.artifacts.get(normalized)
        if artifact is None:
            raise StoreError(f"Artifact not found in manifest: jrdb://{normalized}")
        if artifact.status not in RESOLVABLE_STATUSES:
            if not (allow_candidate and artifact.status == "CANDIDATE"):
                raise StoreError(
                    f"Artifact is not resolvable: {artifact.logical_uri} "
                    f"status={artifact.status}"
                )
        return artifact


Fetcher = Callable[[ArtifactSpec, Path], None]


class StoreResolver:
    """Resolve logical JRDB artifacts into a disposable verified local cache."""

    def __init__(
        self,
        manifest: StoreManifest,
        cache_root: Path | None = None,
        fetcher: Fetcher | None = None,
        allow_candidate: bool = False,
    ) -> None:
        self.manifest = manifest
        if cache_root is None:
            cache_root = default_cache_root()
        self.cache_root = cache_root
        self.fetcher = fetcher
        self.allow_candidate = allow_candidate

    @classmethod
    def from_file(
        cls,
        manifest_path: Path,
        cache_root: Path | None = None,
        fetcher: Fetcher | None = None,
        allow_candidate: bool = False,
    ) -> "StoreResolver":
        manifest = StoreManifest.from_file(manifest_path)
        return cls(manifest, cache_root, fetcher, allow_candidate)

    def resolve(self, logical_name: str, offline: bool = False) -> Path:
        artifact = self.manifest.get(logical_name, self.allow_candidate)
        if artifact.payload.compression == "none":
            self._validate_direct_payload_contract(artifact)
            object_path = self.object_cache_path(artifact)
            if valid_file(
                object_path,
                artifact.storage.size,
                artifact.storage.sha256,
            ):
                return object_path
            if offline:
                raise StoreError(
                    f"Artifact not available in offline cache: {artifact.logical_uri}"
                )
            self._fetch_object(artifact, object_path)
            return object_path

        payload_path = self.payload_cache_path(artifact)
        if valid_file(
            payload_path,
            artifact.payload.size,
            artifact.payload.sha256,
        ):
            return payload_path
        if payload_path.exists():
            payload_path.unlink()

        object_path = self.object_cache_path(artifact)
        if not valid_file(
            object_path,
            artifact.storage.size,
            artifact.storage.sha256,
        ):
            if offline:
                raise StoreError(
                    f"Artifact not available in offline cache: {artifact.logical_uri}"
                )
            self._fetch_object(artifact, object_path)
        self._materialize(artifact, object_path, payload_path)
        return payload_path

    def resolve_year(self, year: int, offline: bool = False) -> Path:
        if year < 1900 or year > 2100:
            raise StoreError(f"Invalid canonical year: {year}")
        return self.resolve(f"jrdb://canonical/{year}", offline=offline)

    def object_cache_path(self, artifact: ArtifactSpec) -> Path:
        return (
            self.cache_root
            / "objects"
            / artifact.storage.sha256
            / artifact.storage.filename
        )

    def payload_cache_path(self, artifact: ArtifactSpec) -> Path:
        parts = artifact.logical_name.split("/")
        return (
            self.cache_root
            / "materialized"
            / Path(*parts)
            / artifact.payload.sha256
            / artifact.payload.filename
        )

    def cached_path(self, logical_name: str) -> Path | None:
        artifact = self.manifest.get(logical_name, self.allow_candidate)
        if artifact.payload.compression == "none":
            path = self.object_cache_path(artifact)
            if valid_file(path, artifact.storage.size, artifact.storage.sha256):
                return path
            return None
        path = self.payload_cache_path(artifact)
        if valid_file(path, artifact.payload.size, artifact.payload.sha256):
            return path
        return None

    def _validate_direct_payload_contract(self, artifact: ArtifactSpec) -> None:
        if artifact.payload.filename != artifact.storage.filename:
            raise StoreError(
                f"Uncompressed payload filename must match storage filename: "
                f"{artifact.logical_uri}"
            )
        if artifact.payload.size != artifact.storage.size:
            raise StoreError(
                f"Uncompressed payload size must match storage size: "
                f"{artifact.logical_uri}"
            )
        if artifact.payload.sha256 != artifact.storage.sha256:
            raise StoreError(
                f"Uncompressed payload hash must match storage hash: "
                f"{artifact.logical_uri}"
            )

    def _fetch_object(self, artifact: ArtifactSpec, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(
            destination.name + f".part.{os.getpid()}"
        )
        if temporary.exists():
            temporary.unlink()
        try:
            if self.fetcher is not None:
                self.fetcher(artifact, temporary)
            else:
                fetch_artifact(artifact, temporary)
            require_valid_file(
                temporary,
                artifact.storage.size,
                artifact.storage.sha256,
                f"downloaded object for {artifact.logical_uri}",
            )
            os.replace(temporary, destination)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise

    def _materialize(
        self,
        artifact: ArtifactSpec,
        object_path: Path,
        payload_path: Path,
    ) -> None:
        if artifact.payload.compression != "zip":
            raise StoreError(
                f"Unsupported compression: {artifact.payload.compression}"
            )
        member = artifact.payload.member
        if member is None or not member:
            raise StoreError(f"ZIP member is missing: {artifact.logical_uri}")

        payload_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = payload_path.with_name(
            payload_path.name + f".part.{os.getpid()}"
        )
        if temporary.exists():
            temporary.unlink()
        try:
            with zipfile.ZipFile(object_path) as archive:
                if member not in archive.namelist():
                    raise StoreError(
                        f"ZIP member not found for {artifact.logical_uri}: {member}"
                    )
                with archive.open(member) as source, temporary.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
            require_valid_file(
                temporary,
                artifact.payload.size,
                artifact.payload.sha256,
                f"materialized payload for {artifact.logical_uri}",
            )
            os.replace(temporary, payload_path)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise


def normalize_logical_name(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("jrdb://"):
        normalized = normalized[len("jrdb://") :]
    normalized = normalized.strip("/")
    if not normalized or "\\" in normalized:
        raise StoreError(f"Invalid logical artifact name: {value!r}")
    parts = normalized.split("/")
    for part in parts:
        if part in {"", ".", ".."} or LOGICAL_PART_RE.fullmatch(part) is None:
            raise StoreError(f"Invalid logical artifact name: {value!r}")
    return "/".join(parts)


def parse_artifact(data: dict[str, Any]) -> ArtifactSpec:
    logical_name = normalize_logical_name(str(data.get("logical_name") or ""))
    status = str(data.get("status") or "").upper()
    if status not in KNOWN_STATUSES:
        raise StoreError(
            f"Unknown artifact status for jrdb://{logical_name}: {status or '<missing>'}"
        )
    storage_data = data.get("storage")
    payload_data = data.get("payload")
    if not isinstance(storage_data, dict) or not isinstance(payload_data, dict):
        raise StoreError(
            f"storage/payload must be objects for jrdb://{logical_name}"
        )

    provider = str(storage_data.get("provider") or "")
    if provider != "google_drive":
        raise StoreError(
            f"Unsupported storage provider for jrdb://{logical_name}: {provider}"
        )
    file_id = str(storage_data.get("file_id") or "").strip()
    if not file_id:
        raise StoreError(f"Missing Drive file_id for jrdb://{logical_name}")

    storage_filename = validate_filename(
        str(storage_data.get("filename") or ""), "storage filename"
    )
    storage_size = positive_int(storage_data.get("size"), "storage size")
    storage_sha = validate_sha256(
        str(storage_data.get("sha256") or ""), "storage sha256"
    )

    compression = str(payload_data.get("compression") or "").lower()
    if compression not in {"none", "zip"}:
        raise StoreError(
            f"Unsupported payload compression for jrdb://{logical_name}: {compression}"
        )
    member_value = payload_data.get("member")
    member: str | None = None
    if member_value is not None:
        member = str(member_value)
    if compression == "zip":
        if member is None or not member:
            raise StoreError(f"ZIP payload member is required for jrdb://{logical_name}")
        if member.startswith("/") or "\\" in member or ".." in Path(member).parts:
            raise StoreError(f"Unsafe ZIP payload member for jrdb://{logical_name}")

    payload_filename = validate_filename(
        str(payload_data.get("filename") or ""), "payload filename"
    )
    payload_size = positive_int(payload_data.get("size"), "payload size")
    payload_sha = validate_sha256(
        str(payload_data.get("sha256") or ""), "payload sha256"
    )

    return ArtifactSpec(
        logical_name=logical_name,
        artifact_type=str(data.get("artifact_type") or ""),
        schema_version=str(data.get("schema_version") or ""),
        data_version=str(data.get("data_version") or ""),
        period_from=str(data.get("period_from") or ""),
        period_to=str(data.get("period_to") or ""),
        status=status,
        storage=StoredObject(
            provider=provider,
            file_id=file_id,
            filename=storage_filename,
            size=storage_size,
            sha256=storage_sha,
        ),
        payload=PayloadSpec(
            compression=compression,
            member=member,
            filename=payload_filename,
            size=payload_size,
            sha256=payload_sha,
        ),
    )


def validate_filename(value: str, label: str) -> str:
    if not value or Path(value).name != value or "/" in value or "\\" in value:
        raise StoreError(f"Invalid {label}: {value!r}")
    return value


def positive_int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise StoreError(f"Invalid {label}: {value!r}") from exc
    if result <= 0:
        raise StoreError(f"Invalid {label}: {value!r}")
    return result


def validate_sha256(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if SHA256_RE.fullmatch(normalized) is None:
        raise StoreError(f"Invalid {label}: {value!r}")
    return normalized


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def valid_file(path: Path, expected_size: int, expected_sha256: str) -> bool:
    if not path.is_file():
        return False
    try:
        if path.stat().st_size != expected_size:
            return False
        return sha256_file(path) == expected_sha256
    except OSError:
        return False


def require_valid_file(
    path: Path,
    expected_size: int,
    expected_sha256: str,
    label: str,
) -> None:
    if not path.is_file():
        raise StoreError(f"Missing {label}: {path}")
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise StoreError(
            f"Size mismatch for {label}: expected={expected_size} actual={actual_size}"
        )
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha256:
        raise StoreError(
            f"SHA-256 mismatch for {label}: expected={expected_sha256} "
            f"actual={actual_sha}"
        )


def default_cache_root() -> Path:
    override = os.environ.get("JRDB_STORE_CACHE")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "JRDB" / "cache"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "JRDB"

    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "jrdb"
    return Path.home() / ".cache" / "jrdb"


def fetch_artifact(artifact: ArtifactSpec, destination: Path) -> None:
    if artifact.storage.provider == "google_drive":
        download_google_drive(artifact.storage.file_id, destination)
        return
    raise StoreError(f"Unsupported storage provider: {artifact.storage.provider}")


def download_google_drive(
    file_id: str,
    destination: Path,
    retries: int = 3,
    timeout_seconds: int = 60,
) -> None:
    query = urllib.parse.urlencode(
        {"id": file_id, "export": "download", "confirm": "t"}
    )
    url = "https://drive.usercontent.google.com/download?" + query
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "JRDB-Store-Resolver/0.1"},
            )
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                with destination.open("wb") as target:
                    shutil.copyfileobj(response, target, length=1024 * 1024)
            return
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            last_error = exc
            if destination.exists():
                destination.unlink()
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 4))
    raise StoreError(f"Google Drive download failed for file_id={file_id}: {last_error}")


def manifest_path_from_args(value: Path | None) -> Path:
    if value is not None:
        return value
    environment = os.environ.get("JRDB_STORE_MANIFEST")
    if environment:
        return Path(environment).expanduser()
    raise StoreError(
        "Store manifest is required. Use --manifest or JRDB_STORE_MANIFEST."
    )


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JRDB logical artifact store resolver")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--cache-root", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List manifest logical artifacts")
    list_parser.add_argument("--include-candidate", action="store_true")

    resolve_parser = subparsers.add_parser("resolve", help="Resolve one logical artifact")
    resolve_parser.add_argument("logical_name")
    resolve_parser.add_argument("--offline", action="store_true")
    resolve_parser.add_argument("--allow-candidate", action="store_true")

    verify_parser = subparsers.add_parser("verify", help="Verify cached artifact only")
    verify_parser.add_argument("logical_name")
    verify_parser.add_argument("--allow-candidate", action="store_true")
    return parser


def main() -> int:
    parser = build_cli()
    args = parser.parse_args()
    try:
        manifest_path = manifest_path_from_args(args.manifest)
        manifest = StoreManifest.from_file(manifest_path)

        if args.command == "list":
            rows: list[dict[str, Any]] = []
            for name in sorted(manifest.artifacts):
                artifact = manifest.artifacts[name]
                if artifact.status == "CANDIDATE" and not args.include_candidate:
                    continue
                rows.append(
                    {
                        "logical_name": artifact.logical_uri,
                        "artifact_type": artifact.artifact_type,
                        "schema_version": artifact.schema_version,
                        "data_version": artifact.data_version,
                        "period_from": artifact.period_from,
                        "period_to": artifact.period_to,
                        "status": artifact.status,
                        "filename": artifact.payload.filename,
                        "sha256": artifact.payload.sha256,
                    }
                )
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0

        resolver = StoreResolver(
            manifest,
            cache_root=args.cache_root,
            allow_candidate=args.allow_candidate,
        )
        if args.command == "resolve":
            path = resolver.resolve(args.logical_name, offline=args.offline)
            print(path)
            return 0
        if args.command == "verify":
            path = resolver.cached_path(args.logical_name)
            if path is None:
                print("not_cached", file=sys.stderr)
                return 2
            print(path)
            return 0
        raise StoreError(f"Unknown command: {args.command}")
    except StoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
