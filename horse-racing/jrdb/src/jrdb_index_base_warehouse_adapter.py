#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JRDB Warehouse -> existing Index Base compatibility adapter.

This module deliberately owns no fixed-width offsets. It projects the accepted
2010-2025 normalized Warehouse rows into the unchanged Index Base v0.1 logical
schema and reproduces the Raw builder's revision/as-of selection rules.

2026 PACI/Raw is intentionally out of scope.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "0.1.0"
MIN_YEAR = 2010
MAX_YEAR = 2025
REQUIRED_FAMILIES = ("BAC", "KYI", "SED", "UKC")
OPTIONAL_FAMILIES = ("CHA", "CYB")
ALL_FAMILIES = REQUIRED_FAMILIES + OPTIONAL_FAMILIES


class WarehouseIndexBaseError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _yyyymmdd(value: Any) -> str | None:
    text = _text(value)
    if re.fullmatch(r"\d{8}", text):
        try:
            return dt.datetime.strptime(text, "%Y%m%d").date().isoformat()
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None


def _hhmm(value: Any) -> str | None:
    text = _text(value).replace(":", "")
    if not re.fullmatch(r"\d{4}", text):
        return None
    hour, minute = int(text[:2]), int(text[2:])
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _race_time_sec(value: Any) -> float | None:
    text = _text(value)
    if len(text) != 4 or not text.isdigit():
        return None
    return int(text[0]) * 60.0 + int(text[1:]) / 10.0


def _record_hash(row: Mapping[str, Any]) -> str:
    value = _text(row.get("source_record_sha256"))
    if len(value) != 64:
        raise WarehouseIndexBaseError("Warehouse source_record_sha256 is missing")
    return value


def _source_member(row: Mapping[str, Any]) -> str:
    value = _text(row.get("source_member"))
    if not value:
        raise WarehouseIndexBaseError("Warehouse source_member is missing")
    return value


def _member_date_from_row(row: Mapping[str, Any]) -> str | None:
    value = _yyyymmdd(row.get("source_member_date"))
    if value:
        return value
    member = _source_member(row)
    match = re.search(r"(\d{6})\.txt$", Path(member).name, re.IGNORECASE)
    return _yyyymmdd("20" + match.group(1)) if match else None


