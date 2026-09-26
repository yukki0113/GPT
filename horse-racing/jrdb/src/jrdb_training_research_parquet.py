#!/usr/bin/env python3
"""Resolve and validate the current JRDB Training Research Parquet generation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CANONICAL_KEY = ["race_key", "horse_no"]
ARTIFACT_TYPE = "jrdb_training_research"
SCHEMA_VERSION = "v0.1"
STORAGE_FORMAT = "parquet"
DEVELOPMENT_ASSET = "training_development.parquet"
DEVELOPMENT_LOGICAL_URI = "jrdb://training-research/v0.1/development"


class TrainingResearchParquetError(RuntimeError):
    """Raised when the Training Research current generation fails closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingResearchParquetError(f"Unreadable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise TrainingResearchParquetError(f"JSON object required: {path}")
    return value


def _relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise TrainingResearchParquetError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise TrainingResearchParquetError(f"Unsafe {label}: {value}")
    root = root.resolve()
    resolved = (root / path).resolve()
    if root not in (resolved, *resolved.parents):
        raise TrainingResearchParquetError(f"{label} escapes root: {value}")
    return resolved


def validate_generation(root: Path, manifest_path: Path) -> dict[str, Any]:
    """Validate the development asset of one immutable Training Research generation."""
    import duckdb

    root = root.resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        raise TrainingResearchParquetError("Unexpected artifact_type")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise TrainingResearchParquetError("Unexpected schema_version")
    if manifest.get("storage_format") != STORAGE_FORMAT:
        raise TrainingResearchParquetError("Unexpected storage_format")
    if manifest.get("canonical_key") != CANONICAL_KEY:
        raise TrainingResearchParquetError("Unexpected canonical_key")

    generation_id = manifest.get("generation_id")
    if not isinstance(generation_id, str) or not generation_id:
        raise TrainingResearchParquetError("generation_id missing")

    logical_uris = manifest.get("logical_uris")
    if not isinstance(logical_uris, dict):
        raise TrainingResearchParquetError("logical_uris missing")
    if logical_uris.get(DEVELOPMENT_LOGICAL_URI) != DEVELOPMENT_ASSET:
        raise TrainingResearchParquetError("Unexpected development logical URI target")

    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        raise TrainingResearchParquetError("assets missing")
    asset = assets.get(DEVELOPMENT_ASSET)
    if not isinstance(asset, dict):
        raise TrainingResearchParquetError("development asset missing")
    if asset.get("filename") != DEVELOPMENT_ASSET:
        raise TrainingResearchParquetError("development filename mismatch")

    development_path = manifest_path.parent / DEVELOPMENT_ASSET
    if not development_path.is_file():
        raise TrainingResearchParquetError(f"Missing development asset: {development_path}")
    size = asset.get("size_bytes")
    if not isinstance(size, int) or size <= 0 or development_path.stat().st_size != size:
        raise TrainingResearchParquetError("development size mismatch")
    sha = asset.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64 or _sha256(development_path) != sha:
        raise TrainingResearchParquetError("development SHA-256 mismatch")

    connection = duckdb.connect()
    try:
        row_count, min_year, max_year = connection.execute(
            "SELECT count(*), min(year), max(year) FROM read_parquet(?)",
            [str(development_path)],
        ).fetchone()
        duplicate_count = connection.execute(
            """
            SELECT count(*) FROM (
              SELECT race_key,horse_no,count(*) AS n
              FROM read_parquet(?)
              GROUP BY race_key,horse_no
              HAVING count(*)>1
            )
            """,
            [str(development_path)],
        ).fetchone()[0]
    finally:
        connection.close()

    expected_rows = asset.get("row_count")
    if not isinstance(expected_rows, int) or int(row_count) != expected_rows:
        raise TrainingResearchParquetError("development row count mismatch")
    if int(duplicate_count) != 0:
        raise TrainingResearchParquetError("duplicate canonical keys in development asset")
    if min_year != 2010 or max_year != 2023:
        raise TrainingResearchParquetError(
            f"development year contract failed: {min_year}..{max_year}"
        )

    return {
        "generation_id": generation_id,
        "manifest": str(manifest_path),
        "development_path": development_path,
        "rows": int(row_count),
        "min_year": int(min_year),
        "max_year": int(max_year),
        "duplicate_keys": int(duplicate_count),
        "sha256": sha,
        "size_bytes": size,
        "manifest_payload": manifest,
    }


def resolve_current(root: Path) -> dict[str, Any]:
    """Resolve current.json and validate its development Parquet asset."""
    root = root.resolve()
    pointer = _read_json(root / "current.json")
    generation_id = pointer.get("generation_id")
    if pointer.get("status") != "SUCCESS":
        raise TrainingResearchParquetError("Training Research current is not SUCCESS")
    if not isinstance(generation_id, str) or not generation_id:
        raise TrainingResearchParquetError("current generation_id missing")
    expected_manifest = f"build-{generation_id}/manifest.json"
    if pointer.get("manifest") != expected_manifest:
        raise TrainingResearchParquetError("current manifest path mismatch")

    manifest_path = _relative(root, expected_manifest, "current.manifest")
    report = validate_generation(root, manifest_path)
    if report["generation_id"] != generation_id:
        raise TrainingResearchParquetError("manifest generation_id does not match current")
    return {"pointer": pointer, **report}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    report = resolve_current(args.root)
    print(json.dumps({
        "status": "PASS",
        "generation_id": report["generation_id"],
        "development_path": str(report["development_path"]),
        "rows": report["rows"],
        "min_year": report["min_year"],
        "max_year": report["max_year"],
        "duplicate_keys": report["duplicate_keys"],
        "sha256": report["sha256"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
