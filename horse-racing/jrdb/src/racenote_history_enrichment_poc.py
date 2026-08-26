#!/usr/bin/env python3
"""Add Analysis Lite / Stats Mart history enrichment to a RaceNote bundle."""
from __future__ import annotations

import argparse
import copy
import json
import sqlite3
from pathlib import Path

JRA_VENUES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}
VENUE_TO_CODE = {value: key for key, value in JRA_VENUES.items()}
TRACK_TYPE = {"1": "芝", "2": "ダート", "3": "障害"}
SURFACE_TO_CODE = {value: key for key, value in TRACK_TYPE.items()}
TRACK_CONDITION = {
    "1": "良",
    "2": "稍重",
    "3": "重",
    "4": "不良",
    "10": "良",
    "11": "速良",
    "12": "遅良",
    "20": "稍重",
    "21": "速稍重",
    "22": "遅稍重",
    "30": "重",
    "31": "速重",
    "32": "遅重",
    "40": "不良",
    "41": "速不良",
    "42": "遅不良",
}
GRADE = {"1": "G1", "2": "G2", "3": "G3", "4": "重賞", "5": "特別", "6": "L"}
TABLE = "fact_entry_result_lite"

# RaceNote distance ranges intentionally overlap at 1400m and 1800m.
# 2400m belongs only to the middle-distance range; long distance begins at 2500m.
DISTANCE_RANGE_DEFINITIONS = (
    {"min_m": 1000, "max_m": 1400},
    {"min_m": 1400, "max_m": 1800},
    {"min_m": 1800, "max_m": 2400},
    {"min_m": 2500, "max_m": None},
)


def decode(mapping: dict[str, str], value: object) -> object:
    """Decode a JRDB code when a mapping is known."""
    if value is None:
        return None
    text = str(value).strip()
    return mapping.get(text, value)


def rate(numerator: int, denominator: int) -> float | None:
    """Return a percentage rounded to one decimal place."""
    if denominator == 0:
        return None
    return round(numerator * 100 / denominator, 1)


def summary(starts: int, wins: int, top3: int) -> dict:
    """Build a compact starts/wins/top3 summary."""
    starts_int = int(starts)
    wins_int = int(wins)
    top3_int = int(top3)
    return {
        "starts": starts_int,
        "wins": wins_int,
        "top3": top3_int,
        "win_rate": rate(wins_int, starts_int),
        "top3_rate": rate(top3_int, starts_int),
    }


def query_summary(connection: sqlite3.Connection, where: str, parameters: list[object]) -> dict:
    """Aggregate one horse-history condition from Analysis Lite."""
    row = connection.execute(
        f"""
        SELECT
            COUNT(*),
            SUM(CASE WHEN finish = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END)
        FROM {TABLE}
        WHERE {where}
        """,
        parameters,
    ).fetchone()
    return summary(row[0] or 0, row[1] or 0, row[2] or 0)


def applicable_distance_ranges(distance_m: int) -> list[dict]:
    """Return all configured ranges that contain the target distance.

    1400m and 1800m intentionally belong to both adjacent ranges.
    2400m belongs only to 1800-2400m, while 2500m and above use 2500+.
    """
    ranges: list[dict] = []
    for definition in DISTANCE_RANGE_DEFINITIONS:
        minimum = int(definition["min_m"])
        maximum = definition["max_m"]
        if distance_m < minimum:
            continue
        if maximum is not None and distance_m > int(maximum):
            continue
        ranges.append(dict(definition))
    return ranges


def distance_where(definition: dict, column: str = "distance") -> tuple[str, list[int]]:
    """Build SQL and parameters for one distance range."""
    minimum = int(definition["min_m"])
    maximum = definition["max_m"]
    if maximum is None:
        return f"{column}>=?", [minimum]
    return f"{column} BETWEEN ? AND ?", [minimum, int(maximum)]


