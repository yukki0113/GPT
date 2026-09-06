#!/usr/bin/env python3
"""Build the JRDB PWA independent-index longitudinal base directly from annual Raw ZIPs.

The output is a normalized research SQLite used by RunPerf / Ability / Edge work.
It deliberately keeps pre-race material, current-result material, workouts, training
analysis and pedigree observations in separate tables so availability boundaries are
visible in the schema instead of being implicit in feature code.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from jrdb_index_base_adapter import (
    parse_bac as adapted_parse_bac,
    parse_kyi as adapted_parse_kyi,
)
from jrdb_ukc import parse_ukc_record

VERSION = "0.1.0"
SCHEMA_VERSION = "v0.1"
REQUIRED_KINDS = ("BAC", "KYI", "SED", "UKC")
OPTIONAL_KINDS = ("CHA", "CYB")


def _text(raw: bytes, offset: int, width: int) -> str:
    """Decode one CP932 fixed-width field and strip surrounding spaces."""
    return raw[offset : offset + width].decode("cp932", "strict").strip()


def _int(raw: bytes, offset: int, width: int) -> int | None:
    """Parse a signed integer field. Blank and malformed values become None."""
    value = _text(raw, offset, width).replace(",", "")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _float(raw: bytes, offset: int, width: int) -> float | None:
    """Parse a signed decimal field. Blank and malformed values become None."""
    value = _text(raw, offset, width).replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _scaled_int(raw: bytes, offset: int, width: int, divisor: float) -> float | None:
    value = _int(raw, offset, width)
    if value is None:
        return None
    return value / divisor


def _signed_int_text(raw: bytes, offset: int, width: int) -> int | None:
    """Parse fields such as +02 / -10 used for body-weight change."""
    value = _text(raw, offset, width)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _yyyymmdd(value: str) -> str | None:
    if not value or not re.fullmatch(r"\d{8}", value):
        return None
    try:
        return dt.datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _member_date(member: str) -> str | None:
    """Derive an ISO business date from a canonical KINDyymmdd.txt member name.

    The index project currently targets 2010-2025 (and current 2026 operation), so
    two-digit member years are intentionally interpreted as 20yy.
    """
    match = re.fullmatch(r"[A-Z]+(\d{6})\.txt", Path(member).name, re.IGNORECASE)
    if match is None:
        return None
    compact = f"20{match.group(1)}"
    return _yyyymmdd(compact)


def _year_from_date_or_key(race_date: str | None, raw: bytes) -> int:
    """Return the four-digit year, preferring the explicit YYYYMMDD field."""
    if race_date is not None:
        return int(race_date[:4])
    two_digit_year = _int(raw, 2, 2)
    if two_digit_year is None:
        raise ValueError("race year is missing")
    return 2000 + two_digit_year


def _semantic_hash(values: dict[str, Any]) -> str:
    """Hash a normalized semantic payload rather than a horse-level raw record."""
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hhmm(value: str) -> str | None:
    if not value or not re.fullmatch(r"\d{4}", value):
        return None
    try:
        hour = int(value[:2])
        minute = int(value[2:])
    except ValueError:
        return None
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _race_time_sec(raw: bytes, offset: int = 143) -> float | None:
    """Parse SED 4-byte race time: 1 byte minutes + 3 bytes tenths of seconds."""
    value = _text(raw, offset, 4)
    if len(value) != 4 or not value.isdigit():
        return None
    return int(value[0]) * 60.0 + int(value[1:]) / 10.0


def _record_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_members(zf: zipfile.ZipFile, kind: str) -> list[str]:
    pattern = re.compile(rf"^{kind}\d{{6}}\.txt$", re.IGNORECASE)
    return sorted(
        [name for name in zf.namelist() if pattern.fullmatch(Path(name).name)],
        key=lambda name: Path(name).name.upper(),
    )


def parse_bac(raw: bytes, member: str) -> dict[str, Any]:
    """Parse race-level pre-race conditions from BAC."""
    race_date = _yyyymmdd(_text(raw, 8, 8))
    return {
        "race_key": _text(raw, 0, 8),
        "race_date": race_date,
        "year": _year_from_date_or_key(race_date, raw),
        "venue_code": _text(raw, 0, 2),
        "race_no": _int(raw, 6, 2),
        "start_time": _hhmm(_text(raw, 16, 4)),
        "distance_m": _int(raw, 20, 4),
        "surface_code": _text(raw, 24, 1),
        "turn_code": _text(raw, 25, 1),
        "inner_outer_code": _text(raw, 26, 1),
        "race_type_code": _text(raw, 27, 2),
        "race_condition_code": _text(raw, 29, 2),
        "race_symbol_code": _text(raw, 31, 3),
        "weight_condition_code": _text(raw, 34, 1),
        "grade_code": _text(raw, 35, 1),
        "race_name": _text(raw, 36, 50),
        "declared_field_size": _int(raw, 94, 2),
        "course_code": _text(raw, 96, 1),
        "meeting_area_code": _text(raw, 97, 1),
        "availability_class": "PRE_RACE",
        "source_kind": "BAC",
        "source_member": member,
        "record_hash": _record_hash(raw),
    }


def parse_kyi(raw: bytes, member: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse one pre-race runner record plus its explicit previous 1-5 links."""
    race_key = _text(raw, 0, 8)
    horse_no = _int(raw, 8, 2)
    runner = {
        "race_key": race_key,
        "horse_no": horse_no,
        "horse_id": _text(raw, 10, 8),
        "horse_name": _text(raw, 18, 36),
        "frame_no": _int(raw, 323, 1),
        "sex_code": _text(raw, 403, 1),
        "jockey_name": _text(raw, 171, 12),
        "jockey_code": _text(raw, 335, 5),
        "trainer_name": _text(raw, 187, 12),
        "trainer_code": _text(raw, 340, 5),
        "carried_weight_kg": _scaled_int(raw, 183, 3, 10.0),
        "running_style_code": _text(raw, 89, 1),
        "distance_aptitude_code": _text(raw, 90, 1),
        "uptrend_code": _text(raw, 91, 1),
        "rotation_interval": _int(raw, 92, 3),
        "pre_idm": _float(raw, 54, 5),
        "training_score": _float(raw, 144, 5),
        "stable_score": _float(raw, 149, 5),
        "training_arrow_code": _text(raw, 154, 1),
        "stable_evaluation_code": _text(raw, 155, 1),
        "blinker_code": _text(raw, 170, 1),
        "condition_class_code": _text(raw, 357, 1),
        "body_weight_pre_kg": _int(raw, 396, 3),
        "body_weight_change_pre_kg": _signed_int_text(raw, 399, 3),
        "start_index": _float(raw, 519, 4),
        "slow_start_rate": _float(raw, 523, 4),
        "stable_run_no": _int(raw, 559, 2),
        "stable_entry_date": _yyyymmdd(_text(raw, 561, 8)),
        "stable_days_before": _int(raw, 569, 3),
        "expected_ten_index": _float(raw, 358, 5),
        "expected_pace_index": _float(raw, 363, 5),
        "expected_last3f_index": _float(raw, 368, 5),
        "expected_position_index": _float(raw, 373, 5),
        "expected_race_pace": _text(raw, 378, 1),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }
    links: list[dict[str, Any]] = []
    for sequence in range(1, 6):
        result_offset = 203 + (sequence - 1) * 16
        race_offset = 283 + (sequence - 1) * 8
        links.append(
            {
                "race_key": race_key,
                "horse_no": horse_no,
                "sequence": sequence,
                "prev_result_key": _text(raw, result_offset, 16) or None,
                "prev_race_key": _text(raw, race_offset, 8) or None,
            }
        )
    return runner, links


