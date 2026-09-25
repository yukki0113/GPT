#!/usr/bin/env python3
"""Resolve and validate immutable JRDB Edge Feature Mart Parquet generations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

ARTIFACT_TYPE = "jrdb_edge_feature_mart"
SCHEMA_VERSION = "v0.2"
STORAGE_FORMAT = "parquet"
FACT_TABLE = "edge_runner_fact"
CANONICAL_KEY = ["race_key", "horse_no"]


class EdgeFeatureMartParquetError(RuntimeError):
    """Raised when the Feature Mart current pointer or generation is invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EdgeFeatureMartParquetError(f"Unreadable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EdgeFeatureMartParquetError(f"JSON object required: {path}")
    return value


def _relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EdgeFeatureMartParquetError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise EdgeFeatureMartParquetError(f"Unsafe {label}: {value}")
    resolved_root = root.resolve()
    resolved = (root / path).resolve()
    if resolved_root not in (resolved, *resolved.parents):
        raise EdgeFeatureMartParquetError(f"{label} escapes root: {value}")
    return resolved


def validate_generation(root: Path, manifest_path: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        raise EdgeFeatureMartParquetError("Unexpected artifact_type")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise EdgeFeatureMartParquetError("Unexpected schema_version")
    if manifest.get("storage_format") != STORAGE_FORMAT:
        raise EdgeFeatureMartParquetError("Unexpected storage_format")
    if manifest.get("validation_status") != "PASS":
        raise EdgeFeatureMartParquetError("Generation validation_status is not PASS")
    if manifest.get("canonical_key") != CANONICAL_KEY:
        raise EdgeFeatureMartParquetError("Unexpected canonical_key")
    generation_id = manifest.get("generation_id")
    if not isinstance(generation_id, str) or not generation_id:
        raise EdgeFeatureMartParquetError("generation_id missing")

    asset = manifest.get("fact_asset")
    if not isinstance(asset, dict):
        raise EdgeFeatureMartParquetError("fact_asset missing")
    if asset.get("name") != FACT_TABLE:
        raise EdgeFeatureMartParquetError("Unexpected fact asset name")
    path = _relative(root, asset.get("relative_path"), "fact_asset.relative_path")
    if not path.is_file():
        raise EdgeFeatureMartParquetError(f"Missing fact asset: {path}")
    size = asset.get("size_bytes")
    if not isinstance(size, int) or size <= 0 or path.stat().st_size != size:
        raise EdgeFeatureMartParquetError("Fact asset size mismatch")
    sha = asset.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64 or _sha256(path) != sha:
        raise EdgeFeatureMartParquetError("Fact asset SHA-256 mismatch")

    con = duckdb.connect()
    try:
        row_count = int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0])
        duplicate_count = int(
            con.execute(
                """
                SELECT count(*) - count(DISTINCT race_key || ':' || CAST(horse_no AS VARCHAR))
                FROM read_parquet(?)
                """,
                [str(path)],
            ).fetchone()[0]
        )
    finally:
        con.close()
    if row_count != manifest.get("row_count"):
        raise EdgeFeatureMartParquetError("Fact row count mismatch")
    if duplicate_count != 0:
        raise EdgeFeatureMartParquetError("Duplicate canonical keys")

    return {
        "generation_id": generation_id,
        "manifest": manifest_path,
        "fact_path": path,
        "rows": row_count,
        "sha256": sha,
        "size_bytes": size,
        "manifest_payload": manifest,
    }


def resolve_current(root: Path) -> dict[str, Any]:
    root = root.resolve()
    pointer = _read_json(root / "current.json")
    generation = pointer.get("generation_id")
    if pointer.get("status") != "CURRENT" or not isinstance(generation, str) or not generation:
        raise EdgeFeatureMartParquetError("Invalid current pointer")
    expected = f"generations/{generation}/manifest.json"
    if pointer.get("manifest") != expected:
        raise EdgeFeatureMartParquetError("Current manifest path does not match generation")
    report = validate_generation(root, _relative(root, expected, "current.manifest"))
    if report["generation_id"] != generation:
        raise EdgeFeatureMartParquetError("Manifest generation_id does not match pointer")
    return {"pointer": pointer, **report}


def connect_current(root: Path) -> tuple[duckdb.DuckDBPyConnection, dict[str, Any]]:
    report = resolve_current(root)
    con = duckdb.connect()
    con.execute("CREATE VIEW edge_runner_fact AS SELECT * FROM read_parquet(?)", [str(report["fact_path"])])
    return con, report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    report = resolve_current(args.root)
    print(json.dumps({
        "status": "PASS",
        "generation_id": report["generation_id"],
        "rows": report["rows"],
        "fact_path": str(report["fact_path"]),
        "sha256": report["sha256"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
