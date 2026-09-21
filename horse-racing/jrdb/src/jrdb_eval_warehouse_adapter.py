#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read accepted JRDB Historical Warehouse rows through existing Eval semantics.

This adapter is deliberately limited to the accepted 2010-2025 historical
Warehouse.  It owns no fixed-width offsets and does not reinterpret JRDB
fields.  Warehouse normalized rows are first restored to the common-parser
logical shape, then passed through the same Eval projection/policy helpers used
by the Raw path.

2026 PACI/SED/Raw is intentionally outside this adapter.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jrdb_eval_horse_result_adapter import project_eval_horse_result_from_parsed
from jrdb_eval_raw_adapter import (
    project_bac_eval_parsed,
    project_sed_horse_eval_parsed,
    project_sed_race_eval_parsed,
)
from jrdb_racenote_warehouse_adapter import unflatten_parser_row


HISTORICAL_YEAR_FROM = 2010
HISTORICAL_YEAR_TO = 2025
REQUIRED_RELATIONS = ("bac", "sed")


class EvalWarehouseError(RuntimeError):
    """Accepted Warehouse evidence cannot satisfy the Eval historical contract."""


def _compact_date(value: object) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _ordinal(row: Mapping[str, Any]) -> tuple[str, int]:
    return (
        str(row.get("source_member") or "").upper(),
        int(row.get("source_record_ordinal") or 0),
    )


