#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attach descriptive Named / Local / Base Trend context to RaceNote v1.

The aggregation model is intentionally derived from the JRDB PWA Fact Lite:
filters -> parameterized WHERE -> GROUP BY axis -> descriptive rows.

No trend row is converted into a forecast score or horse ranking.
"""
from __future__ import annotations

import argparse
import copy
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

VERSION = "RaceNote-Trend-Aggregator-0.1"

VENUE_CODES = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
    "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
}
SURFACE_CODES = {"芝": "1", "ダート": "2", "障害": "3"}

CLASS_CODE_GROUPS = {
    "新馬": ("A1",),
    "未出走": ("A2",),
    "未勝利": ("A3",),
    "1勝クラス": ("04", "05"),
    "2勝クラス": ("08", "09", "10"),
    "3勝クラス": ("15", "16"),
    "オープン": ("OP",),
}
GRADE_CODES = {"G1": "1", "G2": "2", "G3": "3", "重賞": "4", "L": "6"}

AXES: dict[str, dict[str, str]] = {
    "popularity": {
        "label": "人気",
        "select": (
            "CASE "
            "WHEN f.final_win_popularity BETWEEN 1 AND 9 "
            "THEN CAST(f.final_win_popularity AS TEXT) "
            "WHEN f.final_win_popularity >= 10 THEN '10～' "
            "ELSE '不明' END"
        ),
        "group": (
            "CASE "
            "WHEN f.final_win_popularity BETWEEN 1 AND 9 "
            "THEN CAST(f.final_win_popularity AS TEXT) "
            "WHEN f.final_win_popularity >= 10 THEN '10～' "
            "ELSE '不明' END"
        ),
        "joins": "",
    },
    "frame": {
        "label": "枠",
        "select": "CAST(f.frame_no AS TEXT)",
        "group": "f.frame_no",
        "joins": "",
    },
    "style": {
        "label": "脚質",
        "select": "COALESCE(NULLIF(f.running_style,''),'不明')",
        "group": "f.running_style",
        "joins": "",
    },
    "age": {
        "label": "年齢",
        "select": "CAST(f.age AS TEXT)",
        "group": "f.age",
        "joins": "",
    },
    "sex": {
        "label": "性別",
        "select": "COALESCE(NULLIF(f.sex_code,''),'不明')",
        "group": "f.sex_code",
        "joins": "",
    },
    "sire": {
        "label": "種牡馬",
        "select": "COALESCE(NULLIF(f.sire_name,''),'不明')",
        "group": "f.sire_name",
        "joins": "",
    },
    "jockey": {
        "label": "騎手",
        "select": "COALESCE(NULLIF(f.jockey_name,''),'不明')",
        "group": "f.jockey_name",
        "joins": "",
    },
    "prev_distance": {
        "label": "前走距離",
        "select": (
            "CASE "
            "WHEN p.distance IS NULL THEN '前走不明' "
            "WHEN p.distance < f.distance THEN '距離延長' "
            "WHEN p.distance = f.distance THEN '同距離' "
            "ELSE '距離短縮' END"
        ),
        "group": (
            "CASE "
            "WHEN p.distance IS NULL THEN '前走不明' "
            "WHEN p.distance < f.distance THEN '距離延長' "
            "WHEN p.distance = f.distance THEN '同距離' "
            "ELSE '距離短縮' END"
        ),
        "joins": (
            "LEFT JOIN ("
            " SELECT race_key, MAX(distance) AS distance"
            " FROM fact_entry_result_lite GROUP BY race_key"
            ") AS p ON p.race_key=f.prev_race_key_1"
        ),
    },
    "prev_class": {
        "label": "前走クラス",
        "select": (
            "CASE "
            "WHEN pc.race_key IS NULL THEN '前走不明' "
            "WHEN pc.grade_code='1' THEN 'G1' "
            "WHEN pc.grade_code='2' THEN 'G2' "
            "WHEN pc.grade_code='3' THEN 'G3' "
            "WHEN pc.grade_code='4' THEN 'その他重賞' "
            "WHEN pc.grade_code='6' THEN 'L' "
            "WHEN pc.race_condition_code IN ('15','16') THEN '3勝' "
            "WHEN pc.race_condition_code IN ('08','09','10') THEN '2勝' "
            "WHEN pc.race_condition_code IN ('04','05') THEN '1勝' "
            "WHEN pc.race_condition_code='OP' THEN 'オープン' "
            "WHEN pc.race_condition_code='A3' THEN '未勝利' "
            "WHEN pc.race_condition_code='A1' THEN '新馬' "
            "ELSE 'その他' END"
        ),
        "group": (
            "CASE "
            "WHEN pc.race_key IS NULL THEN '前走不明' "
            "WHEN pc.grade_code='1' THEN 'G1' "
            "WHEN pc.grade_code='2' THEN 'G2' "
            "WHEN pc.grade_code='3' THEN 'G3' "
            "WHEN pc.grade_code='4' THEN 'その他重賞' "
            "WHEN pc.grade_code='6' THEN 'L' "
            "WHEN pc.race_condition_code IN ('15','16') THEN '3勝' "
            "WHEN pc.race_condition_code IN ('08','09','10') THEN '2勝' "
            "WHEN pc.race_condition_code IN ('04','05') THEN '1勝' "
            "WHEN pc.race_condition_code='OP' THEN 'オープン' "
            "WHEN pc.race_condition_code='A3' THEN '未勝利' "
            "WHEN pc.race_condition_code='A1' THEN '新馬' "
            "ELSE 'その他' END"
        ),
        "joins": (
            "LEFT JOIN ("
            " SELECT race_key, MAX(race_condition_code) AS race_condition_code,"
            " MAX(grade_code) AS grade_code"
            " FROM fact_entry_result_lite GROUP BY race_key"
            ") AS pc ON pc.race_key=f.prev_race_key_1"
        ),
    },
}


class TrendError(RuntimeError):
    pass


def _table_columns(conn: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in conn.execute("PRAGMA table_info(fact_entry_result_lite)")}


def _require_v14_columns(conn: sqlite3.Connection) -> None:
    required = {
        "race_date", "year", "venue_code", "meeting_no", "meeting_day",
        "race_no", "track_type", "distance", "race_condition_code",
        "grade_code", "race_name", "course_code", "race_key", "frame_no",
        "sex_code", "age", "sire_name", "jockey_name", "running_style",
        "final_win_popularity", "finish", "win_payout", "place_payout",
        "prev_race_key_1",
    }
    missing = sorted(required - _table_columns(conn))
    if missing:
        raise TrendError(
            "Analysis Lite lacks RaceNote Trend columns: " + ", ".join(missing)
        )


def _race_codes(note: Mapping[str, object]) -> dict[str, str | None]:
    race = note.get("race")
    if not isinstance(race, Mapping):
        raise TrendError("RaceNote race is missing")
    source = race.get("source_codes")
    source = source if isinstance(source, Mapping) else {}

    venue = str(source.get("venue_code") or "").strip() or VENUE_CODES.get(str(race.get("venue") or ""))
    surface = str(source.get("surface_code") or "").strip() or SURFACE_CODES.get(str(race.get("surface") or ""))
    class_code = str(source.get("race_class_code") or "").strip() or None
    grade_code = str(source.get("grade_code") or "").strip() or None
    course_code = str(source.get("course_code") or "").strip() or None
    return {
        "venue_code": venue,
        "surface_code": surface,
        "race_class_code": class_code,
        "grade_code": grade_code,
        "course_code": course_code,
    }


def _class_filter(race: Mapping[str, object], codes: Mapping[str, str | None]) -> tuple[str, list[object]]:
    grade = str(race.get("grade") or "").strip()
    if grade in GRADE_CODES:
        return "f.grade_code = ?", [GRADE_CODES[grade]]

    label = str(race.get("class") or "").strip()
    values = CLASS_CODE_GROUPS.get(label)
    if values:
        placeholders = ",".join("?" for _ in values)
        return f"f.race_condition_code IN ({placeholders})", list(values)

    if codes.get("race_class_code"):
        return "f.race_condition_code = ?", [codes["race_class_code"]]
    if codes.get("grade_code"):
        return "f.grade_code = ?", [codes["grade_code"]]
    return "1=1", []


def _base_filters(note: Mapping[str, object]) -> tuple[list[str], list[object], dict[str, object]]:
    race = note["race"]
    codes = _race_codes(note)
    target = str(race.get("date") or "")
    year = int(target[:4])
    clauses = [
        "f.race_date < ?",
        "f.year BETWEEN ? AND ?",
        "f.venue_code = ?",
        "f.track_type = ?",
        "f.distance = ?",
    ]
    params: list[object] = [
        target,
        year - 10,
        year,
        codes["venue_code"],
        codes["surface_code"],
        int(race["distance_m"]),
    ]
    scope = {
        "period": f"{year-10}-{year} as-of {target}",
        "venue": race.get("venue"),
        "surface": race.get("surface"),
        "distance_m": race.get("distance_m"),
    }
    return clauses, params, scope


def _levels(note: Mapping[str, object], kind: str) -> list[dict[str, object]]:
    race = note["race"]
    codes = _race_codes(note)
    base_clauses, base_params, base_scope = _base_filters(note)
    class_sql, class_params = _class_filter(race, codes)
    month = int(str(race["date"])[5:7])
    day = race.get("meeting_day")
    day_int = int(day) if isinstance(day, int) or str(day or "").isdigit() else None

    if kind == "base":
        return [{
            "id": "BASE_COURSE",
            "clauses": base_clauses,
            "params": base_params,
            "scope": {**base_scope, "class_scope": "ALL_CLASS"},
        }]

    if kind == "named":
        name = str(race.get("race_name") or "").strip()
        if not name:
            return []
        strict_clauses = base_clauses + ["TRIM(COALESCE(f.race_name,'')) = ?", class_sql]
        strict_params = base_params + [name] + class_params
        strict_scope = {
            **base_scope,
            "race_name": name,
            "class": race.get("class"),
            "grade": race.get("grade"),
        }
        if codes.get("course_code"):
            return [
                {
                    "id": "NAMED_EXACT",
                    "clauses": strict_clauses + ["f.course_code = ?"],
                    "params": strict_params + [codes["course_code"]],
                    "scope": {**strict_scope, "course_rail": race.get("course_rail")},
                },
                {
                    "id": "NAMED_SAME_CONDITIONS_EXCEPT_RAIL",
                    "clauses": strict_clauses,
                    "params": strict_params,
                    "scope": {**strict_scope, "course_rail": "ANY"},
                },
            ]
        return [{
            "id": "NAMED_EXACT",
            "clauses": strict_clauses,
            "params": strict_params,
            "scope": strict_scope,
        }]

    # Local trend: class is preserved through every fallback level.
    local_base = base_clauses + [class_sql, "CAST(SUBSTR(f.race_date,6,2) AS INTEGER) = ?"]
    local_params = base_params + class_params + [month]
    common_scope = {
        **base_scope,
        "class": race.get("class"),
        "grade": race.get("grade"),
        "month": month,
    }
    levels: list[dict[str, object]] = []

    strict_clauses = list(local_base)
    strict_params = list(local_params)
    strict_scope = dict(common_scope)
    if codes.get("course_code"):
        strict_clauses.append("f.course_code = ?")
        strict_params.append(codes["course_code"])
        strict_scope["course_rail"] = race.get("course_rail")
    if day_int is not None:
        strict_clauses.append("f.meeting_day BETWEEN ? AND ?")
        strict_params.extend([max(1, day_int - 2), min(15, day_int + 2)])
        strict_scope["meeting_day_band"] = [max(1, day_int - 2), min(15, day_int + 2)]

    levels.append({
        "id": "LOCAL_STRICT",
        "clauses": strict_clauses,
        "params": strict_params,
        "scope": strict_scope,
    })

    if day_int is not None:
        c = list(local_base)
        p = list(local_params)
        sc = dict(common_scope)
        if codes.get("course_code"):
            c.append("f.course_code = ?")
            p.append(codes["course_code"])
            sc["course_rail"] = race.get("course_rail")
        levels.append({"id": "LOCAL_DROP_MEETING_DAY", "clauses": c, "params": p, "scope": sc})

    c = base_clauses + [class_sql]
    p = base_params + class_params
    sc = {**base_scope, "class": race.get("class"), "grade": race.get("grade")}
    if codes.get("course_code"):
        c.append("f.course_code = ?")
        p.append(codes["course_code"])
        sc["course_rail"] = race.get("course_rail")
    levels.append({"id": "LOCAL_DROP_MONTH", "clauses": c, "params": p, "scope": sc})

    levels.append({
        "id": "LOCAL_SAME_CLASS_COURSE",
        "clauses": base_clauses + [class_sql],
        "params": base_params + class_params,
        "scope": {
            **base_scope,
            "class": race.get("class"),
            "grade": race.get("grade"),
            "course_rail": "ANY",
        },
    })
    return levels


def _sample(conn: sqlite3.Connection, clauses: list[str], params: list[object]) -> dict[str, object]:
    row = conn.execute(
        "SELECT COUNT(*) AS starts, COUNT(DISTINCT race_key) AS races "
        "FROM fact_entry_result_lite AS f WHERE " + " AND ".join(clauses),
        params,
    ).fetchone()
    return {"starts": int(row[0] or 0), "races": int(row[1] or 0)}


def _axis_rows(
    conn: sqlite3.Connection,
    clauses: list[str],
    params: list[object],
    axis: str,
) -> list[dict[str, object]]:
    config = AXES[axis]
    sql = (
        "SELECT " + config["select"] + " AS item, "
        "COUNT(*) AS starts, "
        "SUM(CASE WHEN f.finish=1 THEN 1 ELSE 0 END) AS wins, "
        "SUM(CASE WHEN f.finish=2 THEN 1 ELSE 0 END) AS seconds, "
        "SUM(CASE WHEN f.finish=3 THEN 1 ELSE 0 END) AS thirds, "
        "SUM(COALESCE(f.win_payout,0)) AS win_payout_sum, "
        "SUM(COALESCE(f.place_payout,0)) AS place_payout_sum "
        "FROM fact_entry_result_lite AS f "
        + config["joins"] + " WHERE " + " AND ".join(clauses)
        + " GROUP BY " + config["group"]
        + " ORDER BY starts DESC, item"
    )
    output: list[dict[str, object]] = []
    for row in conn.execute(sql, params).fetchall():
        starts = int(row[1] or 0)
        wins = int(row[2] or 0)
        seconds = int(row[3] or 0)
        thirds = int(row[4] or 0)
        out = max(0, starts - wins - seconds - thirds)
        output.append({
            "item": row[0],
            "starts": starts,
            "finish_record": {
                "first": wins,
                "second": seconds,
                "third": thirds,
                "out": out,
                "compact": f"({wins}-{seconds}-{thirds}-{out})",
            },
            "win_rate": round(wins * 100 / starts, 1) if starts else None,
            "top3_rate": round((wins + seconds + thirds) * 100 / starts, 1) if starts else None,
            "win_roi": round(float(row[5] or 0) / starts, 1) if starts else None,
            "place_roi": round(float(row[6] or 0) / starts, 1) if starts else None,
        })
    return output


def _aggregate_level(
    conn: sqlite3.Connection,
    level: Mapping[str, object],
) -> dict[str, object]:
    clauses = list(level["clauses"])
    params = list(level["params"])
    sample = _sample(conn, clauses, params)
    dimensions = {
        axis: {
            "label": config["label"],
            "rows": _axis_rows(conn, clauses, params, axis),
        }
        for axis, config in AXES.items()
    }
    return {
        "level_id": level["id"],
        "scope": copy.deepcopy(level["scope"]),
        "sample": sample,
        "dimensions": dimensions,
    }


def _build_block(
    conn: sqlite3.Connection,
    note: Mapping[str, object],
    kind: str,
) -> dict[str, object]:
    levels = _levels(note, kind)
    if not levels:
        return {
            "status": "NOT_APPLICABLE",
            "scope": None,
            "sample": {"starts": 0, "races": 0, "editions": None, "period": None},
            "dimensions": {},
            "provenance_refs": ["P3_ANALYSIS_TREND"],
            "fallback_levels": [],
            "limitations": [],
        }

    aggregated = [_aggregate_level(conn, level) for level in levels]
    selected = next((item for item in aggregated if item["sample"]["starts"] > 0), aggregated[0])
    status = "AVAILABLE" if selected["sample"]["starts"] > 0 else "UNAVAILABLE"
    limitations: list[str] = []
    if status == "UNAVAILABLE":
        limitations.append("No historical rows matched any configured scope.")
    if selected["level_id"] != aggregated[0]["level_id"]:
        limitations.append(
            "The strictest scope had no rows; a broader support scope was selected."
        )

    period = selected["scope"].get("period")
    sample = {
        **selected["sample"],
        "editions": selected["sample"]["races"] if kind == "named" else None,
        "period": period,
    }
    return {
        "status": status,
        "selected_level": selected["level_id"],
        "scope": selected["scope"],
        "sample": sample,
        "dimensions": selected["dimensions"],
        "provenance_refs": ["P3_ANALYSIS_TREND"],
        "fallback_levels": [
            {
                "level_id": item["level_id"],
                "scope": item["scope"],
                "sample": item["sample"],
            }
            for item in aggregated
        ],
        "limitations": limitations,
    }


def attach_trends(note: Mapping[str, object], analysis_db: Path) -> dict[str, object]:
    output = copy.deepcopy(dict(note))
    conn = sqlite3.connect(f"file:{analysis_db}?mode=ro", uri=True)
    try:
        _require_v14_columns(conn)
        named = _build_block(conn, output, "named")
        local = _build_block(conn, output, "local")
        base = _build_block(conn, output, "base")
    finally:
        conn.close()

    output["trend_context"] = {
        "named_race": named,
        "local_context": local,
        "base_context": base,
        "comparison": {
            "status": (
                "AVAILABLE"
                if local["status"] == "AVAILABLE" and base["status"] == "AVAILABLE"
                else "PARTIAL"
            ),
            "notes": [
                (
                    "Local/Named/Base are descriptive samples. "
                    "No block is automatically preferred by RaceNote."
                )
            ],
        },
    }
    provenance = output.setdefault("provenance", [])
    provenance.append({
        "id": "P3_ANALYSIS_TREND",
        "source": "JRDB Analysis Lite v1.4",
        "as_of": str(output.get("metadata", {}).get("as_of") or ""),
        "snapshot": str(analysis_db),
        "transform_version": VERSION,
    })
    missing = output.get("coverage", {}).get("missing_families")
    if isinstance(missing, list):
        output["coverage"]["missing_families"] = [
            item for item in missing
            if item not in {"named_race_trend", "local_context_trend"}
        ]
        if named["status"] != "AVAILABLE":
            output["coverage"]["missing_families"].append("named_race_trend")
        if local["status"] != "AVAILABLE":
            output["coverage"]["missing_families"].append("local_context_trend")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note", type=Path, required=True)
    parser.add_argument("--analysis-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    note = json.loads(args.note.read_text(encoding="utf-8"))
    if not isinstance(note, Mapping):
        raise TrendError("RaceNote root must be object")
    output = attach_trends(note, args.analysis_db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS",
        "named": output["trend_context"]["named_race"]["status"],
        "local": output["trend_context"]["local_context"]["status"],
        "base": output["trend_context"]["base_context"]["status"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
