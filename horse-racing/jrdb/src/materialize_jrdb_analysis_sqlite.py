#!/usr/bin/env python3
"""Materialize a verified Analysis Parquet current generation into temporary SQLite."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "data-storage"))

from data_storage.query import connect_parquet
from jrdb_analysis_parquet_current import (
    CANONICAL_KEY,
    FACT_TABLE,
    METADATA_TABLES,
    resolve_current,
    validate_generation,
)


def load_parquet(sqlite: sqlite3.Connection, table: str, path: Path) -> None:
    """Copy one verified Parquet object into an already-created SQLite table."""
    duck = connect_parquet(path)
    try:
        columns = [row[0] for row in duck.execute("DESCRIBE data").fetchall()]
        rows = duck.execute("SELECT * FROM data").fetchall()
    finally:
        duck.close()
    marks = ",".join("?" for _ in columns)
    names = ",".join(f'"{column}"' for column in columns)
    sqlite.executemany(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', rows)


def _table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def _validate_sqlite(
    connection: sqlite3.Connection, manifest: dict[str, Any], expected_rows: int
) -> dict[str, Any]:
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("materialized Analysis integrity_check failed")
    columns = _table_columns(connection, FACT_TABLE)
    if not set(CANONICAL_KEY).issubset(columns):
        raise RuntimeError("materialized Analysis canonical key columns are missing")
    rows = int(connection.execute(f'SELECT COUNT(*) FROM "{FACT_TABLE}"').fetchone()[0])
    if rows != expected_rows:
        raise RuntimeError(f"materialized Analysis row count mismatch: {rows} != {expected_rows}")
    duplicates = int(
        connection.execute(
            f'SELECT COUNT(*) FROM (SELECT "race_key","horse_no" FROM "{FACT_TABLE}" '
            'GROUP BY "race_key","horse_no" HAVING COUNT(*) > 1)'
        ).fetchone()[0]
    )
    if duplicates:
        raise RuntimeError(f"materialized Analysis duplicate canonical keys: {duplicates}")
    metadata_counts: dict[str, int] = {}
    for table in METADATA_TABLES:
        count = int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        expected = manifest["metadata_tables"][table].get("rows")
        if count != expected:
            raise RuntimeError(f"materialized metadata row count mismatch: {table}")
        metadata_counts[table] = count
    return {
        "status": "PASS",
        "rows": rows,
        "duplicate_canonical_keys": duplicates,
        "metadata_rows": metadata_counts,
        "integrity_check": "ok",
    }


def materialize_generation(
    root: Path, manifest_path: Path, output: Path, schema: Path
) -> dict[str, Any]:
    """Materialize only a full, already-validated immutable generation."""
    if output.exists():
        raise FileExistsError(output)
    report = validate_generation(root, manifest_path)
    manifest = report["manifest"]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output)
    try:
        connection.executescript(schema.read_text(encoding="utf-8"))
        for partition in payload["fact_table"]["partitions"]:
            load_parquet(connection, FACT_TABLE, root / partition["relative_path"])
        for table in sorted(METADATA_TABLES):
            load_parquet(connection, table, root / payload["metadata_tables"][table]["relative_path"])
        connection.commit()
        return {
            "generation_id": report["generation_id"],
            "manifest_path": str(manifest_path),
            **_validate_sqlite(connection, payload, report["rows"]),
        }
    except Exception:
        connection.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        if connection:
            connection.close()


def materialize_current(root: Path, output: Path, schema: Path) -> dict[str, Any]:
    """Resolve current.json first; never materialize a non-current generation by default."""
    current = resolve_current(root)
    return materialize_generation(root.resolve(), current["manifest"], output, schema)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_analysis_schema_v1_3.sql",
    )
    args = parser.parse_args()
    print(materialize_current(args.analysis_root, args.out, args.schema))


if __name__ == "__main__":
    main()
