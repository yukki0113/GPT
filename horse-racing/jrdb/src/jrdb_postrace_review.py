#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure deterministic primitives for JRDB Post-Race Review v0.1.

This module intentionally owns no fixed-width byte offsets and performs no I/O.
JRDB byte interpretation remains in jrdb_raw.py. The functions here accept
already parsed logical values and provide stable, testable Review derivations.
"""
from __future__ import annotations

import math
from typing import Sequence

REVIEW_SCHEMA_VERSION = "v0.1"
REVIEW_LOGIC_VERSION = "v0.1.0"

CLASS_NEWCOMER = "NEWCOMER"
CLASS_MAIDEN = "MAIDEN"
CLASS_1 = "CLASS_1"
CLASS_2 = "CLASS_2"
CLASS_3 = "CLASS_3"
CLASS_OPEN = "OPEN"
CLASS_G3 = "G3"
CLASS_G2 = "G2"
CLASS_G1 = "G1"
CLASS_OTHER = "OTHER"

PACE_VERY_BACK_LOADED = "VERY_BACK_LOADED"
PACE_BACK_LOADED = "BACK_LOADED"
PACE_BALANCED = "BALANCED"
PACE_FRONT_LOADED = "FRONT_LOADED"
PACE_VERY_FRONT_LOADED = "VERY_FRONT_LOADED"

LANE_INNER = "INNER"
LANE_MIDDLE = "MIDDLE"
LANE_OUTER = "OUTER"


def _finite_float(value: object) -> float | None:
    """Return one finite float without inventing a value for blanks/invalids."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _integer(value: object) -> int | None:
    """Return an exact integer value; reject non-integral numerics."""
    number = _finite_float(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def parse_sed_time_seconds(value: object) -> float | None:
    """Convert the SED 4-byte result time into seconds.

    JRDB defines one minute digit followed by three digits representing seconds
    in tenths. Example: 1123 means 1:12.3 = 72.3 seconds.
    """
    if value is None:
        return None
    text = str(value).strip()
    if len(text) != 4 or not text.isdigit():
        return None

    minutes = int(text[0])
    seconds_tenths = int(text[1:])
    if seconds_tenths >= 600:
        return None

    return float(minutes * 60) + float(seconds_tenths) / 10.0


def normalize_class_group(
    race_class_code: object,
    grade_code: object = None,
) -> str:
    """Map JRDB race/grade codes into the Review-owned broad class taxonomy."""
    grade = ""
    if grade_code is not None:
        grade = str(grade_code).strip().upper()

    if grade == "1":
        return CLASS_G1
    if grade == "2":
        return CLASS_G2
    if grade == "3":
        return CLASS_G3

    race_class = ""
    if race_class_code is not None:
        if isinstance(race_class_code, int):
            race_class = f"{race_class_code:02d}"
        else:
            race_class = str(race_class_code).strip().upper()

    if race_class in {"A1", "A2"}:
        return CLASS_NEWCOMER
    if race_class == "A3":
        return CLASS_MAIDEN
    if race_class in {"04", "05"}:
        return CLASS_1
    if race_class in {"08", "09", "10"}:
        return CLASS_2
    if race_class in {"15", "16"}:
        return CLASS_3
    if race_class == "OP":
        return CLASS_OPEN
    return CLASS_OTHER


def frontness(position: object, field_size: object) -> float | None:
    """Normalize a rank into [0, 1], where 1 is front and 0 is last."""
    parsed_position = _integer(position)
    parsed_field_size = _integer(field_size)
    if parsed_position is None or parsed_field_size is None:
        return None
    if parsed_field_size <= 1:
        return None
    if parsed_position < 1 or parsed_position > parsed_field_size:
        return None

    return 1.0 - (
        float(parsed_position - 1) / float(parsed_field_size - 1)
    )


def position_gain(
    from_position: object,
    to_position: object,
    field_size: object,
) -> float | None:
    """Return normalized forward movement; positive means moving toward front."""
    start = frontness(from_position, field_size)
    end = frontness(to_position, field_size)
    if start is None or end is None:
        return None
    return end - start


def pace_balance_seconds(
    first3f_sec: object,
    last3f_sec: object,
) -> float | None:
    """Return signed pace balance; positive means more front-loaded.

    The normative sign is last3f - first3f. A faster opening 3F therefore
    produces a positive value.
    """
    first = _finite_float(first3f_sec)
    last = _finite_float(last3f_sec)
    if first is None or last is None:
        return None
    if first <= 0.0 or last <= 0.0:
        return None
    return last - first


def classify_pace_percentile(percentile: object) -> str | None:
    """Classify a 0-100 historical pace-balance percentile."""
    value = _finite_float(percentile)
    if value is None or value < 0.0 or value > 100.0:
        return None

    if value <= 10.0:
        return PACE_VERY_BACK_LOADED
    if value <= 30.0:
        return PACE_BACK_LOADED
    if value < 70.0:
        return PACE_BALANCED
    if value < 90.0:
        return PACE_FRONT_LOADED
    return PACE_VERY_FRONT_LOADED


def lane_bucket(course_lane_code: object) -> str | None:
    """Map JRDB result course-lane code into Review's three broad buckets."""
    code = _integer(course_lane_code)
    if code in {1, 2}:
        return LANE_INNER
    if code == 3:
        return LANE_MIDDLE
    if code in {4, 5}:
        return LANE_OUTER
    return None


def finish_gap_seconds(
    horse_time_sec: object,
    winner_time_sec: object,
) -> float | None:
    """Return the horse's time deficit to the winner for valid ordered times."""
    horse_time = _finite_float(horse_time_sec)
    winner_time = _finite_float(winner_time_sec)
    if horse_time is None or winner_time is None:
        return None
    if horse_time <= 0.0 or winner_time <= 0.0:
        return None

    gap = horse_time - winner_time
    if gap < 0.0:
        return None
    return gap


def closing_gain_seconds(
    last3f_leader_diff_sec: object,
    finish_gap_sec: object,
) -> float | None:
    """Return leader deficit recovered from last-3F reference to the finish."""
    last3f_gap = _finite_float(last3f_leader_diff_sec)
    finish_gap = _finite_float(finish_gap_sec)
    if last3f_gap is None or finish_gap is None:
        return None
    if last3f_gap < 0.0 or finish_gap < 0.0:
        return None
    return last3f_gap - finish_gap


def corner_frontness(
    corners: Sequence[object] | None,
    field_size: object,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Normalize four SED corner ranks while preserving missing observations."""
    values: list[object] = []
    if corners is not None:
        values = list(corners[:4])
    while len(values) < 4:
        values.append(None)

    return (
        frontness(values[0], field_size),
        frontness(values[1], field_size),
        frontness(values[2], field_size),
        frontness(values[3], field_size),
    )


def position_dynamics(
    corners: Sequence[object] | None,
    finish: object,
    field_size: object,
) -> dict[str, float | None]:
    """Return threshold-free position movement primitives.

    Phase definitions:
    - early: corner 1 -> corner 2
    - middle: corner 2 -> corner 4, falling back to corner 3
    - late: corner 4 -> finish
    """
    values: list[object] = []
    if corners is not None:
        values = list(corners[:4])
    while len(values) < 4:
        values.append(None)

    early = position_gain(values[0], values[1], field_size)

    middle_target = values[3]
    if _integer(middle_target) is None:
        middle_target = values[2]
    middle = position_gain(values[1], middle_target, field_size)

    late = position_gain(values[3], finish, field_size)
    overall = position_gain(values[0], finish, field_size)

    return {
        "early_position_gain": early,
        "middle_position_gain": middle,
        "late_position_gain": late,
        "overall_position_gain": overall,
    }
