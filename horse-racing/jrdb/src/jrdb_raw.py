#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Common JRDB fixed-width Raw/PACI reader.

This module owns byte-position parsing only. It intentionally does not convert
JRDB codes into consumer-facing labels; RaceNote, Eval, PWA and research tools
should apply their own presentation/feature policies above this layer.

Offsets are 1-based to match JRDB's published fixed-length specifications.
"""
from __future__ import annotations

import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

from jrdb_ukc import parse_ukc_record

VERSION = "0.1.0"

# Published record lengths include CR/LF. Annual Raw readers sometimes expose
# records after splitlines(), so BODY_LENGTHS are accepted as well.
RECORD_LENGTHS: dict[str, int] = {
    "BAC": 184,
    "KYI": 1024,
    "CHA": 64,
    "CYB": 96,
    "SED": 376,
    "SKB": 304,
    "ZED": 376,
    "ZKB": 304,
    "UKC": 292,
}
BODY_LENGTHS: dict[str, int] = {
    kind: length - 2 for kind, length in RECORD_LENGTHS.items()
}


class AuditLike(Protocol):
    """Minimal audit contract required by the common reader."""

    record_length_errors: Counter[str]


@dataclass
class ReaderAudit:
    """Standalone audit implementation for consumers without their own audit."""

    record_length_errors: Counter[str] = field(default_factory=Counter)


def text_field(record: bytes, start: int, length: int) -> str | None:
    """Decode one CP932 fixed-width text field using JRDB's 1-based offset."""
    raw = record[start - 1 : start - 1 + length]
    value = raw.decode("cp932", errors="replace").replace("\u3000", " ").strip()
    return value or None


def raw_field(record: bytes, start: int, length: int) -> str:
    """Decode one ASCII-ish JRDB field without semantic conversion."""
    return record[start - 1 : start - 1 + length].decode(
        "ascii", errors="replace"
    ).strip()


def number_field(record: bytes, start: int, length: int) -> int | float | None:
    """Parse a JRDB numeric field, preserving decimal values as float."""
    value = raw_field(record, start, length).replace(",", "")
    if not value:
        return None
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return None


def tenths(record: bytes, start: int, length: int) -> float | None:
    """Parse an integer field stored in tenths and convert to a float."""
    value = number_field(record, start, length)
    return None if value is None else float(value) / 10.0


def ymd(value: str | None) -> str | None:
    """Convert YYYYMMDD text to ISO date without guessing malformed values."""
    if not value or len(value) != 8 or not value.isdigit():
        return None
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def hhmm(value: str | None) -> str | None:
    """Convert HHMM text to HH:MM without range inference."""
    if not value or len(value) != 4 or not value.isdigit():
        return None
    return f"{value[:2]}:{value[2:]}"


def race_key(record: bytes) -> str:
    """Return the raw 8-byte race key as text."""
    return raw_field(record, 1, 8)


def race_horse_key(record: bytes) -> str:
    """Return race key + horse number for pre-race horse records."""
    return race_key(record) + raw_field(record, 9, 2)


def result_key(record: bytes) -> str:
    """Return JRDB result key (blood registration number + YYYYMMDD)."""
    return raw_field(record, 11, 8) + raw_field(record, 19, 8)


def race_key_parts(key: str) -> dict[str, Any]:
    """Split a race key while preserving the hexadecimal-capable day digit."""
    return {
        "venue_code": key[:2],
        "year_yy": key[2:4],
        "meeting": key[4:5],
        "day_raw": key[5:6],
        "race_no": int(key[6:8]) if key[6:8].isdigit() else None,
    }


def _kind(prefix: str) -> str:
    normalized = prefix.upper()
    if normalized not in RECORD_LENGTHS:
        raise KeyError(f"unsupported JRDB record kind: {prefix}")
    return normalized


