#!/usr/bin/env python3
"""Build one immutable Edge Feature Mart Parquet generation from the existing SQLite mart.

The conversion itself is delegated to tools/data-storage. This module owns only
Edge-specific generation metadata, canonical-key contract, and immutable output layout.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

from data_storage.convert import convert
from data_storage.validate import validate
from jrdb_edge_relational import _is_sqlite_file

ARTIFACT_TYPE = "jrdb_edge_feature_mart"
SCHEMA_VERSION = "v0.2"
STORAGE_FORMAT = "parquet"
CANONICAL_KEY = ["race_key", "horse_no"]
SORT_BY = ["race_date", "race_key", "horse_no"]


class EdgeFeatureMartGenerationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_hash(schema: list[dict[str, Any]]) -> str:
    payload = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_generation(
    *,
    sqlite_path: Path | None = None,
    workspace_path: Path | None = None,
    output_root: Path,
    generation_id: str,
    source_generation_id: str | None = None,
    source_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    source_path = workspace_path or sqlite_path
    if source_path is None or not source_path.is_file():
        raise EdgeFeatureMartGenerationError(f"Feature Mart workspace missing: {source_path}")
    if sqlite_path is not None and workspace_path is not None:
        raise EdgeFeatureMartGenerationError("Specify only one of sqlite_path/workspace_path")
    if not generation_id:
        raise EdgeFeatureMartGenerationError("generation_id is required")

    generation_dir = output_root / "generations" / generation_id
    if generation_dir.exists():
        raise FileExistsError(generation_dir)
    generation_dir.mkdir(parents=True)
    parquet_path = generation_dir / "edge_runner_fact.parquet"
    audit_path = generation_dir / "audit.json"
    manifest_path = generation_dir / "manifest.json"

    if _is_sqlite_file(source_path):
        config = {
            "source": {
                "format": "sqlite",
                "path": str(source_path),
                "table": "edge_runner_fact",
                "batch_size": 50000,
            },
            "target": {
                "path": str(parquet_path),
                "compression": "zstd",
                "partition_by": [],
            },
            "keys": {"canonical": CANONICAL_KEY},
            "sort_by": SORT_BY,
            "validation": {"require_row_count_match": True},
        }
        conversion = convert(config)
        validation = validate(config, conversion)
        if validation.get("status") != "success" or validation.get("passed") is not True:
            audit_path.write_text(
                json.dumps({"status": "FAIL", "conversion": conversion, "validation": validation},
                           ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            raise EdgeFeatureMartGenerationError("tools/data-storage validation failed")
    else:
        connection = duckdb.connect(str(source_path), read_only=True)
        try:
            schema_rows = connection.execute("DESCRIBE edge_runner_fact").fetchall()
            schema = [
                {"name": str(row[0]), "type": str(row[1]).lower(), "nullable": str(row[2]).upper() != "NO"}
                for row in schema_rows
            ]
            row_count = int(connection.execute("SELECT COUNT(*) FROM edge_runner_fact").fetchone()[0])
            duplicate_count = int(
                connection.execute(
                    "SELECT COUNT(*) - COUNT(DISTINCT race_key || ':' || CAST(horse_no AS VARCHAR)) "
                    "FROM edge_runner_fact"
                ).fetchone()[0]
            )
            if duplicate_count:
                raise EdgeFeatureMartGenerationError(
                    f"DuckDB workspace duplicate canonical keys: {duplicate_count}"
                )
            literal = str(parquet_path).replace("'", "''")
            connection.execute(
                "COPY (SELECT * FROM edge_runner_fact ORDER BY race_date,race_key,horse_no) "
                f"TO '{literal}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        finally:
            connection.close()
        verification = duckdb.connect()
        try:
            target_rows = int(
                verification.execute(
                    "SELECT COUNT(*) FROM read_parquet(?)", [str(parquet_path)]
                ).fetchone()[0]
            )
            target_duplicates = int(
                verification.execute(
                    "SELECT COUNT(*) - COUNT(DISTINCT race_key || ':' || CAST(horse_no AS VARCHAR)) "
                    "FROM read_parquet(?)",
                    [str(parquet_path)],
                ).fetchone()[0]
            )
        finally:
            verification.close()
        if target_rows != row_count or target_duplicates:
            raise EdgeFeatureMartGenerationError(
                f"DuckDB->Parquet validation failed rows={target_rows}/{row_count} duplicates={target_duplicates}"
            )
        conversion = {
            "operation": "duckdb_to_parquet",
            "input": [str(source_path)],
            "output": str(parquet_path),
            "compression": "zstd",
            "partition_by": [],
            "row_count_source": row_count,
            "input_size_bytes": source_path.stat().st_size,
            "output_size_bytes": parquet_path.stat().st_size,
            "input_sha256": {source_path.name: _sha256(source_path)},
            "schema": schema,
        }
        validation = {
            "status": "success",
            "passed": True,
            "row_count_match": True,
            "duplicate_key_rows": 0,
        }

    schema = conversion.get("schema")
    if not isinstance(schema, list) or not schema:
        raise EdgeFeatureMartGenerationError("conversion schema missing")
    audit = {
        "status": "PASS",
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generation_id": generation_id,
        "conversion": conversion,
        "validation": validation,
        "canonical_key": CANONICAL_KEY,
        "sort_by": SORT_BY,
    }
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    row_count = int(conversion["row_count_source"])
    manifest = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "storage_format": STORAGE_FORMAT,
        "storage_version": "1",
        "generation_id": generation_id,
        "validation_status": "PASS",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "canonical_key": CANONICAL_KEY,
        "sort_by": SORT_BY,
        "row_count": row_count,
        "schema_hash": _schema_hash(schema),
        "source_workspace_format": "sqlite" if _is_sqlite_file(source_path) else "duckdb",
        "source_workspace_sha256": _sha256(source_path),
        "source_generation_id": source_generation_id,
        "source_manifest_sha256": source_manifest_sha256,
        "fact_asset": {
            "name": "edge_runner_fact",
            "relative_path": f"generations/{generation_id}/edge_runner_fact.parquet",
            "rows": row_count,
            "size_bytes": parquet_path.stat().st_size,
            "sha256": _sha256(parquet_path),
        },
        "audit": {
            "relative_path": f"generations/{generation_id}/audit.json",
            "size_bytes": audit_path.stat().st_size,
            "sha256": _sha256(audit_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "PASS",
        "generation_id": generation_id,
        "row_count": row_count,
        "parquet": str(parquet_path),
        "parquet_sha256": manifest["fact_asset"]["sha256"],
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "audit": str(audit_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sqlite", type=Path)
    source.add_argument("--workspace", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--source-generation-id")
    parser.add_argument("--source-manifest-sha256")
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    result = build_generation(
        sqlite_path=args.sqlite,
        workspace_path=args.workspace,
        output_root=args.output_root,
        generation_id=args.generation_id,
        source_generation_id=args.source_generation_id,
        source_manifest_sha256=args.source_manifest_sha256,
    )
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
