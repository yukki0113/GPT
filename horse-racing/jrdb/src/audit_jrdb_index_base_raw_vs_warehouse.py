#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formal logical equivalence audit: annual Raw Index Base vs Warehouse Index Base."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from build_jrdb_index_base_from_raw import build as build_raw
from build_jrdb_index_base_from_warehouse import build as build_warehouse
from jrdb_index_base_warehouse_adapter import WarehouseIndexBaseReader

TABLES = (
    "race_context",
    "race_result_context",
    "runner_pre",
    "runner_previous_link",
    "runner_result",
    "workout_main",
    "training_analysis",
    "horse_profile_observation",
)

KEYS = {
    "race_context": ("race_key",),
    "race_result_context": ("race_key",),
    "runner_pre": ("race_key", "horse_no"),
    "runner_previous_link": ("race_key", "horse_no", "sequence"),
    "runner_result": ("race_key", "horse_no"),
    "workout_main": ("race_key", "horse_no"),
    "training_analysis": ("race_key", "horse_no"),
    "horse_profile_observation": ("horse_id", "data_date", "semantic_hash"),
}


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def _canon(value: object) -> str:
    if value is None:
        return "N:"
    if isinstance(value, float):
        return f"F:{value:.17g}"
    return f"S:{value}"


def _rows(connection: sqlite3.Connection, table: str, columns: list[str]) -> list[tuple]:
    order = ",".join(KEYS[table])
    return connection.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY {order}").fetchall()