def _semantic_hash(values: Mapping[str, Any]) -> str:
    import hashlib
    payload = json.dumps(dict(values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def project_bac(row: Mapping[str, Any]) -> dict[str, Any]:
    key = _text(row.get("race_key_raw"))
    race_date = _yyyymmdd(row.get("race_date")) or _yyyymmdd(row.get("date_raw"))
    if len(key) != 8:
        raise WarehouseIndexBaseError("BAC race_key_raw must be 8 chars")
    year = int(race_date[:4]) if race_date else 2000 + int(key[2:4])
    return {
        "race_key": key,
        "race_date": race_date,
        "year": year,
        "venue_code": key[:2],
        "race_no": _int(key[6:8]),
        "start_time": _hhmm(row.get("post_time") or row.get("post_time_raw")),
        "distance_m": _int(row.get("distance_raw")),
        "surface_code": _text(row.get("surface_code")),
        "turn_code": _text(row.get("turn_code")),
        "inner_outer_code": _text(row.get("layout_code")),
        "race_type_code": _text(row.get("race_type_code")),
        "race_condition_code": _text(row.get("race_class_code")),
        "race_symbol_code": _text(row.get("symbol_code")),
        "weight_condition_code": _text(row.get("weight_rule_code")),
        "grade_code": _text(row.get("grade_code")),
        "race_name": _text(row.get("race_name")),
        "declared_field_size": _int(row.get("field_size")),
        "course_code": _text(row.get("course_code")),
        "meeting_area_code": _text(row.get("meeting_area_code")),
        "availability_class": "PRE_RACE",
        "source_kind": "BAC",
        "source_member": _source_member(row),
        "record_hash": _record_hash(row),
    }


def project_kyi(row: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    key = _text(row.get("race_key_raw"))
    horse_no = _int(row.get("horse_no"))
    weight = _float(row.get("carried_weight_tenths"))
    runner = {
        "race_key": key,
        "horse_no": horse_no,
        "horse_id": _text(row.get("blood_registration_no")),
        "horse_name": _text(row.get("horse_name")),
        "frame_no": _int(row.get("frame_no")),
        "sex_code": _text(row.get("sex_code")),
        "jockey_name": _text(row.get("jockey")),
        "jockey_code": _text(row.get("jockey_code")),
        "trainer_name": _text(row.get("trainer")),
        "trainer_code": _text(row.get("trainer_code")),
        "carried_weight_kg": None if weight is None else weight / 10.0,
        "running_style_code": _text(row.get("running_style_code")),
        "distance_aptitude_code": _text(row.get("distance_fit_code")),
        "uptrend_code": _text(row.get("improvement_code")),
        "rotation_interval": _int(row.get("rotation_interval")),
        "pre_idm": _float(row.get("idm")),
        "training_score": _float(row.get("training_index")),
        "stable_score": _float(row.get("stable_index")),
        "training_arrow_code": _text(row.get("training_arrow_code")),
        "stable_evaluation_code": _text(row.get("stable_evaluation_code")),
        "blinker_code": _text(row.get("blinker_code")),
        "condition_class_code": _text(row.get("condition_class_code")),
        "body_weight_pre_kg": _int(row.get("body_weight_pre_kg")),
        "body_weight_change_pre_kg": _int(row.get("body_weight_change_pre_kg")),
        "start_index": _float(row.get("start_index")),
        "slow_start_rate": _float(row.get("late_break_rate")),
        "stable_run_no": _int(row.get("stable_run_no")),
        "stable_entry_date": _yyyymmdd(row.get("stable_entry_date") or row.get("stable_entry_date_raw")),
        "stable_days_before": _int(row.get("stable_days_before")),
        "expected_ten_index": _float(row.get("pace_index_front")),
        "expected_pace_index": _float(row.get("pace_index_pace")),
        "expected_last3f_index": _float(row.get("pace_index_late")),
        "expected_position_index": _float(row.get("pace_index_position")),
        "expected_race_pace": _text(row.get("forecast_pace_code")),
        "source_member": _source_member(row),
        "record_hash": _record_hash(row),
    }
    links = [
        {
            "race_key": key,
            "horse_no": horse_no,
            "sequence": sequence,
            "prev_result_key": _text(row.get(f"prev_result_key_{sequence}")) or None,
            "prev_race_key": _text(row.get(f"prev_race_key_{sequence}")) or None,
        }
        for sequence in range(1, 6)
    ]
    return runner, links


def project_sed(row: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    key = _text(row.get("race_key_raw"))
    horse_no = _int(row.get("horse_no"))
    race_date = _yyyymmdd(row.get("race_date")) or _yyyymmdd(row.get("date_raw"))
    weight = _float(row.get("carried_weight_tenths"))
    result = {
        "race_key": key,
        "horse_no": horse_no,
        "result_key": _text(row.get("result_key")) or None,
        "horse_id": _text(row.get("blood_registration_no")),
        "horse_name": _text(row.get("horse_name")),
        "finish": _int(row.get("finish")),
        "abnormal_code": _text(row.get("abnormal_code")),
        "time_sec": _race_time_sec(row.get("time_raw")),
        "carried_weight_kg": None if weight is None else weight / 10.0,
        "jockey_name": _text(row.get("jockey")),
        "jockey_code": _text(row.get("jockey_code")),
        "trainer_name": _text(row.get("trainer")),
        "trainer_code": _text(row.get("trainer_code")),
        "final_win_odds": _float(row.get("final_win_odds")),
        "final_win_popularity": _int(row.get("final_popularity")),
        "final_place_odds_lower": _float(row.get("final_place_odds_lower")),
        "idm": _int(row.get("idm")),
        "raw_score": _int(row.get("metric_raw_score")),
        "jrdb_track_diff": _int(row.get("metric_track_diff")),
        "jrdb_pace_score": _int(row.get("metric_pace_score")),
        "jrdb_slow_start_score": _int(row.get("metric_late_break_score")),
        "jrdb_position_score": _int(row.get("metric_position_score")),
        "jrdb_trouble_score": _int(row.get("metric_trouble_score")),
        "jrdb_early_trouble_score": _int(row.get("metric_prev_trouble_score")),
        "jrdb_mid_trouble_score": _int(row.get("metric_mid_trouble_score")),
        "jrdb_late_trouble_score": _int(row.get("metric_late_trouble_score")),
        "jrdb_race_score": _int(row.get("metric_race_score")),
        "course_lane_code": _text(row.get("course_lane_code")),
        "result_uptrend_code": _text(row.get("result_uptrend_code")),
        "result_class_code": _text(row.get("result_class_code")),
        "body_condition_code": _text(row.get("body_condition_code")),
        "mood_code": _text(row.get("mood_code")),
        "race_pace": _text(row.get("race_pace_code")),
        "horse_pace": _text(row.get("horse_pace_code")),
        "front_index": _float(row.get("metric_front_index")),
        "last3f_index": _float(row.get("metric_late_index")),
        "pace_index": _float(row.get("metric_pace_index")),
        "race_pace_index": _float(row.get("metric_race_pace_index")),
        "first_second_time_diff_sec": _float(row.get("first_second_time_diff_sec")),
        "first3f_sec": _float(row.get("first3f_sec")),
        "last3f_sec": _float(row.get("last3f_sec")),
        "corner1": _int(row.get("corner_1")),
        "corner2": _int(row.get("corner_2")),
        "corner3": _int(row.get("corner_3")),
        "corner4": _int(row.get("corner_4")),
        "first3f_leader_diff_sec": _float(row.get("first3f_leader_diff_sec")),
        "last3f_leader_diff_sec": _float(row.get("last3f_leader_diff_sec")),
        "body_weight_kg": _int(row.get("body_weight_kg")),
        "body_weight_change_kg": _int(row.get("body_weight_change_kg")),
        "weather_code": _text(row.get("weather_code")),
        "course_code": _text(row.get("course_code")),
        "race_running_style_code": _text(row.get("race_running_style_code")),
        "fourth_corner_lane_code": _text(row.get("fourth_corner_lane_code")),
        "win_payout": _int(row.get("win_payout")),
        "place_payout": _int(row.get("place_payout")),
        "source_member": _source_member(row),
        "record_hash": _record_hash(row),
    }
    context_semantics = {
        "race_key": key,
        "track_condition_code": _text(row.get("track_condition_code")),
        "weather_code": _text(row.get("weather_code")),
    }
    context = {
        **context_semantics,
        "source_member": _source_member(row),
        "semantic_hash": _semantic_hash(context_semantics),
    }
    year = int(race_date[:4]) if race_date else 2000 + int(key[2:4])
    fallback = {
        "race_key": key,
        "race_date": race_date,
        "year": year,
        "venue_code": key[:2],
        "race_no": _int(key[6:8]),
        "start_time": _hhmm(row.get("start_time") or row.get("start_time_raw")),
        "distance_m": _int(row.get("distance_m")),
        "surface_code": _text(row.get("surface_code")),
        "turn_code": _text(row.get("turn_code")),
        "inner_outer_code": _text(row.get("layout_code")),
        "race_type_code": _text(row.get("race_type_code")),
        "race_condition_code": _text(row.get("race_class_code")),
        "race_symbol_code": _text(row.get("race_symbol_code")),
        "weight_condition_code": _text(row.get("weight_condition_code")),
        "grade_code": _text(row.get("grade_code")),
        "race_name": _text(row.get("race_name")),
        "declared_field_size": _int(row.get("field_size")),
        "course_code": _text(row.get("course_code")),
        "meeting_area_code": None,
        "availability_class": "CURRENT_RESULT_FALLBACK",
        "source_kind": "SED_FALLBACK",
        "source_member": _source_member(row),
        "record_hash": _record_hash(row),
    }
    return result, context, fallback


def project_cha(row: Mapping[str, Any]) -> dict[str, Any]:
    key = _text(row.get("race_horse_key"))
    return {
        "race_key": _text(row.get("race_key_raw")) or key[:8],
        "horse_no": _int(key[8:10]),
        "training_date": _yyyymmdd(row.get("workout_date") or row.get("date_raw")),
        "weekday": _text(row.get("weekday")),
        "workout_count": _int(row.get("workout_count")),
        "course_code": _text(row.get("course_code")),
        "effort_code": _text(row.get("strength_code")),
        "chase_state_code": _text(row.get("state_code")),
        "rider_type_code": _text(row.get("rider_type_code")),
        "furlong_count": _int(row.get("furlongs")),
        "first_segment_sec": _float(row.get("clock_front")),
        "middle_segment_sec": _float(row.get("clock_middle")),
        "final_segment_sec": _float(row.get("clock_last")),
        "jrdb_first_segment_index": _int(row.get("clock_index_front")),
        "jrdb_middle_segment_index": _int(row.get("clock_index_middle")),
        "jrdb_final_segment_index": _int(row.get("clock_index_last")),
        "jrdb_workout_index": _int(row.get("clock_index_total")),
        "pair_result_code": _text(row.get("pair_result_code")),
        "pair_effort_code": _text(row.get("pair_strength_code")),
        "pair_age": _int(row.get("pair_age")),
        "pair_class_code": _text(row.get("pair_class_code")),
        "source_member": _source_member(row),
        "record_hash": _record_hash(row),
    }


def _used_flag(value: Any) -> int | None:
    numeric = _int(value)
    return numeric if numeric in (0, 1) else None


def project_cyb(row: Mapping[str, Any]) -> dict[str, Any]:
    key = _text(row.get("race_horse_key"))
    return {
        "race_key": _text(row.get("race_key_raw")) or key[:8],
        "horse_no": _int(key[8:10]),
        "training_type_code": _text(row.get("training_type_code")),
        "training_course_type_code": _text(row.get("training_course_type_code")),
        "used_slope": _used_flag(row.get("course_count_slope")),
        "used_wood": _used_flag(row.get("course_count_wood")),
        "used_dirt": _used_flag(row.get("course_count_dirt")),
        "used_turf": _used_flag(row.get("course_count_turf")),
        "used_pool": _used_flag(row.get("course_count_pool")),
        "used_jump": _used_flag(row.get("course_count_obstacle")),
        "used_polytrack": _used_flag(row.get("course_count_polytrack")),
        "training_distance_code": _text(row.get("distance_pattern_code")),
        "training_focus_code": _text(row.get("focus_code")),
        "jrdb_workout_index": _int(row.get("training_index")),
        "finish_index": _int(row.get("condition_index")),
        "training_volume_code": _text(row.get("volume_grade")),
        "finish_change_code": _text(row.get("condition_change_code")),
        "training_evaluation_code": _text(row.get("training_grade_code")),
        "week_ago_workout_index": _int(row.get("one_week_ago_index")),
        "week_ago_course_code": _text(row.get("one_week_ago_course")),
        "source_member": _source_member(row),
        "record_hash": _record_hash(row),
    }


def project_ukc(row: Mapping[str, Any]) -> dict[str, Any]:
    data_date = _yyyymmdd(row.get("data_date_iso")) or _yyyymmdd(row.get("data_date"))
    if data_date is None:
        data_date = _member_date_from_row(row)
    if data_date is None:
        raise WarehouseIndexBaseError("UKC data_date is missing")
    birth_raw = _text(row.get("birth_date"))
    return {
        "horse_id": _text(row.get("horse_id")),
        "data_date": data_date,
        "horse_name": _text(row.get("horse_name")),
        "sex_code": _text(row.get("sex_code")),
        "sire_name": _text(row.get("sire_name")),
        "dam_name": _text(row.get("dam_name")),
        "broodmare_sire_name": _text(row.get("broodmare_sire_name")),
        "birth_date": _yyyymmdd(row.get("birth_date_iso")) or _yyyymmdd(birth_raw) or birth_raw,
        "sire_birth_year": _int(row.get("sire_birth_year")),
        "dam_birth_year": _int(row.get("dam_birth_year")),
        "broodmare_sire_birth_year": _int(row.get("broodmare_sire_birth_year")),
        "breeder_name": _text(row.get("breeder_name")),
        "breeding_place": _text(row.get("breeding_place")),
        "sire_line_code": _text(row.get("sire_line_code")),
        "broodmare_sire_line_code": _text(row.get("broodmare_sire_line_code")),
        "semantic_hash": _text(row.get("semantic_hash")),
        "source_member": _source_member(row),
        "record_hash": _record_hash(row),
    }


def _unique_put(target: dict[Any, dict[str, Any]], key: Any, value: dict[str, Any], kind: str) -> None:
    existing = target.get(key)
    if existing is None:
        target[key] = value
        return
    existing_hash = existing.get("record_hash") or existing.get("semantic_hash")
    value_hash = value.get("record_hash") or value.get("semantic_hash")
    if existing_hash == value_hash:
        return
    raise WarehouseIndexBaseError(f"non-identical duplicate {kind} key={key}")


def _put_bac_revision(target: dict[str, dict[str, Any]], value: dict[str, Any]) -> None:
    key = value["race_key"]
    existing = target.get(key)
    if existing is None:
        target[key] = value
        return
    if existing.get("record_hash") == value.get("record_hash"):
        return
    ignored = {"race_date", "source_member", "record_hash"}
    if ({k: v for k, v in existing.items() if k not in ignored}
            != {k: v for k, v in value.items() if k not in ignored}):
        raise WarehouseIndexBaseError(f"non-identical duplicate BAC key={key}")
    if not existing.get("race_date") or not value.get("race_date"):
        raise WarehouseIndexBaseError(f"ambiguous BAC date revision key={key}")
    if value["race_date"] > existing["race_date"]:
        target[key] = value


def _member_date(member: str) -> str | None:
    match = re.fullmatch(r"[A-Z]+(\d{6})\.txt", Path(member).name, re.IGNORECASE)
    return _yyyymmdd("20" + match.group(1)) if match else None


def _put_pre_race_revision(
    target: dict[tuple[str, int], dict[str, Any]],
    key: tuple[str, int],
    value: dict[str, Any],
    kind: str,
    races: Mapping[str, dict[str, Any]],
) -> None:
    existing = target.get(key)
    if existing is None:
        target[key] = value
        return
    if existing.get("record_hash") == value.get("record_hash"):
        return
    race = races.get(key[0])
    canonical_date = race.get("race_date") if race else None
    existing_date = _member_date(_text(existing.get("source_member")))
    value_date = _member_date(_text(value.get("source_member")))
    if canonical_date is None or existing_date is None or value_date is None:
        raise WarehouseIndexBaseError(f"ambiguous duplicate {kind} key={key}")
    existing_is = existing_date == canonical_date
    value_is = value_date == canonical_date
    if existing_is and not value_is:
        return
    if value_is and not existing_is:
        target[key] = value
        return
    raise WarehouseIndexBaseError(f"ambiguous duplicate {kind} key={key}")


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


def materialize_year_rows(rows: Mapping[str, Iterable[Mapping[str, Any]]]) -> YearData:
    races: dict[str, dict[str, Any]] = {}
    result_contexts: dict[str, dict[str, Any]] = {}
    runners: dict[tuple[str, int], dict[str, Any]] = {}
    previous_links: list[dict[str, Any]] = []
    results: dict[tuple[str, int], dict[str, Any]] = {}
    workouts: dict[tuple[str, int], dict[str, Any]] = {}
    training: dict[tuple[str, int], dict[str, Any]] = {}
    profiles: list[dict[str, Any]] = []

    bac_rows = sorted(rows.get("BAC", []), key=lambda r: (_text(r.get("source_member")), _int(r.get("source_record_ordinal")) or 0))
    for row in bac_rows:
        _put_bac_revision(races, project_bac(row))

    for row in sorted(rows.get("KYI", []), key=lambda r: (_text(r.get("source_member")), _int(r.get("source_record_ordinal")) or 0)):
        runner, links = project_kyi(row)
        key = (runner["race_key"], runner["horse_no"])
        _unique_put(runners, key, runner, "KYI")
        previous_links.extend(links)

    for row in sorted(rows.get("SED", []), key=lambda r: (_text(r.get("source_member")), _int(r.get("source_record_ordinal")) or 0)):
        result, context, fallback = project_sed(row)
        key = (result["race_key"], result["horse_no"])
        _unique_put(results, key, result, "SED")
        _unique_put(result_contexts, context["race_key"], context, "SED_RACE_CONTEXT")
        if fallback["race_key"] not in races:
            races[fallback["race_key"]] = fallback

    for row in sorted(rows.get("CHA", []), key=lambda r: (_text(r.get("source_member")), _int(r.get("source_record_ordinal")) or 0)):
        workout = project_cha(row)
        key = (workout["race_key"], workout["horse_no"])
        _put_pre_race_revision(workouts, key, workout, "CHA", races)

    for row in sorted(rows.get("CYB", []), key=lambda r: (_text(r.get("source_member")), _int(r.get("source_record_ordinal")) or 0)):
        item = project_cyb(row)
        key = (item["race_key"], item["horse_no"])
        _put_pre_race_revision(training, key, item, "CYB", races)

    for row in sorted(rows.get("UKC", []), key=lambda r: (_text(r.get("source_member")), _int(r.get("source_record_ordinal")) or 0)):
        profiles.append(project_ukc(row))

    return YearData(races, result_contexts, runners, previous_links, results, workouts, training, profiles)


class WarehouseIndexBaseReader:
    """Resolve an accepted final manifest and expose yearly normalized relations."""

    def __init__(self, current: Path, *, asset_roots: Mapping[str, Path]) -> None:
        self.current_path = Path(current)
        self.current = json.loads(self.current_path.read_text(encoding="utf-8"))
        if self.current.get("artifact_type") != "jrdb_normalized_warehouse_current" or self.current.get("status") != "accepted":
            raise WarehouseIndexBaseError("JRDB current pointer is not accepted")
        manifest_rel = self.current.get("manifest")
        if not isinstance(manifest_rel, str) or not manifest_rel.endswith("/manifest.json"):
            raise WarehouseIndexBaseError("JRDB current pointer has no manifest")
        self.manifest_path = self.current_path.parent / manifest_rel
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if self.manifest.get("generation_id") != self.current.get("generation_id") or self.manifest.get("status") != "PASS":
            raise WarehouseIndexBaseError("JRDB current/manifest generation mismatch")
        self.asset_roots = {str(k).upper(): Path(v) for k, v in asset_roots.items()}
        self.assets = list(self.manifest.get("assets", []))
        if not self.assets:
            raise WarehouseIndexBaseError("Warehouse manifest has no assets")
        self.covered_years = sorted({int(a["year"]) for a in self.assets if a.get("year") is not None})

    def _asset(self, family: str, year: int) -> tuple[Path, dict[str, Any]] | None:
        matches = [a for a in self.assets if _text(a.get("family")).upper() == family.upper() and int(a.get("year", -1)) == year]
        if not matches:
            if family in OPTIONAL_FAMILIES:
                return None
            raise WarehouseIndexBaseError(f"manifest has no {family}/{year}")
        if len(matches) != 1:
            raise WarehouseIndexBaseError(f"manifest has multiple {family}/{year} assets")
        asset = matches[0]
        root = self.asset_roots.get(family.upper())
        if root is None:
            raise WarehouseIndexBaseError(f"asset root not supplied for {family}")
        path = root / _text(asset.get("relative_path"))
        if not path.is_file():
            raise WarehouseIndexBaseError(f"missing immutable asset: {path}")
        return path, asset

    def year_rows(self, year: int) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        if year < MIN_YEAR or year > MAX_YEAR or year not in self.covered_years:
            raise WarehouseIndexBaseError(f"{year}: outside accepted 2010-2025 Warehouse coverage")
        try:
            import duckdb
        except ImportError as exc:
            raise WarehouseIndexBaseError("Warehouse Index Base reader requires duckdb") from exc
        rows: dict[str, list[dict[str, Any]]] = {}
        evidence: dict[str, Any] = {}
        connection = duckdb.connect(":memory:")
        try:
            for family in ALL_FAMILIES:
                resolved = self._asset(family, year)
                if resolved is None:
                    rows[family] = []
                    continue
                path, asset = resolved
                cursor = connection.execute("SELECT * FROM read_parquet(?) ORDER BY source_member, source_record_ordinal", [str(path)])
                names = [item[0] for item in cursor.description]
                rows[family] = [dict(zip(names, values)) for values in cursor.fetchall()]
                evidence[family] = {
                    "path": str(path),
                    "sha256": _text(asset.get("sha256")),
                    "size_bytes": _int(asset.get("size_bytes")),
                    "row_count": len(rows[family]),
                }
        finally:
            connection.close()
        return rows, evidence

    def load_year(self, year: int) -> tuple[YearData, dict[str, Any]]:
        rows, evidence = self.year_rows(year)
        data = materialize_year_rows(rows)
        return data, {
            "source_mode": "warehouse",
            "source_generation_id": self.current.get("generation_id"),
            "year": year,
            "assets": evidence,
        }
