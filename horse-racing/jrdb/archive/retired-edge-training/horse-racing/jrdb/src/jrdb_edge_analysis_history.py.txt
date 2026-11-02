#!/usr/bin/env python3
"""Analysis-history adapters for JRDB Edge current matching.

The Edge matcher only needs the exact previous-race fact referenced by PACI KYI.
This module keeps that lookup contract identical across the legacy SQLite
compatibility artifact and the canonical Analysis Parquet current generation.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from jrdb_analysis_parquet_current import resolve_current

LookupKey = tuple[str, str, str]

ANALYSIS_TABLE = "fact_entry_result_lite"
REQUIRED_COLUMNS = {
    "race_key",
    "race_date",
    "horse_no",
    "horse_id",
    "track_type",
    "distance",
    "frame_no",
}


class AnalysisHistoryError(RuntimeError):
    """Raised when an Analysis history source is malformed or ambiguous."""


class AnalysisHistory(Protocol):
    source_kind: str
    source_info: dict[str, Any]

    def lookup(
        self,
        *,
        prev_race_key: str,
        horse_id: str,
        target_date: str,
    ) -> dict[str, Any] | None:
        ...

    def lookup_many(
        self,
        requests: list[LookupKey],
    ) -> dict[LookupKey, dict[str, Any] | None]:
        ...

    def close(self) -> None:
        ...


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _project_previous(row: tuple[Any, ...], *, prev_race_key: str, target_date: str) -> dict[str, Any]:
    previous_date = _text(row[0])
    if previous_date is None or previous_date >= target_date:
        raise AnalysisHistoryError(
            f"previous race is not strictly prior: {prev_race_key} {previous_date!r} >= {target_date}"
        )
    return {
        "race_date": previous_date,
        "surface_code": _text(row[1]),
        "distance_m": _int(row[2]),
        "frame_no": _int(row[3]),
    }


def _lookup_many(
    connection: Any,
    *,
    fact_table: str,
    requests: list[LookupKey],
) -> dict[LookupKey, dict[str, Any] | None]:
    """Resolve exact previous-race links with one fact-table scan.

    The request keys are staged in a tiny temporary table and semi-joined to
    Analysis. This avoids the SQLite-era anti-pattern of issuing one Parquet
    query per runner.
    """
    normalized = sorted(set(requests))
    if not normalized:
        return {}

    temp_table = "edge_prev_lookup_keys"
    connection.execute(f"DROP TABLE IF EXISTS {temp_table}")
    connection.execute(
        f"CREATE TEMP TABLE {temp_table} ("
        "prev_race_key VARCHAR, horse_id VARCHAR, target_date VARCHAR)"
    )
    try:
        connection.executemany(
            f"INSERT INTO {temp_table} VALUES (?,?,?)",
            normalized,
        )
        rows = connection.execute(
            f"""
            SELECT
                k.prev_race_key,
                k.horse_id,
                k.target_date,
                a.race_date,
                a.track_type,
                a.distance,
                a.frame_no,
                a.horse_no
            FROM {temp_table} AS k
            LEFT JOIN {fact_table} AS a
              ON a.race_key = k.prev_race_key
             AND a.horse_id = k.horse_id
            ORDER BY
                k.prev_race_key,
                k.horse_id,
                k.target_date,
                a.horse_no
            """
        ).fetchall()

        grouped: dict[LookupKey, list[tuple[Any, ...]]] = {
            key: [] for key in normalized
        }
        for row in rows:
            key = (str(row[0]), str(row[1]), str(row[2]))
            if row[3] is not None:
                grouped[key].append(tuple(row[3:7]))

        output: dict[LookupKey, dict[str, Any] | None] = {}
        for key in normalized:
            matches = grouped[key]
            if not matches:
                output[key] = None
                continue
            if len(matches) > 1:
                raise AnalysisHistoryError(
                    "ambiguous Analysis previous link: "
                    f"race_key={key[0]} horse_id={key[1]}"
                )
            output[key] = _project_previous(
                matches[0],
                prev_race_key=key[0],
                target_date=key[2],
            )
        return output
    finally:
        connection.execute(f"DROP TABLE IF EXISTS {temp_table}")


class SQLiteAnalysisHistory:
    """Legacy/compatibility Analysis SQLite reader."""

    source_kind = "SQLITE"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise AnalysisHistoryError(f"Analysis Lite DB not found: {self.path}")
        self.connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        rows = self.connection.execute(f"PRAGMA table_info({ANALYSIS_TABLE})").fetchall()
        columns = {str(row[1]) for row in rows}
        missing = REQUIRED_COLUMNS - columns
        if missing:
            self.connection.close()
            raise AnalysisHistoryError(
                f"Analysis Lite is missing required column(s): {sorted(missing)}"
            )
        if self.connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            self.connection.close()
            raise AnalysisHistoryError("Analysis Lite integrity_check failed")
        coverage = self.connection.execute(
            f"SELECT MIN(race_date),MAX(race_date),COUNT(*) FROM {ANALYSIS_TABLE}"
        ).fetchone()
        self.source_info = {
            "kind": self.source_kind,
            "path": str(self.path),
            "generation_id": None,
            "min_race_date": coverage[0],
            "max_race_date": coverage[1],
            "rows": int(coverage[2]),
        }

    def lookup_many(
        self,
        requests: list[LookupKey],
    ) -> dict[LookupKey, dict[str, Any] | None]:
        return _lookup_many(
            self.connection,
            fact_table=ANALYSIS_TABLE,
            requests=requests,
        )

    def lookup(
        self,
        *,
        prev_race_key: str,
        horse_id: str,
        target_date: str,
    ) -> dict[str, Any] | None:
        key = (prev_race_key, horse_id, target_date)
        return self.lookup_many([key])[key]

    def close(self) -> None:
        self.connection.close()


class ParquetAnalysisHistory:
    """Canonical Analysis Parquet current-generation reader."""

    source_kind = "PARQUET"

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        report = resolve_current(self.root)
        manifest_path = Path(report["manifest"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        partitions = manifest["fact_table"]["partitions"]
        paths = [(self.root / part["relative_path"]).resolve() for part in partitions]
        if not paths:
            raise AnalysisHistoryError("Analysis Parquet current generation has no fact partitions")

        try:
            import duckdb
        except ImportError as error:
            raise AnalysisHistoryError(
                "duckdb is required for Analysis Parquet Edge matching"
            ) from error

        self.connection = duckdb.connect(":memory:")
        quoted = ",".join("'" + str(path).replace("'", "''") + "'" for path in paths)
        self.connection.execute(
            f"CREATE VIEW analysis_fact AS "
            f"SELECT * FROM read_parquet([{quoted}], union_by_name=true)"
        )
        columns = {str(row[0]) for row in self.connection.execute("DESCRIBE analysis_fact").fetchall()}
        missing = REQUIRED_COLUMNS - columns
        if missing:
            self.connection.close()
            raise AnalysisHistoryError(
                f"Analysis Parquet is missing required column(s): {sorted(missing)}"
            )
        coverage = self.connection.execute(
            "SELECT MIN(race_date),MAX(race_date),COUNT(*) FROM analysis_fact"
        ).fetchone()
        self.source_info = {
            "kind": self.source_kind,
            "path": str(self.root),
            "generation_id": report.get("generation_id"),
            "min_race_date": coverage[0],
            "max_race_date": coverage[1],
            "rows": int(coverage[2]),
        }

    def lookup_many(
        self,
        requests: list[LookupKey],
    ) -> dict[LookupKey, dict[str, Any] | None]:
        return _lookup_many(
            self.connection,
            fact_table="analysis_fact",
            requests=requests,
        )

    def lookup(
        self,
        *,
        prev_race_key: str,
        horse_id: str,
        target_date: str,
    ) -> dict[str, Any] | None:
        key = (prev_race_key, horse_id, target_date)
        return self.lookup_many([key])[key]

    def close(self) -> None:
        self.connection.close()


def open_analysis_history(
    *,
    analysis_db: str | Path | None = None,
    analysis_root: str | Path | None = None,
) -> AnalysisHistory | None:
    """Open exactly one Analysis history source; Parquet and SQLite are mutually exclusive."""
    if analysis_db is not None and analysis_root is not None:
        raise AnalysisHistoryError("Specify only one of analysis_db or analysis_root")
    if analysis_root is not None:
        return ParquetAnalysisHistory(analysis_root)
    if analysis_db is not None:
        return SQLiteAnalysisHistory(analysis_db)
    return None