def split_fixed_records(
    data: bytes,
    prefix: str,
    audit: AuditLike | None = None,
) -> list[bytes]:
    """Split either CRLF-inclusive fixed blocks or line-separated body records.

    PACI members are commonly read as fixed blocks whose published length includes
    CR/LF. Annual Raw processing often uses splitlines() first. Supporting both
    representations keeps storage choice out of consumer parsers.
    """
    kind = _kind(prefix)
    full_length = RECORD_LENGTHS[kind]
    body_length = BODY_LENGTHS[kind]

    if not data:
        return []

    if len(data) % full_length == 0:
        return [
            data[offset : offset + full_length]
            for offset in range(0, len(data), full_length)
        ]

    lines = data.splitlines()
    if lines and all(len(line) == body_length for line in lines):
        return lines

    if audit is not None:
        audit.record_length_errors[kind] += 1
    return []


def read_fixed_records(
    zf: zipfile.ZipFile,
    member: str,
    prefix: str,
    audit: AuditLike | None = None,
) -> list[bytes]:
    """Read and split one ZIP member into JRDB records."""
    return split_fixed_records(zf.read(member), prefix, audit)


def canonical_members(zf: zipfile.ZipFile, prefix: str) -> list[str]:
    """Return canonical KINDyymmdd.txt members in lexical order."""
    kind = _kind(prefix)
    pattern = re.compile(rf"^{kind}\d{{6}}\.txt$", re.IGNORECASE)
    return sorted(
        [name for name in zf.namelist() if pattern.fullmatch(Path(name).name)],
        key=lambda name: Path(name).name.upper(),
    )


def iter_archive_records(
    archive: Path,
    prefix: str,
    audit: AuditLike | None = None,
    reverse_members: bool = False,
) -> Iterable[tuple[str, bytes]]:
    """Yield (member, record) pairs from an annual or PACI ZIP."""
    with zipfile.ZipFile(archive) as zf:
        members = canonical_members(zf, prefix)
        if reverse_members:
            members.reverse()
        for member in members:
            for record in read_fixed_records(zf, member, prefix, audit):
                yield member, record


