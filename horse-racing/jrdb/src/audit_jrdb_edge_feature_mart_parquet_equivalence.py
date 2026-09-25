#!/usr/bin/env python3
"""Audit exact logical equivalence between Edge Feature Mart SQLite and Parquet."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import duckdb

CANONICAL_KEY = ["race_key", "horse_no"]
ORDER_BY = ["race_date", "race_key", "horse_no"]


class FeatureMartEquivalenceError(RuntimeError):
    pass


def _canonical_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, float):
        if math.isnan(value):
            return {"__float__": "NaN"}
        if math.isinf(value):
            return {"__float__": "Infinity" if value > 0 else "-Infinity"}
        if value == 0.0:
            return 0.0
        return value
    return value


def _row_hash_update(digest: "hashlib._Hash", row: Iterable[Any]) -> None:
    payload = json.dumps(
        [_canonical_value(value) for value in row],
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    digest.update(payload.encode("utf-8"))
    digest.update(b"\n")


def _sqlite_columns(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {"name": str(row[1]), "declared_type": str(row[2] or "").upper(), "not_null": bool(row[3])}
        for row in connection.execute("PRAGMA table_info(edge_runner_fact)")
    ]


def _duckdb_columns(connection: duckdb.DuckDBPyConnection, path: Path) -> list[dict[str, Any]]:
    return [
        {"name": str(row[0]), "type": str(row[1]).upper(), "null": str(row[2])}
        for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()
    ]


def _type_family_sqlite(declared: str) -> str:
    value = declared.upper()
    if "INT" in value:
        return "INTEGER"
    if any(token in value for token in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    if "BLOB" in value:
        return "BLOB"
    return "TEXT"


def _type_family_parquet(value: str) -> str:
    value = value.upper()
    if value in {"BIGINT", "INTEGER", "SMALLINT", "TINYINT", "UBIGINT", "UINTEGER", "USMALLINT", "UTINYINT"}:
        return "INTEGER"
    if value in {"DOUBLE", "FLOAT", "DECIMAL"} or value.startswith("DECIMAL"):
        return "REAL"
    if value == "BLOB":
        return "BLOB"
    return "TEXT"


def _aggregate_sqlite(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "rows": connection.execute("SELECT count(*) FROM edge_runner_fact").fetchone()[0],
        "pre_race_eligible": connection.execute(
            "SELECT count(*) FROM edge_runner_fact WHERE is_pre_race_eligible=1"
        ).fetchone()[0],
        "result_labeled": connection.execute(
            "SELECT count(*) FROM edge_runner_fact WHERE label_finish IS NOT NULL"
        ).fetchone()[0],
        "track_condition_snapshot": connection.execute(
            "SELECT count(*) FROM edge_runner_fact WHERE track_condition_code IS NOT NULL"
        ).fetchone()[0],
        "status_counts": dict(connection.execute(
            "SELECT calculation_status,count(*) FROM edge_runner_fact GROUP BY calculation_status ORDER BY calculation_status"
        ).fetchall()),
        "surface_counts": dict(connection.execute(
            "SELECT COALESCE(surface_code,'<NULL>'),count(*) FROM edge_runner_fact GROUP BY surface_code ORDER BY surface_code"
        ).fetchall()),
    }


def _aggregate_parquet(connection: duckdb.DuckDBPyConnection, path: Path) -> dict[str, Any]:
    def one(sql: str) -> int:
        return int(connection.execute(sql, [str(path)]).fetchone()[0])
    status_rows = connection.execute(
        """
        SELECT calculation_status,count(*)
        FROM read_parquet(?)
        GROUP BY calculation_status ORDER BY calculation_status
        """,
        [str(path)],
    ).fetchall()
    surface_rows = connection.execute(
        """
        SELECT COALESCE(surface_code,'<NULL>'),count(*)
        FROM read_parquet(?)
        GROUP BY surface_code ORDER BY surface_code
        """,
        [str(path)],
    ).fetchall()
    return {
        "rows": one("SELECT count(*) FROM read_parquet(?)"),
        "pre_race_eligible": one("SELECT count(*) FROM read_parquet(?) WHERE is_pre_race_eligible=1"),
        "result_labeled": one("SELECT count(*) FROM read_parquet(?) WHERE label_finish IS NOT NULL"),
        "track_condition_snapshot": one("SELECT count(*) FROM read_parquet(?) WHERE track_condition_code IS NOT NULL"),
        "status_counts": {str(key): int(value) for key, value in status_rows},
        "surface_counts": {str(key): int(value) for key, value in surface_rows},
    }


def audit(sqlite_path: Path, parquet_path: Path) -> dict[str, Any]:
    if not sqlite_path.is_file() or not parquet_path.is_file():
        raise FeatureMartEquivalenceError("input asset missing")

    sqlite = sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro", uri=True)
    duck = duckdb.connect()
    try:
        sqlite_cols = _sqlite_columns(sqlite)
        parquet_cols = _duckdb_columns(duck, parquet_path)
        sqlite_names = [item["name"] for item in sqlite_cols]
        parquet_names = [item["name"] for item in parquet_cols]
        column_names_equal = sqlite_names == parquet_names
        logical_types_equal = column_names_equal and all(
            _type_family_sqlite(left["declared_type"]) == _type_family_parquet(right["type"])
            for left, right in zip(sqlite_cols, parquet_cols)
        )

        key_sql = ",".join(CANONICAL_KEY)
        sqlite_dup = int(sqlite.execute(
            f"SELECT count(*)-(SELECT count(*) FROM (SELECT {key_sql} FROM edge_runner_fact GROUP BY {key_sql})) FROM edge_runner_fact"
        ).fetchone()[0])
        parquet_dup = int(duck.execute(
            """
            SELECT count(*) - count(DISTINCT race_key || ':' || CAST(horse_no AS VARCHAR))
            FROM read_parquet(?)
            """,
            [str(parquet_path)],
        ).fetchone()[0])

        null_sqlite = {
            name: int(sqlite.execute(f'SELECT count(*) FROM edge_runner_fact WHERE "{name}" IS NULL').fetchone()[0])
            for name in sqlite_names
        }
        null_parquet = {
            name: int(duck.execute(
                f'SELECT count(*) FROM read_parquet(?) WHERE "{name}" IS NULL',
                [str(parquet_path)],
            ).fetchone()[0])
            for name in parquet_names
        }
        null_semantics_equal = null_sqlite == null_parquet

        select = ",".join(f'"{name}"' for name in sqlite_names)
        order = ",".join(f'"{name}"' for name in ORDER_BY)
        sqlite_cursor = sqlite.execute(f"SELECT {select} FROM edge_runner_fact ORDER BY {order}")
        duck_cursor = duck.execute(
            f"SELECT {select} FROM read_parquet(?) ORDER BY {order}",
            [str(parquet_path)],
        )
        sqlite_hash = hashlib.sha256()
        parquet_hash = hashlib.sha256()
        row_count_sqlite = row_count_parquet = 0
        while True:
            srows = sqlite_cursor.fetchmany(5000)
            prows = duck_cursor.fetchmany(5000)
            if not srows and not prows:
                break
            if len(srows) != len(prows):
                raise FeatureMartEquivalenceError(
                    f"stream batch row mismatch sqlite={len(srows)} parquet={len(prows)}"
                )
            for srow, prow in zip(srows, prows):
                _row_hash_update(sqlite_hash, srow)
                _row_hash_update(parquet_hash, prow)
                row_count_sqlite += 1
                row_count_parquet += 1

        sqlite_agg = _aggregate_sqlite(sqlite)
        parquet_agg = _aggregate_parquet(duck, parquet_path)
        row_hash_equal = sqlite_hash.hexdigest() == parquet_hash.hexdigest()
        aggregates_equal = sqlite_agg == parquet_agg
        pass_gate = all([
            row_count_sqlite == row_count_parquet,
            column_names_equal,
            logical_types_equal,
            sqlite_dup == 0,
            parquet_dup == 0,
            null_semantics_equal,
            row_hash_equal,
            aggregates_equal,
        ])
        return {
            "status": "PASS" if pass_gate else "FAIL",
            "gate": "EDGE_FEATURE_MART_PARQUET_EQUIVALENCE",
            "row_count_equal": row_count_sqlite == row_count_parquet,
            "row_count_sqlite": row_count_sqlite,
            "row_count_parquet": row_count_parquet,
            "schema_columns_equal": column_names_equal,
            "logical_types_equal": logical_types_equal,
            "canonical_key": CANONICAL_KEY,
            "duplicate_key_rows_sqlite": sqlite_dup,
            "duplicate_key_rows_parquet": parquet_dup,
            "null_semantics_equal": null_semantics_equal,
            "canonical_row_hash_sqlite": sqlite_hash.hexdigest(),
            "canonical_row_hash_parquet": parquet_hash.hexdigest(),
            "canonical_row_hash_equal": row_hash_equal,
            "representative_aggregates_equal": aggregates_equal,
            "representative_aggregates_sqlite": sqlite_agg,
            "representative_aggregates_parquet": parquet_agg,
            "column_count": len(sqlite_names),
            "columns": sqlite_names,
        }
    finally:
        sqlite.close()
        duck.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.sqlite, args.parquet)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
