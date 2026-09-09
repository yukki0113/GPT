#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build JRDB Newspaper base JSON directly from PACI/Common Reader.

This consumer deliberately does not import RaceNote internals. Fixed-width parsing
belongs to jrdb_raw.Parser; this module owns only Newspaper projection, history
selection, and validation policy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from jrdb_raw import (
    Parser,
    ReaderAudit,
    canonical_members,
    hhmm,
    race_key_parts,
    read_fixed_records,
    ymd,
)

VERSION = "0.1.1"

VENUES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
SURFACE = {"1": "芝", "2": "ダート", "3": "障害"}
TURN = {"1": "右", "2": "左", "3": "直線", "9": "その他"}
LAYOUT = {"1": "通常（内）", "2": "外", "3": "直線ダート", "9": "その他"}
COURSE = {"1": "A", "2": "A1", "3": "A2", "4": "B", "5": "C", "6": "D"}
RACE_TYPE = {"11": "2歳", "12": "3歳", "13": "3歳以上", "14": "4歳以上", "20": "障害", "99": "その他"}
RACE_CLASS = {
    "A1": "新馬", "A2": "未出走", "A3": "未勝利",
    "04": "1勝クラス", "05": "1勝クラス",
    "08": "2勝クラス", "09": "2勝クラス", "10": "2勝クラス",
    "15": "3勝クラス", "16": "3勝クラス", "OP": "オープン",
}
GRADE = {"1": "G1", "2": "G2", "3": "G3", "4": "重賞", "5": "特別", "6": "L"}
WEIGHT_RULE = {"1": "ハンデ", "2": "別定", "3": "馬齢", "4": "定量"}
TRACK_CONDITION = {
    "10": "良", "11": "速良", "12": "遅良",
    "20": "稍重", "21": "速稍重", "22": "遅稍重",
    "30": "重", "31": "速重", "32": "遅重",
    "40": "不良", "41": "速不良", "42": "遅不良",
    "1": "良", "2": "稍重", "3": "重", "4": "不良",
}
SEX = {"1": "牡", "2": "牝", "3": "セン"}
RUNNING_STYLE = {"1": "逃げ", "2": "先行", "3": "差し", "4": "追込", "5": "好位差し", "6": "自在"}
DISTANCE_FIT = {"1": "短距離", "2": "中距離", "3": "長距離", "5": "マイル", "6": "万能"}
MARK = {"1": "◎", "2": "○", "3": "▲", "4": "注", "5": "△", "6": "△", "9": "☆"}
TRAINING_ARROW = {"1": "デキ抜群", "2": "上昇", "3": "平行線", "4": "やや下降気味", "5": "デキ落ち"}
PACE = {"H": "ハイ", "M": "平均", "S": "スロー"}

PACI_KINDS = ("BAC", "KYI", "CHA", "CYB", "ZED", "ZKB", "UKC")
EXTERNAL_SOURCES = ("eval", "racenote_prediction", "keibailuka", "edge", "my_index")


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


def _label(table: dict[str, str], code: Any) -> str | None:
    key = _text(code)
    return table.get(key) if key else None


def _race_time_sec(value: Any) -> float | None:
    raw = _text(value)
    if len(raw) != 4 or not raw.isdigit():
        return None
    return int(raw[0]) * 60.0 + int(raw[1:]) / 10.0


