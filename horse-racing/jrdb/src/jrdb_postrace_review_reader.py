#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only consumer contract for RaceReviewDB.

Consumers resolve the current generation first, then query immutable Parquet
relations. Horse history joins use JRDB blood registration number (horse_id)
as the stable identity. Horse name is descriptive only.

Default history queries are as-of exclusive: race_date < target_date.
"""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


class RaceReviewReaderError(RuntimeError):
    """Raised when RaceReviewDB cannot satisfy the consumer contract."""


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_date(value: object) -> str:
    text = _text(value)
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) != 8:
        raise ValueError(f"invalid date: {value!r}")
    parsed = dt.date(
        int(digits[:4]),
        int(digits[4:6]),
        int(digits[6:8]),
    )
    return parsed.isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RaceReviewReaderError(
            f"unreadable RaceReviewDB JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RaceReviewReaderError(
            f"RaceReviewDB JSON object required: {path}"
        )
    return value


class RaceReviewReader:
    """Query one extracted RaceReviewDB CURRENT root through DuckDB."""

    def __init__(self, root: Path) -> None:
        try:
            import duckdb
        except ImportError as exc:
            raise RaceReviewReaderError(
                "RaceReviewDB reader requires duckdb"
            ) from exc

        self._duckdb = duckdb
        self.root = Path(root).resolve()
        current = _read_json(self.root / "current.json")
        if current.get("status") != "CURRENT":
            raise RaceReviewReaderError(
                "RaceReviewDB current pointer is not CURRENT"
            )
        if current.get("artifact_type") != "jrdb_postrace_review":
            raise RaceReviewReaderError(
                "unexpected RaceReviewDB artifact type"
            )

        manifest_ref = current.get("manifest")
        if not isinstance(manifest_ref, str):
            raise RaceReviewReaderError(
                "RaceReviewDB current has no manifest"
            )
        self.manifest = _read_json(self.root / manifest_ref)
        if self.manifest.get("validation_status") != "PASS":
            raise RaceReviewReaderError(
                "RaceReviewDB current manifest is not PASS"
            )
        if (
            self.manifest.get("generation_id")
            != current.get("generation_id")
        ):
            raise RaceReviewReaderError(
                "RaceReviewDB current/manifest generation mismatch"
            )

        self.generation_id = _text(
            self.manifest.get("generation_id")
        )
        self.period_from = _text(self.manifest.get("period_from"))
        self.period_to = _text(self.manifest.get("period_to"))
        self.review_schema_version = _text(
            self.manifest.get("schema_version")
        )
        self.review_logic_version = _text(
            self.manifest.get("review_logic_version")
        )
        self.baseline_version = _text(
            self.manifest.get("baseline_version")
        )

    def _paths(self, relation: str) -> list[Path]:
        relations = self.manifest.get("relations")
        if not isinstance(relations, Mapping):
            raise RaceReviewReaderError(
                "RaceReviewDB manifest has no relations"
            )
        meta = relations.get(relation)
        if not isinstance(meta, Mapping):
            raise RaceReviewReaderError(
                f"RaceReviewDB relation not found: {relation}"
            )

        paths: list[Path] = []
        for partition in meta.get("partitions") or []:
            if not isinstance(partition, Mapping):
                continue
            relative = partition.get("relative_path")
            if not isinstance(relative, str):
                continue
            path = self.root / relative
            if not path.is_file():
                raise RaceReviewReaderError(
                    f"RaceReviewDB object missing: {path}"
                )
            paths.append(path)
        return paths

    @staticmethod
    def _read_parquet_sql(paths: Sequence[Path]) -> tuple[str, list[str]]:
        if not paths:
            raise RaceReviewReaderError(
                "RaceReviewDB relation has no Parquet objects"
            )
        marks = ", ".join("?" for _ in paths)
        return (
            f"read_parquet([{marks}], union_by_name=true)",
            [str(path) for path in paths],
        )

    @staticmethod
    def _rows(cursor: Any) -> list[dict[str, object]]:
        names = [item[0] for item in cursor.description]
        return [
            dict(zip(names, values))
            for values in cursor.fetchall()
        ]

    def metadata(self) -> dict[str, object]:
        """Return stable metadata consumers may log for provenance."""
        relations = self.manifest.get("relations") or {}
        row_counts = {
            name: meta.get("total_rows")
            for name, meta in relations.items()
            if isinstance(meta, Mapping)
        }
        return {
            "generation_id": self.generation_id,
            "period_from": self.period_from,
            "period_to": self.period_to,
            "review_schema_version": self.review_schema_version,
            "review_logic_version": self.review_logic_version,
            "baseline_version": self.baseline_version,
            "row_counts": row_counts,
        }

    def horse_history(
        self,
        horse_id: str,
        *,
        before_date: object,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Return one horse's prior Review rows, newest first.

        horse_id is JRDB blood_registration_no. Horse name lookup is
        intentionally unsupported because it is not a stable identity key.
        """
        normalized_horse = _text(horse_id)
        if not normalized_horse:
            raise ValueError("horse_id is required")
        target_date = _normalize_date(before_date)

        paths = self._paths("fact_horse_performance")
        table_sql, params = self._read_parquet_sql(paths)
        query = (
            "SELECT * "
            f"FROM {table_sql} "
            "WHERE horse_id = ? "
            "AND race_date < CAST(? AS DATE) "
            "ORDER BY race_date DESC, race_key DESC"
        )
        query_params: list[object] = [
            *params,
            normalized_horse,
            target_date,
        ]
        if limit is not None:
            if limit < 1:
                raise ValueError("limit must be positive")
            query += " LIMIT ?"
            query_params.append(int(limit))

        connection = self._duckdb.connect(":memory:")
        try:
            return self._rows(
                connection.execute(query, query_params)
            )
        finally:
            connection.close()

    def histories_for_horses(
        self,
        horse_ids: Iterable[str],
        *,
        before_date: object,
        per_horse_limit: int = 5,
    ) -> dict[str, list[dict[str, object]]]:
        """Batch history query for a target race field.

        Missing history is represented by an empty list, never by a
        name-based fallback.
        """
        if per_horse_limit < 1:
            raise ValueError("per_horse_limit must be positive")

        normalized = sorted(
            {
                _text(horse_id)
                for horse_id in horse_ids
                if _text(horse_id)
            }
        )
        result = {horse_id: [] for horse_id in normalized}
        if not normalized:
            return result

        target_date = _normalize_date(before_date)
        paths = self._paths("fact_horse_performance")
        table_sql, params = self._read_parquet_sql(paths)
        horse_marks = ", ".join("?" for _ in normalized)

        query = (
            "WITH ranked AS ("
            "SELECT *, "
            "ROW_NUMBER() OVER ("
            "PARTITION BY horse_id "
            "ORDER BY race_date DESC, race_key DESC"
            ") AS _history_rank "
            f"FROM {table_sql} "
            f"WHERE horse_id IN ({horse_marks}) "
            "AND race_date < CAST(? AS DATE)"
            ") "
            "SELECT * EXCLUDE (_history_rank) "
            "FROM ranked "
            "WHERE _history_rank <= ? "
            "ORDER BY horse_id, race_date DESC, race_key DESC"
        )
        query_params: list[object] = [
            *params,
            *normalized,
            target_date,
            per_horse_limit,
        ]

        connection = self._duckdb.connect(":memory:")
        try:
            rows = self._rows(
                connection.execute(query, query_params)
            )
        finally:
            connection.close()

        for row in rows:
            key = _text(row.get("horse_id"))
            if key in result:
                result[key].append(row)
        return result

    def race_review(
        self,
        race_key: str,
    ) -> dict[str, object] | None:
        """Return race-level Review plus its race context."""
        normalized = _text(race_key)
        if not normalized:
            raise ValueError("race_key is required")

        review_paths = self._paths("fact_race_review")
        context_paths = self._paths("fact_race_context")
        review_sql, review_params = self._read_parquet_sql(
            review_paths
        )
        context_sql, context_params = self._read_parquet_sql(
            context_paths
        )

        query = (
            "SELECT r.*, "
            "c.first3f_reference_sec, c.last3f_reference_sec, "
            "c.pace_balance_sec, c.pace_balance_percentile, "
            "c.pace_shape AS context_pace_shape "
            f"FROM {review_sql} r "
            f"JOIN {context_sql} c USING (race_key) "
            "WHERE r.race_key = ?"
        )
        params: list[object] = [
            *review_params,
            *context_params,
            normalized,
        ]

        connection = self._duckdb.connect(":memory:")
        try:
            rows = self._rows(
                connection.execute(query, params)
            )
        finally:
            connection.close()

        if not rows:
            return None
        if len(rows) != 1:
            raise RaceReviewReaderError(
                f"duplicate race Review rows: {normalized}"
            )
        return rows[0]
