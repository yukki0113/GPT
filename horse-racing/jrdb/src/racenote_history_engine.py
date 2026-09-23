#!/usr/bin/env python3
"""Add Analysis-canonical history enrichment to a RaceNote bundle."""
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


def sample_size_band(starts: int) -> str:
    """Return a descriptive sample-size band derived only from starts."""
    if starts == 0:
        return "none"
    if starts < 20:
        return "small"
    if starts < 50:
        return "moderate"
    return "sufficient"


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
        "sample_size_band": sample_size_band(starts_int),
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
    """Aggregate prior completed years directly from Analysis canonical.

    table is retained only for call compatibility with the frozen engine
    surface; the active query never reads Stats Mart.
    """
    del table
    if year_end < year_start:
        return 0, 0, 0
    row = connection.execute(
        f"""
        SELECT
            COUNT(*),
            SUM(CASE WHEN finish = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END)
        FROM {TABLE}
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
    """Build an as-of-safe Analysis-canonical statistic."""
    year = int(race_date[:4])
    year_start = year - years + 1
    prior = mart_prior(
        analysis,
        mart_table,
        analysis_column,
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
            "source": "JRDB Analysis canonical (as-of-exclusive)",
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


def build_run_layers(horse: dict, older_limit: int) -> dict:
    """Describe the meaning and observed size of detailed and compact run layers."""
    return {
        "recent_runs": {
            "source": "PACI",
            "role": "detailed_recent_history",
            "observed_count": len(horse.get("recent_runs", [])),
            "max_count": 5,
            "career_completeness": "not_guaranteed",
        },
        "older_runs": {
            "source": "JRDB Analysis Lite",
            "role": "compact_older_history",
            "observed_count": len(horse.get("older_runs", [])),
            "max_count": older_limit,
            "selection": "strictly_older_than_oldest_recent_run",
            "career_completeness": "not_guaranteed",
        },
    }


def build_history_coverage(
    horse: dict,
    profile: dict | None,
    older_limit: int,
) -> dict:
    """Describe the observable JRDB/JRA history without guessing overseas completeness."""
    trainer_base = horse.get("basic", {}).get("trainer_base")
    domestic_bases = {"美浦", "栗東", "地方"}
    observed_starts = 0
    if profile is not None:
        observed_starts = int(profile.get("career", {}).get("starts") or 0)

    foreign_based = trainer_base not in domestic_bases and trainer_base not in (None, "")
    if observed_starts > 0:
        reason = "jra_history_observed"
        overseas_coverage = "not_guaranteed"
    elif foreign_based:
        reason = "foreign_based_entry_no_jra_history"
        overseas_coverage = "not_in_scope"
    else:
        reason = "no_prior_jra_history_observed"
        overseas_coverage = "not_guaranteed"

    return {
        "scope": "jrdb_jra_history",
        "observed_history": "present" if observed_starts > 0 else "none",
        "observed_starts": observed_starts,
        "overseas_history_coverage": overseas_coverage,
        "reason": reason,
        "run_layers": build_run_layers(horse, older_limit),
    }


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
            "all rolling statistics from JRDB Analysis canonical with race_date < target_date"
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
            horse["history_coverage"] = {
                "scope": "jrdb_jra_history",
                "observed_history": "unknown",
                "observed_starts": None,
                "overseas_history_coverage": "not_guaranteed",
                "reason": "target_entry_not_found",
                "run_layers": build_run_layers(horse, older_limit),
            }
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
        profile_value = (
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
        horse["history_coverage"] = build_history_coverage(
            horse,
            profile_value,
            older_limit,
        )
        if (
            horse["history_coverage"]["reason"]
            == "foreign_based_entry_no_jra_history"
        ):
            profile_value = None
        horse["historical_profile"] = profile_value

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


def _count_summary(values: tuple[int, int, int]) -> dict:
    """Convert bulk SQL counts to the existing semantic summary."""
    return summary(*(int(value or 0) for value in values))


class BulkEnrichmentIndex:
    """Request-scoped DuckDB bulk aggregates.

    The index deliberately contains only SQL aggregate results and the small
    target-day/target-horse row sets needed to render the existing contract.
    It never creates a pandas/DataFrame representation of the full Parquet
    source.  Each dimension is scanned once for the whole request and then
    grouped in memory by its canonical keys.
    """

    def __init__(self, analysis: object, bases: list[dict], older_limit: int, years: int):
        self.analysis = analysis
        self.bases = bases
        self.older_limit = older_limit
        self.years = years
        self.race_date = str(bases[0]["race"]["date"])
        self.year = int(self.race_date[:4])
        self.year_start = self.year - years + 1
        self.entries: dict[tuple[str, str, int, int], object] = {}
        self.horse_rows: dict[str, list[dict]] = {}
        self.horse_aggregates: dict[str, list[tuple]] = {}
        self.dimension_aggregates: dict[str, dict[tuple, tuple[int, int, int]]] = {}
        self.window_start = self.race_date
        self._load()

    @staticmethod
    def _placeholders(values: list[object]) -> str:
        return ",".join("?" for _ in values)

    @staticmethod
    def _add(target: dict, key: object, row: tuple) -> None:
        old = target.get(key, (0, 0, 0))
        target[key] = tuple(old[index] + int(row[index] or 0) for index in range(3))

    def _load(self) -> None:
        window_row = self.analysis.execute(f"SELECT MIN(race_date) FROM {TABLE}").fetchone()
        if window_row and window_row[0] is not None:
            self.window_start = str(window_row[0])
        target_rows = self.analysis.execute(
            f"SELECT * FROM {TABLE} WHERE race_date=?", [self.race_date]
        ).fetchall()
        requested_keys = set()
        for base in self.bases:
            race = base["race"]
            venue_code = VENUE_TO_CODE[race["venue"]]
            race_key = (self.race_date, venue_code, int(race["race_no"]))
            for horse in base.get("horses", []):
                requested_keys.add(race_key + (int(horse["basic"]["horse_no"]),))
        for row in target_rows:
            key = (str(row["race_date"]), str(row["venue_code"]), int(row["race_no"]), int(row["horse_no"]))
            if key in requested_keys:
                self.entries[key] = row

        horse_ids = sorted({str(row["horse_id"]) for row in self.entries.values() if row["horse_id"]})
        if not horse_ids:
            return
        placeholders = self._placeholders(horse_ids)
        aggregate_rows = self.analysis.execute(
            f"""
            SELECT horse_id, track_type, venue_code, distance, year,
                   COUNT(*),
                   SUM(CASE WHEN finish=1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END)
            FROM {TABLE}
            WHERE race_date<? AND horse_id IN ({placeholders})
            GROUP BY horse_id, track_type, venue_code, distance, year
            """,
            [self.race_date, *horse_ids],
        ).fetchall()
        for row in aggregate_rows:
            self.horse_aggregates.setdefault(str(row[0]), []).append(tuple(row[1:]))

        detail_rows = self.analysis.execute(
            f"""
            SELECT horse_id, race_date, race_no, venue_code, track_type,
                   distance, track_condition_code, grade_code, running_style,
                   training_index, finish, abnormal_code, final_win_odds,
                   final_win_popularity
            FROM {TABLE}
            WHERE race_date<? AND horse_id IN ({placeholders})
            ORDER BY horse_id, race_date DESC, race_no DESC
            """,
            [self.race_date, *horse_ids],
        ).fetchall()
        for row in detail_rows:
            self.horse_rows.setdefault(str(row[0]), []).append(row)

        for column in ("sire_name", "jockey_name", "frame_no"):
            values = sorted({row[column] for row in self.entries.values() if row[column] not in (None, "")})
            if not values:
                continue
            value_placeholders = self._placeholders(values)
            rows = self.analysis.execute(
                f"""
                SELECT {column}, venue_code, track_type, distance, year,
                       COUNT(*),
                       SUM(CASE WHEN finish=1 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END)
                FROM {TABLE}
                WHERE race_date<? AND year>=? AND {column} IN ({value_placeholders})
                GROUP BY {column}, venue_code, track_type, distance, year
                """,
                [self.race_date, self.year_start, *values],
            ).fetchall()
            grouped: dict[tuple, tuple[int, int, int]] = {}
            for row in rows:
                self._add(grouped, (row[0], str(row[1]), str(row[2]), int(row[3] or 0)), row[5:8])
            self.dimension_aggregates[column] = grouped

    def _horse_summary(self, horse_id: str, predicate) -> dict:
        counts = (0, 0, 0)
        for track_type, venue_code, distance, year, starts, wins, top3 in self.horse_aggregates.get(horse_id, []):
            if predicate(str(track_type), str(venue_code), int(distance or 0), int(year)):
                counts = tuple(counts[index] + int((starts, wins, top3)[index] or 0) for index in range(3))
        return _count_summary(counts)

    def _stat(self, column: str, value: object, venue: str, track: str, distance: int, race_date: str) -> dict:
        grouped = self.dimension_aggregates.get(column, {})
        exact = self._stat_summary(grouped, value, venue, track, lambda item: item == distance)
        output = dict(exact)
        output.update({"period": f"{self.year_start}-{self.year}YTD", "as_of_exclusive": race_date, "track_condition_scope": "all_conditions", "source": "JRDB Analysis canonical (as-of-exclusive)"})
        output["distance_ranges"] = []
        for definition in applicable_distance_ranges(distance):
            minimum, maximum = int(definition["min_m"]), definition["max_m"]
            in_range = lambda item, minimum=minimum, maximum=maximum: item >= minimum and (maximum is None or item <= int(maximum))
            item = dict(definition)
            item.update(self._stat_summary(grouped, value, venue, track, in_range))
            item.update({"period": f"{self.year_start}-{self.year}YTD", "as_of_exclusive": race_date, "track_condition_scope": "all_conditions", "source": "JRDB Analysis canonical (as-of-exclusive)"})
            output["distance_ranges"].append(item)
        return output

    @staticmethod
    def _stat_summary(grouped: dict, value: object, venue: str, track: str, distance_predicate) -> dict:
        counts = (0, 0, 0)
        for (dimension, row_venue, row_track, row_distance), row_counts in grouped.items():
            if dimension == value and row_venue == venue and row_track == track and distance_predicate(row_distance):
                counts = tuple(counts[index] + row_counts[index] for index in range(3))
        return _count_summary(counts)

    def enrich_one(self, base: dict) -> tuple[dict, list[str]]:
        race = base["race"]
        race_date = str(race["date"])
        venue_code = VENUE_TO_CODE[race["venue"]]
        race_no = int(race["race_no"])
        track_type = SURFACE_TO_CODE.get(race["surface"], race["surface"])
        distance = int(race["distance_m"])
        output = copy.deepcopy(base)
        warnings: list[str] = []
        output.setdefault("metadata", {})["history_enrichment_poc"] = {
            "version": "0.2", "older_runs_per_horse": self.older_limit, "stats_window_years": self.years,
            "as_of_exclusive": race_date,
            "future_leakage_policy": "all rolling statistics from JRDB Analysis canonical with race_date < target_date",
            "distance_range_policy": {"ranges": [dict(item) for item in DISTANCE_RANGE_DEFINITIONS], "overlap_boundaries_m": [1400, 1800], "long_distance_min_m": 2500},
        }
        for horse in output.get("horses", []):
            horse_no = int(horse["basic"]["horse_no"])
            entry = self.entries.get((race_date, venue_code, race_no, horse_no))
            if entry is None:
                warnings.append(f"target_entry_not_found:horse_no={horse_no}")
                horse["older_runs"] = []
                horse["historical_profile"] = None
                horse["stats"] = {"sire": None, "jockey": None}
                horse["history_coverage"] = {"scope": "jrdb_jra_history", "observed_history": "unknown", "observed_starts": None, "overseas_history_coverage": "not_guaranteed", "reason": "target_entry_not_found", "run_layers": build_run_layers(horse, self.older_limit)}
                continue
            horse_id = str(entry["horse_id"]) if entry["horse_id"] else None
            recent = horse.get("recent_runs", [])
            cutoff = min((item.get("race", {}).get("date") for item in recent if item.get("race", {}).get("date")), default=race_date)
            older = [row for row in self.horse_rows.get(horse_id, []) if str(row[1]) < str(cutoff)][:self.older_limit] if horse_id else []
            horse["older_runs"] = [{"date": row[1], "venue": JRA_VENUES.get(str(row[3]), row[3]), "race_no": row[2], "surface": decode(TRACK_TYPE, row[4]), "distance_m": row[5], "track_condition": decode(TRACK_CONDITION, row[6]), "grade": decode(GRADE, row[7]), "running_style": row[8], "training_index": row[9], "finish": row[10], "abnormal_code": row[11], "final_win_odds": row[12], "final_popularity": row[13]} for row in older]
            if horse_id:
                profile = {
                    "source": "JRDB Analysis Lite", "source_window_start": self.window_start, "as_of_exclusive": race_date,
                    "career": self._horse_summary(horse_id, lambda *_: True),
                    "same_surface": self._horse_summary(horse_id, lambda surface, *_: surface == track_type),
                    "same_distance": self._horse_summary(horse_id, lambda _surface, _venue, row_distance, _year: row_distance == distance),
                    "distance_ranges": [],
                    "same_venue": self._horse_summary(horse_id, lambda _surface, venue, *_: venue == venue_code),
                }
                for definition in applicable_distance_ranges(distance):
                    minimum, maximum = int(definition["min_m"]), definition["max_m"]
                    item = dict(definition)
                    item.update(self._horse_summary(horse_id, lambda _surface, _venue, row_distance, _year, minimum=minimum, maximum=maximum: row_distance >= minimum and (maximum is None or row_distance <= int(maximum))))
                    profile["distance_ranges"].append(item)
                horse["historical_profile"] = profile
            else:
                horse["historical_profile"] = None
            horse["history_coverage"] = build_history_coverage(horse, horse.get("historical_profile"), self.older_limit)
            if horse["history_coverage"]["reason"] == "foreign_based_entry_no_jra_history":
                horse["historical_profile"] = None
            sire = entry["sire_name"]
            jockey = entry["jockey_name"] or horse["basic"].get("jockey")
            horse["stats"] = {"sire": self._stat("sire_name", sire, venue_code, track_type, distance, race_date) if sire else None, "jockey": self._stat("jockey_name", jockey, venue_code, track_type, distance, race_date) if jockey else None}
        frames = {}
        for frame_no in range(1, 9):
            stat = self._stat("frame_no", frame_no, venue_code, track_type, distance, race_date)
            if stat["starts"]:
                frames[str(frame_no)] = stat
        output["race"]["race_trends"] = {"frame": frames}
        return output, warnings


def enrich_many(bases: list[dict], analysis: object, mart: object, older_limit: int, years: int) -> list[tuple[dict, list[str]]]:
    """Enrich one request's bundles with shared DuckDB bulk scans."""
    if not bases:
        return []
    index = BulkEnrichmentIndex(analysis, bases, older_limit, years)
    return [index.enrich_one(base) for base in bases]


def metrics(value: dict) -> dict:
    """Measure formatted JSON character and UTF-8 byte size."""
    text = json.dumps(value, ensure_ascii=False, indent=2)
    return {"chars": len(text), "utf8_bytes": len(text.encode())}


def main() -> None:
    """Generate 8-run and 10-run enrichment variants."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--mart", help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", default="./racenote_history_poc")
    parser.add_argument("--stats-window-years", type=int, default=5)
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base = json.loads(bundle_path.read_text(encoding="utf-8"))
    base_metrics = metrics(base)

    analysis = sqlite3.connect(args.analysis)
    analysis.row_factory = sqlite3.Row

    variants: dict[str, dict] = {}
    try:
        for total_runs, older_limit in ((8, 3), (10, 5)):
            enriched, warnings = enrich(
                base,
                analysis,
                None,
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