# Keep pre-common implementations only as temporary equivalence oracles.
LegacyParseBac = parse_bac
LegacyParseKyi = parse_kyi
parse_bac = adapted_parse_bac
parse_kyi = adapted_parse_kyi


def parse_sed(
    raw: bytes,
    member: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Parse current result, result context, and a BAC-missing fallback from SED."""
    race_key = _text(raw, 0, 8)
    horse_no = _int(raw, 8, 2)
    horse_id = _text(raw, 10, 8)
    race_date_raw = _text(raw, 18, 8)
    result_key = f"{horse_id}{race_date_raw}" if horse_id and race_date_raw else None

    result = {
        "race_key": race_key,
        "horse_no": horse_no,
        "result_key": result_key,
        "horse_id": horse_id,
        "horse_name": _text(raw, 26, 36),
        "finish": _int(raw, 140, 2),
        "abnormal_code": _text(raw, 142, 1),
        "time_sec": _race_time_sec(raw),
        "carried_weight_kg": _scaled_int(raw, 147, 3, 10.0),
        "jockey_name": _text(raw, 150, 12),
        "jockey_code": _text(raw, 322, 5),
        "trainer_name": _text(raw, 162, 12),
        "trainer_code": _text(raw, 327, 5),
        "final_win_odds": _float(raw, 174, 6),
        "final_win_popularity": _int(raw, 180, 2),
        "final_place_odds_lower": _float(raw, 290, 6),
        "idm": _int(raw, 182, 3),
        "raw_score": _int(raw, 185, 3),
        "jrdb_track_diff": _int(raw, 188, 3),
        "jrdb_pace_score": _int(raw, 191, 3),
        "jrdb_slow_start_score": _int(raw, 194, 3),
        "jrdb_position_score": _int(raw, 197, 3),
        "jrdb_trouble_score": _int(raw, 200, 3),
        "jrdb_early_trouble_score": _int(raw, 203, 3),
        "jrdb_mid_trouble_score": _int(raw, 206, 3),
        "jrdb_late_trouble_score": _int(raw, 209, 3),
        "jrdb_race_score": _int(raw, 212, 3),
        "course_lane_code": _text(raw, 215, 1),
        "result_uptrend_code": _text(raw, 216, 1),
        "result_class_code": _text(raw, 217, 2),
        "body_condition_code": _text(raw, 219, 1),
        "mood_code": _text(raw, 220, 1),
        "race_pace": _text(raw, 221, 1),
        "horse_pace": _text(raw, 222, 1),
        "front_index": _float(raw, 223, 5),
        "last3f_index": _float(raw, 228, 5),
        "pace_index": _float(raw, 233, 5),
        "race_pace_index": _float(raw, 238, 5),
        "first_second_time_diff_sec": _scaled_int(raw, 255, 3, 10.0),
        "first3f_sec": _scaled_int(raw, 258, 3, 10.0),
        "last3f_sec": _scaled_int(raw, 261, 3, 10.0),
        "corner1": _int(raw, 308, 2),
        "corner2": _int(raw, 310, 2),
        "corner3": _int(raw, 312, 2),
        "corner4": _int(raw, 314, 2),
        "first3f_leader_diff_sec": _scaled_int(raw, 316, 3, 10.0),
        "last3f_leader_diff_sec": _scaled_int(raw, 319, 3, 10.0),
        "body_weight_kg": _int(raw, 332, 3),
        "body_weight_change_kg": _signed_int_text(raw, 335, 3),
        "weather_code": _text(raw, 338, 1),
        "course_code": _text(raw, 339, 1),
        "race_running_style_code": _text(raw, 340, 1),
        "fourth_corner_lane_code": _text(raw, 369, 1),
        "win_payout": _int(raw, 341, 7),
        "place_payout": _int(raw, 348, 7),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }

    race_date = _yyyymmdd(race_date_raw)
    fallback = {
        "race_key": race_key,
        "race_date": race_date,
        "year": _year_from_date_or_key(race_date, raw),
        "venue_code": _text(raw, 0, 2),
        "race_no": _int(raw, 6, 2),
        "start_time": _hhmm(_text(raw, 370, 4)),
        "distance_m": _int(raw, 62, 4),
        "surface_code": _text(raw, 66, 1),
        "turn_code": _text(raw, 67, 1),
        "inner_outer_code": _text(raw, 68, 1),
        "race_type_code": _text(raw, 71, 2),
        "race_condition_code": _text(raw, 73, 2),
        "race_symbol_code": _text(raw, 75, 3),
        "weight_condition_code": _text(raw, 78, 1),
        "grade_code": _text(raw, 79, 1),
        "race_name": _text(raw, 80, 50),
        "declared_field_size": _int(raw, 130, 2),
        "course_code": _text(raw, 339, 1),
        "meeting_area_code": None,
        "availability_class": "CURRENT_RESULT_FALLBACK",
        "source_kind": "SED_FALLBACK",
        "source_member": member,
        "record_hash": _record_hash(raw),
    }

    result_context_semantics = {
        "race_key": race_key,
        "track_condition_code": _text(raw, 69, 2),
        "weather_code": _text(raw, 338, 1),
    }
    result_context = {
        **result_context_semantics,
        "source_member": member,
        "semantic_hash": _semantic_hash(result_context_semantics),
    }
    return result, result_context, fallback


def parse_cha(raw: bytes, member: str) -> dict[str, Any]:
    """Parse the JRDB selected main workout (CHA)."""
    return {
        "race_key": _text(raw, 0, 8),
        "horse_no": _int(raw, 8, 2),
        "training_date": _yyyymmdd(_text(raw, 12, 8)),
        "weekday": _text(raw, 10, 2),
        "workout_count": _int(raw, 20, 1),
        "course_code": _text(raw, 21, 2),
        "effort_code": _text(raw, 23, 1),
        "chase_state_code": _text(raw, 24, 2),
        "rider_type_code": _text(raw, 26, 1),
        "furlong_count": _int(raw, 27, 1),
        "first_segment_sec": _scaled_int(raw, 28, 3, 10.0),
        "middle_segment_sec": _scaled_int(raw, 31, 3, 10.0),
        "final_segment_sec": _scaled_int(raw, 34, 3, 10.0),
        "jrdb_first_segment_index": _int(raw, 37, 3),
        "jrdb_middle_segment_index": _int(raw, 40, 3),
        "jrdb_final_segment_index": _int(raw, 43, 3),
        "jrdb_workout_index": _int(raw, 46, 3),
        "pair_result_code": _text(raw, 49, 1),
        "pair_effort_code": _text(raw, 50, 1),
        "pair_age": _int(raw, 51, 2),
        "pair_class_code": _text(raw, 53, 2),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }


def _used_flag(raw: bytes, offset: int) -> int | None:
    value = _text(raw, offset, 2)
    if value == "01":
        return 1
    if value == "00":
        return 0
    return None


def parse_cyb(raw: bytes, member: str) -> dict[str, Any]:
    """Parse JRDB intermediate training analysis (CYB)."""
    return {
        "race_key": _text(raw, 0, 8),
        "horse_no": _int(raw, 8, 2),
        "training_type_code": _text(raw, 10, 2),
        "training_course_type_code": _text(raw, 12, 1),
        "used_slope": _used_flag(raw, 13),
        "used_wood": _used_flag(raw, 15),
        "used_dirt": _used_flag(raw, 17),
        "used_turf": _used_flag(raw, 19),
        "used_pool": _used_flag(raw, 21),
        "used_jump": _used_flag(raw, 23),
        "used_polytrack": _used_flag(raw, 25),
        "training_distance_code": _text(raw, 27, 1),
        "training_focus_code": _text(raw, 28, 1),
        "jrdb_workout_index": _int(raw, 29, 3),
        "finish_index": _int(raw, 32, 3),
        "training_volume_code": _text(raw, 35, 1),
        "finish_change_code": _text(raw, 36, 1),
        "training_evaluation_code": _text(raw, 85, 1),
        "week_ago_workout_index": _int(raw, 86, 3),
        "week_ago_course_code": _text(raw, 89, 2),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }


# Keep remaining pre-common implementations as equivalence oracles until
# production binding is switched after exact adapter regression tests pass.
LegacyParseSed = parse_sed
LegacyParseCha = parse_cha
LegacyParseCyb = parse_cyb


def profile_observation(raw: bytes, member: str) -> dict[str, Any]:
    """Parse one dated UKC profile observation for as-of pedigree joins."""
    record = parse_ukc_record(raw)
    data_date = _yyyymmdd(record.data_date)
    if data_date is None:
        data_date = _member_date(member)
    if data_date is None:
        raise ValueError(f"UKC profile observation has no usable date: {member}")

    return {
        "horse_id": record.horse_id,
        "data_date": data_date,
        "horse_name": record.horse_name,
        "sex_code": record.sex_code,
        "sire_name": record.sire_name,
        "dam_name": record.dam_name,
        "broodmare_sire_name": record.broodmare_sire_name,
        "birth_date": _yyyymmdd(record.birth_date) or record.birth_date,
        "sire_birth_year": record.sire_birth_year,
        "dam_birth_year": record.dam_birth_year,
        "broodmare_sire_birth_year": record.broodmare_sire_birth_year,
        "breeder_name": record.breeder_name,
        "breeding_place": record.breeding_place,
        "sire_line_code": record.sire_line_code,
        "broodmare_sire_line_code": record.broodmare_sire_line_code,
        "semantic_hash": record.semantic_hash(),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }


@dataclass
class YearData:
    races: dict[str, dict[str, Any]]
    result_contexts: dict[str, dict[str, Any]]
    runners: dict[tuple[str, int], dict[str, Any]]
    previous_links: list[dict[str, Any]]
    results: dict[tuple[str, int], dict[str, Any]]
    workouts: dict[tuple[str, int], dict[str, Any]]
    training: dict[tuple[str, int], dict[str, Any]]
    profiles: list[dict[str, Any]]


def _unique_put(
    target: dict[Any, dict[str, Any]],
    key: Any,
    value: dict[str, Any],
    kind: str,
) -> None:
    existing = target.get(key)
    if existing is None:
        target[key] = value
        return
    existing_hash = existing.get("record_hash") or existing.get("semantic_hash")
    value_hash = value.get("record_hash") or value.get("semantic_hash")
    if existing_hash == value_hash:
        return
    raise ValueError(f"non-identical duplicate {kind} key={key}")


def _put_bac_revision(
    target: dict[str, dict[str, Any]],
    value: dict[str, Any],
) -> None:
    """Resolve a BAC postponement revision without relaxing race identity checks."""
    key = value["race_key"]
    existing = target.get(key)
    if existing is None:
        target[key] = value
        return
    if existing.get("record_hash") == value.get("record_hash"):
        return

    ignored_fields = {"race_date", "source_member", "record_hash"}
    existing_identity = {
        field: field_value
        for field, field_value in existing.items()
        if field not in ignored_fields
    }
    value_identity = {
        field: field_value
        for field, field_value in value.items()
        if field not in ignored_fields
    }
    if existing_identity != value_identity:
        raise ValueError(f"non-identical duplicate BAC key={key}")

    existing_date = existing.get("race_date")
    value_date = value.get("race_date")
    if not existing_date or not value_date:
        raise ValueError(f"ambiguous BAC date revision key={key}")
    if value_date > existing_date:
        target[key] = value


def _put_pre_race_revision(
    target: dict[tuple[str, int], dict[str, Any]],
    key: tuple[str, int],
    value: dict[str, Any],
    kind: str,
    races: dict[str, dict[str, Any]],
) -> None:
    """Resolve postponed-day pre-race snapshots against the canonical BAC race date."""
    existing = target.get(key)
    if existing is None:
        target[key] = value
        return
    if existing.get("record_hash") == value.get("record_hash"):
        return

    race = races.get(key[0])
    canonical_date = race.get("race_date") if race else None
    existing_date = _member_date(existing.get("source_member", ""))
    value_date = _member_date(value.get("source_member", ""))
    if canonical_date is None or existing_date is None or value_date is None:
        raise ValueError(f"ambiguous duplicate {kind} key={key}")

    existing_is_canonical = existing_date == canonical_date
    value_is_canonical = value_date == canonical_date
    if existing_is_canonical and not value_is_canonical:
        return
    if value_is_canonical and not existing_is_canonical:
        target[key] = value
        return
    raise ValueError(f"ambiguous duplicate {kind} key={key}")


def _archive_path(raw_root: Path, kind: str, year: int) -> Path:
    return raw_root / kind / f"{kind}_{year}.zip"


def _read_kind(
    archive: Path,
    kind: str,
    parser: Callable[[bytes, str], Any],
) -> Iterable[tuple[str, Any]]:
    with zipfile.ZipFile(archive) as zf:
        for member in _canonical_members(zf, kind):
            for raw in zf.read(member).splitlines():
                if not raw:
                    continue
                yield member, parser(raw, member)


def load_year(raw_root: Path, year: int) -> YearData:
    races: dict[str, dict[str, Any]] = {}
    result_contexts: dict[str, dict[str, Any]] = {}
    runners: dict[tuple[str, int], dict[str, Any]] = {}
    previous_links: list[dict[str, Any]] = []
    results: dict[tuple[str, int], dict[str, Any]] = {}
    workouts: dict[tuple[str, int], dict[str, Any]] = {}
    training: dict[tuple[str, int], dict[str, Any]] = {}
    profiles: list[dict[str, Any]] = []

    for _, race in _read_kind(_archive_path(raw_root, "BAC", year), "BAC", parse_bac):
        _put_bac_revision(races, race)

    for _, parsed in _read_kind(_archive_path(raw_root, "KYI", year), "KYI", parse_kyi):
        runner, links = parsed
        key = (runner["race_key"], runner["horse_no"])
        _unique_put(runners, key, runner, "KYI")
        previous_links.extend(links)

    for _, parsed in _read_kind(_archive_path(raw_root, "SED", year), "SED", parse_sed):
        result, result_context, fallback = parsed
        key = (result["race_key"], result["horse_no"])
        _unique_put(results, key, result, "SED")
        _unique_put(result_contexts, result_context["race_key"], result_context, "SED_RACE_CONTEXT")
        if fallback["race_key"] not in races:
            races[fallback["race_key"]] = fallback

    cha_archive = _archive_path(raw_root, "CHA", year)
    if cha_archive.exists():
        for _, workout in _read_kind(cha_archive, "CHA", parse_cha):
            key = (workout["race_key"], workout["horse_no"])
            _put_pre_race_revision(workouts, key, workout, "CHA", races)

    cyb_archive = _archive_path(raw_root, "CYB", year)
    if cyb_archive.exists():
        for _, row in _read_kind(cyb_archive, "CYB", parse_cyb):
            key = (row["race_key"], row["horse_no"])
            _put_pre_race_revision(training, key, row, "CYB", races)

    for _, profile in _read_kind(_archive_path(raw_root, "UKC", year), "UKC", profile_observation):
        profiles.append(profile)

    return YearData(
        races,
        result_contexts,
        runners,
        previous_links,
        results,
        workouts,
        training,
        profiles,
    )


def _insert_dicts(connection: sqlite3.Connection, table: str, rows: Iterable[dict[str, Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    columns = list(rows[0].keys())
    sql = (
        f"INSERT INTO {table} ({','.join(columns)}) "
        f"VALUES ({','.join('?' for _ in columns)})"
    )
    connection.executemany(sql, [tuple(row[column] for column in columns) for row in rows])
    return len(rows)


def _source_meta(raw_root: Path, year: int, kind: str, hash_archives: bool) -> dict[str, Any] | None:
    path = _archive_path(raw_root, kind, year)
    if not path.exists():
        return None
    with zipfile.ZipFile(path) as zf:
        member_count = len(_canonical_members(zf, kind))
    return {
        "source_kind": kind,
        "year": year,
        "archive_path": str(path),
        "archive_sha256": _archive_sha256(path) if hash_archives else None,
        "archive_size_bytes": path.stat().st_size,
        "member_count": member_count,
    }


def build(
    raw_root: Path,
    years: list[int],
    output: Path,
    schema_path: Path,
    hash_archives: bool = True,
) -> dict[str, Any]:
    """Build the longitudinal base. Existing output files are never overwritten."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing database: {output}")

    for year in years:
        for kind in REQUIRED_KINDS:
            path = _archive_path(raw_root, kind, year)
            if not path.exists():
                raise FileNotFoundError(f"required archive missing: {path}")

    connection = sqlite3.connect(output)
    connection.execute("PRAGMA journal_mode=MEMORY")
    connection.execute("PRAGMA synchronous=OFF")
    connection.executescript(schema_path.read_text(encoding="utf-8"))

    started = dt.datetime.now().isoformat(timespec="seconds")
    build_id = connection.execute(
        """
        INSERT INTO meta_index_base_build(
          builder_version,schema_version,started_at,status,years_json
        ) VALUES(?,?,?,?,?)
        """,
        (VERSION, SCHEMA_VERSION, started, "RUNNING", json.dumps(sorted(years))),
    ).lastrowid

    anomaly_count = 0
    source_manifest: list[dict[str, Any]] = []
    try:
        for year in sorted(years):
            for kind in REQUIRED_KINDS + OPTIONAL_KINDS:
                meta = _source_meta(raw_root, year, kind, hash_archives)
                if meta is None:
                    anomaly_count += 1
                    connection.execute(
                        """
                        INSERT INTO meta_index_base_anomaly(
                          build_id,severity,anomaly_type,source_kind,year,detail,detected_at
                        ) VALUES(?,?,?,?,?,?,?)
                        """,
                        (
                            build_id,
                            "WARN",
                            "OPTIONAL_ARCHIVE_MISSING",
                            kind,
                            year,
                            str(_archive_path(raw_root, kind, year)),
                            dt.datetime.now().isoformat(timespec="seconds"),
                        ),
                    )
                    continue
                source_manifest.append(meta)
                connection.execute(
                    """
                    INSERT INTO meta_index_base_source(
                      build_id,source_kind,year,archive_path,archive_sha256,
                      archive_size_bytes,member_count,imported_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        build_id,
                        meta["source_kind"],
                        meta["year"],
                        meta["archive_path"],
                        meta["archive_sha256"],
                        meta["archive_size_bytes"],
                        meta["member_count"],
                        dt.datetime.now().isoformat(timespec="seconds"),
                    ),
                )

            data = load_year(raw_root, year)
            _insert_dicts(connection, "race_context", data.races.values())
            _insert_dicts(connection, "race_result_context", data.result_contexts.values())
            _insert_dicts(connection, "runner_pre", data.runners.values())
            _insert_dicts(connection, "runner_previous_link", data.previous_links)
            _insert_dicts(connection, "runner_result", data.results.values())
            _insert_dicts(connection, "workout_main", data.workouts.values())
            _insert_dicts(connection, "training_analysis", data.training.values())

            # UKC is snapshot-like and may repeat semantically identical observations.
            for profile in data.profiles:
                columns = list(profile.keys())
                connection.execute(
                    f"INSERT OR IGNORE INTO horse_profile_observation ({','.join(columns)}) "
                    f"VALUES ({','.join('?' for _ in columns)})",
                    tuple(profile[column] for column in columns),
                )
            connection.commit()

        counts = {
            "race_count": connection.execute("SELECT COUNT(*) FROM race_context").fetchone()[0],
            "race_result_context_count": connection.execute(
                "SELECT COUNT(*) FROM race_result_context"
            ).fetchone()[0],
            "runner_pre_count": connection.execute("SELECT COUNT(*) FROM runner_pre").fetchone()[0],
            "runner_result_count": connection.execute("SELECT COUNT(*) FROM runner_result").fetchone()[0],
            "workout_count": connection.execute("SELECT COUNT(*) FROM workout_main").fetchone()[0],
            "training_count": connection.execute("SELECT COUNT(*) FROM training_analysis").fetchone()[0],
            "profile_observation_count": connection.execute("SELECT COUNT(*) FROM horse_profile_observation").fetchone()[0],
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

        finished = dt.datetime.now().isoformat(timespec="seconds")
        connection.execute(
            """
            UPDATE meta_index_base_build
            SET finished_at=?,status='SUCCESS',source_manifest_json=?,
                race_count=?,race_result_context_count=?,runner_pre_count=?,runner_result_count=?,workout_count=?,
                training_count=?,profile_observation_count=?,anomaly_count=?
            WHERE build_id=?
            """,
            (
                finished,
                json.dumps(source_manifest, ensure_ascii=False),
                counts["race_count"],
                counts["race_result_context_count"],
                counts["runner_pre_count"],
                counts["runner_result_count"],
                counts["workout_count"],
                counts["training_count"],
                counts["profile_observation_count"],
                anomaly_count,
                build_id,
            ),
        )
        connection.commit()
        connection.execute("ANALYZE")
        connection.commit()
        return {
            **counts,
            "anomaly_count": anomaly_count,
            "integrity_check": integrity,
            "size_bytes": output.stat().st_size,
            "build_id": build_id,
        }
    except Exception as exc:
        connection.execute(
            """
            UPDATE meta_index_base_build
            SET finished_at=?,status='ERROR',message=?,anomaly_count=?
            WHERE build_id=?
            """,
            (
                dt.datetime.now().isoformat(timespec="seconds"),
                str(exc),
                anomaly_count,
                build_id,
            ),
        )
        connection.commit()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_index_base_schema_v0_1.sql",
    )
    parser.add_argument(
        "--no-archive-hash",
        action="store_true",
        help="Skip annual ZIP SHA-256 calculation for faster exploratory builds.",
    )
    args = parser.parse_args()

    result = build(
        raw_root=args.raw_root,
        years=args.years,
        output=args.db,
        schema_path=args.schema,
        hash_archives=not args.no_archive_hash,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
