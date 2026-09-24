#!/usr/bin/env python3
"""Historical RaceNote reader for immutable JRDB Warehouse Parquet."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jrdb_racenote_warehouse_adapter import (
    RaceNoteWarehouseError, out_of_warehouse_previous_keys,
    previous_result_year, require_historical_year, select_raw_compatible_rows,
    unflatten_parser_row,
)
from racenote_jrdb import Audit, BundleBuilder

RELATION_PARENT = {"bac":"BAC","kyi":"KYI","cha":"CHA","cyb":"CYB","zed":"ZED","zkb":"ZKB"}

class WarehouseRaceNoteReaderError(RaceNoteWarehouseError):
    pass

def _text(value: object) -> str:
    return "" if value is None else str(value)

def _date(value: object) -> str:
    return "".join(c for c in _text(value) if c.isdigit())


def _raw_archive_order(rows: Iterable[dict[str, Any]], family: str) -> list[dict[str, Any]]:
    """Reproduce annual-Raw iteration order before BundleBuilder's first-key index.

    A historical SED/SKB annual ZIP can retain an older member.  The Raw
    reconstruction loops archive years first, then lexical member order.  A
    timestamp-only sort would instead let a retained older member in a newer
    archive win, changing the first-row duplicate policy in BundleBuilder.
    """
    ordered = sorted(
        rows,
        key=lambda row: (
            int(row.get("year") or 0),
            _text(row.get("source_member")).upper(),
            int(row.get("source_record_ordinal") or 0),
        ),
    )
    return [unflatten_parser_row(family, row) for row in ordered]

class WarehouseRaceNoteReader:
    """Resolve one accepted Warehouse generation without altering RaceNote semantics."""
    def __init__(self, current: Path, *, asset_roots: Mapping[str, Path]) -> None:
        self.current_path = Path(current)
        self.current = self._json(self.current_path)
        if self.current.get("artifact_type") != "jrdb_normalized_warehouse_current" or self.current.get("status") != "accepted":
            raise WarehouseRaceNoteReaderError("accepted dedicated JRDB Warehouse current required")
        ref = self.current.get("manifest")
        if not isinstance(ref, str) or not ref.endswith("/manifest.json"):
            raise WarehouseRaceNoteReaderError("current pointer has no final manifest")
        self.manifest = self._json(self.current_path.parent / ref)
        if self.manifest.get("status") != "PASS" or self.manifest.get("generation_id") != self.current.get("generation_id"):
            raise WarehouseRaceNoteReaderError("Warehouse current/manifest mismatch")
        self.assets = list(self.manifest.get("assets") or [])
        self.asset_roots = {str(k).upper(): Path(v) for k, v in asset_roots.items()}
        self.covered_years = {int(x["year"]) for x in self.assets if x.get("year") is not None}

    @staticmethod
    def _json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WarehouseRaceNoteReaderError(f"unreadable Warehouse JSON: {path}") from exc
        if not isinstance(value, dict):
            raise WarehouseRaceNoteReaderError(f"Warehouse JSON object required: {path}")
        return value

    def _paths(self, relation: str, year: int) -> list[Path]:
        root = self.asset_roots.get(RELATION_PARENT[relation])
        if root is None:
            raise WarehouseRaceNoteReaderError(f"asset root not supplied for {RELATION_PARENT[relation]}")
        paths = [root / str(x["relative_path"]) for x in self.assets if str(x.get("family","")).lower() == relation and int(x.get("year",-1)) == year]
        if not paths:
            raise WarehouseRaceNoteReaderError(f"manifest has no {relation}/{year} asset")
        for path in paths:
            if not path.is_file():
                raise WarehouseRaceNoteReaderError(f"missing immutable asset: {path}")
        return paths

    def _rows_on(
        self,
        connection: Any,
        relation: str,
        years: Iterable[int],
        where: str = "",
        params: list[object] | None = None,
    ) -> list[dict[str, Any]]:
        """Read one logical relation across one or more annual Parquet objects.

        The caller owns the DuckDB connection so a RaceNote build can reuse one
        connection for all families. Filtering is expressed in DuckDB before
        rows cross into Python, which avoids materializing whole annual
        relations just to retain a small set of race/result keys.
        """
        normalized_years = sorted({int(year) for year in years})
        if not normalized_years:
            return []
        paths = [
            path
            for year in normalized_years
            for path in self._paths(relation, year)
        ]
        marks = ", ".join("?" for _ in paths)
        query = f"SELECT * FROM read_parquet([{marks}], union_by_name=true)"
        if where:
            query += " WHERE " + where
        values = [str(path) for path in paths] + list(params or [])
        cursor = connection.execute(query, values)
        names = [item[0] for item in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def _rows(self, relation: str, year: int) -> list[dict[str, Any]]:
        """Compatibility wrapper for one-off annual relation reads."""
        try:
            import duckdb
        except ImportError as exc:
            raise WarehouseRaceNoteReaderError("RaceNote Warehouse reader requires duckdb") from exc
        connection = duckdb.connect(":memory:")
        try:
            return self._rows_on(connection, relation, [year])
        finally:
            connection.close()

    @staticmethod
    def _replace_filter_table(
        connection: Any,
        table: str,
        values: Iterable[str],
    ) -> None:
        """Replace a small temporary key table used by bulk semi-joins."""
        rows = [
            (value,)
            for value in sorted({str(value) for value in values if str(value)})
        ]
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')
        connection.execute(f'CREATE TEMP TABLE "{table}" (value VARCHAR PRIMARY KEY)')
        if rows:
            connection.executemany(f'INSERT INTO "{table}" VALUES (?)', rows)

    @staticmethod
    def _member_date_where(day: dt.date) -> tuple[str, list[object]]:
        """Build a tolerant SQL predicate equivalent to Python date compaction."""
        return (
            "replace(CAST(source_member_date AS VARCHAR), '-', '') = ?",
            [day.strftime("%Y%m%d")],
        )

    @staticmethod
    def _member(rows: Iterable[dict[str, Any]], day: dt.date | None) -> list[dict[str, Any]]:
        if day is None:
            return list(rows)
        matches = [x for x in rows if _date(x.get("source_member_date")) == day.strftime("%Y%m%d")]
        if not matches:
            raise WarehouseRaceNoteReaderError(f"no Warehouse rows for source_member_date={day:%Y%m%d}")
        return matches

    def boundary_previous_keys(self, year: int) -> list[str]:
        require_historical_year(year)
        return out_of_warehouse_previous_keys(self._rows("kyi", year))

    def build(
        self,
        day: dt.date,
        *,
        race_keys: Iterable[str] | None = None,
        source_member_date: dt.date | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """Build one historical RaceNote day with bulk Parquet filtering."""
        year = require_historical_year(day.year)
        requested_keys = {str(value) for value in race_keys or [] if str(value)}

        try:
            import duckdb
        except ImportError as exc:
            raise WarehouseRaceNoteReaderError(
                "RaceNote Warehouse reader requires duckdb"
            ) from exc

        connection = duckdb.connect(":memory:")
        try:
            # Preserve strict delivery-date semantics. With source_member_date,
            # fetch that delivery once and apply an explicit race subset after
            # the delivery check so previous failure behavior remains intact.
            if source_member_date is not None:
                member_where, member_params = self._member_date_where(
                    source_member_date
                )
                bac = self._member(
                    self._rows_on(
                        connection,
                        "bac",
                        [year],
                        member_where,
                        member_params,
                    ),
                    source_member_date,
                )
            elif requested_keys:
                self._replace_filter_table(
                    connection,
                    "target_race_keys",
                    requested_keys,
                )
                bac = self._rows_on(
                    connection,
                    "bac",
                    [year],
                    "EXISTS ("
                    "SELECT 1 FROM target_race_keys t "
                    "WHERE t.value = race_key_raw"
                    ")",
                )
            else:
                bac = self._rows_on(
                    connection,
                    "bac",
                    [year],
                    "race_date = ?",
                    [day.isoformat()],
                )

            if requested_keys:
                keys = set(requested_keys)
                bac = [
                    row
                    for row in bac
                    if _text(row.get("race_key_raw")) in keys
                ]
            else:
                bac = [
                    row
                    for row in bac
                    if _text(row.get("race_date")) == day.isoformat()
                ]
                keys = {
                    _text(row.get("race_key_raw"))
                    for row in bac
                    if _text(row.get("race_key_raw"))
                }

            self._replace_filter_table(connection, "target_race_keys", keys)

            if source_member_date is not None:
                member_where, member_params = self._member_date_where(
                    source_member_date
                )
                kyi = self._member(
                    self._rows_on(
                        connection,
                        "kyi",
                        [year],
                        member_where,
                        member_params,
                    ),
                    source_member_date,
                )
                kyi = [
                    row
                    for row in kyi
                    if _text(row.get("race_key_raw")) in keys
                ]
            else:
                kyi = self._rows_on(
                    connection,
                    "kyi",
                    [year],
                    "EXISTS ("
                    "SELECT 1 FROM target_race_keys t "
                    "WHERE t.value = race_key_raw"
                    ")",
                )

            if not bac or not kyi:
                raise WarehouseRaceNoteReaderError(
                    f"{day}: no Warehouse BAC/KYI rows"
                )

            boundary = out_of_warehouse_previous_keys(kyi)
            if boundary:
                raise WarehouseRaceNoteReaderError(
                    f"{day}: out-of-coverage previous-result keys require "
                    f"explicit Raw boundary fallback: {boundary[:5]}"
                )

            previous = {
                _text(item.get("result_key"))
                for row in kyi
                for item in unflatten_parser_row("KYI", row).get("previous", [])
                if _text(item.get("result_key"))
                and _text(item.get("result_key")) != "0" * 16
            }
            parsed = {
                "BAC": select_raw_compatible_rows("BAC", bac),
                "KYI": select_raw_compatible_rows("KYI", kyi),
            }

            race_where = (
                "EXISTS ("
                "SELECT 1 FROM target_race_keys t "
                "WHERE t.value = substr(race_horse_key, 1, 8)"
                ")"
            )
            for relation, family in (("cha", "CHA"), ("cyb", "CYB")):
                relation_rows = self._rows_on(
                    connection,
                    relation,
                    [year],
                    race_where,
                )
                parsed[family] = _raw_archive_order(relation_rows, family)

            previous_years = sorted(
                {
                    previous_result_year(value)
                    for value in previous
                    if previous_result_year(value) is not None
                }
            )
            for source_year in previous_years:
                if source_year not in self.covered_years:
                    raise WarehouseRaceNoteReaderError(
                        f"{day}: previous-result year {source_year} not in "
                        "accepted Warehouse coverage"
                    )

            self._replace_filter_table(
                connection,
                "target_result_keys",
                previous,
            )
            result_where = (
                "EXISTS ("
                "SELECT 1 FROM target_result_keys t "
                "WHERE t.value = result_key"
                ")"
            )
            for relation, family in (("zed", "ZED"), ("zkb", "ZKB")):
                relation_rows = self._rows_on(
                    connection,
                    relation,
                    previous_years,
                    result_where,
                )
                parsed[family] = select_raw_compatible_rows(
                    family,
                    relation_rows,
                )
        finally:
            connection.close()

        audit = Audit()
        builder = BundleBuilder(parsed, audit)
        horses: dict[str, list[dict[str, Any]]] = {}
        for row in parsed["KYI"]:
            horses.setdefault(
                _text(row.get("race_key_raw")),
                [],
            ).append(row)

        bundles = {
            _text(row["race_key_raw"]): builder.build(
                row,
                horses.get(_text(row["race_key_raw"]), []),
            )
            for row in parsed["BAC"]
        }
        if audit.bundle_errors:
            raise WarehouseRaceNoteReaderError(
                "; ".join(audit.bundle_errors)
            )

        return bundles, {
            "generation_id": self.manifest["generation_id"],
            "race_count": len(bundles),
            "record_counts": {
                family: len(rows)
                for family, rows in parsed.items()
            },
            "joins": dict(builder.join),
            "previous_result_years": previous_years,
            "boundary_fallback_required": False,
        }
