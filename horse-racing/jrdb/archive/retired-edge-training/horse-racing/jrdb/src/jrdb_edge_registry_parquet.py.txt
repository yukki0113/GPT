#!/usr/bin/env python3
"""Resolve validated Edge Registry Parquet current generations and compatibility views."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

ARTIFACT_TYPE = "jrdb_edge_registry"
SCHEMA_VERSION = "v0.2"
STORAGE_FORMAT = "parquet"
TABLES = {
    "edge_registry_meta": ["registry_version"],
    "edge_definition": ["edge_id"],
    "edge_metric_snapshot": ["edge_id", "snapshot_id"],
    "edge_validation_event": ["validation_id"],
    "edge_statistical_guard": ["edge_id"],
}


class EdgeRegistryParquetError(RuntimeError):
    """Raised when the canonical Registry generation cannot be trusted."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EdgeRegistryParquetError(f"Unreadable JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise EdgeRegistryParquetError(f"JSON object required: {path}")
    return payload


def _relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EdgeRegistryParquetError(f"{label} must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise EdgeRegistryParquetError(f"Unsafe {label}: {value}")
    base = root.resolve()
    resolved = (root / relative).resolve()
    if base not in (resolved, *resolved.parents):
        raise EdgeRegistryParquetError(f"{label} escapes root: {value}")
    return resolved


def validate_generation(root: Path, manifest_path: Path) -> dict[str, Any]:
    """Validate immutable Registry assets against the generation manifest."""
    root = root.resolve()
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        raise EdgeRegistryParquetError("Unexpected artifact_type")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise EdgeRegistryParquetError("Unexpected schema_version")
    if manifest.get("storage_format") != STORAGE_FORMAT:
        raise EdgeRegistryParquetError("Unexpected storage_format")
    if manifest.get("validation_status") != "PASS":
        raise EdgeRegistryParquetError("Generation validation_status is not PASS")
    generation_id = manifest.get("generation_id")
    if not isinstance(generation_id, str) or not generation_id:
        raise EdgeRegistryParquetError("generation_id missing")

    table_assets = manifest.get("tables")
    if not isinstance(table_assets, dict):
        raise EdgeRegistryParquetError("Registry table assets missing")

    tables: dict[str, dict[str, Any]] = {}
    connection = duckdb.connect()
    try:
        for table, expected_key in TABLES.items():
            asset = table_assets.get(table)
            if not isinstance(asset, dict):
                raise EdgeRegistryParquetError(f"Missing table asset: {table}")
            if asset.get("canonical_key") != expected_key:
                raise EdgeRegistryParquetError(f"Unexpected canonical key: {table}")
            path = _relative(root, asset.get("relative_path"), f"{table}.relative_path")
            if not path.is_file():
                raise EdgeRegistryParquetError(f"Missing Registry asset: {path}")
            size = asset.get("size_bytes")
            sha = asset.get("sha256")
            if not isinstance(size, int) or size <= 0 or path.stat().st_size != size:
                raise EdgeRegistryParquetError(f"Registry asset size mismatch: {table}")
            if not isinstance(sha, str) or len(sha) != 64 or _sha256(path) != sha:
                raise EdgeRegistryParquetError(f"Registry asset SHA-256 mismatch: {table}")
            rows = int(connection.execute(
                "SELECT count(*) FROM read_parquet(?)", [str(path)]
            ).fetchone()[0])
            if rows != asset.get("rows"):
                raise EdgeRegistryParquetError(f"Registry row count mismatch: {table}")
            key_expr = " || '|' || ".join(
                f"COALESCE(CAST({column} AS VARCHAR),'<NULL>')" for column in expected_key
            )
            duplicates = int(connection.execute(
                f"SELECT count(*)-count(DISTINCT {key_expr}) FROM read_parquet(?)",
                [str(path)],
            ).fetchone()[0])
            if duplicates != 0:
                raise EdgeRegistryParquetError(f"Duplicate canonical keys: {table}")
            tables[table] = {
                "path": path,
                "rows": rows,
                "size_bytes": size,
                "sha256": sha,
                "canonical_key": expected_key,
            }
    finally:
        connection.close()

    serving = None
    serving_asset = manifest.get("serving_catalog")
    if serving_asset is not None:
        if not isinstance(serving_asset, dict):
            raise EdgeRegistryParquetError("Invalid serving_catalog manifest entry")
        path = _relative(root, serving_asset.get("relative_path"), "serving_catalog.relative_path")
        if not path.is_file():
            raise EdgeRegistryParquetError(f"Missing serving catalog: {path}")
        size = serving_asset.get("size_bytes")
        sha = serving_asset.get("sha256")
        if not isinstance(size, int) or size <= 0 or path.stat().st_size != size:
            raise EdgeRegistryParquetError("Serving catalog size mismatch")
        if not isinstance(sha, str) or len(sha) != 64 or _sha256(path) != sha:
            raise EdgeRegistryParquetError("Serving catalog SHA-256 mismatch")
        serving = {"path": path, "size_bytes": size, "sha256": sha}

    return {
        "generation_id": generation_id,
        "manifest": manifest_path,
        "manifest_payload": manifest,
        "tables": tables,
        "serving_catalog": serving,
    }


def resolve_current(root: Path) -> dict[str, Any]:
    """Resolve current.json and fail closed on pointer/generation drift."""
    root = root.resolve()
    pointer = _read_json(root / "current.json")
    generation_id = pointer.get("generation_id")
    if pointer.get("status") != "CURRENT" or not isinstance(generation_id, str) or not generation_id:
        raise EdgeRegistryParquetError("Invalid Registry current pointer")
    expected_manifest = f"generations/{generation_id}/manifest.json"
    if pointer.get("manifest") != expected_manifest:
        raise EdgeRegistryParquetError("Current manifest path does not match generation")
    report = validate_generation(root, _relative(root, expected_manifest, "current.manifest"))
    if report["generation_id"] != generation_id:
        raise EdgeRegistryParquetError("Manifest generation_id does not match pointer")
    return {"pointer": pointer, **report}


def _sql_type(data_type: pa.DataType) -> str:
    if pa.types.is_integer(data_type) or pa.types.is_boolean(data_type):
        return "INTEGER"
    if pa.types.is_floating(data_type) or pa.types.is_decimal(data_type):
        return "REAL"
    if pa.types.is_binary(data_type) or pa.types.is_large_binary(data_type):
        return "BLOB"
    return "TEXT"


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def materialize_current_sqlite(root: Path, output: Path) -> dict[str, Any]:
    """LEGACY_REPRO only: create SQLite from validated Registry Parquet current."""
    report = resolve_current(root)
    if output.exists():
        raise EdgeRegistryParquetError(f"Refusing to overwrite compatibility SQLite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        for table, expected_key in TABLES.items():
            parquet_path = report["tables"][table]["path"]
            pf = pq.ParquetFile(parquet_path)
            schema = pf.schema_arrow
            definitions = [f"{_quote(field.name)} {_sql_type(field.type)}" for field in schema]
            connection.execute(f"CREATE TABLE {_quote(table)} (" + ",".join(definitions) + ")")
            placeholders = ",".join("?" for _ in schema)
            insert_sql = f"INSERT INTO {_quote(table)} VALUES (" + placeholders + ")"
            connection.execute("BEGIN")
            for batch in pf.iter_batches(batch_size=5000):
                columns = [batch.column(index).to_pylist() for index in range(batch.num_columns)]
                connection.executemany(insert_sql, zip(*columns))
            connection.commit()
            actual = int(connection.execute(f"SELECT count(*) FROM {_quote(table)}").fetchone()[0])
            if actual != report["tables"][table]["rows"]:
                raise EdgeRegistryParquetError(
                    f"Compatibility SQLite row mismatch {table}: "
                    f"expected={report['tables'][table]['rows']} actual={actual}"
                )
            index_columns = ",".join(_quote(value) for value in expected_key)
            connection.execute(
                f"CREATE UNIQUE INDEX {_quote('compat_' + table + '_key')} "
                f"ON {_quote(table)} ({index_columns})"
            )
        connection.commit()
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise EdgeRegistryParquetError(f"Compatibility SQLite integrity failed: {integrity}")
    except Exception:
        connection.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass
    return {
        "status": "PASS",
        "source_mode": "parquet_canonical",
        "compatibility_role": "legacy_repro_sqlite",
        "generation_id": report["generation_id"],
        "table_rows": {name: item["rows"] for name, item in report["tables"].items()},
        "output": str(output),
    }



def connect_current(root: Path) -> tuple[duckdb.DuckDBPyConnection, dict[str, Any]]:
    """Open validated Registry current directly as DuckDB views.

    This is the normal canonical read path. Parquet must not be materialized
    back into SQLite for current research/serving reads.
    """
    report = resolve_current(root)
    connection = duckdb.connect()
    try:
        for table, item in report["tables"].items():
            literal = str(item["path"]).replace("'", "''")
            connection.execute(
                f'CREATE VIEW "{table}" AS SELECT * FROM read_parquet(\'{literal}\')'
            )
    except Exception:
        connection.close()
        raise
    return connection, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--legacy-materialize-sqlite",
        type=Path,
        help="Legacy reproduction only; current consumers must use Parquet/DuckDB.",
    )
    args = parser.parse_args()
    if args.legacy_materialize_sqlite is not None:
        result = materialize_current_sqlite(args.root, args.legacy_materialize_sqlite)
        result["deprecated"] = True
        result["operational_role"] = "LEGACY_REPRO_ONLY"
    else:
        report = resolve_current(args.root)
        result = {
            "status": "PASS",
            "generation_id": report["generation_id"],
            "table_rows": {name: item["rows"] for name, item in report["tables"].items()},
            "serving_sha256": (
                report["serving_catalog"]["sha256"] if report["serving_catalog"] else None
            ),
            "canonical_read_mode": "PARQUET_DUCKDB",
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
