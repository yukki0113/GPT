#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source adapters for JRDB Post-Race Review v0.1.

Fixed-width byte interpretation remains exclusively in jrdb_raw.py. This module
consumes normalized Warehouse rows or already-parsed current SED/KYI/BAC rows
and projects them into one stable Review input shape.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jrdb_postrace_review import (
    lane_bucket,
    normalize_class_group,
    parse_sed_time_seconds,
)

RELATION_PARENT = {
    "bac": "BAC",
    "kyi": "KYI",
    "sed": "SED",
}
REQUIRED_RELATIONS = ("bac", "kyi", "sed")
HISTORICAL_YEAR_FROM = 2010
HISTORICAL_YEAR_TO = 2025


class PostRaceReviewSourceError(RuntimeError):
    """Raised when source evidence cannot satisfy the Review input contract."""


def _text(value: object) -> str:
    """Return stripped text without inventing missing values."""
    if value is None:
        return ""
    return str(value).strip()


def _int(value: object) -> int | None:
    """Return an integer only when the source value is integer-like."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not number.is_integer():
        return None
    return int(number)


def _tenths_to_float(value: object) -> float | None:
    """Convert an integer-tenths source value into a finite float."""
    number = _int(value)
    if number is None:
        return None
    return float(number) / 10.0


def _compact_date(value: object) -> str:
    """Keep digits only for normalized date comparison."""
    return "".join(character for character in _text(value) if character.isdigit())


def _iso_date(value: object) -> str | None:
    """Normalize YYYYMMDD or YYYY-MM-DD without guessing malformed dates."""
    digits = _compact_date(value)
    if len(digits) != 8:
        return None
    try:
        parsed = dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None
    return parsed.isoformat()


def _race_no(race_key: str) -> int | None:
    """Extract the R number while preserving the raw hexadecimal-capable day."""
    if len(race_key) != 8 or not race_key[6:8].isdigit():
        return None
    return int(race_key[6:8])


def _metric(row: Mapping[str, Any], name: str) -> object:
    """Read either flattened Warehouse metric or nested parsed-Raw metric."""
    flat = row.get(f"metric_{name}")
    if flat is not None:
        return flat
    metrics = row.get("metrics")
    if isinstance(metrics, Mapping):
        return metrics.get(name)
    return None


def _corner(row: Mapping[str, Any], index: int) -> object:
    """Read either flattened Warehouse corner or nested parsed-Raw corner."""
    flat = row.get(f"corner_{index}")
    if flat is not None:
        return flat
    corners = row.get("corners")
    if isinstance(corners, (list, tuple)) and len(corners) >= index:
        return corners[index - 1]
    return None


def _race_date_from_sed(row: Mapping[str, Any]) -> str | None:
    """Prefer Warehouse normalized race_date, then SED date_raw."""
    normalized = _iso_date(row.get("race_date"))
    if normalized is not None:
        return normalized
    return _iso_date(row.get("date_raw"))


def project_sed_result(row: Mapping[str, Any]) -> dict[str, object]:
    """Project one SED Warehouse/parsed row into Review result facts."""
    race_key = _text(row.get("race_key_raw"))
    horse_no = _int(row.get("horse_no"))
    race_horse_key = None
    if len(race_key) == 8 and horse_no is not None:
        race_horse_key = f"{race_key}{horse_no:02d}"

    carried_weight_kg = _tenths_to_float(row.get("carried_weight_tenths"))
    course_lane_code = _text(row.get("course_lane_code")) or None
    fourth_corner_lane_code = _text(row.get("fourth_corner_lane_code")) or None

    return {
        "race_key": race_key or None,
        "race_horse_key": race_horse_key,
        "race_date": _race_date_from_sed(row),
        "venue_code": race_key[:2] if len(race_key) == 8 else None,
        "race_no": _race_no(race_key),
        "horse_no": horse_no,
        "horse_id": _text(row.get("blood_registration_no")) or None,
        "horse_name": _text(row.get("horse_name")) or None,
        "distance_m": _int(row.get("distance_m")),
        "surface_code": _text(row.get("surface_code")) or None,
        "turn_code": _text(row.get("turn_code")) or None,
        "layout_code": _text(row.get("layout_code")) or None,
        "track_condition_code": _text(row.get("track_condition_code")) or None,
        "race_type_code": _text(row.get("race_type_code")) or None,
        "race_class_code": _text(row.get("race_class_code")) or None,
        "grade_code": _text(row.get("grade_code")) or None,
        "declared_class_group": normalize_class_group(
            row.get("race_class_code"),
            row.get("grade_code"),
        ),
        "field_size": _int(row.get("field_size")),
        "finish": _int(row.get("finish")),
        "abnormal_code": _text(row.get("abnormal_code")) or None,
        "time_raw": _text(row.get("time_raw")) or None,
        "time_sec": parse_sed_time_seconds(row.get("time_raw")),
        "carried_weight_kg": carried_weight_kg,
        "jockey": _text(row.get("jockey")) or None,
        "trainer": _text(row.get("trainer")) or None,
        "final_win_odds": row.get("final_win_odds"),
        "final_popularity": _int(row.get("final_popularity")),
        "idm": row.get("idm"),
        "first3f_sec": row.get("first3f_sec"),
        "last3f_sec": row.get("last3f_sec"),
        "first3f_leader_diff_sec": row.get("first3f_leader_diff_sec"),
        "last3f_leader_diff_sec": row.get("last3f_leader_diff_sec"),
        "corner1_position": _int(_corner(row, 1)),
        "corner2_position": _int(_corner(row, 2)),
        "corner3_position": _int(_corner(row, 3)),
        "corner4_position": _int(_corner(row, 4)),
        "race_pace_code": _text(row.get("race_pace_code")) or None,
        "horse_pace_code": _text(row.get("horse_pace_code")) or None,
        "course_lane_code": course_lane_code,
        "course_lane_bucket": lane_bucket(course_lane_code),
        "fourth_corner_lane_code": fourth_corner_lane_code,
        "fourth_corner_lane_bucket": lane_bucket(fourth_corner_lane_code),
        "course_code": _text(row.get("course_code")) or None,
        "race_running_style_code": _text(row.get("race_running_style_code")) or None,
        "jrdb_raw_score": _metric(row, "raw_score"),
        "jrdb_track_diff": _metric(row, "track_diff"),
        "jrdb_pace_score": _metric(row, "pace_score"),
        "jrdb_late_break_score": _metric(row, "late_break_score"),
        "jrdb_position_score": _metric(row, "position_score"),
        "jrdb_trouble_score": _metric(row, "trouble_score"),
        "jrdb_prev_trouble_score": _metric(row, "prev_trouble_score"),
        "jrdb_mid_trouble_score": _metric(row, "mid_trouble_score"),
        "jrdb_late_trouble_score": _metric(row, "late_trouble_score"),
        "jrdb_race_score": _metric(row, "race_score"),
        "jrdb_front_index": _metric(row, "front_index"),
        "jrdb_late_index": _metric(row, "late_index"),
        "jrdb_pace_index": _metric(row, "pace_index"),
        "jrdb_race_pace_index": _metric(row, "race_pace_index"),
        "source_member": _text(row.get("source_member")) or None,
        "source_member_date": _iso_date(row.get("source_member_date")),
        "source_archive_sha256": _text(row.get("source_archive_sha256")) or None,
        "source_member_sha256": _text(row.get("source_member_sha256")) or None,
        "source_record_sha256": _text(row.get("source_record_sha256")) or None,
    }


def project_kyi_context(row: Mapping[str, Any]) -> tuple[tuple[str, int | None], dict[str, object]]:
    """Project pre-race KYI context used only as supporting Review evidence."""
    race_key = _text(row.get("race_key_raw"))
    horse_no = _int(row.get("horse_no"))
    key = (race_key, horse_no)
    return key, {
        "frame_no": _int(row.get("frame_no")),
        "declared_running_style_code": _text(row.get("running_style_code")) or None,
        "start_index": row.get("start_index"),
        "late_break_rate": row.get("late_break_rate"),
    }


def project_bac_context(row: Mapping[str, Any]) -> tuple[str, dict[str, object]]:
    """Project race-master context without replacing SED result facts."""
    race_key = _text(row.get("race_key_raw"))
    return race_key, {
        "post_time": _text(row.get("post_time")) or _text(row.get("post_time_raw")) or None,
        "bac_course_code": _text(row.get("course_code")) or None,
        "meeting": _text(row.get("meeting")) or None,
    }


def build_review_input_rows(
    sed_rows: Iterable[Mapping[str, Any]],
    kyi_rows: Iterable[Mapping[str, Any]] = (),
    bac_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, object]]:
    """Join normalized SED results to optional KYI/BAC supporting context."""
    kyi_by_key: dict[tuple[str, int | None], dict[str, object]] = {}
    for row in kyi_rows:
        key, context = project_kyi_context(row)
        kyi_by_key.setdefault(key, context)

    bac_by_race: dict[str, dict[str, object]] = {}
    ordered_bac = sorted(
        bac_rows,
        key=lambda row: (
            _text(row.get("source_member_date")),
            _text(row.get("source_member")),
            _int(row.get("source_record_ordinal")) or 0,
        ),
    )
    for row in ordered_bac:
        race_key, context = project_bac_context(row)
        if race_key:
            bac_by_race[race_key] = context

    results: list[dict[str, object]] = []
    seen: set[tuple[str, int | None]] = set()
    for row in sed_rows:
        projected = project_sed_result(row)
        race_key = _text(projected.get("race_key"))
        horse_no = _int(projected.get("horse_no"))
        key = (race_key, horse_no)
        if not race_key or horse_no is None:
            raise PostRaceReviewSourceError("SED Review row has no canonical race/horse key")
        if key in seen:
            raise PostRaceReviewSourceError(
                f"duplicate SED Review key: {race_key}/{horse_no}"
            )
        seen.add(key)

        projected.update(kyi_by_key.get(key, {}))
        projected.update(bac_by_race.get(race_key, {}))
        results.append(projected)

    results.sort(
        key=lambda row: (
            _text(row.get("race_date")),
            _text(row.get("race_key")),
            _int(row.get("horse_no")) or 0,
        )
    )
    return results


class HistoricalReviewWarehouseReader:
    """Read Review source rows from one accepted JRDB Historical Warehouse."""

    def __init__(self, current: Path, *, asset_roots: Mapping[str, Path]) -> None:
        self.current_path = Path(current)
        self.current = self._read_json(self.current_path)
        if (
            self.current.get("artifact_type") != "jrdb_normalized_warehouse_current"
            or self.current.get("status") != "accepted"
        ):
            raise PostRaceReviewSourceError(
                "accepted dedicated JRDB Warehouse current pointer required"
            )

        manifest_ref = self.current.get("manifest")
        if not isinstance(manifest_ref, str) or not manifest_ref.endswith(
            "/manifest.json"
        ):
            raise PostRaceReviewSourceError("Warehouse current has no final manifest")

        self.manifest = self._read_json(self.current_path.parent / manifest_ref)
        if (
            self.manifest.get("status") != "PASS"
            or self.manifest.get("generation_id")
            != self.current.get("generation_id")
        ):
            raise PostRaceReviewSourceError("Warehouse current/manifest mismatch")

        self.assets = list(self.manifest.get("assets") or [])
        self.asset_roots = {
            str(key).upper(): Path(value)
            for key, value in asset_roots.items()
        }
        if not self.assets:
            raise PostRaceReviewSourceError("Warehouse manifest has no assets")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PostRaceReviewSourceError(
                f"unreadable Warehouse JSON: {path}"
            ) from exc
        if not isinstance(value, dict):
            raise PostRaceReviewSourceError(
                f"Warehouse JSON object required: {path}"
            )
        return value

    def _paths(self, relation: str, year: int) -> list[Path]:
        normalized = relation.lower()
        parent = RELATION_PARENT[normalized]
        root = self.asset_roots.get(parent)
        if root is None:
            raise PostRaceReviewSourceError(f"asset root not supplied for {parent}")

        paths: list[Path] = []
        for asset in self.assets:
            if str(asset.get("family", "")).lower() != normalized:
                continue
            if int(asset.get("year", -1)) != year:
                continue
            path = root / str(asset.get("relative_path", ""))
            if not path.is_file():
                raise PostRaceReviewSourceError(
                    f"missing immutable Warehouse asset: {path}"
                )
            paths.append(path)

        if not paths:
            raise PostRaceReviewSourceError(
                f"manifest has no {normalized}/{year} asset"
            )
        return paths

    def _rows(
        self,
        relation: str,
        year: int,
        where: str = "",
        params: list[object] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            import duckdb
        except ImportError as exc:
            raise PostRaceReviewSourceError(
                "Historical Review Warehouse reader requires duckdb"
            ) from exc

        paths = self._paths(relation, year)
        connection = duckdb.connect(":memory:")
        try:
            marks = ", ".join("?" for _ in paths)
            query = f"SELECT * FROM read_parquet([{marks}], union_by_name=true)"
            if where:
                query += " WHERE " + where
            cursor = connection.execute(
                query,
                [str(path) for path in paths] + list(params or []),
            )
            names = [item[0] for item in cursor.description]
            return [
                dict(zip(names, values))
                for values in cursor.fetchall()
            ]
        finally:
            connection.close()

    def read_year(
        self,
        year: int,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        """Return one accepted Warehouse year's unified Review source rows."""
        if not HISTORICAL_YEAR_FROM <= year <= HISTORICAL_YEAR_TO:
            raise PostRaceReviewSourceError(
                f"{year}: outside accepted historical Review Warehouse coverage "
                f"{HISTORICAL_YEAR_FROM}-{HISTORICAL_YEAR_TO}"
            )

        sed = self._rows("sed", year)
        if not sed:
            raise PostRaceReviewSourceError(
                f"{year}: no Warehouse SED rows"
            )

        race_keys = {
            _text(row.get("race_key_raw"))
            for row in sed
            if _text(row.get("race_key_raw"))
        }

        kyi = [
            row
            for row in self._rows("kyi", year)
            if _text(row.get("race_key_raw")) in race_keys
        ]
        bac = [
            row
            for row in self._rows("bac", year)
            if _text(row.get("race_key_raw")) in race_keys
        ]

        rows = build_review_input_rows(sed, kyi, bac)
        if not rows:
            raise PostRaceReviewSourceError(
                f"{year}: no Review source rows"
            )

        dates = sorted(
            {
                _text(row.get("race_date"))
                for row in rows
                if _text(row.get("race_date"))
            }
        )
        return rows, {
            "source_mode": "historical_warehouse",
            "source_generation_id": self.current.get("generation_id"),
            "year": year,
            "period_from": dates[0] if dates else None,
            "period_to": dates[-1] if dates else None,
            "race_count": len({row["race_key"] for row in rows}),
            "row_count": len(rows),
            "relations": list(REQUIRED_RELATIONS),
        }

    def read_day(self, day: dt.date) -> tuple[list[dict[str, object]], dict[str, object]]:
        """Return one historical day's unified Review input rows and provenance."""
        if not HISTORICAL_YEAR_FROM <= day.year <= HISTORICAL_YEAR_TO:
            raise PostRaceReviewSourceError(
                f"{day}: outside accepted historical Review Warehouse coverage "
                f"{HISTORICAL_YEAR_FROM}-{HISTORICAL_YEAR_TO}"
            )

        sed = self._rows(
            "sed",
            day.year,
            "race_date = ?",
            [day.isoformat()],
        )
        if not sed:
            raise PostRaceReviewSourceError(f"{day}: no Warehouse SED rows")

        race_keys = {
            _text(row.get("race_key_raw"))
            for row in sed
            if _text(row.get("race_key_raw"))
        }

        kyi = [
            row
            for row in self._rows("kyi", day.year)
            if _text(row.get("race_key_raw")) in race_keys
        ]
        bac = self._rows(
            "bac",
            day.year,
            "race_date = ?",
            [day.isoformat()],
        )

        rows = build_review_input_rows(sed, kyi, bac)
        if not rows:
            raise PostRaceReviewSourceError(f"{day}: no Review source rows")

        return rows, {
            "source_mode": "historical_warehouse",
            "source_generation_id": self.current.get("generation_id"),
            "race_date": day.isoformat(),
            "race_count": len({row["race_key"] for row in rows}),
            "row_count": len(rows),
            "relations": list(REQUIRED_RELATIONS),
        }
