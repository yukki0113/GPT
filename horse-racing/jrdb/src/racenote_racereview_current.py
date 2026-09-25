#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve the operational RaceReviewDB CURRENT snapshot for RaceNote.

The operational RaceReviewDB contract exposes one stable Google Drive file ID.
This resolver downloads that stored ZIP through the repository's common Drive
bridge, validates the archive, safely extracts it, opens it through the
read-only RaceReviewReader, and caches the accepted generation locally.

A failed download / extraction / reader validation never replaces the existing
accepted local cache state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jrdb_postrace_review_reader import RaceReviewReader

STABLE_CURRENT_FILE_ID = "1UwNfrupMTHRPhkzULPvClGre4MWz2TFg"
EXPECTED_CURRENT_FILENAME = "RaceReviewDB_CURRENT.zip"
RESOLVER_VERSION = "RaceNote-RaceReview-Current-Resolver-0.1"
STATE_FILENAME = "racereview_current_resolver_state.json"


class RaceReviewCurrentResolverError(RuntimeError):
    """Raised when the operational CURRENT snapshot cannot be resolved."""


@dataclass(frozen=True)
class ResolvedRaceReviewCurrent:
    """One validated local RaceReviewDB CURRENT generation."""

    root: Path
    reader: RaceReviewReader
    provenance: dict[str, object]


def _repo_root() -> Path:
    """Return repository root from this source file location."""
    return Path(__file__).resolve().parents[3]


def _drive_api():
    """Import the repository's common Google Drive byte bridge."""
    root = _repo_root()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        from tools.gpt_io.gdrive import gdrive_api
    except Exception as exc:
        raise RaceReviewCurrentResolverError(
            "repository Google Drive bridge is unavailable"
        ) from exc
    return gdrive_api


def _sha256(path: Path) -> str:
    """Return SHA-256 for one stored file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RaceReviewCurrentResolverError(
            f"unreadable resolver state: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RaceReviewCurrentResolverError(
            f"resolver state must be an object: {path}"
        )
    return value


def _safe_member_path(root: Path, member_name: str) -> Path:
    """Return safe extraction target and reject path traversal."""
    candidate = (root / member_name).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise RaceReviewCurrentResolverError(
            f"unsafe ZIP member path: {member_name}"
        ) from exc
    return candidate


def _extract_zip_safely(zip_path: Path, destination: Path) -> Path:
    """Validate and safely extract one RaceReviewDB ZIP.

    Returns the unique directory that directly contains current.json.
    """
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise RaceReviewCurrentResolverError(
                    f"corrupt ZIP member: {bad_member}"
                )
            for member in archive.infolist():
                target = _safe_member_path(destination, member.filename)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source:
                    with target.open("wb") as output:
                        shutil.copyfileobj(source, output)
    except RaceReviewCurrentResolverError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise RaceReviewCurrentResolverError(
            "RaceReviewDB CURRENT is not a valid ZIP"
        ) from exc

    current_files = sorted(destination.rglob("current.json"))
    if len(current_files) != 1:
        raise RaceReviewCurrentResolverError(
            "RaceReviewDB ZIP must contain exactly one current.json"
        )
    return current_files[0].parent


def _drive_fingerprint(meta: dict[str, Any]) -> dict[str, object]:
    """Normalize stable Drive metadata used for cache-hit detection."""
    return {
        "file_id": str(meta.get("id") or ""),
        "name": str(meta.get("name") or ""),
        "modified_time": str(meta.get("modifiedTime") or ""),
        "size_bytes": int(meta.get("size") or 0),
        "md5_checksum": str(meta.get("md5Checksum") or ""),
    }


def _same_fingerprint(
    state: dict[str, Any],
    fingerprint: dict[str, object],
) -> bool:
    """Return whether resolver state points at the same Drive object bytes."""
    stored = state.get("drive")
    if not isinstance(stored, dict):
        return False
    for key, value in fingerprint.items():
        if stored.get(key) != value:
            return False
    return True


def _write_state_atomic(path: Path, state: dict[str, object]) -> None:
    """Atomically publish local resolver state after all validation passes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _validated_cached(
    cache_root: Path,
    state: dict[str, Any],
    fingerprint: dict[str, object],
) -> ResolvedRaceReviewCurrent | None:
    """Return validated cache hit or None."""
    if not _same_fingerprint(state, fingerprint):
        return None

    generation_id = str(state.get("generation_id") or "")
    relative = str(state.get("root_relative_path") or "")
    if not generation_id or not relative:
        return None

    root = (cache_root / relative).resolve()
    try:
        root.relative_to(cache_root.resolve())
    except ValueError:
        return None
    if not root.is_dir():
        return None

    try:
        reader = RaceReviewReader(root)
    except Exception:
        return None
    if reader.generation_id != generation_id:
        return None

    provenance = {
        "resolver_version": RESOLVER_VERSION,
        "cache_status": "HIT",
        "drive": fingerprint,
        "generation_id": reader.generation_id,
        "period_from": reader.period_from,
        "period_to": reader.period_to,
        "review_schema_version": reader.review_schema_version,
        "review_logic_version": reader.review_logic_version,
        "baseline_version": reader.baseline_version,
        "root": str(root),
        "zip_sha256": str(state.get("zip_sha256") or ""),
    }
    return ResolvedRaceReviewCurrent(
        root=root,
        reader=reader,
        provenance=provenance,
    )