def target_entry(
    connection: sqlite3.Connection,
    race_date: str,
    venue_code: str,
    race_no: int,
    horse_no: int,
) -> sqlite3.Row | None:
    """Return the target entry row from Analysis Lite."""
    return connection.execute(
        f"SELECT * FROM {TABLE} WHERE race_date=? AND venue_code=? AND race_no=? AND horse_no=?",
        (race_date, venue_code, race_no, horse_no),
    ).fetchone()


def horse_distance_ranges(
    connection: sqlite3.Connection,
    horse_id: str,
    race_date: str,
    target_distance: int,
) -> list[dict]:
    """Aggregate the horse's own history for target-relevant distance ranges."""
    output: list[dict] = []
    base_where = "horse_id=? AND race_date<?"
    base_parameters: list[object] = [horse_id, race_date]

    for definition in applicable_distance_ranges(target_distance):
        range_where, range_parameters = distance_where(definition)
        item = dict(definition)
        item.update(
            query_summary(
                connection,
                base_where + " AND " + range_where,
                base_parameters + range_parameters,
            )
        )
        output.append(item)
    return output


def historical_profile(
    connection: sqlite3.Connection,
    horse_id: str,
    race_date: str,
    venue_code: str,
    track_type: str,
    distance: int,
    window_start: str,
) -> dict:
    """Build compact horse-history aggregates from Analysis Lite."""
    base_where = "horse_id=? AND race_date<?"
    base_parameters: list[object] = [horse_id, race_date]
    return {
        "source": "JRDB Analysis Lite",
        "source_window_start": window_start,
        "as_of_exclusive": race_date,
        "career": query_summary(connection, base_where, base_parameters),
        "same_surface": query_summary(
            connection,
            base_where + " AND track_type=?",
            base_parameters + [track_type],
        ),
        "same_distance": query_summary(
            connection,
            base_where + " AND distance=?",
            base_parameters + [distance],
        ),
        "distance_ranges": horse_distance_ranges(
            connection,
            horse_id,
            race_date,
            distance,
        ),
        "same_venue": query_summary(
            connection,
            base_where + " AND venue_code=?",
            base_parameters + [venue_code],
        ),
    }


def older_runs(
    connection: sqlite3.Connection,
    horse_id: str,
    race_date: str,
    recent_runs: list[dict],
    limit: int,
) -> list[dict]:
    """Return compact Analysis rows older than the PACI detailed recent runs."""
    recent_dates = [
        item.get("race", {}).get("date")
        for item in recent_runs
        if item.get("race", {}).get("date")
    ]
    cutoff = min(recent_dates) if recent_dates else race_date
    rows = connection.execute(
        f"""
        SELECT
            race_date,
            venue_code,
            race_no,
            track_type,
            distance,
            track_condition_code,
            grade_code,
            running_style,
            training_index,
            finish,
            abnormal_code,
            final_win_odds,
            final_win_popularity
        FROM {TABLE}
        WHERE horse_id=? AND race_date<?
        ORDER BY race_date DESC, race_no DESC
        LIMIT ?
        """,
        (horse_id, cutoff, limit),
    ).fetchall()
    return [
        {
            "date": row["race_date"],
            "venue": JRA_VENUES.get(str(row["venue_code"]), row["venue_code"]),
            "race_no": row["race_no"],
            "surface": decode(TRACK_TYPE, row["track_type"]),
            "distance_m": row["distance"],
            "track_condition": decode(TRACK_CONDITION, row["track_condition_code"]),
            "grade": decode(GRADE, row["grade_code"]),
            "running_style": row["running_style"],
            "training_index": row["training_index"],
            "finish": row["finish"],
            "abnormal_code": row["abnormal_code"],
            "final_win_odds": row["final_win_odds"],
            "final_popularity": row["final_win_popularity"],
        }
        for row in rows
    ]


