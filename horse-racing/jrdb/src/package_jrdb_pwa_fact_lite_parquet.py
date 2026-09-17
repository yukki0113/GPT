#!/usr/bin/env python3
"""Create and verify the immutable browser-delivery package for Fact Lite Parquet.

This utility deliberately packages a generation from its manifest metadata rather
than exposing a collection of guessed table filenames to a browser consumer.  It
does not alter the SQLite Fact Lite distribution; that cutover is a later PWA
stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


ARTIFACT_TYPE = "jrdb_fact_lite"
SCHEMA_VERSION = "v0.3"
STORAGE_FORMAT = "parquet"
STORAGE_VERSION = "1"
REQUIRED_TABLES = (
    "meta_pwa_fact_build",
    "dim_sire",
    "dim_bms",
    "dim_jockey",
    "dim_race",
    "fact_stats_entry",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def _safe_relative(value: object) -> PurePosixPath:
    relative = PurePosixPath(str(value or ""))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"unsafe package path: {value!r}")
    return relative


def _table_rows(path: Path) -> int:
    sys.path.insert(0, str(ROOT / "tools" / "data-storage"))
    from data_storage.query import connect_parquet

    connection = connect_parquet(path)
    try:
        return int(connection.execute("SELECT COUNT(*) FROM data").fetchone()[0])
    finally:
        connection.close()


def package_generation(
    parquet_dir: Path,
    equivalence_audit: Path,
    data_version: str,
    output_root: Path,
) -> dict[str, Any]:
    """Build a self-contained current pointer and immutable generation directory."""
    if not data_version or any(char not in "0123456789" for char in data_version):
        raise RuntimeError("data_version must be an eight-digit YYYYMMDD value")
    if len(data_version) != 8:
        raise RuntimeError("data_version must be an eight-digit YYYYMMDD value")
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite package root: {output_root}")

    audit = _read_json(equivalence_audit)
    if audit.get("status") != "PASS":
        raise RuntimeError("Fact Lite equivalence audit is not PASS")
    audit_rows = audit.get("table_rows")
    if not isinstance(audit_rows, dict):
        tables = audit.get("tables")
        if isinstance(tables, dict):
            audit_rows = {
                table: entry.get("rows")
                for table, entry in tables.items()
                if isinstance(entry, dict) and "rows" in entry
            }
    if not isinstance(audit_rows, dict):
        raise RuntimeError("equivalence audit table_rows is required")

    generation_id = f"fact-lite-v0_3-{data_version}"
    generation_root = output_root / "generations" / generation_id
    generation_root.mkdir(parents=True)
    tables: dict[str, dict[str, Any]] = {}
    for table in REQUIRED_TABLES:
        source = parquet_dir / f"{table}.parquet"
        if not source.is_file():
            raise RuntimeError(f"required Parquet table missing: {source}")
        row_count = _table_rows(source)
        if table != "meta_pwa_fact_build" and int(audit_rows.get(table, -1)) != row_count:
            raise RuntimeError(f"equivalence audit row mismatch: {table}")
        destination = generation_root / source.name
        shutil.copyfile(source, destination)
        tables[table] = {
            "path": source.name,
            "size_bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "rows": row_count,
        }

    manifest = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "storage_format": STORAGE_FORMAT,
        "storage_version": STORAGE_VERSION,
        "generation_id": generation_id,
        "tables": tables,
        "validation_status": "PASS",
    }
    manifest_path = generation_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    current = {
        "status": "CURRENT",
        "generation_id": generation_id,
        "manifest": f"generations/{generation_id}/manifest.json",
    }
    (output_root / "current.json").write_text(
        json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return verify_package(output_root)


def verify_package(package_root: Path) -> dict[str, Any]:
    """Fail closed on a malformed pointer, manifest, or package asset."""
    current = _read_json(package_root / "current.json")
    generation_id = str(current.get("generation_id") or "")
    if current.get("status") != "CURRENT" or not generation_id:
        raise RuntimeError("invalid Fact Lite Parquet current pointer")
    manifest_relative = _safe_relative(current.get("manifest"))
    expected_manifest = PurePosixPath("generations") / generation_id / "manifest.json"
    if manifest_relative != expected_manifest:
        raise RuntimeError("current pointer manifest path does not match generation")
    manifest_path = package_root.joinpath(*manifest_relative.parts)
    manifest = _read_json(manifest_path)
    expected = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "storage_format": STORAGE_FORMAT,
        "storage_version": STORAGE_VERSION,
        "generation_id": generation_id,
        "validation_status": "PASS",
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Fact Lite Parquet manifest contract mismatch")
    tables = manifest.get("tables")
    if not isinstance(tables, dict) or set(tables) != set(REQUIRED_TABLES):
        raise RuntimeError("Fact Lite Parquet manifest table set mismatch")
    total_size = 0
    for table in REQUIRED_TABLES:
        entry = tables[table]
        if not isinstance(entry, dict):
            raise RuntimeError(f"invalid table entry: {table}")
        relative = _safe_relative(entry.get("path"))
        if len(relative.parts) != 1 or relative.suffix != ".parquet":
            raise RuntimeError(f"invalid table path: {table}")
        asset = manifest_path.parent.joinpath(*relative.parts)
        if not asset.is_file():
            raise RuntimeError(f"Parquet asset missing: {table}")
        size = asset.stat().st_size
        if size != int(entry.get("size_bytes") or -1):
            raise RuntimeError(f"Parquet asset size mismatch: {table}")
        if sha256_file(asset) != str(entry.get("sha256") or ""):
            raise RuntimeError(f"Parquet asset SHA-256 mismatch: {table}")
        if int(entry.get("rows") or -1) < 0:
            raise RuntimeError(f"invalid Parquet row count: {table}")
        total_size += size
    return {
        "generation_id": generation_id,
        "manifest_path": str(manifest_relative),
        "manifest_sha256": sha256_file(manifest_path),
        "manifest_size_bytes": manifest_path.stat().st_size,
        "asset_count": len(REQUIRED_TABLES),
        "asset_size_bytes": total_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    package = subparsers.add_parser("package")
    package.add_argument("--parquet-dir", type=Path, required=True)
    package.add_argument("--equivalence-audit", type=Path, required=True)
    package.add_argument("--data-version", required=True)
    package.add_argument("--output-root", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "package":
        result = package_generation(args.parquet_dir, args.equivalence_audit, args.data_version, args.output_root)
    else:
        result = verify_package(args.package_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
