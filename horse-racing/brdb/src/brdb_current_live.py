#!/usr/bin/env python3
"""Resolve BRDB's *operational* CURRENT from the canonical Drive folder.

This is distinct from the immutable, SHA-pinned historical public transport.
Always discover the one CURRENT by exact name at the start of each call.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from brdb_current import (
    BRDBCurrentResolverError, EXPECTED_CURRENT_FILENAME, STATE_FILENAME,
    ResolvedBRDBCurrent, _cached, _read_json, _safe_extract, _sha256, _write_state,
)
from brdb_pedigree_reader import BloodReviewReader

DEFAULT_DRIVE_FOLDER_ID = "1WhcWthqKlTvVrbK3-gkiPZW70yr9e6Bv"
DYNAMIC_TRANSPORT_ID = "brdb-canonical-folder-current-v0.2"
LIVE_RESOLVER_VERSION = "BRDB-Current-Resolver-0.2"
_ID = re.compile(r"[A-Za-z0-9_-]{10,128}\Z")
_MD5 = re.compile(r"[a-fA-F0-9]{32}\Z")


def _drive_bridge():
    try:
        from tools.gpt_io.gdrive import gdrive_api
    except ImportError as exc:
        raise BRDBCurrentResolverError("Drive API bridge unavailable") from exc
    return gdrive_api


def _fingerprint(meta: dict[str, Any], folder_id: str) -> dict[str, object]:
    """Strict source identity: any revision change makes a cache miss."""
    if (meta.get("name") != EXPECTED_CURRENT_FILENAME
            or meta.get("trashed") is True
            or meta.get("mimeType") != "application/zip"
            or folder_id not in (meta.get("parents") or [])):
        raise BRDBCurrentResolverError("BRDB CURRENT source name, type or parent mismatch")
    file_id = str(meta.get("id") or "")
    modified = str(meta.get("modifiedTime") or "")
    md5 = str(meta.get("md5Checksum") or "").lower()
    version = str(meta.get("version") or "")
    try:
        size = int(meta.get("size") or 0)
    except (TypeError, ValueError) as exc:
        raise BRDBCurrentResolverError("invalid BRDB CURRENT Drive size") from exc
    if not _ID.fullmatch(file_id) or not _MD5.fullmatch(md5) or size <= 0 or not modified or not version:
        raise BRDBCurrentResolverError("incomplete BRDB CURRENT revision metadata")
    return {
        "file_id": file_id,
        "name": EXPECTED_CURRENT_FILENAME,
        "parent_id": folder_id,
        "modified_time": modified,
        "version": version,
        "size_bytes": size,
        "md5_checksum": md5,
    }


def _discover(service: Any, api: Any, folder_id: str) -> dict[str, object]:
    """Exact-match and exhaustive paging; 0 or 2+ candidates fail closed."""
    if not _ID.fullmatch(folder_id):
        raise BRDBCurrentResolverError("invalid canonical BRDB Drive folder ID")
    escaped = EXPECTED_CURRENT_FILENAME.replace("'", "\\'")
    query = f"'{folder_id}' in parents and name='{escaped}' and trashed=false"
    fields = "nextPageToken,files(id,name,mimeType,size,modifiedTime,md5Checksum,parents,trashed,version)"
    found: list[dict[str, Any]] = []
    token: str | None = None
    seen_tokens = set()
    try:
        while True:
            params = dict(q=query, fields=fields, pageSize=1000,
                          supportsAllDrives=True, includeItemsFromAllDrives=True)
            if token:
                params["pageToken"] = token
            result = service.files().list(**params).execute()
            found.extend(result.get("files", []))
            if len(found) > 1:
                raise BRDBCurrentResolverError("ambiguous BRDB CURRENT: duplicate exact filename")
            token = result.get("nextPageToken")
            if not token:
                break
            if token in seen_tokens:
                raise BRDBCurrentResolverError("repeated Drive listing page token")
            seen_tokens.add(token)
        if len(found) != 1:
            raise BRDBCurrentResolverError("BRDB CURRENT not found at canonical folder")
        # Metadata re-read after listing guards against a moved/renamed object.
        meta = api.metadata(service, str(found[0].get("id") or ""))
        fingerprint = _fingerprint(meta, folder_id)
        if str(found[0].get("id")) != fingerprint["file_id"]:
            raise BRDBCurrentResolverError("discovered BRDB CURRENT identity mismatch")
        return fingerprint
    except BRDBCurrentResolverError:
        raise
    except Exception as exc:
        raise BRDBCurrentResolverError("BRDB CURRENT discovery failed") from exc


def _verified_cached(cache_root: Path, state_path: Path, fingerprint: dict[str, object]):
    if not state_path.is_file():
        return None
    try:
        state = _read_json(state_path)
    except BRDBCurrentResolverError:
        return None
    if state.get("drive") != fingerprint or state.get("transport_mode") != "dynamic":
        return None
    if not re.fullmatch(r"[a-f0-9]{64}", str(state.get("zip_sha256") or "")):
        return None
    transport = {"manifest_sha256": DYNAMIC_TRANSPORT_ID, "file_id": fingerprint["file_id"],
                 "expected_size": fingerprint["size_bytes"], "zip_sha256": state["zip_sha256"]}
    return _cached(cache_root, state, transport)


def _md5(path: Path) -> str:
    digest = hashlib.md5()  # nosec - Google Drive metadata transport fingerprint, not integrity trust
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_brdb_current_live(
    cache_root: Path,
    *,
    folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
    force_refresh: bool = False,
    service: Any | None = None,
    api: Any | None = None,
) -> ResolvedBRDBCurrent:
    """Fail-closed dynamic CURRENT with atomic cache promotion."""
    cache_root = Path(cache_root).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    api = api or _drive_bridge()
    if service is None:
        try:
            service, _ = api.load_service(folder_id)
        except Exception as exc:
            raise BRDBCurrentResolverError(
                "BRDB dynamic CURRENT requires authenticated Google Drive service"
            ) from exc

    first = _discover(service, api, folder_id)
    state_path = cache_root / STATE_FILENAME
    if not force_refresh:
        hit = _verified_cached(cache_root, state_path, first)
        if hit is not None:
            # A change between listing and Reader validation must not become a stale hit.
            if _discover(service, api, folder_id) != first:
                raise BRDBCurrentResolverError("BRDB CURRENT changed during cache revalidation")
            provenance = {**hit.provenance, "resolver_version": LIVE_RESOLVER_VERSION,
                          "drive": first, "transport_mode": "dynamic",
                          "zip_sha256": _read_json(state_path)["zip_sha256"]}
            return ResolvedBRDBCurrent(root=hit.root, reader=hit.reader, provenance=provenance)

    with tempfile.TemporaryDirectory(prefix="brdb-current-live-", dir=cache_root) as tmp:
        stage = Path(tmp)
        archive_path = stage / EXPECTED_CURRENT_FILENAME
        try:
            downloaded = api.download(service, str(first["file_id"]), archive_path)
        except Exception as exc:
            raise BRDBCurrentResolverError("BRDB CURRENT download failed") from exc
        if not archive_path.is_file() or archive_path.stat().st_size != first["size_bytes"]:
            raise BRDBCurrentResolverError("BRDB CURRENT download size mismatch")
        if _md5(archive_path) != first["md5_checksum"]:
            raise BRDBCurrentResolverError("BRDB CURRENT download MD5 mismatch")
        if isinstance(downloaded, dict) and downloaded.get("sha256"):
            if str(downloaded["sha256"]).lower() != _sha256(archive_path):
                raise BRDBCurrentResolverError("BRDB CURRENT transport SHA mismatch")
        zip_sha = _sha256(archive_path)
        if _discover(service, api, folder_id) != first:
            raise BRDBCurrentResolverError("BRDB CURRENT changed during download")
        extracted_root = _safe_extract(archive_path, stage / "extracted")
        try:
            reader = BloodReviewReader(extracted_root)
        except Exception as exc:
            raise BRDBCurrentResolverError("downloaded BRDB CURRENT failed Reader validation") from exc
        if not reader.generation_id or not re.fullmatch(r"[0-9a-f]{16}", reader.generation_id):
            raise BRDBCurrentResolverError("invalid BRDB CURRENT generation")
        if _discover(service, api, folder_id) != first:
            raise BRDBCurrentResolverError("BRDB CURRENT changed during validation")

        generations = cache_root / "generations"
        generations.mkdir(parents=True, exist_ok=True)
        accepted_root = generations / reader.generation_id
        if accepted_root.is_symlink():
            raise BRDBCurrentResolverError("unsafe BRDB generation cache symlink")
        if accepted_root.exists():
            try:
                existing_reader = BloodReviewReader(accepted_root)
            except Exception as exc:
                raise BRDBCurrentResolverError("existing BRDB cached generation is invalid") from exc
            if existing_reader.generation_id != reader.generation_id:
                raise BRDBCurrentResolverError("cached BRDB generation mismatch")
            # A generation must not silently change pedigree facts under the same ID.
            for name in ("current.json", "manifest.json"):
                if _sha256(accepted_root / name) != _sha256(extracted_root / name):
                    raise BRDBCurrentResolverError("BRDB generation payload conflict")
            reader = existing_reader
        else:
            shutil.move(str(extracted_root), str(accepted_root))
            try:
                reader = BloodReviewReader(accepted_root)
            except Exception as exc:
                shutil.rmtree(accepted_root, ignore_errors=True)
                raise BRDBCurrentResolverError("promoted BRDB CURRENT failed readback") from exc

        state = {
            "resolver_version": LIVE_RESOLVER_VERSION,
            "transport_mode": "dynamic",
            "transport_manifest_sha256": DYNAMIC_TRANSPORT_ID,
            "generation_id": reader.generation_id,
            "root_relative_path": str(accepted_root.relative_to(cache_root)),
            "drive": first,
            "file_id": first["file_id"],
            "zip_sha256": zip_sha,
        }
        _write_state(state_path, state)
        return ResolvedBRDBCurrent(
            root=accepted_root, reader=reader,
            provenance={"resolver_version": LIVE_RESOLVER_VERSION,
                        "cache_status": "REFRESHED", "transport_mode": "dynamic",
                        "generation_id": reader.generation_id, "drive": first,
                        "zip_sha256": zip_sha, "root": str(accepted_root)},
        )