def mart_prior(
    connection: sqlite3.Connection,
    table: str,
    dimension_column: str,
    dimension_value: object,
    year_start: int,
    year_end: int,
    venue_code: str,
    track_type: str,
    distance_where_sql: str,
    distance_parameters: list[int],
) -> tuple[int, int, int]:
    """Aggregate prior completed years from Stats Mart."""
    if year_end < year_start:
        return 0, 0, 0
    row = connection.execute(
        f"""
        SELECT
            COALESCE(SUM(starts), 0),
            COALESCE(SUM(wins), 0),
            COALESCE(SUM(top3), 0)
        FROM {table}
        WHERE year BETWEEN ? AND ?
          AND venue_code=?
          AND track_type=?
          AND {distance_where_sql}
          AND {dimension_column}=?
        """,
        [year_start, year_end, venue_code, track_type]
        + distance_parameters
        + [dimension_value],
    ).fetchone()
    return tuple(int(value or 0) for value in row)


def current_year(
    connection: sqlite3.Connection,
    analysis_column: str,
    dimension_value: object,
    year: int,
    race_date: str,
    venue_code: str,
    track_type: str,
    distance_where_sql: str,
    distance_parameters: list[int],
) -> tuple[int, int, int]:
    """Aggregate target-year rows before the target date from Analysis Lite."""
    row = connection.execute(
        f"""
        SELECT
            COUNT(*),
            SUM(CASE WHEN finish = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END)
        FROM {TABLE}
        WHERE year=?
          AND race_date<?
          AND venue_code=?
          AND track_type=?
          AND {distance_where_sql}
          AND {analysis_column}=?
        """,
        [year, race_date, venue_code, track_type]
        + distance_parameters
        + [dimension_value],
    ).fetchone()
    return tuple(int(value or 0) for value in row)


def as_of_summary(
    analysis: sqlite3.Connection,
    mart: sqlite3.Connection,
    mart_table: str,
    mart_column: str,
    analysis_column: str,
    dimension_value: object,
    race_date: str,
    venue_code: str,
    track_type: str,
    distance_where_sql: str,
    distance_parameters: list[int],
    years: int,
) -> dict:
    """Build an as-of-safe Mart + Analysis statistic."""
    year = int(race_date[:4])
    year_start = year - years + 1
    prior = mart_prior(
        mart,
        mart_table,
        mart_column,
        dimension_value,
        year_start,
        year - 1,
        venue_code,
        track_type,
        distance_where_sql,
        distance_parameters,
    )
    target_year = current_year(
        analysis,
        analysis_column,
        dimension_value,
        year,
        race_date,
        venue_code,
        track_type,
        distance_where_sql,
        distance_parameters,
    )
    output = summary(*(prior[index] + target_year[index] for index in range(3)))
    output.update(
        {
            "period": f"{year_start}-{year}YTD",
            "as_of_exclusive": race_date,
            "track_condition_scope": "all_conditions",
            "source": "Stats Mart prior years + Analysis Lite target-year YTD",
        }
    )
    return output


def exact_stat(
    analysis: sqlite3.Connection,
    mart: sqlite3.Connection,
    mart_table: str,
    mart_column: str,
    analysis_column: str,
    dimension_value: object,
    race_date: str,
    venue_code: str,
    track_type: str,
    distance: int,
    years: int,
) -> dict:
    """Build the existing exact-distance statistic."""
    return as_of_summary(
        analysis,
        mart,
        mart_table,
        mart_column,
        analysis_column,
        dimension_value,
        race_date,
        venue_code,
        track_type,
        "distance=?",
        [distance],
        years,
    )


