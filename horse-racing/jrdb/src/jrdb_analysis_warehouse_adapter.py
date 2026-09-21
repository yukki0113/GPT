#!/usr/bin/env python3
"""Read an immutable JRDB Warehouse generation into the Analysis Lite contract.

This is deliberately a *consumer* adapter.  It never interprets fixed-width
bytes and never changes Warehouse assets.  The parsed/normalized columns in
the accepted Warehouse are projected to exactly the same 34 Analysis Lite
logical columns produced by :mod:`jrdb_analysis_raw_adapter`.

The module consumes local copies of the dedicated JRDB ``current.json`` and
final-generation ``manifest.json`` plus locally materialized immutable asset
roots.  Drive transfer remains outside the adapter so ordinary unit tests and
the production connector have the same deterministic reader.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from update_jrdb_analysis_incremental import FACT_COLUMNS

RELATION_PARENT = {
    "bac": "BAC", "kyi": "KYI", "cha": "CHA", "cyb": "CYB",
    "sed": "SED", "skb": "SKB", "zed": "ZED", "zkb": "ZKB",
    "ukc": "UKC", "ukc_source_record_lineage": "UKC",
    "hjc_race": "HJC", "hjc_payout": "HJC",
}
REQUIRED_RELATIONS = ("bac", "kyi", "sed", "cyb", "ukc")


class WarehouseAnalysisError(RuntimeError):
    """Raised when immutable Warehouse evidence cannot satisfy the adapter."""


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _compact_date(value: object) -> str:
    return "".join(ch for ch in _text(value) if ch.isdigit())


def _project_bac(row: Mapping[str, Any], date: dt.date) -> dict[str, object]:
    key = _text(row.get("race_key_raw"))
    return {
        "race_date": date.isoformat(), "year": date.year,
        "venue_code": key[:2], "race_no": _int(key[6:8]),
        "distance": _int(row.get("distance_raw")),
        "track_type": _text(row.get("surface_code")),
        "race_condition_code": _text(row.get("race_class_code")),
        "track_condition_code": None,
        "grade_code": _text(row.get("grade_code")),
        "win5_leg_no": _int(row.get("win5_leg_no")),
    }


def _project_kyi(row: Mapping[str, Any]) -> tuple[tuple[str, int | None], dict[str, object]]:
    key = _text(row.get("race_key_raw"))
    return (key, _int(row.get("horse_no"))), {
        "frame_no": _int(row.get("frame_no")),
        "horse_id": _text(row.get("blood_registration_no")),
        "horse_name": _text(row.get("horse_name")),
        "jockey_name": _text(row.get("jockey")),
        "running_style": _text(row.get("running_style_code")),
        "distance_aptitude": _text(row.get("distance_fit_code")),
        "uptrend": _text(row.get("improvement_code")),
        "prev_result_key_1": _text(row.get("prev_result_key_1")) or None,
        "prev_race_key_1": _text(row.get("prev_race_key_1")) or None,
    }


def _project_sed(row: Mapping[str, Any], date: dt.date) -> tuple[tuple[str, int | None], dict[str, object], dict[str, object]]:
    key = _text(row.get("race_key_raw"))
    result = {
        "finish": _int(row.get("finish")), "abnormal_code": _text(row.get("abnormal_code")),
        "final_win_odds": _int(row.get("final_win_odds")),
        "final_win_popularity": _int(row.get("final_popularity")),
        "win_payout": _int(row.get("win_payout")), "place_payout": _int(row.get("place_payout")),
    }
    fallback = {
        "race_date": date.isoformat(), "year": date.year, "venue_code": key[:2],
        "race_no": _int(key[6:8]), "distance": _int(row.get("distance_m")),
        "track_type": _text(row.get("surface_code")), "race_condition_code": None,
        "track_condition_code": _text(row.get("track_condition_code")),
        "grade_code": None, "win5_leg_no": None,
    }
    return (key, _int(row.get("horse_no"))), result, fallback


def _project_cyb(row: Mapping[str, Any]) -> tuple[tuple[str, int | None], int | None]:
    value = _text(row.get("race_horse_key"))
    return (value[:8], _int(value[8:10])), _int(row.get("training_index"))


def _project_ukc(row: Mapping[str, Any]) -> tuple[str, dict[str, object]]:
    birth = _text(row.get("birth_date"))
    birth_year = int(birth[:4]) if len(birth) >= 4 and birth[:4].isdigit() else None
    return _text(row.get("horse_id")), {
        "sex_code": _text(row.get("sex_code")), "birth_year": birth_year,
        "sire_name": _text(row.get("sire_name")),
        "broodmare_sire_name": _text(row.get("broodmare_sire_name")),
        "sire_line_code": _text(row.get("sire_line_code")),
        "broodmare_sire_line_code": _text(row.get("broodmare_sire_line_code")),
        "data_date": _text(row.get("data_date")),
    }


def _as_dicts(connection: Any, query: str, params: list[object]) -> list[dict[str, Any]]:
    cursor = connection.execute(query, params)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, values)) for values in cursor.fetchall()]


class WarehouseAnalysisReader:
    """Resolve one accepted generation and expose completed Analysis dates."""

    def __init__(self, current: Path, *, asset_roots: Mapping[str, Path]) -> None:
        self.current_path = Path(current)
        self.current = self._read_json(self.current_path)
        if self.current.get("artifact_type") != "jrdb_normalized_warehouse_current" or self.current.get("status") != "accepted":
            raise WarehouseAnalysisError("JRDB dedicated current pointer is not accepted")
        manifest_rel = self.current.get("manifest")
        if not isinstance(manifest_rel, str) or not manifest_rel.endswith("/manifest.json"):
            raise WarehouseAnalysisError("JRDB current pointer has no final manifest path")
        self.manifest_path = self.current_path.parent / manifest_rel
        self.manifest = self._read_json(self.manifest_path)
        if self.manifest.get("generation_id") != self.current.get("generation_id") or self.manifest.get("status") != "PASS":
            raise WarehouseAnalysisError("JRDB current/manifest generation mismatch")
        self.asset_roots = {str(k).upper(): Path(v) for k, v in asset_roots.items()}
        self.assets = list(self.manifest.get("assets", []))
        if not self.assets:
            raise WarehouseAnalysisError("final Warehouse manifest has no assets")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WarehouseAnalysisError(f"unreadable Warehouse JSON: {path}") from exc
        if not isinstance(value, dict):
            raise WarehouseAnalysisError(f"Warehouse JSON object required: {path}")
        return value

    def _paths(self, relation: str, year: int) -> list[Path]:
        relation = relation.lower()
        parent = RELATION_PARENT[relation]
        root = self.asset_roots.get(parent)
        if root is None:
            raise WarehouseAnalysisError(f"asset root not supplied for {parent}")
        paths = []
        for asset in self.assets:
            if str(asset.get("family", "")).lower() != relation or int(asset.get("year", -1)) != year:
                continue
            path = root / str(asset.get("relative_path", ""))
            if not path.is_file():
                raise WarehouseAnalysisError(f"missing immutable asset: {path}")
            paths.append(path)
        if not paths:
            raise WarehouseAnalysisError(f"manifest has no {relation}/{year} asset")
        return paths

    def _asset_sha256s(self, relation: str, year: int) -> list[str]:
        """Return manifest-bound object hashes for Analysis ingest provenance."""
        values = [str(asset.get("sha256")) for asset in self.assets
                  if str(asset.get("family", "")).lower() == relation.lower()
                  and int(asset.get("year", -1)) == year]
        if not values or any(len(value) != 64 for value in values):
            raise WarehouseAnalysisError(f"manifest SHA evidence missing for {relation}/{year}")
        return values

    def _relation_rows(self, relation: str, year: int, where: str = "", params: list[object] | None = None) -> list[dict[str, Any]]:
        try:
            import duckdb  # deferred: pure projection tests need no DuckDB
        except ImportError as exc:
            raise WarehouseAnalysisError("Warehouse reader requires duckdb") from exc
        paths = self._paths(relation, year)
        connection = duckdb.connect(":memory:")
        try:
            placeholders = ", ".join("?" for _ in paths)
            query = f"SELECT * FROM read_parquet([{placeholders}], union_by_name=true)"
            if where:
                query += " WHERE " + where
            return _as_dicts(connection, query, [str(path) for path in paths] + list(params or []))
        finally:
            connection.close()

    @staticmethod
    def _for_member(rows: Iterable[dict[str, Any]], member_date: dt.date | None) -> list[dict[str, Any]]:
        if member_date is None:
            return list(rows)
        expected = member_date.strftime("%Y%m%d")
        matched = [row for row in rows if _compact_date(row.get("source_member_date")) == expected]
        if not matched:
            raise WarehouseAnalysisError(f"no Warehouse rows for source_member_date={expected}")
        return matched

    @staticmethod
    def _first(rows: Iterable[dict[str, Any]], key: tuple[str, ...]) -> list[dict[str, Any]]:
        """Match Raw adapter's setdefault: first source ordinal wins deterministically."""
        result: dict[tuple[object, ...], dict[str, Any]] = {}
        ordered = sorted(rows, key=lambda row: (_text(row.get("source_member")), _int(row.get("source_record_ordinal")) or 0))
        for row in ordered:
            result.setdefault(tuple(row.get(column) for column in key), row)
        return list(result.values())

    def parse_day(self, date: dt.date, *, source_member_date: dt.date | None = None) -> tuple[list[tuple], dict[str, object]]:
        """Produce the exact Analysis fact tuples for one historical date.

        ``source_member_date`` is deliberately strict when supplied.  It binds
        the comparison to the same Raw delivery as the Raw-direct side; without
        it, the final Warehouse's deterministic canonical first row is used.
        """
        year = date.year
        bac = self._for_member(self._relation_rows("bac", year, "race_date = ?", [date.isoformat()]), source_member_date)
        sed = self._for_member(self._relation_rows("sed", year, "race_date = ?", [date.isoformat()]), source_member_date)
        bac = self._first(bac, ("race_key_raw", "source_member_date"))
        sed = self._first(sed, ("race_key_raw", "horse_no"))
        race_keys = {_text(row.get("race_key_raw")) for row in bac + sed}
        if not race_keys:
            raise WarehouseAnalysisError(f"{date}: no Warehouse BAC/SED rows")
        # DuckDB parameter arrays differ across releases; fetch the yearly
        # immutable partitions then constrain in Python for portability.
        kyi = self._for_member(self._relation_rows("kyi", year), source_member_date)
        cyb = self._for_member(self._relation_rows("cyb", year), source_member_date)
        ukc = self._for_member(self._relation_rows("ukc", year), source_member_date)
        kyi = self._first((row for row in kyi if _text(row.get("race_key_raw")) in race_keys), ("race_key_raw", "horse_no"))
        cyb = self._first((row for row in cyb if _text(row.get("race_horse_key"))[:8] in race_keys), ("race_horse_key", "source_member_date"))
        ukc = self._first(ukc, ("horse_id", "data_date"))

        races: dict[str, dict[str, object]] = {}
        entries: dict[tuple[str, int | None], dict[str, object]] = {}
        results: dict[tuple[str, int | None], dict[str, object]] = {}
        training: dict[tuple[str, int | None], int | None] = {}
        horses: dict[str, dict[str, object]] = {}
        for row in ukc:
            horse_id, profile = _project_ukc(row)
            old = horses.get(horse_id)
            if old is None or str(profile["data_date"]) >= str(old["data_date"]):
                horses[horse_id] = profile
        for row in bac:
            races.setdefault(_text(row.get("race_key_raw")), _project_bac(row, date))
        for row in kyi:
            key, entry = _project_kyi(row); entries.setdefault(key, entry)
        for row in sed:
            key, result, fallback = _project_sed(row, date)
            if key[0] not in races:
                races[key[0]] = fallback
            elif not races[key[0]]["track_condition_code"]:
                races[key[0]]["track_condition_code"] = fallback["track_condition_code"]
            results.setdefault(key, result)
        for row in cyb:
            key, value = _project_cyb(row); training.setdefault(key, value)

        rows: list[tuple] = []
        missing_profiles = 0
        for key, entry in entries.items():
            race, result = races.get(key[0]), results.get(key)
            if race is None or result is None:
                continue
            profile = horses.get(str(entry["horse_id"]), {})
            if not profile:
                missing_profiles += 1
            birth_year = profile.get("birth_year")
            age = date.year - int(birth_year) if birth_year else None
            rows.append((race["race_date"], race["year"], race["venue_code"], race["race_no"], race["track_type"], race["distance"], race["race_condition_code"], race["track_condition_code"], race["grade_code"], race["win5_leg_no"], key[0], key[1], entry["frame_no"], entry["horse_id"], entry["horse_name"], profile.get("sex_code"), age, profile.get("sire_name"), profile.get("broodmare_sire_name"), profile.get("sire_line_code"), profile.get("broodmare_sire_line_code"), entry["jockey_name"], entry["running_style"], entry["distance_aptitude"], entry["uptrend"], training.get(key), result["finish"], result["abnormal_code"], result["final_win_odds"], result["final_win_popularity"], result["win_payout"], result["place_payout"], entry["prev_result_key_1"], entry["prev_race_key_1"]))
        if not rows:
            raise WarehouseAnalysisError(f"{date}: no joinable Warehouse Analysis rows")
        asset_refs = {relation: [str(path) for path in self._paths(relation, year)] for relation in REQUIRED_RELATIONS}
        asset_hashes = {relation: self._asset_sha256s(relation, year) for relation in REQUIRED_RELATIONS}
        return rows, {"source_mode": "warehouse", "source_generation_id": self.current["generation_id"], "source_member_date": source_member_date.isoformat() if source_member_date else None, "source_manifest": asset_refs, "source_sha256s": asset_hashes, "race_count": len({row[10] for row in rows}), "row_count": len(rows), "missing_profile_rows": missing_profiles, "fact_columns": list(FACT_COLUMNS)}
