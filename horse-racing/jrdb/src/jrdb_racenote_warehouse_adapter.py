#!/usr/bin/env python3
"""RaceNote compatibility helpers for accepted JRDB Historical Warehouse rows.

This module deliberately does not change the RaceNote v0.2 schema or prediction
semantics. It reverses only the SQL-friendly flattening performed by
`jrdb_warehouse_normalize` so the existing `racenote_jrdb.BundleBuilder`
continues to own all RaceNote normalization/join logic.

Production routing is intentionally separate. A Warehouse path must pass the
formal Raw-vs-Warehouse RaceNote audit before `racenote_request` may make it
the standard historical backend.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

HISTORICAL_YEAR_FROM = 2010
HISTORICAL_YEAR_TO = 2025
PROVENANCE_COLUMNS = {
    "source_kind", "source_archive_name", "source_archive_sha256",
    "source_member", "source_member_date", "source_member_sha256",
    "source_record_ordinal", "source_record_sha256", "parser_version",
    "warehouse_schema_version", "warehouse_ingested_at", "year",
}
SAFE_DERIVED_COLUMNS = {
    "race_date", "post_time", "workout_date", "comment_date",
    "result_date", "start_time", "birth_date_iso", "data_date_iso",
    "venue_code", "year_yy", "day_raw", "race_no",
}


class RaceNoteWarehouseError(RuntimeError):
    """Warehouse evidence cannot safely satisfy the RaceNote compatibility contract."""


def require_historical_year(year: int) -> int:
    """Fail closed outside the accepted 2010-2025 Historical Warehouse coverage."""
    value = int(year)
    if not HISTORICAL_YEAR_FROM <= value <= HISTORICAL_YEAR_TO:
        raise RaceNoteWarehouseError(
            f"year {value} outside accepted RaceNote Historical Warehouse coverage "
            f"{HISTORICAL_YEAR_FROM}-{HISTORICAL_YEAR_TO}; keep the 2026 PACI/Raw route"
        )
    return value


def _base(row: Mapping[str, Any], *, drop_prefixes: tuple[str, ...] = ()) -> dict[str, Any]:
    """Return parser-owned scalar fields only, leaving consumer semantics untouched."""
    return {
        key: value
        for key, value in row.items()
        if key not in PROVENANCE_COLUMNS
        and key not in SAFE_DERIVED_COLUMNS
        and not any(key.startswith(prefix) for prefix in drop_prefixes)
    }


def unflatten_bac(row: Mapping[str, Any]) -> dict[str, Any]:
    return _base(row)


def unflatten_kyi(row: Mapping[str, Any]) -> dict[str, Any]:
    result = _base(
        row,
        drop_prefixes=("prev_result_key_", "prev_race_key_", "mark_", "pace_index_", "pace_rank_", "forecast_position_", "trait_code_"),
    )
    result["previous"] = [
        {
            "result_key": row.get(f"prev_result_key_{index}"),
            "race_key_raw": row.get(f"prev_race_key_{index}"),
        }
        for index in range(1, 6)
    ]
    mark_names = ("total", "idm", "info", "jockey", "stable", "training", "longshot")
    result["marks"] = {name: row.get(f"mark_{name}") for name in mark_names}
    pace_names = ("front", "pace", "late", "position")
    result["pace_indices"] = {name: row.get(f"pace_index_{name}") for name in pace_names}
    result["pace_ranks"] = {name: row.get(f"pace_rank_{name}") for name in pace_names}
    result["forecast_positions"] = {
        position: (
            row.get(f"forecast_position_{position}_lower"),
            row.get(f"forecast_position_{position}_upper"),
            row.get(f"forecast_position_{position}_code"),
        )
        for position in ("mid", "last3f", "finish")
    }
    result["trait_codes"] = [row.get(f"trait_code_{index}") for index in range(1, 7)]
    return result


def unflatten_cha(row: Mapping[str, Any]) -> dict[str, Any]:
    result = _base(row, drop_prefixes=("clock_", "clock_index_", "pair_"))
    result["clock"] = {name: row.get(f"clock_{name}") for name in ("front", "middle", "last")}
    result["clock_index"] = {
        name: row.get(f"clock_index_{name}") for name in ("front", "middle", "last", "total")
    }
    result["pair"] = {
        "result_code": row.get("pair_result_code"),
        "strength_code": row.get("pair_strength_code"),
        "age": row.get("pair_age"),
        "class_code": row.get("pair_class_code"),
    }
    return result


def unflatten_cyb(row: Mapping[str, Any]) -> dict[str, Any]:
    result = _base(row, drop_prefixes=("course_count_",))
    result["course_counts"] = {
        name: row.get(f"course_count_{name}")
        for name in ("slope", "wood", "dirt", "turf", "pool", "obstacle", "polytrack")
    }
    return result


def unflatten_sed(row: Mapping[str, Any]) -> dict[str, Any]:
    result = _base(row, drop_prefixes=("metric_", "corner_"))
    metric_names = (
        "raw_score", "track_diff", "pace_score", "late_break_score",
        "position_score", "trouble_score", "prev_trouble_score",
        "mid_trouble_score", "late_trouble_score", "race_score",
        "front_index", "late_index", "pace_index", "race_pace_index",
    )
    result["metrics"] = {name: row.get(f"metric_{name}") for name in metric_names}
    result["corners"] = [row.get(f"corner_{index}") for index in range(1, 5)]
    return result


def unflatten_skb(row: Mapping[str, Any]) -> dict[str, Any]:
    result = _base(row, drop_prefixes=("tokki_code_", "equipment_code_", "leg_code_"))
    result["tokki_codes"] = [row.get(f"tokki_code_{index}") for index in range(1, 7)]
    result["equipment_codes"] = [row.get(f"equipment_code_{index}") for index in range(1, 9)]
    result["leg_codes"] = {
        name: row.get(f"leg_code_{name}")
        for name in ("overall", "left_front", "right_front", "left_hind", "right_hind")
    }
    return result


def unflatten_parser_row(family: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Reverse Warehouse flattening into the common-parser logical shape."""
    normalized = family.upper()
    if normalized == "BAC":
        return unflatten_bac(row)
    if normalized == "KYI":
        return unflatten_kyi(row)
    if normalized == "CHA":
        return unflatten_cha(row)
    if normalized == "CYB":
        return unflatten_cyb(row)
    if normalized in {"SED", "ZED"}:
        return unflatten_sed(row)
    if normalized in {"SKB", "ZKB"}:
        return unflatten_skb(row)
    raise RaceNoteWarehouseError(f"unsupported RaceNote Warehouse family: {family!r}")