def _row_hash(columns: list[str], rows: Iterable[tuple]) -> str:
    digest = hashlib.sha256(("|".join(columns) + "\n").encode())
    for row in rows:
        digest.update("\x1f".join(_canon(value) for value in row).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _null_blank(columns: list[str], rows: list[tuple]) -> dict[str, dict[str, int]]:
    return {
        col: {
            "null": sum(row[i] is None for row in rows),
            "blank": sum(row[i] == "" for row in rows),
        }
        for i, col in enumerate(columns)
    }


def _record_hash_profile(columns: list[str], rows: list[tuple]) -> dict[str, Any] | None:
    if "record_hash" not in columns:
        return None
    idx = columns.index("record_hash")
    values = [row[idx] for row in rows]
    return {
        "count": len(values),
        "missing": sum(not value for value in values),
        "sha256_of_sorted_hashes": hashlib.sha256(
            ("\n".join(sorted(str(v) for v in values)) + "\n").encode()
        ).hexdigest(),
    }


def _column_diagnostics(
    table: str,
    columns: list[str],
    raw_rows: list[tuple],
    wh_rows: list[tuple],
    *,
    sample_limit: int = 5,
) -> dict[str, Any]:
    key_columns = KEYS[table]
    key_indexes = [columns.index(name) for name in key_columns]
    raw_keys = [tuple(row[i] for i in key_indexes) for row in raw_rows]
    wh_keys = [tuple(row[i] for i in key_indexes) for row in wh_rows]
    keys_equal = raw_keys == wh_keys
    result: dict[str, Any] = {
        "key_columns": list(key_columns),
        "ordered_keys_equal": keys_equal,
        "mismatch_counts": {},
        "samples": {},
    }
    if not keys_equal:
        raw_set = set(raw_keys)
        wh_set = set(wh_keys)
        result["raw_only_key_count"] = len(raw_set - wh_set)
        result["warehouse_only_key_count"] = len(wh_set - raw_set)
        result["raw_only_key_samples"] = [list(item) for item in sorted(raw_set - wh_set)[:sample_limit]]
        result["warehouse_only_key_samples"] = [list(item) for item in sorted(wh_set - raw_set)[:sample_limit]]
        return result

    for idx, column in enumerate(columns):
        count = 0
        samples: list[dict[str, Any]] = []
        for row_no, (raw_row, wh_row) in enumerate(zip(raw_rows, wh_rows)):
            if raw_row[idx] == wh_row[idx]:
                continue
            count += 1
            if len(samples) < sample_limit:
                samples.append({
                    "key": list(raw_keys[row_no]),
                    "raw": raw_row[idx],
                    "warehouse": wh_row[idx],
                })
        if count:
            result["mismatch_counts"][column] = count
            result["samples"][column] = samples
    return result


def _representative(table: str, columns: list[str], rows: list[tuple]) -> dict[str, Any]:
    index = {name: columns.index(name) for name in columns}
    out: dict[str, Any] = {"rows": len(rows)}
    if "race_key" in index:
        out["race_keys"] = len({row[index["race_key"]] for row in rows})
    if "year" in index:
        out["by_year"] = sorted(Counter(row[index["year"]] for row in rows).items())
    if "venue_code" in index:
        out["by_venue"] = sorted(Counter(row[index["venue_code"]] for row in rows).items())
    if "finish" in index:
        out["finish_non_null"] = sum(row[index["finish"]] is not None for row in rows)
    if "training_date" in index:
        out["training_date_non_null"] = sum(row[index["training_date"]] is not None for row in rows)
    return out


def compare_databases(raw_db: Path, warehouse_db: Path, warehouse_repeat_db: Path) -> dict[str, Any]:
    raw = sqlite3.connect(raw_db)
    wh = sqlite3.connect(warehouse_db)
    repeat = sqlite3.connect(warehouse_repeat_db)
    try:
        result: dict[str, Any] = {"status": "PASS", "tables": {}}
        for table in TABLES:
            raw_cols = _columns(raw, table)
            wh_cols = _columns(wh, table)
            repeat_cols = _columns(repeat, table)
            raw_rows = _rows(raw, table, raw_cols)
            wh_rows = _rows(wh, table, wh_cols)
            repeat_rows = _rows(repeat, table, repeat_cols)
            raw_hash = _row_hash(raw_cols, raw_rows)
            wh_hash = _row_hash(wh_cols, wh_rows)
            repeat_hash = _row_hash(repeat_cols, repeat_rows)
            table_result = {
                "schema_equal": raw_cols == wh_cols == repeat_cols,
                "columns": raw_cols,
                "row_count": {"raw": len(raw_rows), "warehouse": len(wh_rows), "repeat": len(repeat_rows)},
                "row_count_equal": len(raw_rows) == len(wh_rows) == len(repeat_rows),
                "canonical_row_hash": {"raw": raw_hash, "warehouse": wh_hash, "repeat": repeat_hash},
                "canonical_row_hash_equal": raw_hash == wh_hash == repeat_hash,
                "null_blank_semantics_equal": _null_blank(raw_cols, raw_rows) == _null_blank(wh_cols, wh_rows),
                "record_hash_profile": {
                    "raw": _record_hash_profile(raw_cols, raw_rows),
                    "warehouse": _record_hash_profile(wh_cols, wh_rows),
                },
                "record_hash_equivalent": _record_hash_profile(raw_cols, raw_rows) == _record_hash_profile(wh_cols, wh_rows),
                "representative_query_equal": _representative(table, raw_cols, raw_rows) == _representative(table, wh_cols, wh_rows),
                "representative_query": {
                    "raw": _representative(table, raw_cols, raw_rows),
                    "warehouse": _representative(table, wh_cols, wh_rows),
                },
                "idempotence_equal": wh_hash == repeat_hash,
                "column_diagnostics": _column_diagnostics(
                    table,
                    raw_cols,
                    raw_rows,
                    wh_rows,
                ) if raw_cols == wh_cols and len(raw_rows) == len(wh_rows) else None,
            }
            table_result["pass"] = all(
                table_result[key]
                for key in (
                    "schema_equal",
                    "row_count_equal",
                    "canonical_row_hash_equal",
                    "null_blank_semantics_equal",
                    "record_hash_equivalent",
                    "representative_query_equal",
                    "idempotence_equal",
                )
            )
            if not table_result["pass"]:
                result["status"] = "FAIL"
            result["tables"][table] = table_result
        result["integrity"] = {
            "raw": raw.execute("PRAGMA integrity_check").fetchone()[0],
            "warehouse": wh.execute("PRAGMA integrity_check").fetchone()[0],
            "warehouse_repeat": repeat.execute("PRAGMA integrity_check").fetchone()[0],
        }
        if set(result["integrity"].values()) != {"ok"}:
            result["status"] = "FAIL"
        return result
    finally:
        raw.close()
        wh.close()
        repeat.close()


def _asset_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        family, sep, path = value.partition("=")
        if not sep or not family or not path:
            raise ValueError("--asset-root requires FAMILY=/local/staging/root")
        roots[family.upper()] = Path(path)
    return roots


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--warehouse-current", type=Path)
    source.add_argument("--warehouse-manifest", type=Path)
    parser.add_argument("--asset-root", action="append", required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_index_base_schema_v0_1.sql",
    )
    parser.add_argument("--audit-json", type=Path)
    args = parser.parse_args()

    reader = WarehouseIndexBaseReader(
        args.warehouse_current,
        manifest=args.warehouse_manifest,
        asset_roots=_asset_roots(args.asset_root),
    )
    with tempfile.TemporaryDirectory(prefix="jrdb-index-base-dual-") as temp:
        root = Path(temp)
        raw_db = root / "raw.sqlite"
        wh_db = root / "warehouse.sqlite"
        wh_repeat_db = root / "warehouse-repeat.sqlite"
        raw_build = build_raw(args.raw_root, args.years, raw_db, args.schema, hash_archives=False)
        wh_build = build_warehouse(reader, args.years, wh_db, args.schema)
        wh_repeat_build = build_warehouse(reader, args.years, wh_repeat_db, args.schema)
        result = compare_databases(raw_db, wh_db, wh_repeat_db)
        result.update({
            "years": sorted(args.years),
            "raw_build": raw_build,
            "warehouse_build": wh_build,
            "warehouse_repeat_build": wh_repeat_build,
            "source_generation_id": reader.current.get("generation_id"),
        })

    if args.audit_json:
        args.audit_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
