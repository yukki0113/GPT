#!/usr/bin/env python3
"""Validated Analysis readers for RaceNote.

Production uses the immutable current Analysis Parquet generation through DuckDB.
SQLite is retained as an explicit compatibility/audit backend only.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from jrdb_analysis_parquet_current import resolve_current

TABLE = "fact_entry_result_lite"
REQUIRED_COLUMNS = {
    "race_date", "year", "venue_code", "race_no", "track_type", "distance",
    "race_key", "horse_no", "horse_id", "frame_no", "sire_name", "jockey_name",
    "finish", "final_win_odds", "final_win_popularity",
}
TARGET_COLUMNS = (
    "race_date, year, venue_code, race_no, track_type, distance, "
    "race_condition_code, track_condition_code, grade_code, race_key, horse_no, "
    "frame_no, horse_id, horse_name, sex_code, age, sire_name, "
    "broodmare_sire_name, sire_line_code, broodmare_sire_line_code, jockey_name, "
    "running_style, distance_aptitude, uptrend, training_index"
)


class AnalysisBackendError(RuntimeError):
    """Raised when an Analysis source cannot be safely opened."""


class RowMapping(dict):
    """Mapping row that preserves the tuple-style indexing used by the engine."""

    def __init__(self, columns: list[str], values: tuple[Any, ...]):
        super().__init__(zip(columns, values))
        self._values = values

    def __getitem__(self, key: object) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def __iter__(self):
        return iter(self._values)


class Result:
    def __init__(self, cursor: Any):
        columns = [item[0] for item in (cursor.description or [])]
        self._rows = [RowMapping(columns, tuple(row)) for row in cursor.fetchall()]

    def fetchone(self) -> RowMapping | None:
        return self._rows.pop(0) if self._rows else None

    def fetchall(self) -> list[RowMapping]:
        rows, self._rows = self._rows, []
        return rows


class SQLiteAnalysisBackend:
    """Compatibility backend for explicit audit/rollback/equivalence runs."""

    source_kind = "SQLITE"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise AnalysisBackendError(f"Analysis SQLite not found: {self.path}")
        self.connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        columns = {row[1] for row in self.connection.execute(f"PRAGMA table_info({TABLE})")}
        missing = REQUIRED_COLUMNS - columns
        if missing:
            self.close()
            raise AnalysisBackendError(f"Analysis SQLite missing columns: {sorted(missing)}")
        if self.connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            self.close()
            raise AnalysisBackendError("Analysis SQLite integrity_check failed")
        self.source_info = self._coverage()

    def _coverage(self) -> dict[str, Any]:
        row = self.connection.execute(
            f"SELECT MIN(race_date), MAX(race_date), COUNT(*) FROM {TABLE}"
        ).fetchone()
        return {
            "kind": self.source_kind,
            "path": str(self.path),
            "generation_id": None,
            "min_race_date": row[0],
            "max_race_date": row[1],
            "rows": int(row[2]),
        }

    def execute(self, sql: str, parameters: list[Any] | tuple[Any, ...] = ()) -> Any:
        return self.connection.execute(sql, parameters)

    def close(self) -> None:
        self.connection.close()


class DuckDBParquetAnalysisBackend:
    """Production reader for a verified immutable current generation."""

    source_kind = "PARQUET"

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        report = resolve_current(self.root)
        self.manifest_path = Path(report["manifest"]).resolve()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        partitions = manifest["fact_table"]["partitions"]
        paths = [(self.root / item["relative_path"]).resolve() for item in partitions]
        if not paths:
            raise AnalysisBackendError("Analysis Parquet current generation has no partitions")
        try:
            import duckdb
        except ImportError as error:
            raise AnalysisBackendError("duckdb is required for PARQUET_DUCKDB") from error
        self.connection = duckdb.connect(":memory:")
        quoted = ",".join("'" + str(path).replace("'", "''") + "'" for path in paths)
        try:
            self.connection.execute(
                "CREATE VIEW analysis_fact AS "
                f"SELECT * FROM read_parquet([{quoted}], union_by_name=true)"
            )
            columns = {row[0] for row in self.connection.execute("DESCRIBE analysis_fact").fetchall()}
            missing = REQUIRED_COLUMNS - columns
            if missing:
                raise AnalysisBackendError(f"Analysis Parquet missing columns: {sorted(missing)}")
            duplicates = self.connection.execute(
                "SELECT COUNT(*) FROM ("
                "SELECT race_key, horse_no FROM analysis_fact "
                "GROUP BY race_key, horse_no HAVING COUNT(*) > 1)"
            ).fetchone()[0]
            if duplicates:
                raise AnalysisBackendError(f"Analysis Parquet duplicate canonical keys: {duplicates}")
            self.source_info = self._coverage(report)
        except Exception:
            self.close()
            raise

    def _coverage(self, report: dict[str, Any]) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT MIN(race_date), MAX(race_date), COUNT(*) FROM analysis_fact"
        ).fetchone()
        return {
            "kind": self.source_kind,
            "backend": "parquet_duckdb",
            "path": str(self.root),
            "manifest_path": str(self.manifest_path),
            "generation_id": report.get("generation_id"),
            "min_race_date": row[0],
            "max_race_date": row[1],
            "rows": int(row[2]),
        }

    def execute(self, sql: str, parameters: list[Any] | tuple[Any, ...] = ()) -> Result:
        # The engine keeps its stable logical table name; Parquet exposes one
        # validated DuckDB view for that logical table.
        sql = sql.replace(TABLE, "analysis_fact")
        return Result(self.connection.execute(sql, parameters))

    def close(self) -> None:
        self.connection.close()


def open_analysis_backend(
    *,
    analysis_root: str | Path | None = None,
    analysis_db: str | Path | None = None,
    backend: str = "parquet",
) -> DuckDBParquetAnalysisBackend | SQLiteAnalysisBackend:
    """Open one source; automatic SQLite fallback is intentionally forbidden."""
    if backend == "parquet":
        if analysis_root is None or analysis_db is not None:
            raise AnalysisBackendError("parquet backend requires --analysis-root only")
        return DuckDBParquetAnalysisBackend(analysis_root)
    if backend == "sqlite":
        if analysis_db is None or analysis_root is not None:
            raise AnalysisBackendError("sqlite backend requires --analysis only")
        return SQLiteAnalysisBackend(analysis_db)
    raise AnalysisBackendError(f"Unsupported Analysis backend: {backend}")
