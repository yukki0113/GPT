#!/usr/bin/env python3
"""Small DB-API compatibility layer for Edge analytical workspaces.

Active large-mart execution prefers DuckDB. Legacy SQLite remains readable for
reproduction/tests, but callers should not need storage-specific branches.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import duckdb


class EdgeRow:
    """Tuple-like row with SQLite-Row-style named access."""

    def __init__(self, columns: Sequence[str], values: Sequence[Any]):
        self._columns = tuple(columns)
        self._values = tuple(values)
        self._index = {name: index for index, name in enumerate(self._columns)}

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, str):
            return self._values[self._index[key]]
        return self._values[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def keys(self) -> list[str]:
        return list(self._columns)

    def __repr__(self) -> str:
        return f"EdgeRow({dict(self)!r})"


class EdgeCursor:
    def __init__(self, relation: Any):
        self._relation = relation
        description = relation.description or []
        self._columns = [str(item[0]) for item in description]

    @property
    def rowcount(self) -> int:
        value = getattr(self._relation, "rowcount", -1)
        return int(value if value is not None else -1)

    def _wrap(self, row: Sequence[Any] | None) -> EdgeRow | None:
        return None if row is None else EdgeRow(self._columns, row)

    def fetchone(self) -> EdgeRow | None:
        return self._wrap(self._relation.fetchone())

    def fetchall(self) -> list[EdgeRow]:
        return [EdgeRow(self._columns, row) for row in self._relation.fetchall()]

    def __iter__(self) -> Iterator[EdgeRow]:
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row


class EdgeConnection:
    def __init__(self, connection: Any, *, engine: str):
        self._connection = connection
        self.engine = engine

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        if self.engine == "sqlite":
            return self._connection.execute(sql, tuple(params or ()))
        relation = self._connection.execute(sql, list(params or ()))
        return EdgeCursor(relation)

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> Any:
        if self.engine == "sqlite":
            return self._connection.executemany(sql, rows)
        relation = self._connection.executemany(sql, rows)
        return EdgeCursor(relation)

    def executescript(self, script: str) -> None:
        if self.engine == "sqlite":
            self._connection.executescript(script)
            return
        # Edge schema/calibration scripts contain simple semicolon-delimited SQL
        # and no stored procedures. Execute statements independently in DuckDB.
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self._connection.execute(statement)

    def commit(self) -> None:
        if self.engine == "sqlite":
            self._connection.commit()
        else:
            # DuckDB autocommits unless an explicit transaction is active.
            try:
                self._connection.commit()
            except Exception:
                pass

    def close(self) -> None:
        self._connection.close()

    @property
    def raw(self) -> Any:
        return self._connection


def _is_sqlite_file(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def connect_edge_mart(path: str | Path, *, read_only: bool = False) -> EdgeConnection:
    """Open an Edge Feature Mart workspace.

    Production prefers DuckDB workspaces derived from canonical Parquet. Existing
    SQLite workspaces remain supported only for tests/reproduction.
    """
    target = Path(path)
    if _is_sqlite_file(target):
        uri = f"file:{target}?mode=ro" if read_only else str(target)
        connection = sqlite3.connect(uri, uri=read_only)
        connection.row_factory = sqlite3.Row
        return EdgeConnection(connection, engine="sqlite")
    connection = duckdb.connect(str(target), read_only=read_only)
    return EdgeConnection(connection, engine="duckdb")
