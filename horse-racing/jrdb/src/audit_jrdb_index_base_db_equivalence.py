#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare two JRDB Index Base v0.1 databases table-by-table.

This audit intentionally ignores build/source metadata because Raw and Warehouse
are different provenance media.  The eight consumer-facing Index Base relations
must remain exactly equivalent, including the legacy record_hash values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

TABLES: tuple[str, ...] = (
    "race_context",
    "race_result_context",
    "runner_pre",
    "runner_previous_link",
    "runner_result",
    "workout_main",
    "training_analysis",
    "horse_profile_observation",
)


def _normalize(value: Any) -> Any:
    """Normalize SQLite values for deterministic cross-database hashing."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float: {value!r}")
        return {"__float__": value.hex()}
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    return value


def _table_signature(database: Path, table: str) -> dict[str, Any]:
    """Return schema, row count and canonical row hash for one table."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        info = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        if not info:
            raise ValueError(f"missing table {table}: {database}")

        columns: list[str] = [str(row[1]) for row in info]
        primary_key_pairs: list[tuple[int, str]] = [
            (int(row[5]), str(row[1]))
            for row in info
            if int(row[5]) > 0
        ]
        primary_key_pairs.sort()
        order_by: list[str] = [name for _, name in primary_key_pairs]
        if not order_by:
            order_by = list(columns)

        quoted_columns: str = ",".join(
            '"' + column.replace('"', '""') + '"'
            for column in columns
        )
        quoted_order: str = ",".join(
            '"' + column.replace('"', '""') + '"'
            for column in order_by
        )
        cursor = connection.execute(
            f'SELECT {quoted_columns} FROM "{table}" ORDER BY {quoted_order}'
        )

        digest = hashlib.sha256()
        row_count: int = 0
        for row in cursor:
            payload = json.dumps(
                [_normalize(value) for value in row],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            digest.update(payload.encode("utf-8"))
            digest.update(b"\n")
            row_count += 1

        schema: list[dict[str, Any]] = [
            {
                "name": str(row[1]),
                "type": str(row[2]),
                "notnull": int(row[3]),
                "pk": int(row[5]),
            }
            for row in info
        ]
        return {
            "schema": schema,
            "order_by": order_by,
            "row_count": row_count,
            "sha256": digest.hexdigest(),
        }
    finally:
        connection.close()


def _integrity(database: Path) -> str:
    """Return SQLite integrity_check output."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        if row is None:
            return "missing"
        return str(row[0])
    finally:
        connection.close()


def compare(left: Path, right: Path) -> dict[str, Any]:
    """Compare all consumer-facing Index Base relations exactly."""
    tables: dict[str, Any] = {}
    passed: bool = True
    for table in TABLES:
        left_signature = _table_signature(left, table)
        right_signature = _table_signature(right, table)
        equal = left_signature == right_signature
        if not equal:
            passed = False
        tables[table] = {
            "pass": equal,
            "left": left_signature,
            "right": right_signature,
        }

    left_integrity = _integrity(left)
    right_integrity = _integrity(right)
    if left_integrity != "ok" or right_integrity != "ok":
        passed = False

    return {
        "status": "PASS" if passed else "FAIL",
        "left_integrity": left_integrity,
        "right_integrity": right_integrity,
        "tables": tables,
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = compare(args.left, args.right)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "PASS":
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
