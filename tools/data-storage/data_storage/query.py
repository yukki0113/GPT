from __future__ import annotations

from pathlib import Path

import duckdb

from .common import parquet_glob, sql_literal


def connect_parquet(path: str | Path, view_name: str = "data") -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(":memory:")
    pattern = parquet_glob(path)
    connection.execute(
        f'CREATE VIEW "{view_name.replace(chr(34), chr(34) * 2)}" AS '
        f"SELECT * FROM read_parquet({sql_literal(pattern)}, hive_partitioning=true, union_by_name=true)"
    )
    return connection


def execute_query(path: str | Path, sql: str) -> tuple[list[str], list[tuple]]:
    connection = connect_parquet(path)
    try:
        cursor = connection.execute(sql)
        return [item[0] for item in cursor.description], cursor.fetchall()
    finally:
        connection.close()

