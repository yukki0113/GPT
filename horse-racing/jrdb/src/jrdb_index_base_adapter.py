#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapt Common JRDB Raw Reader rows to the existing index-base schema.

This module contains no fixed-width offsets. Byte-position ownership stays in
`jrdb_raw.Parser`; this layer only preserves the established PWA/index-base
field names, types, provenance and availability semantics.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any

from jrdb_raw import Parser

_COMMON = Parser()


def _record_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _yyyymmdd(value: str | None) -> str | None:
    if not value or not re.fullmatch(r"\d{8}", value):
        return None
    try:
        return dt.datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _hhmm(value: str | None) -> str | None:
    if not value or not re.fullmatch(r"\d{4}", value):
        return None
    hour = int(value[:2])
    minute = int(value[2:])
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _int_value(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _year(race_date: str | None, race_key_raw: str) -> int:
    if race_date is not None:
        return int(race_date[:4])
    year_yy = race_key_raw[2:4]
    if not year_yy.isdigit():
        raise ValueError("race year is missing")
    return 2000 + int(year_yy)


def parse_bac(raw: bytes, member: str) -> dict[str, Any]:
    """Return the established index-base BAC row via Common Reader."""
    parsed = _COMMON.bac(raw)
    race_key_raw = str(parsed["race_key_raw"])
    race_date = _yyyymmdd(str(parsed.get("date_raw") or ""))
    return {
        "race_key": race_key_raw,
        "race_date": race_date,
        "year": _year(race_date, race_key_raw),
        "venue_code": race_key_raw[:2],
        "race_no": _int_value(race_key_raw[6:8]),
        "start_time": _hhmm(str(parsed.get("post_time_raw") or "")),
        "distance_m": _int_value(parsed.get("distance_raw")),
        "surface_code": str(parsed.get("surface_code") or ""),
        "turn_code": str(parsed.get("turn_code") or ""),
        "inner_outer_code": str(parsed.get("layout_code") or ""),
        "race_type_code": str(parsed.get("race_type_code") or ""),
        "race_condition_code": str(parsed.get("race_class_code") or ""),
        "race_symbol_code": str(parsed.get("symbol_code") or ""),
        "weight_condition_code": str(parsed.get("weight_rule_code") or ""),
        "grade_code": str(parsed.get("grade_code") or ""),
        "race_name": str(parsed.get("race_name") or ""),
        "declared_field_size": _int_value(parsed.get("field_size")),
        "course_code": str(parsed.get("course_code") or ""),
        "meeting_area_code": str(parsed.get("meeting_area_code") or ""),
        "availability_class": "PRE_RACE",
        "source_kind": "BAC",
        "source_member": member,
        "record_hash": _record_hash(raw),
    }


def parse_kyi(raw: bytes, member: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the established index-base KYI runner/link rows via Common Reader."""
    parsed = _COMMON.kyi(raw)
    race_key_raw = str(parsed["race_key_raw"])
    horse_no = _int_value(parsed.get("horse_no"))
    carried_weight_tenths = _float_value(parsed.get("carried_weight_tenths"))
    pace = parsed.get("pace_indices") or {}

    runner = {
        "race_key": race_key_raw,
        "horse_no": horse_no,
        "horse_id": str(parsed.get("blood_registration_no") or ""),
        "horse_name": str(parsed.get("horse_name") or ""),
        "frame_no": _int_value(parsed.get("frame_no")),
        "sex_code": str(parsed.get("sex_code") or ""),
        "jockey_name": str(parsed.get("jockey") or ""),
        "jockey_code": str(parsed.get("jockey_code") or ""),
        "trainer_name": str(parsed.get("trainer") or ""),
        "trainer_code": str(parsed.get("trainer_code") or ""),
        "carried_weight_kg": (
            carried_weight_tenths / 10.0
            if carried_weight_tenths is not None
            else None
        ),
        "running_style_code": str(parsed.get("running_style_code") or ""),
        "distance_aptitude_code": str(parsed.get("distance_fit_code") or ""),
        "uptrend_code": str(parsed.get("improvement_code") or ""),
        "rotation_interval": _int_value(parsed.get("rotation_interval")),
        "pre_idm": _float_value(parsed.get("idm")),
        "training_score": _float_value(parsed.get("training_index")),
        "stable_score": _float_value(parsed.get("stable_index")),
        "training_arrow_code": str(parsed.get("training_arrow_code") or ""),
        "stable_evaluation_code": str(parsed.get("stable_evaluation_code") or ""),
        "blinker_code": str(parsed.get("blinker_code") or ""),
        "condition_class_code": str(parsed.get("condition_class_code") or ""),
        "body_weight_pre_kg": _int_value(parsed.get("body_weight_pre_kg")),
        "body_weight_change_pre_kg": _int_value(
            parsed.get("body_weight_change_pre_kg")
        ),
        "start_index": _float_value(parsed.get("start_index")),
        "slow_start_rate": _float_value(parsed.get("late_break_rate")),
        "stable_run_no": _int_value(parsed.get("stable_run_no")),
        "stable_entry_date": _yyyymmdd(
            str(parsed.get("stable_entry_date_raw") or "")
        ),
        "stable_days_before": _int_value(parsed.get("stable_days_before")),
        "expected_ten_index": _float_value(pace.get("front")),
        "expected_pace_index": _float_value(pace.get("pace")),
        "expected_last3f_index": _float_value(pace.get("late")),
        "expected_position_index": _float_value(pace.get("position")),
        "expected_race_pace": str(parsed.get("forecast_pace_code") or ""),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }

    links: list[dict[str, Any]] = []
    previous = parsed.get("previous") or []
    for sequence, item in enumerate(previous, start=1):
        if not isinstance(item, dict):
            continue
        links.append(
            {
                "race_key": race_key_raw,
                "horse_no": horse_no,
                "sequence": sequence,
                "prev_result_key": item.get("result_key") or None,
                "prev_race_key": item.get("race_key_raw") or None,
            }
        )
    return runner, links