def source_order(row: Mapping[str, Any]) -> tuple[str, int]:
    """Reproduce `jrdb_raw.iter_archive_records` lexical member/ordinal order."""
    member = str(row.get("source_member") or "").upper()
    ordinal = int(row.get("source_record_ordinal") or 0)
    return member, ordinal


def select_raw_compatible_rows(family: str, rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Select correction snapshots exactly as the current RaceNote Raw route observes them.

    BAC final bundles are overwritten as annual members advance, so the last
    source-order snapshot is the effective race row. CHA/CYB are indexed with
    first-wins semantics by `BundleBuilder`. KYI/SED/SKB use their canonical
    business key and are expected to be unique in the accepted Warehouse.
    """
    normalized = family.upper()
    ordered = sorted(rows, key=source_order)
    if normalized == "BAC":
        by_key: dict[str, Mapping[str, Any]] = {}
        for row in ordered:
            by_key[str(row.get("race_key_raw") or "")] = row
        return [unflatten_bac(by_key[key]) for key in sorted(by_key)]
    if normalized in {"CHA", "CYB"}:
        by_key: dict[str, Mapping[str, Any]] = {}
        for row in ordered:
            by_key.setdefault(str(row.get("race_horse_key") or ""), row)
        converter = unflatten_cha if normalized == "CHA" else unflatten_cyb
        return [converter(by_key[key]) for key in sorted(by_key)]
    converter = {
        "KYI": unflatten_kyi,
        "SED": unflatten_sed,
        "SKB": unflatten_skb,
        "ZED": unflatten_sed,
        "ZKB": unflatten_skb,
    }.get(normalized)
    if converter is None:
        raise RaceNoteWarehouseError(f"unsupported RaceNote Warehouse family: {family!r}")
    return [converter(row) for row in ordered]


def previous_result_year(result_key: str) -> int | None:
    """Return YYYY from `blood_registration_no + YYYYMMDD` without guessing."""
    text = str(result_key or "")
    if len(text) != 16 or not text[-8:].isdigit():
        return None
    return int(text[-8:-4])


def out_of_warehouse_previous_keys(kyi_rows: list[Mapping[str, Any]]) -> list[str]:
    """Identify the 2010 boundary that prevents strict SED/SKB Raw-route replay."""
    values: set[str] = set()
    for row in kyi_rows:
        parsed = unflatten_kyi(row)
        for previous in parsed["previous"]:
            key = str(previous.get("result_key") or "")
            year = previous_result_year(key)
            if year is not None and year < HISTORICAL_YEAR_FROM:
                values.add(key)
    return sorted(values)