def range_stats(
    analysis: sqlite3.Connection,
    mart: sqlite3.Connection,
    mart_table: str,
    mart_column: str,
    analysis_column: str,
    dimension_value: object,
    race_date: str,
    venue_code: str,
    track_type: str,
    target_distance: int,
    years: int,
) -> list[dict]:
    """Build target-relevant overlapping distance-range statistics."""
    output: list[dict] = []
    for definition in applicable_distance_ranges(target_distance):
        where_sql, parameters = distance_where(definition)
        item = dict(definition)
        item.update(
            as_of_summary(
                analysis,
                mart,
                mart_table,
                mart_column,
                analysis_column,
                dimension_value,
                race_date,
                venue_code,
                track_type,
                where_sql,
                parameters,
                years,
            )
        )
        output.append(item)
    return output


def statistic_with_ranges(
    analysis: sqlite3.Connection,
    mart: sqlite3.Connection,
    mart_table: str,
    mart_column: str,
    analysis_column: str,
    dimension_value: object,
    race_date: str,
    venue_code: str,
    track_type: str,
    distance: int,
    years: int,
) -> dict:
    """Preserve exact-distance fields and append distance_ranges."""
    output = exact_stat(
        analysis,
        mart,
        mart_table,
        mart_column,
        analysis_column,
        dimension_value,
        race_date,
        venue_code,
        track_type,
        distance,
        years,
    )
    output["distance_ranges"] = range_stats(
        analysis,
        mart,
        mart_table,
        mart_column,
        analysis_column,
        dimension_value,
        race_date,
        venue_code,
        track_type,
        distance,
        years,
    )
    return output


def enrich(
    base: dict,
    analysis: sqlite3.Connection,
    mart: sqlite3.Connection,
    older_limit: int,
    years: int,
) -> tuple[dict, list[str]]:
    """Enrich one RaceNote bundle."""
    race_date = base["race"]["date"]
    venue_name = base["race"]["venue"]
    venue_code = VENUE_TO_CODE[venue_name]
    race_no = int(base["race"]["race_no"])
    track_type = SURFACE_TO_CODE.get(base["race"]["surface"], base["race"]["surface"])
    distance = int(base["race"]["distance_m"])
    window_start = analysis.execute(f"SELECT MIN(race_date) FROM {TABLE}").fetchone()[0]

    output = copy.deepcopy(base)
    warnings: list[str] = []
    output.setdefault("metadata", {})["history_enrichment_poc"] = {
        "version": "0.2",
        "older_runs_per_horse": older_limit,
        "stats_window_years": years,
        "as_of_exclusive": race_date,
        "future_leakage_policy": (
            "prior completed years from Stats Mart; target year from Analysis Lite "
            "with race_date < target_date"
        ),
        "distance_range_policy": {
            "ranges": [dict(item) for item in DISTANCE_RANGE_DEFINITIONS],
            "overlap_boundaries_m": [1400, 1800],
            "long_distance_min_m": 2500,
        },
    }

    for horse in output.get("horses", []):
        horse_no = int(horse["basic"]["horse_no"])
        entry = target_entry(analysis, race_date, venue_code, race_no, horse_no)
        if entry is None:
            warnings.append(f"target_entry_not_found:horse_no={horse_no}")
            horse["older_runs"] = []
            horse["historical_profile"] = None
            horse["stats"] = {"sire": None, "jockey": None}
            continue

        horse_id = entry["horse_id"]
        horse["older_runs"] = (
            older_runs(
                analysis,
                horse_id,
                race_date,
                horse.get("recent_runs", []),
                older_limit,
            )
            if horse_id
            else []
        )
        horse["historical_profile"] = (
            historical_profile(
                analysis,
                horse_id,
                race_date,
                venue_code,
                track_type,
                distance,
                window_start,
            )
            if horse_id
            else None
        )

        sire = entry["sire_name"]
        jockey = entry["jockey_name"] or horse["basic"].get("jockey")
        horse["stats"] = {
            "sire": (
                statistic_with_ranges(
                    analysis,
                    mart,
                    "mart_sire_yearly",
                    "sire_name",
                    "sire_name",
                    sire,
                    race_date,
                    venue_code,
                    track_type,
                    distance,
                    years,
                )
                if sire
                else None
            ),
            "jockey": (
                statistic_with_ranges(
                    analysis,
                    mart,
                    "mart_jockey_yearly",
                    "jockey_name",
                    "jockey_name",
                    jockey,
                    race_date,
                    venue_code,
                    track_type,
                    distance,
                    years,
                )
                if jockey
                else None
            ),
        }

    frames: dict[str, dict] = {}
    for frame_no in range(1, 9):
        frame_stat = statistic_with_ranges(
            analysis,
            mart,
            "mart_frame_yearly",
            "frame_no",
            "frame_no",
            frame_no,
            race_date,
            venue_code,
            track_type,
            distance,
            years,
        )
        if frame_stat["starts"]:
            frames[str(frame_no)] = frame_stat
    output["race"]["race_trends"] = {"frame": frames}
    return output, warnings


