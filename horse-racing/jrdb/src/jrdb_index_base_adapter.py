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
import json
import re
from typing import Any

from jrdb_raw import Parser

_COMMON = Parser()


def _record_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _semantic_hash(values: dict[str, Any]) -> str:
    payload = json.dumps(
        values, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _race_time_sec(value: str | None) -> float | None:
    if value is None or len(value) != 4 or not value.isdigit():
        return None
    return int(value[0]) * 60.0 + int(value[1:]) / 10.0


def _used_flag(value: Any) -> int | None:
    numeric = _int_value(value)
    return numeric if numeric in (0, 1) else None


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


def parse_sed(
    raw: bytes,
    member: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return the established index-base SED rows via Common Reader."""
    parsed = _COMMON.sed(raw)
    race_key_raw = str(parsed.get("race_key_raw") or "")
    race_date = _yyyymmdd(str(parsed.get("date_raw") or ""))
    metrics = parsed.get("metrics") or {}
    corners = parsed.get("corners") or []
    carried_weight_tenths = _float_value(parsed.get("carried_weight_tenths"))

    result = {
        "race_key": race_key_raw,
        "horse_no": _int_value(parsed.get("horse_no")),
        "result_key": parsed.get("result_key") or None,
        "horse_id": str(parsed.get("blood_registration_no") or ""),
        "horse_name": str(parsed.get("horse_name") or ""),
        "finish": _int_value(parsed.get("finish")),
        "abnormal_code": str(parsed.get("abnormal_code") or ""),
        "time_sec": _race_time_sec(str(parsed.get("time_raw") or "")),
        "carried_weight_kg": (
            carried_weight_tenths / 10.0
            if carried_weight_tenths is not None
            else None
        ),
        "jockey_name": str(parsed.get("jockey") or ""),
        "jockey_code": str(parsed.get("jockey_code") or ""),
        "trainer_name": str(parsed.get("trainer") or ""),
        "trainer_code": str(parsed.get("trainer_code") or ""),
        "final_win_odds": _float_value(parsed.get("final_win_odds")),
        "final_win_popularity": _int_value(parsed.get("final_popularity")),
        "final_place_odds_lower": _float_value(
            parsed.get("final_place_odds_lower")
        ),
        "idm": _int_value(parsed.get("idm")),
        "raw_score": _int_value(metrics.get("raw_score")),
        "jrdb_track_diff": _int_value(metrics.get("track_diff")),
        "jrdb_pace_score": _int_value(metrics.get("pace_score")),
        "jrdb_slow_start_score": _int_value(metrics.get("late_break_score")),
        "jrdb_position_score": _int_value(metrics.get("position_score")),
        "jrdb_trouble_score": _int_value(metrics.get("trouble_score")),
        "jrdb_early_trouble_score": _int_value(metrics.get("prev_trouble_score")),
        "jrdb_mid_trouble_score": _int_value(metrics.get("mid_trouble_score")),
        "jrdb_late_trouble_score": _int_value(metrics.get("late_trouble_score")),
        "jrdb_race_score": _int_value(metrics.get("race_score")),
        "course_lane_code": str(parsed.get("course_lane_code") or ""),
        "result_uptrend_code": str(parsed.get("result_uptrend_code") or ""),
        "result_class_code": str(parsed.get("result_class_code") or ""),
        "body_condition_code": str(parsed.get("body_condition_code") or ""),
        "mood_code": str(parsed.get("mood_code") or ""),
        "race_pace": str(parsed.get("race_pace_code") or ""),
        "horse_pace": str(parsed.get("horse_pace_code") or ""),
        "front_index": _float_value(metrics.get("front_index")),
        "last3f_index": _float_value(metrics.get("late_index")),
        "pace_index": _float_value(metrics.get("pace_index")),
        "race_pace_index": _float_value(metrics.get("race_pace_index")),
        "first_second_time_diff_sec": _float_value(
            parsed.get("first_second_time_diff_sec")
        ),
        "first3f_sec": _float_value(parsed.get("first3f_sec")),
        "last3f_sec": _float_value(parsed.get("last3f_sec")),
        "corner1": _int_value(corners[0]) if len(corners) > 0 else None,
        "corner2": _int_value(corners[1]) if len(corners) > 1 else None,
        "corner3": _int_value(corners[2]) if len(corners) > 2 else None,
        "corner4": _int_value(corners[3]) if len(corners) > 3 else None,
        "first3f_leader_diff_sec": _float_value(
            parsed.get("first3f_leader_diff_sec")
        ),
        "last3f_leader_diff_sec": _float_value(
            parsed.get("last3f_leader_diff_sec")
        ),
        "body_weight_kg": _int_value(parsed.get("body_weight_kg")),
        "body_weight_change_kg": _int_value(parsed.get("body_weight_change_kg")),
        "weather_code": str(parsed.get("weather_code") or ""),
        "course_code": str(parsed.get("course_code") or ""),
        "race_running_style_code": str(
            parsed.get("race_running_style_code") or ""
        ),
        "fourth_corner_lane_code": str(
            parsed.get("fourth_corner_lane_code") or ""
        ),
        "win_payout": _int_value(parsed.get("win_payout")),
        "place_payout": _int_value(parsed.get("place_payout")),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }

    context_semantics = {
        "race_key": race_key_raw,
        "track_condition_code": str(parsed.get("track_condition_code") or ""),
        "weather_code": str(parsed.get("weather_code") or ""),
    }
    result_context = {
        **context_semantics,
        "source_member": member,
        "semantic_hash": _semantic_hash(context_semantics),
    }

    fallback = {
        "race_key": race_key_raw,
        "race_date": race_date,
        "year": _year(race_date, race_key_raw),
        "venue_code": race_key_raw[:2],
        "race_no": _int_value(race_key_raw[6:8]),
        "start_time": _hhmm(str(parsed.get("start_time_raw") or "")),
        "distance_m": _int_value(parsed.get("distance_m")),
        "surface_code": str(parsed.get("surface_code") or ""),
        "turn_code": str(parsed.get("turn_code") or ""),
        "inner_outer_code": str(parsed.get("layout_code") or ""),
        "race_type_code": str(parsed.get("race_type_code") or ""),
        "race_condition_code": str(parsed.get("race_class_code") or ""),
        "race_symbol_code": str(parsed.get("race_symbol_code") or ""),
        "weight_condition_code": str(parsed.get("weight_condition_code") or ""),
        "grade_code": str(parsed.get("grade_code") or ""),
        "race_name": str(parsed.get("race_name") or ""),
        "declared_field_size": _int_value(parsed.get("field_size")),
        "course_code": str(parsed.get("course_code") or ""),
        "meeting_area_code": None,
        "availability_class": "CURRENT_RESULT_FALLBACK",
        "source_kind": "SED_FALLBACK",
        "source_member": member,
        "record_hash": _record_hash(raw),
    }
    return result, result_context, fallback


def parse_cha(raw: bytes, member: str) -> dict[str, Any]:
    """Return the established index-base CHA row via Common Reader."""
    parsed = _COMMON.cha(raw)
    key = str(parsed.get("race_horse_key") or "")
    clock = parsed.get("clock") or {}
    clock_index = parsed.get("clock_index") or {}
    pair = parsed.get("pair") or {}
    return {
        "race_key": key[:8],
        "horse_no": _int_value(key[8:10]),
        "training_date": _yyyymmdd(str(parsed.get("date_raw") or "")),
        "weekday": str(parsed.get("weekday") or ""),
        "workout_count": _int_value(parsed.get("workout_count")),
        "course_code": str(parsed.get("course_code") or ""),
        "effort_code": str(parsed.get("strength_code") or ""),
        "chase_state_code": str(parsed.get("state_code") or ""),
        "rider_type_code": str(parsed.get("rider_type_code") or ""),
        "furlong_count": _int_value(parsed.get("furlongs")),
        "first_segment_sec": _float_value(clock.get("front")),
        "middle_segment_sec": _float_value(clock.get("middle")),
        "final_segment_sec": _float_value(clock.get("last")),
        "jrdb_first_segment_index": _int_value(clock_index.get("front")),
        "jrdb_middle_segment_index": _int_value(clock_index.get("middle")),
        "jrdb_final_segment_index": _int_value(clock_index.get("last")),
        "jrdb_workout_index": _int_value(clock_index.get("total")),
        "pair_result_code": str(pair.get("result_code") or ""),
        "pair_effort_code": str(pair.get("strength_code") or ""),
        "pair_age": _int_value(pair.get("age")),
        "pair_class_code": str(pair.get("class_code") or ""),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }


def parse_cyb(raw: bytes, member: str) -> dict[str, Any]:
    """Return the established index-base CYB row via Common Reader."""
    parsed = _COMMON.cyb(raw)
    key = str(parsed.get("race_horse_key") or "")
    counts = parsed.get("course_counts") or {}
    return {
        "race_key": key[:8],
        "horse_no": _int_value(key[8:10]),
        "training_type_code": str(parsed.get("training_type_code") or ""),
        "training_course_type_code": str(
            parsed.get("training_course_type_code") or ""
        ),
        "used_slope": _used_flag(counts.get("slope")),
        "used_wood": _used_flag(counts.get("wood")),
        "used_dirt": _used_flag(counts.get("dirt")),
        "used_turf": _used_flag(counts.get("turf")),
        "used_pool": _used_flag(counts.get("pool")),
        "used_jump": _used_flag(counts.get("obstacle")),
        "used_polytrack": _used_flag(counts.get("polytrack")),
        "training_distance_code": str(parsed.get("distance_pattern_code") or ""),
        "training_focus_code": str(parsed.get("focus_code") or ""),
        "jrdb_workout_index": _int_value(parsed.get("training_index")),
        "finish_index": _int_value(parsed.get("condition_index")),
        "training_volume_code": str(parsed.get("volume_grade") or ""),
        "finish_change_code": str(parsed.get("condition_change_code") or ""),
        "training_evaluation_code": str(parsed.get("training_grade_code") or ""),
        "week_ago_workout_index": _int_value(parsed.get("one_week_ago_index")),
        "week_ago_course_code": str(parsed.get("one_week_ago_course") or ""),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }


def parse_ukc(raw: bytes, member: str) -> dict[str, Any]:
    """Return the established index-base UKC profile via Common Reader."""
    parsed = _COMMON.ukc(raw)
    data_date = _yyyymmdd(str(parsed.get("data_date") or ""))
    if data_date is None:
        match = re.search(r"(\d{6})\.txt$", member, re.IGNORECASE)
        if match is not None:
            data_date = _yyyymmdd(f"20{match.group(1)}")
    if data_date is None:
        raise ValueError(f"UKC profile observation has no usable date: {member}")

    birth_raw = str(parsed.get("birth_date") or "")
    return {
        "horse_id": str(parsed.get("horse_id") or ""),
        "data_date": data_date,
        "horse_name": str(parsed.get("horse_name") or ""),
        "sex_code": str(parsed.get("sex_code") or ""),
        "sire_name": str(parsed.get("sire_name") or ""),
        "dam_name": str(parsed.get("dam_name") or ""),
        "broodmare_sire_name": str(parsed.get("broodmare_sire_name") or ""),
        "birth_date": _yyyymmdd(birth_raw) or birth_raw,
        "sire_birth_year": _int_value(parsed.get("sire_birth_year")),
        "dam_birth_year": _int_value(parsed.get("dam_birth_year")),
        "broodmare_sire_birth_year": _int_value(parsed.get("broodmare_sire_birth_year")),
        "breeder_name": str(parsed.get("breeder_name") or ""),
        "breeding_place": str(parsed.get("breeding_place") or ""),
        "sire_line_code": str(parsed.get("sire_line_code") or ""),
        "broodmare_sire_line_code": str(parsed.get("broodmare_sire_line_code") or ""),
        "semantic_hash": str(parsed.get("semantic_hash") or ""),
        "source_member": member,
        "record_hash": _record_hash(raw),
    }
