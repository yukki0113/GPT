#!/usr/bin/env python3
"""Publish and promote one immutable Analysis Parquet generation safely.

``drive_root`` is a Drive-mounted/synchronised upload directory.
``roundtrip_root`` is a separately re-downloaded copy of that Drive root after
the candidate assets have been uploaded.  No API credential is held by this
module.  The independent round-trip copy is mandatory before pointer promotion.

The module never overwrites an immutable asset.  It publishes only a new
generation and advances ``current.json`` after remote round-trip validation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from jrdb_analysis_parquet_current import resolve_current, validate_generation


class AnalysisDrivePublishError(RuntimeError):
    """Raised when an Analysis Drive publication cannot be promoted safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisDrivePublishError(f"Unreadable JSON: {path}") from error
    if not isinstance(value, dict):
        raise AnalysisDrivePublishError(f"JSON object required: {path}")
    return value


def _safe(relative: object) -> Path:
    value = PurePosixPath(str(relative or ""))
    if not value.parts or value.is_absolute() or ".." in value.parts:
        raise AnalysisDrivePublishError(f"Unsafe artifact path: {relative!r}")
    return Path(*value.parts)


def _asset_paths(manifest: dict[str, Any], generation_id: str) -> list[Path]:
    fact = manifest.get("fact_table")
    metadata = manifest.get("metadata_tables")
    if not isinstance(fact, dict) or not isinstance(metadata, dict):
        raise AnalysisDrivePublishError("Candidate manifest lacks fact or metadata entries")
    paths = [Path("generations") / generation_id / "manifest.json", Path("generations") / generation_id / "audit.json"]
    for entry in fact.get("partitions", []):
        if not isinstance(entry, dict):
            raise AnalysisDrivePublishError("Invalid fact entry")
        paths.append(_safe(entry.get("relative_path")))
    for entry in metadata.values():
        if not isinstance(entry, dict):
            raise AnalysisDrivePublishError("Invalid metadata entry")
        paths.append(_safe(entry.get("relative_path")))
    if len(set(paths)) != len(paths):
        raise AnalysisDrivePublishError("Duplicate candidate artifact path")
    return paths


def _copy_immutable(source_root: Path, target_root: Path, relative: Path) -> None:
    source, target = source_root / relative, target_root / relative
    if not source.is_file():
        raise AnalysisDrivePublishError(f"Candidate artifact missing: {relative}")
    if target.exists():
        if not target.is_file() or target.stat().st_size != source.stat().st_size or _sha256(target) != _sha256(source):
            raise AnalysisDrivePublishError(f"Immutable Drive artifact collision: {relative}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if target.stat().st_size != source.stat().st_size or _sha256(target) != _sha256(source):
        raise AnalysisDrivePublishError(f"Drive artifact copy validation failed: {relative}")


def _audit_gate(audit: dict[str, Any]) -> None:
    expected = {
        "status": "PASS", "row_count_equal": True, "canonical_key_equal": True,
        "schema_contract_equal": True, "row_level_equivalence": True,
        "metadata_preserved": True, "duplicate_key_rows": 0,
    }
    for key, value in expected.items():
        if audit.get(key) != value:
            raise AnalysisDrivePublishError(f"Remote audit gate failed: {key}")


def publish_and_promote(
    candidate_root: Path, drive_root: Path, roundtrip_root: Path, generation_id: str
) -> dict[str, Any]:
    """Copy assets, validate an independently re-fetched root, then promote."""
    candidate_root, drive_root, roundtrip_root = (
        candidate_root.resolve(), drive_root.resolve(), roundtrip_root.resolve()
    )
    if roundtrip_root == drive_root:
        raise ValueError("roundtrip_root must be a separately re-downloaded directory")
    if not generation_id:
        raise ValueError("generation_id is required")
    candidate_manifest_path = candidate_root / "generations" / generation_id / "manifest.json"
    candidate = validate_generation(candidate_root, candidate_manifest_path)
    if candidate.get("generation_id") != generation_id:
        raise AnalysisDrivePublishError("Candidate manifest generation does not match request")
    candidate_manifest = _read_json(candidate_manifest_path)
    asset_paths = _asset_paths(candidate_manifest, generation_id)

    current_path = drive_root / "current.json"
    current_before = current_path.read_bytes()
    previous = resolve_current(drive_root)
    if (drive_root / "generations" / generation_id).exists():
        raise FileExistsError(drive_root / "generations" / generation_id)
    for relative in asset_paths:
        _copy_immutable(candidate_root, drive_root, relative)

    remote_current_before = (roundtrip_root / "current.json").read_bytes()
    remote_previous = resolve_current(roundtrip_root)
    if remote_previous["generation_id"] != previous["generation_id"]:
        raise AnalysisDrivePublishError("Drive current generation changed before round-trip validation")
    remote_manifest_path = roundtrip_root / "generations" / generation_id / "manifest.json"
    remote = validate_generation(roundtrip_root, remote_manifest_path)
    if remote.get("generation_id") != generation_id or remote.get("rows") != candidate.get("rows"):
        raise AnalysisDrivePublishError("Drive round-trip generation mismatch")
    _audit_gate(_read_json(remote_manifest_path.with_name("audit.json")))
    if current_path.read_bytes() != current_before or (roundtrip_root / "current.json").read_bytes() != remote_current_before:
        raise AnalysisDrivePublishError("Drive current.json changed during candidate publication")

    pointer = {
        "status": "CURRENT",
        "generation_id": generation_id,
        "manifest": f"generations/{generation_id}/manifest.json",
        "previous_generation_id": previous["generation_id"],
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    pending = current_path.with_suffix(".json.pending")
    pending.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(current_path)
    return {
        "status": "PROMOTED",
        "generation_id": generation_id,
        "previous_generation_id": previous["generation_id"],
        "manifest": pointer["manifest"],
        "rows": remote["rows"],
        "asset_count": len(asset_paths),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--drive-root", required=True, type=Path)
    parser.add_argument("--roundtrip-root", required=True, type=Path,
                        help="separately re-downloaded Drive root after asset upload")
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    result = publish_and_promote(args.candidate_root, args.drive_root, args.roundtrip_root, args.generation_id)
    if args.result_json:
        args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