def resolve_racereview_current(
    cache_root: Path,
    *,
    file_id: str = STABLE_CURRENT_FILE_ID,
    force_refresh: bool = False,
    service: Any | None = None,
    automation_root_id: str | None = None,
) -> ResolvedRaceReviewCurrent:
    """Resolve stable Drive CURRENT to one validated local generation."""
    api = _drive_api()
    cache_root = Path(cache_root).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    state_path = cache_root / STATE_FILENAME

    if service is None:
        service, automation_root_id = api.load_service(
            automation_root_id
        )
    if not automation_root_id:
        raise RaceReviewCurrentResolverError(
            "Drive automation root is required"
        )

    try:
        api.assert_under_root(
            service,
            file_id,
            automation_root_id,
        )
        drive_meta = api.metadata(service, file_id)
    except Exception as exc:
        raise RaceReviewCurrentResolverError(
            "failed to resolve RaceReviewDB stable Drive CURRENT"
        ) from exc

    fingerprint = _drive_fingerprint(drive_meta)
    if fingerprint["file_id"] != file_id:
        raise RaceReviewCurrentResolverError(
            "Drive metadata file ID mismatch"
        )
    if fingerprint["name"] != EXPECTED_CURRENT_FILENAME:
        raise RaceReviewCurrentResolverError(
            "stable RaceReviewDB file has unexpected name"
        )

    if not force_refresh and state_path.is_file():
        try:
            state = _read_json(state_path)
            cached = _validated_cached(
                cache_root,
                state,
                fingerprint,
            )
            if cached is not None:
                return cached
        except RaceReviewCurrentResolverError:
            pass

    with tempfile.TemporaryDirectory(
        prefix="racereview-current-",
        dir=str(cache_root),
    ) as temp_dir:
        staging = Path(temp_dir)
        zip_path = staging / EXPECTED_CURRENT_FILENAME
        try:
            downloaded = api.download(
                service,
                file_id,
                zip_path,
                force=False,
            )
        except Exception as exc:
            raise RaceReviewCurrentResolverError(
                "RaceReviewDB CURRENT download failed"
            ) from exc

        zip_sha256 = str(
            downloaded.get("sha256") or _sha256(zip_path)
        )
        extracted = staging / "extracted"
        extracted_root = _extract_zip_safely(
            zip_path,
            extracted,
        )

        try:
            reader = RaceReviewReader(extracted_root)
        except Exception as exc:
            raise RaceReviewCurrentResolverError(
                "downloaded RaceReviewDB CURRENT failed reader validation"
            ) from exc

        generation_id = reader.generation_id
        if not generation_id:
            raise RaceReviewCurrentResolverError(
                "RaceReviewDB generation_id is empty"
            )

        generations = cache_root / "generations"
        generations.mkdir(parents=True, exist_ok=True)
        accepted_root = generations / generation_id

        if accepted_root.exists():
            try:
                accepted_reader = RaceReviewReader(accepted_root)
            except Exception as exc:
                raise RaceReviewCurrentResolverError(
                    "existing cached generation is invalid"
                ) from exc
            if accepted_reader.generation_id != generation_id:
                raise RaceReviewCurrentResolverError(
                    "cached generation identity mismatch"
                )
            reader = accepted_reader
        else:
            shutil.move(
                str(extracted_root),
                str(accepted_root),
            )
            try:
                reader = RaceReviewReader(accepted_root)
            except Exception as exc:
                shutil.rmtree(accepted_root, ignore_errors=True)
                raise RaceReviewCurrentResolverError(
                    "accepted local generation failed read-back"
                ) from exc

        relative_root = accepted_root.relative_to(cache_root)
        state = {
            "resolver_version": RESOLVER_VERSION,
            "drive": fingerprint,
            "generation_id": reader.generation_id,
            "period_from": reader.period_from,
            "period_to": reader.period_to,
            "review_schema_version": reader.review_schema_version,
            "review_logic_version": reader.review_logic_version,
            "baseline_version": reader.baseline_version,
            "root_relative_path": str(relative_root),
            "zip_sha256": zip_sha256,
        }
        _write_state_atomic(state_path, state)

        provenance = {
            "resolver_version": RESOLVER_VERSION,
            "cache_status": "REFRESHED",
            "drive": fingerprint,
            "generation_id": reader.generation_id,
            "period_from": reader.period_from,
            "period_to": reader.period_to,
            "review_schema_version": reader.review_schema_version,
            "review_logic_version": reader.review_logic_version,
            "baseline_version": reader.baseline_version,
            "root": str(accepted_root),
            "zip_sha256": zip_sha256,
        }
        return ResolvedRaceReviewCurrent(
            root=accepted_root,
            reader=reader,
            provenance=provenance,
        )


def main() -> int:
    """Resolve operational CURRENT and print validated provenance."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument(
        "--file-id",
        default=STABLE_CURRENT_FILE_ID,
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
    )
    args = parser.parse_args()

    resolved = resolve_racereview_current(
        args.cache_root,
        file_id=args.file_id,
        force_refresh=args.force_refresh,
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                **resolved.provenance,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