def metrics(value: dict) -> dict:
    """Measure formatted JSON character and UTF-8 byte size."""
    text = json.dumps(value, ensure_ascii=False, indent=2)
    return {"chars": len(text), "utf8_bytes": len(text.encode())}


def main() -> None:
    """Generate 8-run and 10-run enrichment variants."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--mart", required=True)
    parser.add_argument("--output-dir", default="./racenote_history_poc")
    parser.add_argument("--stats-window-years", type=int, default=5)
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base = json.loads(bundle_path.read_text(encoding="utf-8"))
    base_metrics = metrics(base)

    analysis = sqlite3.connect(args.analysis)
    mart = sqlite3.connect(args.mart)
    analysis.row_factory = sqlite3.Row
    mart.row_factory = sqlite3.Row

    variants: dict[str, dict] = {}
    try:
        for total_runs, older_limit in ((8, 3), (10, 5)):
            enriched, warnings = enrich(
                base,
                analysis,
                mart,
                older_limit,
                args.stats_window_years,
            )
            text = json.dumps(enriched, ensure_ascii=False, indent=2)
            output_path = output_dir / (
                f"{bundle_path.stem}_enriched_{total_runs}runs_poc.json"
            )
            output_path.write_text(text + "\n", encoding="utf-8")
            variant_metrics = metrics(enriched)
            variants[str(total_runs)] = {
                "path": str(output_path),
                **variant_metrics,
                "incremental_utf8_bytes": (
                    variant_metrics["utf8_bytes"] - base_metrics["utf8_bytes"]
                ),
                "warning_count": len(warnings),
                "warnings": warnings,
                "older_runs_counts": [
                    len(horse.get("older_runs", []))
                    for horse in enriched.get("horses", [])
                ],
            }
    finally:
        analysis.close()
        mart.close()

    comparison = {
        "poc_version": "0.2",
        "target": {
            "date": base["race"]["date"],
            "venue": base["race"]["venue"],
            "race_no": base["race"]["race_no"],
            "race_name": base["race"].get("race_name"),
            "horses": len(base.get("horses", [])),
        },
        "base": base_metrics,
        "variants": variants,
        "distance_range_policy": {
            "ranges": [dict(item) for item in DISTANCE_RANGE_DEFINITIONS],
            "overlap_boundaries_m": [1400, 1800],
            "long_distance_min_m": 2500,
        },
        "notes": [
            "8runs = PACI recent_runs (up to 5) + Analysis older_runs (up to 3).",
            "10runs = PACI recent_runs (up to 5) + Analysis older_runs (up to 5).",
            "Stats use all track conditions; target-year rows are recalculated from Analysis before target date to prevent future leakage.",
            "Exact-distance statistics are preserved and target-relevant distance_ranges are appended.",
            "1400m and 1800m intentionally belong to both adjacent ranges; 2400m is middle only and long distance begins at 2500m.",
        ],
    }
    comparison_path = output_dir / f"{bundle_path.stem}_enrichment_comparison_poc.json"
    comparison_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