def _age_on_date(birth_date: Any, target_date: str) -> int | None:
    raw = _text(birth_date).replace("-", "")
    target = target_date.replace("-", "")
    if len(raw) != 8 or not raw.isdigit() or len(target) != 8 or not target.isdigit():
        return None
    age = int(target[:4]) - int(raw[:4])
    return age if age >= 0 else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_paci(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    """Parse Newspaper-relevant PACI members with Common Reader only."""
    parser_audit = ReaderAudit()
    parser = Parser(parser_audit)
    parsed: dict[str, list[dict[str, Any]]] = {kind: [] for kind in PACI_KINDS}

    with zipfile.ZipFile(path) as archive:
        for kind in PACI_KINDS:
            method = getattr(parser, kind.lower())
            for member in canonical_members(archive, kind):
                for record in read_fixed_records(archive, member, kind, parser_audit):
                    item = method(record)
                    item["_source_member"] = member
                    parsed[kind].append(item)

    if parser_audit.record_length_errors:
        raise ValueError(f"PACI record length error: {dict(parser_audit.record_length_errors)}")
    if not parsed["BAC"] or not parsed["KYI"]:
        raise ValueError("PACI has no BAC/KYI records")
    return parsed, dict(parser_audit.record_length_errors)


def _unique_index(rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = _text(row.get(key))
        if not value:
            continue
        if value in output:
            raise ValueError(f"duplicate {label} key: {value}")
        output[value] = row
    return output


def _profile_index(rows: Iterable[dict[str, Any]], target_date_raw: str) -> dict[str, dict[str, Any]]:
    """Choose latest non-future PACI UKC observation for each horse."""
    output: dict[str, dict[str, Any]] = {}
    scores: dict[str, str] = {}
    for row in rows:
        horse_id = _text(row.get("horse_id"))
        if not horse_id:
            continue
        data_date = _text(row.get("data_date"))
        if data_date and len(data_date) == 8 and data_date.isdigit() and data_date > target_date_raw:
            continue
        score = data_date if len(data_date) == 8 and data_date.isdigit() else "00000000"
        if horse_id not in output or score >= scores[horse_id]:
            output[horse_id] = row
            scores[horse_id] = score
    return output


def _normalize_workout(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    return {
        "date": ymd(_text(raw.get("date_raw"))),
        "weekday": raw.get("weekday"),
        "workout_count": raw.get("workout_count"),
        "course_code": raw.get("course_code"),
        "strength_code": raw.get("strength_code"),
        "state_code": raw.get("state_code"),
        "rider_type_code": raw.get("rider_type_code"),
        "furlongs": raw.get("furlongs"),
        "clock": raw.get("clock"),
        "clock_index": raw.get("clock_index"),
        "pair": raw.get("pair"),
    }


def _normalize_training(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    return {
        "training_type_code": raw.get("training_type_code"),
        "training_course_type_code": raw.get("training_course_type_code"),
        "course_counts": raw.get("course_counts"),
        "distance_pattern_code": raw.get("distance_pattern_code"),
        "focus_code": raw.get("focus_code"),
        "training_index": raw.get("training_index"),
        "condition_index": raw.get("condition_index"),
        "volume_grade": raw.get("volume_grade"),
        "condition_change_code": raw.get("condition_change_code"),
        "comment": raw.get("comment"),
        "comment_date": ymd(_text(raw.get("comment_date_raw"))),
        "training_grade_code": raw.get("training_grade_code"),
        "one_week_ago_index": raw.get("one_week_ago_index"),
        "one_week_ago_course": raw.get("one_week_ago_course"),
    }


def _history_from_zed(
    zed: dict[str, Any],
    zkb: dict[str, Any] | None,
    *,
    sequence: int,
    link_sequence: int,
) -> dict[str, Any]:
    parts = race_key_parts(_text(zed.get("race_key_raw")))
    metrics = zed.get("metrics") if isinstance(zed.get("metrics"), dict) else {}
    notes = None
    if zkb is not None:
        notes = {
            "paddock_comment": zkb.get("paddock_comment"),
            "leg_comment": zkb.get("leg_comment"),
            "equipment_comment": zkb.get("equipment_comment"),
            "race_comment": zkb.get("race_comment"),
            "tokki_codes": zkb.get("tokki_codes") or [],
            "equipment_codes": zkb.get("equipment_codes") or [],
        }
    carried = _float(zed.get("carried_weight_tenths"))
    finish = _int(zed.get("finish"))
    time_gap_sec = _float(zed.get("first_second_time_diff_sec"))
    time_gap_reference = None
    if time_gap_sec is not None and finish is not None:
        if finish == 1:
            time_gap_reference = "RUNNER_UP"
        elif finish > 1:
            time_gap_reference = "WINNER"
    return {
        "sequence": sequence,
        "link_sequence": link_sequence,
        "source_layer": "detailed_recent_history",
        "source_kind": "paci_previous_detail",
        "detail_level": "detailed",
        "race_key": zed.get("race_key_raw"),
        "result_key": zed.get("result_key"),
        "date": ymd(_text(zed.get("date_raw"))),
        "venue_code": parts.get("venue_code"),
        "venue": VENUES.get(_text(parts.get("venue_code")), _text(parts.get("venue_code")) or None),
        "race_no": parts.get("race_no"),
        "race_name": zed.get("race_name"),
        "class_label": _label(RACE_CLASS, zed.get("race_class_code")),
        "grade_label": _label(GRADE, zed.get("grade_code")),
        "surface": _label(SURFACE, zed.get("surface_code")),
        "distance_m": _int(zed.get("distance_m")),
        "track_condition": _label(TRACK_CONDITION, zed.get("track_condition_code")),
        "field_size": _int(zed.get("field_size")),
        "horse_no": _int(zed.get("horse_no")),
        "finish": finish,
        "final_popularity": _int(zed.get("final_popularity")),
        "final_win_odds": _float(zed.get("final_win_odds")),
        "jockey_name": zed.get("jockey"),
        "carried_weight_kg": carried / 10.0 if carried is not None else None,
        "corner_positions": list(zed.get("corners") or []),
        "time_sec": _race_time_sec(zed.get("time_raw")),
        "time_gap_sec": time_gap_sec,
        "time_gap_reference": time_gap_reference,
        "first3f_sec": _float(zed.get("first3f_sec")),
        "last3f_sec": _float(zed.get("last3f_sec")),
        "last3f_rank": None,
        "idm": _float(zed.get("idm")),
        "body_weight_kg": _int(zed.get("body_weight_kg")),
        "body_weight_change_kg": _int(zed.get("body_weight_change_kg")),
        "abnormal_code": _text(zed.get("abnormal_code")) or None,
        "notes": notes,
        "jrdb_result": {
            "raw_score": metrics.get("raw_score"),
            "track_diff": metrics.get("track_diff"),
            "pace_score": metrics.get("pace_score"),
            "late_break_score": metrics.get("late_break_score"),
            "position_score": metrics.get("position_score"),
            "trouble_score": metrics.get("trouble_score"),
            "race_score": metrics.get("race_score"),
            "front_index": metrics.get("front_index"),
            "late_index": metrics.get("late_index"),
            "pace_index": metrics.get("pace_index"),
            "race_pace_index": metrics.get("race_pace_index"),
            "race_running_style_code": zed.get("race_running_style_code"),
        },
    }


def _analysis_history(
    analysis_path: Path,
    horse_id: str,
    *,
    before: str,
    limit: int,
    start_sequence: int,
) -> list[dict[str, Any]]:
    """Read compact older history directly from shared Analysis Lite."""
    if limit <= 0 or not horse_id:
        return []
    connection = sqlite3.connect(analysis_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT race_key, race_date, venue_code, race_no, track_type, distance,
                   race_condition_code, track_condition_code, grade_code,
                   running_style, training_index, finish, abnormal_code,
                   final_win_odds, final_win_popularity
            FROM fact_entry_result_lite
            WHERE horse_id=? AND race_date<?
            ORDER BY race_date DESC, race_no DESC
            LIMIT ?
            """,
            (horse_id, before, limit),
        ).fetchall()
    finally:
        connection.close()

    output: list[dict[str, Any]] = []
    for offset, row in enumerate(rows):
        output.append({
            "sequence": start_sequence + offset,
            "link_sequence": None,
            "source_layer": "compact_older_history",
            "source_kind": "analysis_compact",
            "detail_level": "compact",
            "race_key": row["race_key"],
            "result_key": None,
            "date": row["race_date"],
            "venue_code": row["venue_code"],
            "venue": VENUES.get(_text(row["venue_code"]), _text(row["venue_code"]) or None),
            "race_no": row["race_no"],
            "race_name": None,
            "class_label": _label(RACE_CLASS, row["race_condition_code"]),
            "grade_label": _label(GRADE, row["grade_code"]),
            "surface": _label(SURFACE, row["track_type"]),
            "distance_m": row["distance"],
            "track_condition": _label(TRACK_CONDITION, row["track_condition_code"]),
            "field_size": None,
            "horse_no": None,
            "finish": row["finish"],
            "final_popularity": row["final_win_popularity"],
            "final_win_odds": row["final_win_odds"],
            "jockey_name": None,
            "carried_weight_kg": None,
            "corner_positions": [],
            "time_sec": None,
            "time_gap_sec": None,
            "time_gap_reference": None,
            "first3f_sec": None,
            "last3f_sec": None,
            "last3f_rank": None,
            "idm": None,
            "body_weight_kg": None,
            "body_weight_change_kg": None,
            "abnormal_code": row["abnormal_code"],
            "notes": None,
            "jrdb_result": {
                "running_style_code": row["running_style"],
                "training_index": row["training_index"],
            },
        })
    return output


def _history_for_runner(
    runner: dict[str, Any],
    *,
    target_date_raw: str,
    zed_index: dict[str, dict[str, Any]],
    zkb_index: dict[str, dict[str, Any]],
    analysis_path: Path | None,
    diagnostics: Counter[str],
) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    previous = runner.get("previous")
    if not isinstance(previous, list):
        previous = []

    for link_sequence, link in enumerate(previous[:5], start=1):
        if not isinstance(link, dict):
            continue
        result_key = _text(link.get("result_key"))
        if not result_key or result_key == "0" * 16:
            continue
        diagnostics["previous_expected"] += 1
        zed = zed_index.get(result_key)
        if zed is None:
            diagnostics["previous_unresolved"] += 1
            continue
        history_date = _text(zed.get("date_raw"))
        if not history_date or len(history_date) != 8 or not history_date.isdigit():
            raise ValueError(f"invalid linked history date: {result_key}={history_date!r}")
        if history_date >= target_date_raw:
            raise ValueError(
                f"target/future result contamination: {result_key} "
                f"history={history_date} target={target_date_raw}"
            )
        diagnostics["previous_resolved"] += 1
        zkb = zkb_index.get(result_key)
        if zkb is not None:
            diagnostics["zkb_resolved"] += 1
        history.append(_history_from_zed(
            zed,
            zkb,
            sequence=len(history) + 1,
            link_sequence=link_sequence,
        ))

    if analysis_path is not None and len(history) < 8:
        before = history[-1]["date"] if history else ymd(target_date_raw)
        if before:
            older = _analysis_history(
                analysis_path,
                _text(runner.get("blood_registration_no")),
                before=before,
                limit=8 - len(history),
                start_sequence=len(history) + 1,
            )
            diagnostics["analysis_compact_added"] += len(older)
            history.extend(older)
    return history[:8]


def _runner_row(
    runner: dict[str, Any],
    *,
    target_date: str,
    profile: dict[str, Any] | None,
    cha: dict[str, Any] | None,
    cyb: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    carried = _float(runner.get("carried_weight_tenths"))
    marks_raw = runner.get("marks") if isinstance(runner.get("marks"), dict) else {}
    pace_indices = runner.get("pace_indices") if isinstance(runner.get("pace_indices"), dict) else {}
    pace_ranks = runner.get("pace_ranks") if isinstance(runner.get("pace_ranks"), dict) else {}
    profile = profile or {}
    return {
        "key": {
            "race_horse_key": runner.get("race_horse_key"),
            "horse_id": _text(runner.get("blood_registration_no")) or None,
            "horse_no": _int(runner.get("horse_no")),
            "frame_no": _int(runner.get("frame_no")),
        },
        "basic": {
            "horse_name": runner.get("horse_name"),
            "sex_label": _label(SEX, runner.get("sex_code")),
            "age": _age_on_date(profile.get("birth_date"), target_date),
            "carried_weight_kg": carried / 10.0 if carried is not None else None,
            "jockey_name": runner.get("jockey"),
            "jockey_code": runner.get("jockey_code"),
            "trainer_name": runner.get("trainer"),
            "sire_name": profile.get("sire_name"),
            "dam_name": profile.get("dam_name"),
            "broodmare_sire_name": profile.get("broodmare_sire_name"),
            "running_style_label": _label(RUNNING_STYLE, runner.get("running_style_code")),
            "distance_fit_label": _label(DISTANCE_FIT, runner.get("distance_fit_code")),
            "body_weight_pre_kg": _int(runner.get("body_weight_pre_kg")),
            "body_weight_change_pre_kg": _int(runner.get("body_weight_change_pre_kg")),
        },
        "jrdb": {
            "marks": {key: _label(MARK, value) for key, value in marks_raw.items()},
            "ability": {
                "idm": _float(runner.get("idm")),
                "total_index": _float(runner.get("total_index")),
                "jockey_index": _float(runner.get("jockey_index")),
                "info_index": _float(runner.get("info_index")),
                "stable_index": _float(runner.get("stable_index")),
                "longshot_index": _float(runner.get("longshot_index")),
                "running_style_code": runner.get("running_style_code"),
                "distance_fit_code": runner.get("distance_fit_code"),
                "heavy_track_fit_code": runner.get("heavy_track_fit_code"),
                "jrdb_class_code": runner.get("jrdb_class_code"),
                "improvement_code": runner.get("improvement_code"),
                "rotation_interval": _int(runner.get("rotation_interval")),
            },
            "training": {
                "summary": {
                    "training_index": _float(runner.get("training_index")),
                    "training_arrow_code": runner.get("training_arrow_code"),
                    "training_arrow": _label(TRAINING_ARROW, runner.get("training_arrow_code")),
                    "stable_evaluation_code": runner.get("stable_evaluation_code"),
                },
                "main_workout": _normalize_workout(cha),
                "analysis": _normalize_training(cyb),
            },
            "pace": {
                "start_index": _float(runner.get("start_index")),
                "late_break_rate": _float(runner.get("late_break_rate")),
                "forecast_pace_code": runner.get("forecast_pace_code"),
                "forecast_pace": _label(PACE, runner.get("forecast_pace_code")),
                "indices": pace_indices,
                "ranks": pace_ranks,
                "forecast_positions": runner.get("forecast_positions"),
            },
        },
        "addons": {
            "eval": None,
            "racenote_prediction": None,
            "keibailuka": None,
            "my_index": None,
        },
        "history": history,
        "edge_matches": [],
    }


def validate_bundle(bundle: dict[str, Any]) -> None:
    """Fail closed on Newspaper business invariants independent of JSON Schema."""
    if bundle.get("schema_version") != "0.1":
        raise ValueError("unexpected Newspaper schema version")
    race = bundle.get("race") or {}
    target_date = _text(race.get("date"))
    horses = bundle.get("horses")
    if not isinstance(horses, list):
        raise ValueError("horses must be a list")
    field_size = _int(race.get("field_size"))
    if field_size is not None and field_size != len(horses):
        raise ValueError(f"field size mismatch: BAC={field_size} horses={len(horses)}")

    horse_numbers: set[int] = set()
    for horse in horses:
        horse_no = _int((horse.get("key") or {}).get("horse_no"))
        if horse_no is None or horse_no in horse_numbers:
            raise ValueError(f"duplicate/invalid horse_no: {horse_no}")
        horse_numbers.add(horse_no)
        history = horse.get("history") or []
        if len(history) > 8:
            raise ValueError(f"history exceeds 8: horse_no={horse_no}")
        for expected_sequence, run in enumerate(history, start=1):
            if run.get("sequence") != expected_sequence:
                raise ValueError(f"history sequence gap: horse_no={horse_no}")
            run_date = _text(run.get("date"))
            if not run_date or run_date >= target_date:
                raise ValueError(
                    f"non-historical run: horse_no={horse_no} run={run_date} target={target_date}"
                )


def build_race_bundle(
    parsed: dict[str, list[dict[str, Any]]],
    race_key: str,
    *,
    source_sha256: str | None = None,
    analysis_path: Path | None = None,
    revision: int = 1,
    generated_at: str | None = None,
) -> dict[str, Any]:
    bac_index = _unique_index(parsed.get("BAC", []), "race_key_raw", "BAC")
    race_raw = bac_index.get(race_key)
    if race_raw is None:
        raise KeyError(f"BAC race not found: {race_key}")
    target_date_raw = _text(race_raw.get("date_raw"))
    target_date = ymd(target_date_raw)
    if target_date is None:
        raise ValueError(f"invalid target date: {target_date_raw!r}")

    runners = [
        row for row in parsed.get("KYI", [])
        if _text(row.get("race_key_raw")) == race_key and _text(row.get("cancel_flag")) != "1"
    ]
    runners.sort(key=lambda row: (_int(row.get("horse_no")) or 999))
    field_size = _int(race_raw.get("field_size"))
    if field_size is not None and len(runners) != field_size:
        raise ValueError(f"field size mismatch: BAC={field_size} KYI={len(runners)}")

    cha_index = _unique_index(parsed.get("CHA", []), "race_horse_key", "CHA")
    cyb_index = _unique_index(parsed.get("CYB", []), "race_horse_key", "CYB")
    zed_index = _unique_index(parsed.get("ZED", []), "result_key", "ZED")
    zkb_index = _unique_index(parsed.get("ZKB", []), "result_key", "ZKB")
    profiles = _profile_index(parsed.get("UKC", []), target_date_raw)

    diagnostics: Counter[str] = Counter()
    horses: list[dict[str, Any]] = []
    for runner in runners:
        horse_id = _text(runner.get("blood_registration_no"))
        history = _history_for_runner(
            runner,
            target_date_raw=target_date_raw,
            zed_index=zed_index,
            zkb_index=zkb_index,
            analysis_path=analysis_path,
            diagnostics=diagnostics,
        )
        race_horse = _text(runner.get("race_horse_key"))
        horses.append(_runner_row(
            runner,
            target_date=target_date,
            profile=profiles.get(horse_id),
            cha=cha_index.get(race_horse),
            cyb=cyb_index.get(race_horse),
            history=history,
        ))

    parts = race_key_parts(race_key)
    generated_at = generated_at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    source_status: dict[str, dict[str, Any]] = {
        "jrdb_base": {
            "state": "READY",
            "source_version": VERSION,
            "generated_at": generated_at,
            "semantic_sha256": source_sha256,
            "message": None,
        },
        "jrdb_history": {
            "state": "READY",
            "source_version": VERSION,
            "generated_at": generated_at,
            "semantic_sha256": None,
            "message": (
                f"resolved={diagnostics['previous_resolved']} "
                f"unresolved={diagnostics['previous_unresolved']} "
                f"analysis_added={diagnostics['analysis_compact_added']}"
            ),
            "coverage_complete": diagnostics["previous_unresolved"] == 0,
            "expected_count": diagnostics["previous_expected"],
            "resolved_count": diagnostics["previous_resolved"],
            "unresolved_count": diagnostics["previous_unresolved"],
            "supplemental_count": diagnostics["analysis_compact_added"],
        },
    }
    for source in EXTERNAL_SOURCES:
        source_status[source] = {
            "state": "PENDING",
            "source_version": None,
            "generated_at": None,
            "semantic_sha256": None,
            "message": None,
        }

    bundle = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_race",
        "metadata": {
            "generated_at": generated_at,
            "revision": revision,
            "base_snapshot_id": source_sha256,
            "source_status": source_status,
            "diagnostics": dict(diagnostics),
        },
        "race": {
            "race_key": race_key,
            "date": target_date,
            "venue_code": parts.get("venue_code"),
            "venue": VENUES.get(_text(parts.get("venue_code")), _text(parts.get("venue_code"))),
            "meeting": race_raw.get("meeting"),
            "race_no": parts.get("race_no"),
            "start_time": hhmm(_text(race_raw.get("post_time_raw"))),
            "race_name": race_raw.get("race_name"),
            "surface": _label(SURFACE, race_raw.get("surface_code")),
            "distance_m": _int(race_raw.get("distance_raw")),
            "turn": _label(TURN, race_raw.get("turn_code")),
            "course_layout": _label(LAYOUT, race_raw.get("layout_code")),
            "course_label": _label(COURSE, race_raw.get("course_code")),
            "class_label": _label(RACE_CLASS, race_raw.get("race_class_code")),
            "grade_label": _label(GRADE, race_raw.get("grade_code")),
            "race_type_label": _label(RACE_TYPE, race_raw.get("race_type_code")),
            "weight_rule_label": _label(WEIGHT_RULE, race_raw.get("weight_rule_code")),
            "field_size": field_size,
        },
        "race_notes": {
            "items": [],
            "racenote_short_comment": None,
        },
        "horses": horses,
    }
    validate_bundle(bundle)
    return bundle


def build_from_paci(
    paci_path: Path,
    race_key: str,
    *,
    analysis_path: Path | None = None,
    revision: int = 1,
    generated_at: str | None = None,
) -> dict[str, Any]:
    parsed, _audit = load_paci(paci_path)
    return build_race_bundle(
        parsed,
        race_key,
        source_sha256=_sha256(paci_path),
        analysis_path=analysis_path,
        revision=revision,
        generated_at=generated_at,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one JRDB Newspaper base race JSON")
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--race-key", required=True)
    parser.add_argument("--analysis", type=Path)
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    bundle = build_from_paci(
        args.paci,
        args.race_key,
        analysis_path=args.analysis,
        revision=args.revision,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "success",
        "race_key": args.race_key,
        "horses": len(bundle["horses"]),
        "output": str(args.output),
        "size_bytes": args.output.stat().st_size,
        "diagnostics": bundle["metadata"]["diagnostics"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