class WarehouseEvalReader:
    """Resolve one accepted historical generation and expose Eval projections."""

    def __init__(
        self,
        current: Path,
        *,
        asset_roots: Mapping[str, Path],
        manifest: Path | None = None,
    ) -> None:
        self.current_path = Path(current)
        self.current = self._read_json(self.current_path)
        if (
            self.current.get("artifact_type") != "jrdb_normalized_warehouse_current"
            or self.current.get("status") != "accepted"
        ):
            raise EvalWarehouseError("JRDB dedicated current pointer is not accepted")

        if manifest is None:
            manifest_rel = self.current.get("manifest")
            if not isinstance(manifest_rel, str) or not manifest_rel.endswith("/manifest.json"):
                raise EvalWarehouseError("JRDB current pointer has no final manifest path")
            self.manifest_path = self.current_path.parent / manifest_rel
        else:
            self.manifest_path = Path(manifest)
        self.manifest = self._read_json(self.manifest_path)
        if (
            self.manifest.get("generation_id") != self.current.get("generation_id")
            or self.manifest.get("status") != "PASS"
        ):
            raise EvalWarehouseError("JRDB current/manifest generation mismatch")

        self.asset_roots = {str(key).upper(): Path(value) for key, value in asset_roots.items()}
        self.assets = list(self.manifest.get("assets") or [])
        if not self.assets:
            raise EvalWarehouseError("final Warehouse manifest has no assets")
        self.covered_years = {
            int(asset["year"])
            for asset in self.assets
            if asset.get("year") is not None
            and str(asset.get("family") or "").lower() in REQUIRED_RELATIONS
        }
        if not self.covered_years:
            raise EvalWarehouseError("Warehouse manifest has no Eval BAC/SED coverage")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvalWarehouseError(f"unreadable Warehouse JSON: {path}") from exc
        if not isinstance(value, dict):
            raise EvalWarehouseError(f"Warehouse JSON object required: {path}")
        return value

    def require_historical_date(self, date: dt.date) -> dt.date:
        if not (HISTORICAL_YEAR_FROM <= date.year <= HISTORICAL_YEAR_TO):
            raise EvalWarehouseError(
                f"{date}: Eval Historical Warehouse is limited to "
                f"{HISTORICAL_YEAR_FROM}-{HISTORICAL_YEAR_TO}; use the 2026 PACI/Raw path"
            )
        if date.year not in self.covered_years:
            raise EvalWarehouseError(f"{date}: year absent from accepted Warehouse manifest")
        return date

    def _paths(self, relation: str, year: int) -> list[Path]:
        relation = relation.lower()
        family = relation.upper()
        root = self.asset_roots.get(family)
        if root is None:
            raise EvalWarehouseError(f"asset root not supplied for {family}")
        paths: list[Path] = []
        for asset in self.assets:
            if (
                str(asset.get("family") or "").lower() != relation
                or int(asset.get("year", -1)) != year
            ):
                continue
            path = root / str(asset.get("relative_path") or "")
            if not path.is_file():
                raise EvalWarehouseError(f"missing immutable Warehouse asset: {path}")
            paths.append(path)
        if not paths:
            raise EvalWarehouseError(f"manifest has no {relation}/{year} asset")
        return sorted(paths)

    def asset_sha256s(self, relation: str, year: int) -> list[str]:
        values = [
            str(asset.get("sha256") or "")
            for asset in self.assets
            if str(asset.get("family") or "").lower() == relation.lower()
            and int(asset.get("year", -1)) == year
        ]
        if not values or any(len(value) != 64 for value in values):
            raise EvalWarehouseError(f"manifest SHA evidence missing for {relation}/{year}")
        return values

    def relation_rows(self, relation: str, year: int) -> list[dict[str, Any]]:
        if year not in self.covered_years:
            raise EvalWarehouseError(f"year {year} absent from accepted Warehouse coverage")
        try:
            import duckdb
        except ImportError as exc:
            raise EvalWarehouseError("Warehouse Eval reader requires duckdb") from exc
        paths = self._paths(relation, year)
        connection = duckdb.connect(":memory:")
        try:
            placeholders = ", ".join("?" for _ in paths)
            cursor = connection.execute(
                f"SELECT * FROM read_parquet([{placeholders}], union_by_name=true)",
                [str(path) for path in paths],
            )
            names = [item[0] for item in cursor.description]
            return [dict(zip(names, values)) for values in cursor.fetchall()]
        finally:
            connection.close()

    @staticmethod
    def select_member_date(
        rows: Iterable[Mapping[str, Any]],
        date: dt.date,
    ) -> list[dict[str, Any]]:
        expected = date.strftime("%Y%m%d")
        matched = [dict(row) for row in rows if _compact_date(row.get("source_member_date")) == expected]
        return sorted(matched, key=_ordinal)

    def member_rows(self, relation: str, date: dt.date) -> list[dict[str, Any]]:
        self.require_historical_date(date)
        rows = self.select_member_date(self.relation_rows(relation, date.year), date)
        if not rows:
            raise EvalWarehouseError(
                f"no Warehouse {relation.upper()} rows for source_member_date={date:%Y%m%d}"
            )
        return rows

    def raw_compatible_parsed_rows(self, relation: str, date: dt.date) -> list[dict[str, Any]]:
        family = relation.upper()
        return [unflatten_parser_row(family, row) for row in self.member_rows(relation, date)]

    def bac_eval_rows(self, date: dt.date) -> list[dict[str, object]]:
        return [project_bac_eval_parsed(row) for row in self.raw_compatible_parsed_rows("bac", date)]

    def sed_race_eval_rows(self, date: dt.date) -> list[dict[str, object]]:
        return [project_sed_race_eval_parsed(row) for row in self.raw_compatible_parsed_rows("sed", date)]

    def sed_horse_base_rows(self, date: dt.date) -> list[dict[str, object]]:
        return [project_sed_horse_eval_parsed(row) for row in self.raw_compatible_parsed_rows("sed", date)]

    def sed_horse_result_rows(
        self,
        date: dt.date,
        venue_labels: Mapping[str, str],
        abnormality_labels: Mapping[str, str],
    ) -> list[dict[str, object]]:
        return [
            project_eval_horse_result_from_parsed(row, venue_labels, abnormality_labels)
            for row in self.raw_compatible_parsed_rows("sed", date)
        ]

    def provenance(self, relation: str, date: dt.date) -> dict[str, object]:
        rows = self.member_rows(relation, date)
        return {
            "source_mode": "warehouse",
            "source_generation_id": self.current.get("generation_id"),
            "source_member_date": date.isoformat(),
            "source_relation": relation.lower(),
            "source_asset_sha256s": self.asset_sha256s(relation, date.year),
            "source_archive_names": sorted({str(row.get("source_archive_name") or "") for row in rows}),
            "source_members": sorted({str(row.get("source_member") or "") for row in rows}),
            "source_record_sha256s": sorted({str(row.get("source_record_sha256") or "") for row in rows}),
        }
