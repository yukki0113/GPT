#!/usr/bin/env python3
"""Validate a freshly connector-materialized BRDB CURRENT; never access Drive API.

The orchestration layer resolves the exact current file through ChatGPT's native
Google Drive connector and supplies a new receipt and downloaded ZIP per call.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time

from brdb_current import (
    BRDBCurrentResolverError, EXPECTED_CURRENT_FILENAME, STATE_FILENAME,
    ResolvedBRDBCurrent, _read_json, _sha256,
    _safe_extract, _write_state,
)
from brdb_pedigree_reader import BloodReviewReader, REQUIRED_FILES

CANONICAL_FOLDER_ID = "1WhcWthqKlTvVrbK3-gkiPZW70yr9e6Bv"
TRANSPORT = "native_google_drive_connector"
RECEIPT_MAX_AGE = timedelta(hours=1)
LOCK_WAIT_SECONDS = 20
VALID_ID = re.compile(r"[A-Za-z0-9_-]{10,128}\Z")


def _time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise BRDBCurrentResolverError(f"missing {field}")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BRDBCurrentResolverError(f"invalid {field}") from exc
    if result.tzinfo is None:
        raise BRDBCurrentResolverError(f"{field} must be timezone aware")
    return result.astimezone(timezone.utc)


def _source(receipt_path: Path) -> dict[str, object]:
    data = _read_json(receipt_path)
    if data.get("schema_version") != 1 or data.get("transport") != TRANSPORT:
        raise BRDBCurrentResolverError("invalid connector source receipt")
    if data.get("folder_id") != CANONICAL_FOLDER_ID:
        raise BRDBCurrentResolverError("unexpected BRDB canonical folder")
    if type(data.get("candidate_count")) is not int or data["candidate_count"] != 1:
        raise BRDBCurrentResolverError("BRDB CURRENT source must be unique")
    if data.get("file_name") != EXPECTED_CURRENT_FILENAME:
        raise BRDBCurrentResolverError("BRDB CURRENT filename mismatch")
    file_id = data.get("file_id")
    if not isinstance(file_id, str) or VALID_ID.fullmatch(file_id) is None:
        raise BRDBCurrentResolverError("invalid BRDB CURRENT file ID")
    size = data.get("source_size_bytes")
    if type(size) is not int or size <= 0:
        raise BRDBCurrentResolverError("invalid BRDB CURRENT source size")
    modified = _time(data.get("source_modified_time"), "source_modified_time")
    observed = _time(data.get("observed_at_utc"), "observed_at_utc")
    now = datetime.now(timezone.utc)
    if observed - now > timedelta(minutes=5) or now - observed > RECEIPT_MAX_AGE:
        raise BRDBCurrentResolverError("connector receipt is stale or from the future")
    if modified > observed + timedelta(minutes=5):
        raise BRDBCurrentResolverError("BRDB source modified time is after observation")
    return {
        "file_id": file_id,
        "folder_id": CANONICAL_FOLDER_ID,
        "file_name": EXPECTED_CURRENT_FILENAME,
        "size_bytes": size,
        "source_modified_time": modified.isoformat(),
        "observed_at_utc": observed.isoformat(),
    }


@contextlib.contextmanager
def _cache_lock(cache_root: Path):
    lock = cache_root / ".brdb-current-connector.lock"
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise BRDBCurrentResolverError("BRDB cache lock busy; retry after inspecting owner")
            time.sleep(0.1)
    try:
        yield
    finally:
        lock.rmdir()


def _read_state(path: Path) -> dict:
    return _read_json(path) if path.is_file() else {}


def _cache_reader(cache_root: Path, state: dict, identity: dict):
    previous = state.get("source")
    if state.get("transport") != TRANSPORT or not isinstance(previous, dict):
        return None
    # Observation timestamp is per handoff, not a remote content revision.
    stable_keys = ("file_id", "folder_id", "file_name", "size_bytes",
                   "source_modified_time", "zip_sha256")
    if any(previous.get(key) != identity.get(key) for key in stable_keys):
        return None
    relative = state.get("root_relative_path")
    generation = state.get("generation_id")
    if not isinstance(relative, str) or not isinstance(generation, str):
        return None
    root = (cache_root / relative).resolve()
    if not root.is_relative_to(cache_root) or not root.is_dir() or (cache_root / relative).is_symlink():
        return None
    try:
        reader = BloodReviewReader(root)
    except Exception:
        return None
    return (root, reader) if reader.generation_id == generation else None


def _assert_not_older(state: dict, source: dict, new_sha: str) -> None:
    previous = state.get("source")
    if not isinstance(previous, dict):
        return
    if (previous.get("file_id") == source["file_id"]
            and previous.get("zip_sha256") == new_sha):
        return
    old_modified = previous.get("source_modified_time")
    if old_modified and _time(source["source_modified_time"], "source_modified_time") < _time(
            old_modified, "previous source_modified_time"):
        raise BRDBCurrentResolverError("BRDB CURRENT source regressed to an older revision")


def resolve_connector_current(
    cache_root: Path,
    *,
    current_zip: Path,
    connector_receipt: Path,
    force_refresh: bool = False,
) -> ResolvedBRDBCurrent:
    """Resolve one fresh connector handoff, with no network/Drive side effects."""
    cache_root = Path(cache_root).resolve()
    current_zip = Path(current_zip)
    if not current_zip.is_file() or current_zip.is_symlink() or current_zip.name != EXPECTED_CURRENT_FILENAME:
        raise BRDBCurrentResolverError("fresh connector BloodReviewDB_CURRENT.zip is required")
    if not Path(connector_receipt).is_file():
        raise BRDBCurrentResolverError("fresh connector source receipt is required")

    source = _source(Path(connector_receipt))
    cache_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="brdb-connector-stage-", dir=cache_root) as tmp:
        staged = Path(tmp)
        staged_zip = staged / EXPECTED_CURRENT_FILENAME
        before = _sha256(current_zip)
        shutil.copyfile(current_zip, staged_zip)
        zip_sha = _sha256(staged_zip)
        if zip_sha != before or _sha256(current_zip) != before:
            raise BRDBCurrentResolverError("BRDB source changed during connector handoff")
        if staged_zip.stat().st_size != source["size_bytes"]:
            raise BRDBCurrentResolverError("connector source size mismatch")
        identity = {**source, "zip_sha256": zip_sha}
        state_path = cache_root / STATE_FILENAME

        with _cache_lock(cache_root):
            state = _read_state(state_path)
            _assert_not_older(state, source, zip_sha)
            if not force_refresh:
                cached = _cache_reader(cache_root, state, identity)
                if cached is not None:
                    root, reader = cached
                    return ResolvedBRDBCurrent(
                        root=root, reader=reader,
                        provenance={"resolver_version": "BRDB-Current-Connector-0.2",
                                    "cache_status": "HIT", "generation_id": reader.generation_id,
                                    "source": identity, "root": str(root)},
                    )

            extracted = _safe_extract(staged_zip, staged / "extracted")
            try:
                reader = BloodReviewReader(extracted)
            except Exception as exc:
                raise BRDBCurrentResolverError("connector BRDB CURRENT Reader validation failed") from exc
            generation = reader.generation_id
            if not isinstance(generation, str) or not re.fullmatch(r"[a-f0-9]{16}", generation):
                raise BRDBCurrentResolverError("invalid BRDB CURRENT generation ID")
            generations = cache_root / "generations"
            generations.mkdir(parents=True, exist_ok=True)
            accepted = generations / generation
            if accepted.is_symlink():
                raise BRDBCurrentResolverError("BRDB cache generation symlink is unsafe")
            if accepted.exists():
                try:
                    existing = BloodReviewReader(accepted)
                except Exception as exc:
                    raise BRDBCurrentResolverError("existing BRDB generation invalid") from exc
                if existing.generation_id != generation:
                    raise BRDBCurrentResolverError("BRDB cached generation mismatch")
                for filename in ("current.json", "manifest.json", *REQUIRED_FILES):
                    if _sha256(accepted / filename) != _sha256(extracted / filename):
                        raise BRDBCurrentResolverError("immutable BRDB generation content conflict")
                reader = existing
            else:
                os.replace(extracted, accepted)
                try:
                    reader = BloodReviewReader(accepted)
                except Exception as exc:
                    shutil.rmtree(accepted, ignore_errors=True)
                    raise BRDBCurrentResolverError("promoted BRDB generation failed readback") from exc

            state = {
                "resolver_version": "BRDB-Current-Connector-0.2",
                "transport": TRANSPORT,
                "source": identity,
                "generation_id": reader.generation_id,
                "root_relative_path": str(accepted.relative_to(cache_root)),
                "zip_sha256": zip_sha,
            }
            _write_state(state_path, state)
            return ResolvedBRDBCurrent(
                root=accepted, reader=reader,
                provenance={"resolver_version": "BRDB-Current-Connector-0.2",
                            "cache_status": "REFRESHED", "generation_id": reader.generation_id,
                            "source": identity, "root": str(accepted)},
            )
