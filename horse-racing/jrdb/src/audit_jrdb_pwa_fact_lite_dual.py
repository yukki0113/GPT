#!/usr/bin/env python3
"""Fail-closed semantic equivalence audit for Fact Lite dual outputs.

This intentionally compares logical values, not SQLite pages or Parquet physical
types.  It is used before a new SQLite artifact may replace the PWA delivery
generation.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "data-storage"))
from data_storage.query import connect_parquet

TABLES = ("dim_sire", "dim_bms", "dim_jockey", "dim_race", "fact_stats_entry")
META_COLUMNS = ("builder_version", "schema_version", "source_analysis", "status", "row_count", "period_from", "period_to")


def _value(value: Any) -> str:
    if value is None:
        return "N:"
    if isinstance(value, bytes):
        return "B:" + base64.b64encode(value).decode("ascii")
    if isinstance(value, float):
        return "F:" + format(value, ".17g")
    return "S:" + str(value)


def _digest(cursor: Any, columns: list[str]) -> tuple[int, str]:
    digest = hashlib.sha256(("|".join(columns) + "\n").encode("utf-8"))
    rows = 0
    while batch := cursor.fetchmany(10_000):
        for row in batch:
            digest.update("\x1f".join(_value(value) for value in row).encode("utf-8"))
            digest.update(b"\n")
            rows += 1
    return rows, digest.hexdigest()


def _sqlite_table(path: Path, table: str, columns: list[str]) -> tuple[int, str]:
    order = ",".join(f'"{item}"' for item in columns)
    selected = ",".join(f'"{item}"' for item in columns)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        actual = [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
        if actual != columns:
            raise RuntimeError(f"SQLite schema mismatch: {path.name}:{table}")
        return _digest(db.execute(f'SELECT {selected} FROM "{table}" ORDER BY {order}'), columns)


def _parquet_table(directory: Path, table: str, columns: list[str]) -> tuple[int, str]:
    connection = connect_parquet(directory / f"{table}.parquet")
    try:
        actual = [row[0] for row in connection.execute("DESCRIBE data").fetchall()]
        if actual != columns:
            raise RuntimeError(f"Parquet schema mismatch: {table}")
        order = ",".join(f'"{item}"' for item in columns)
        selected = ",".join(f'"{item}"' for item in columns)
        return _digest(connection.execute(f"SELECT {selected} FROM data ORDER BY {order}"), columns)
    finally:
        connection.close()


def _columns(path: Path, table: str) -> list[str]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        return [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]


def audit(legacy: Path, new_sqlite: Path, parquet: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"status": "PASS", "tables": {}}
    for table in TABLES:
        columns = _columns(legacy, table)
        legacy_value = _sqlite_table(legacy, table, columns)
        new_value = _sqlite_table(new_sqlite, table, columns)
        parquet_value = _parquet_table(parquet, table, columns)
        if legacy_value != new_value:
            raise RuntimeError(f"Legacy SQLite != new SQLite: {table}")
        if new_value != parquet_value:
            raise RuntimeError(f"new SQLite != Parquet: {table}")
        report["tables"][table] = {"rows": legacy_value[0], "canonical_row_hash": legacy_value[1]}
    with sqlite3.connect(f"file:{legacy}?mode=ro", uri=True) as left, sqlite3.connect(f"file:{new_sqlite}?mode=ro", uri=True) as right:
        left_meta = left.execute(f"SELECT {','.join(META_COLUMNS)} FROM meta_pwa_fact_build ORDER BY build_id DESC LIMIT 1").fetchone()
        right_meta = right.execute(f"SELECT {','.join(META_COLUMNS)} FROM meta_pwa_fact_build ORDER BY build_id DESC LIMIT 1").fetchone()
    if left_meta != right_meta:
        raise RuntimeError("Fact Lite semantic build metadata mismatch")
    report["legacy_equals_new_sqlite"] = True
    report["new_sqlite_equals_parquet"] = True
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-sqlite", type=Path, required=True)
    parser.add_argument("--new-sqlite", type=Path, required=True)
    parser.add_argument("--parquet-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.legacy_sqlite, args.new_sqlite, args.parquet_dir)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