class Parser:
    """Parse JRDB fixed byte positions only; no code-to-label conversion occurs."""

    def __init__(self, audit: AuditLike | None = None) -> None:
        self.audit = audit

    def bac(self, record: bytes) -> dict[str, Any]:
        return {
            "race_key_raw": race_key(record),
            "date_raw": raw_field(record, 9, 8),
            "post_time_raw": raw_field(record, 17, 4),
            "distance_raw": raw_field(record, 21, 4),
            "surface_code": raw_field(record, 25, 1),
            "turn_code": raw_field(record, 26, 1),
            "layout_code": raw_field(record, 27, 1),
            "race_type_code": raw_field(record, 28, 2),
            "race_class_code": raw_field(record, 30, 2),
            "symbol_code": raw_field(record, 32, 3),
            "weight_rule_code": raw_field(record, 35, 1),
            "grade_code": raw_field(record, 36, 1),
            "race_name": text_field(record, 37, 50),
            "meeting": text_field(record, 87, 8),
            "field_size": number_field(record, 95, 2),
            "course_code": raw_field(record, 97, 1),
            "meeting_area_code": raw_field(record, 98, 1),
        }

    def kyi(self, record: bytes) -> dict[str, Any]:
        previous = [
            {
                "result_key": raw_field(record, 204 + index * 16, 16),
                "race_key_raw": raw_field(record, 284 + index * 8, 8),
            }
            for index in range(5)
        ]
        return {
            "race_key_raw": race_key(record),
            "race_horse_key": race_horse_key(record),
            "horse_no": number_field(record, 9, 2),
            "blood_registration_no": raw_field(record, 11, 8),
            "horse_name": text_field(record, 19, 36),
            "idm": number_field(record, 55, 5),
            "jockey_index": number_field(record, 60, 5),
            "info_index": number_field(record, 65, 5),
            "total_index": number_field(record, 85, 5),
            "running_style_code": raw_field(record, 90, 1),
            "distance_fit_code": raw_field(record, 91, 1),
            "improvement_code": raw_field(record, 92, 1),
            "rotation_interval": number_field(record, 93, 3),
            "base_win_odds": number_field(record, 96, 5),
            "base_win_rank": number_field(record, 101, 2),
            "base_place_odds": number_field(record, 103, 5),
            "base_place_rank": number_field(record, 108, 2),
            "training_index": number_field(record, 145, 5),
            "stable_index": number_field(record, 150, 5),
            "training_arrow_code": raw_field(record, 155, 1),
            "stable_evaluation_code": raw_field(record, 156, 1),
            "jockey_expected_top2_rate": number_field(record, 157, 4),
            "longshot_index": number_field(record, 161, 3),
            "hoof_code": raw_field(record, 164, 2),
            "heavy_track_fit_code": raw_field(record, 166, 1),
            "jrdb_class_code": raw_field(record, 167, 2),
            "blinker_code": raw_field(record, 171, 1),
            "jockey": text_field(record, 172, 12),
            "carried_weight_tenths": number_field(record, 184, 3),
            "apprentice_code": raw_field(record, 187, 1),
            "trainer": text_field(record, 188, 12),
            "trainer_base": text_field(record, 200, 4),
            "previous": previous,
            "frame_no": number_field(record, 324, 1),
            "condition_class_code": raw_field(record, 358, 1),
            "distance_fit2_code": raw_field(record, 396, 1),
            "body_weight_pre_kg": number_field(record, 397, 3),
            "body_weight_change_pre_kg": number_field(record, 400, 3),
            "cancel_flag": raw_field(record, 403, 1),
            "sex_code": raw_field(record, 404, 1),
            "marks": {
                "total": raw_field(record, 327, 1),
                "idm": raw_field(record, 328, 1),
                "info": raw_field(record, 329, 1),
                "jockey": raw_field(record, 330, 1),
                "stable": raw_field(record, 331, 1),
                "training": raw_field(record, 332, 1),
                "longshot": raw_field(record, 333, 1),
            },
            "turf_fit_code": raw_field(record, 334, 1),
            "dirt_fit_code": raw_field(record, 335, 1),
            "jockey_code": raw_field(record, 336, 5),
            "trainer_code": raw_field(record, 341, 5),
            "pace_indices": {
                "front": number_field(record, 359, 5),
                "pace": number_field(record, 364, 5),
                "late": number_field(record, 369, 5),
                "position": number_field(record, 374, 5),
            },
            "pace_ranks": {
                "front": number_field(record, 453, 2),
                "pace": number_field(record, 455, 2),
                "late": number_field(record, 457, 2),
                "position": number_field(record, 459, 2),
            },
            "forecast_pace_code": raw_field(record, 379, 1),
            "forecast_positions": {
                "mid": (
                    number_field(record, 380, 2),
                    number_field(record, 382, 2),
                    raw_field(record, 384, 1),
                ),
                "last3f": (
                    number_field(record, 385, 2),
                    number_field(record, 387, 2),
                    raw_field(record, 389, 1),
                ),
                "finish": (
                    number_field(record, 390, 2),
                    number_field(record, 392, 2),
                    raw_field(record, 394, 1),
                ),
            },
            "symbol_code": raw_field(record, 395, 1),
            "start_index": number_field(record, 520, 4),
            "late_break_rate": number_field(record, 524, 4),
            "stable_run_no": number_field(record, 560, 2),
            "stable_entry_date_raw": raw_field(record, 562, 8),
            "stable_days_before": number_field(record, 570, 3),
            "rest_reason_code": raw_field(record, 542, 2),
            "farm_name": text_field(record, 573, 50),
            "farm_rank": raw_field(record, 623, 1),
            "farm_index_rank": number_field(record, 624, 1),
            "trait_codes": [
                raw_field(record, pos, 3)
                for pos in (502, 505, 508, 511, 514, 517)
            ],
        }

    def cha(self, record: bytes) -> dict[str, Any]:
        return {
            "race_horse_key": race_horse_key(record),
            "weekday": text_field(record, 11, 2),
            "workout_count": number_field(record, 21, 1),
            "date_raw": raw_field(record, 13, 8),
            "course_code": raw_field(record, 22, 2),
            "strength_code": raw_field(record, 24, 1),
            "state_code": raw_field(record, 25, 2),
            "rider_type_code": raw_field(record, 27, 1),
            "furlongs": number_field(record, 28, 1),
            "clock": {
                "front": tenths(record, 29, 3),
                "middle": tenths(record, 32, 3),
                "last": tenths(record, 35, 3),
            },
            "clock_index": {
                "front": number_field(record, 38, 3),
                "middle": number_field(record, 41, 3),
                "last": number_field(record, 44, 3),
                "total": number_field(record, 47, 3),
            },
            "pair": {
                "result_code": raw_field(record, 50, 1),
                "strength_code": raw_field(record, 51, 1),
                "age": number_field(record, 52, 2),
                "class_code": raw_field(record, 54, 2),
            },
        }

    def cyb(self, record: bytes) -> dict[str, Any]:
        return {
            "race_horse_key": race_horse_key(record),
            "training_type_code": raw_field(record, 11, 2),
            "training_course_type_code": raw_field(record, 13, 1),
            "course_counts": {
                "slope": number_field(record, 14, 2),
                "wood": number_field(record, 16, 2),
                "dirt": number_field(record, 18, 2),
                "turf": number_field(record, 20, 2),
                "pool": number_field(record, 22, 2),
                "obstacle": number_field(record, 24, 2),
                "polytrack": number_field(record, 26, 2),
            },
            "distance_pattern_code": raw_field(record, 28, 1),
            "focus_code": raw_field(record, 29, 1),
            "training_index": number_field(record, 30, 3),
            "condition_index": number_field(record, 33, 3),
            "volume_grade": raw_field(record, 36, 1),
            "condition_change_code": raw_field(record, 37, 1),
            "comment": text_field(record, 38, 40),
            "comment_date_raw": raw_field(record, 78, 8),
            "training_grade_code": raw_field(record, 86, 1),
            "one_week_ago_index": number_field(record, 87, 3),
            "one_week_ago_course": raw_field(record, 90, 2),
        }

    def sed(self, record: bytes) -> dict[str, Any]:
        """Parse SED current-result data; ZED is byte-compatible."""
        return {
            "race_key_raw": race_key(record),
            "horse_no": number_field(record, 9, 2),
            "result_key": result_key(record),
            "blood_registration_no": raw_field(record, 11, 8),
            "date_raw": raw_field(record, 19, 8),
            "horse_name": text_field(record, 27, 36),
            "race_name": text_field(record, 81, 50),
            "distance_m": number_field(record, 63, 4),
            "surface_code": raw_field(record, 67, 1),
            "turn_code": raw_field(record, 68, 1),
            "layout_code": raw_field(record, 69, 1),
            "track_condition_code": raw_field(record, 70, 2),
            "race_type_code": raw_field(record, 72, 2),
            "race_class_code": raw_field(record, 74, 2),
            "race_symbol_code": raw_field(record, 76, 3),
            "weight_condition_code": raw_field(record, 79, 1),
            "grade_code": raw_field(record, 80, 1),
            "field_size": number_field(record, 131, 2),
            "finish": number_field(record, 141, 2),
            "abnormal_code": raw_field(record, 143, 1),
            "time_raw": raw_field(record, 144, 4),
            "carried_weight_tenths": number_field(record, 148, 3),
            "jockey": text_field(record, 151, 12),
            "trainer": text_field(record, 163, 12),
            "final_win_odds": number_field(record, 175, 6),
            "final_popularity_raw": raw_field(record, 181, 2),
            "final_popularity": number_field(record, 181, 2),
            "idm": number_field(record, 183, 3),
            "metrics": {
                "raw_score": number_field(record, 186, 3),
                "track_diff": number_field(record, 189, 3),
                "pace_score": number_field(record, 192, 3),
                "late_break_score": number_field(record, 195, 3),
                "position_score": number_field(record, 198, 3),
                "trouble_score": number_field(record, 201, 3),
                "prev_trouble_score": number_field(record, 204, 3),
                "mid_trouble_score": number_field(record, 207, 3),
                "late_trouble_score": number_field(record, 210, 3),
                "race_score": number_field(record, 213, 3),
                "front_index": number_field(record, 224, 5),
                "late_index": number_field(record, 229, 5),
                "pace_index": number_field(record, 234, 5),
                "race_pace_index": number_field(record, 239, 5),
            },
            "course_lane_code": raw_field(record, 216, 1),
            "result_uptrend_code": raw_field(record, 217, 1),
            "result_class_code": raw_field(record, 218, 2),
            "mood_code": raw_field(record, 221, 1),
            "corners": [
                number_field(record, pos, 2)
                for pos in (309, 311, 313, 315)
            ],
            "first_second_time_diff_sec": tenths(record, 256, 3),
            "first3f_sec": tenths(record, 259, 3),
            "last3f_sec": tenths(record, 262, 3),
            "first3f_leader_diff_sec": tenths(record, 317, 3),
            "last3f_leader_diff_sec": tenths(record, 320, 3),
            "race_pace_code": raw_field(record, 222, 1),
            "horse_pace_code": raw_field(record, 223, 1),
            "final_place_odds_lower": number_field(record, 291, 6),
            "jockey_code": raw_field(record, 323, 5),
            "trainer_code": raw_field(record, 328, 5),
            "body_weight_kg": number_field(record, 333, 3),
            "body_weight_change_kg": number_field(record, 336, 3),
            "weather_code": raw_field(record, 339, 1),
            "body_condition_code": raw_field(record, 220, 1),
            "course_code": raw_field(record, 340, 1),
            "race_running_style_code": raw_field(record, 341, 1),
            "win_payout": number_field(record, 342, 7),
            "place_payout": number_field(record, 349, 7),
            "fourth_corner_lane_code": raw_field(record, 370, 1),
            "start_time_raw": raw_field(record, 371, 4),
        }

    def zed(self, record: bytes) -> dict[str, Any]:
        """Parse ZED using the SED-compatible layout."""
        return self.sed(record)

    def skb(self, record: bytes) -> dict[str, Any]:
        """Parse SKB current-result extension; ZKB is byte-compatible."""
        return {
            "result_key": result_key(record),
            "tokki_codes": [
                raw_field(record, 27 + index * 3, 3)
                for index in range(6)
            ],
            "equipment_codes": [
                raw_field(record, 45 + index * 3, 3)
                for index in range(8)
            ],
            "leg_codes": {
                "overall": raw_field(record, 69, 3),
                "left_front": raw_field(record, 78, 3),
                "right_front": raw_field(record, 87, 3),
                "left_hind": raw_field(record, 96, 3),
                "right_hind": raw_field(record, 105, 3),
            },
            "paddock_comment": text_field(record, 114, 40),
            "leg_comment": text_field(record, 154, 40),
            "equipment_comment": text_field(record, 194, 40),
            "race_comment": text_field(record, 234, 40),
        }

    def zkb(self, record: bytes) -> dict[str, Any]:
        """Parse ZKB using the SKB-compatible layout."""
        return self.skb(record)

    def ukc(self, record: bytes) -> dict[str, Any]:
        """Parse UKC horse profile data using the validated common UKC parser."""
        body = record[:-2] if len(record) == RECORD_LENGTHS["UKC"] else record
        parsed = parse_ukc_record(body)
        return {
            "horse_id": parsed.horse_id,
            "horse_name": parsed.horse_name,
            "sex_code": parsed.sex_code,
            "coat_color_code": parsed.coat_color_code,
            "horse_symbol_code": parsed.horse_symbol_code,
            "sire_name": parsed.sire_name,
            "dam_name": parsed.dam_name,
            "broodmare_sire_name": parsed.broodmare_sire_name,
            "birth_date": parsed.birth_date,
            "sire_birth_year": parsed.sire_birth_year,
            "dam_birth_year": parsed.dam_birth_year,
            "broodmare_sire_birth_year": parsed.broodmare_sire_birth_year,
            "owner_name": parsed.owner_name,
            "owner_group_code": parsed.owner_group_code,
            "breeder_name": parsed.breeder_name,
            "breeding_place": parsed.breeding_place,
            "deregistered_flag": parsed.deregistered_flag,
            "data_date": parsed.data_date,
            "sire_line_code": parsed.sire_line_code,
            "broodmare_sire_line_code": parsed.broodmare_sire_line_code,
            "semantic_hash": parsed.semantic_hash(),
        }
