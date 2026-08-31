#!/usr/bin/env python3
"""Build transparent time-aware RunPerf candidate features from JRDB Index Base.

The builder is deliberately model-light. It creates the historical inputs required to
compare B0/B1/T0-T3/JRDB benchmarks without fitting coefficients or using market data.
ExpectedTime is strictly past-only at race-date granularity; same-day results are added
to history only after every race on that date has received its baseline.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import heapq
import itertools
import json
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Iterable

VERSION = "0.1.0"
SCHEMA_VERSION = "0.1"
DEFAULT_METHODS = ("EXPANDING", "ROLLING_2Y", "ROLLING_3Y", "ROLLING_5Y")
ROLLING_YEARS = {
    "EXPANDING": None,
    "ROLLING_2Y": 2,
    "ROLLING_3Y": 3,
    "ROLLING_5Y": 5,
}
CONDITION_GROUP = {
    "A1": "0",
    "A2": "0",
    "A3": "0",
    "04": "1",
    "05": "1",
    "08": "2",
    "09": "2",
    "10": "2",
    "15": "3",
    "16": "3",
    "OP": "9",
}
NORMAL_ABNORMAL_CODES = {None, "", "0"}


class DualHeapMedian:
    """Median tracker supporting insertion and lazy deletion in O(log n)."""

    def __init__(self) -> None:
        self._small: list[float] = []
        self._large: list[float] = []
        self._delayed: collections.Counter[float] = collections.Counter()
        self._small_size = 0
        self._large_size = 0

    def __len__(self) -> int:
        return self._small_size + self._large_size

    def add(self, value: float) -> None:
        """Add one numeric observation."""
        if not self._small or value <= -self._small[0]:
            heapq.heappush(self._small, -value)
            self._small_size += 1
        else:
            heapq.heappush(self._large, value)
            self._large_size += 1
        self._rebalance()

    def remove(self, value: float) -> None:
        """Lazily remove one observation known to exist."""
        self._delayed[value] += 1
        if self._small and value <= -self._small[0]:
            self._small_size -= 1
            if value == -self._small[0]:
                self._prune_small()
        else:
            self._large_size -= 1
            if self._large and value == self._large[0]:
                self._prune_large()
        self._rebalance()

    def median(self) -> float | None:
        """Return the current median, or None when empty."""
        if len(self) == 0:
            return None
        self._prune_small()
        self._prune_large()
        if self._small_size > self._large_size:
            return -self._small[0]
        return (-self._small[0] + self._large[0]) / 2.0

    def _prune_small(self) -> None:
        while self._small:
            value = -self._small[0]
            if self._delayed[value] <= 0:
                break
            heapq.heappop(self._small)
            self._delayed[value] -= 1
            if self._delayed[value] == 0:
                del self._delayed[value]

    def _prune_large(self) -> None:
        while self._large:
            value = self._large[0]
            if self._delayed[value] <= 0:
                break
            heapq.heappop(self._large)
            self._delayed[value] -= 1
            if self._delayed[value] == 0:
                del self._delayed[value]

    def _rebalance(self) -> None:
        if self._small_size > self._large_size + 1:
            value = -heapq.heappop(self._small)
            heapq.heappush(self._large, value)
            self._small_size -= 1
            self._large_size += 1
            self._prune_small()
        elif self._small_size < self._large_size:
            value = heapq.heappop(self._large)
            heapq.heappush(self._small, -value)
            self._large_size -= 1
            self._small_size += 1
            self._prune_large()


class TimeAwareMedianSeries:
    """Chronological median series with an optional calendar-year window."""

    def __init__(self, window_years: int | None) -> None:
        self._window_years = window_years
        self._queue: collections.deque[tuple[dt.date, float]] = collections.deque()
        self._median = DualHeapMedian()

    def add(self, date_value: dt.date, value: float) -> None:
        """Append one chronological observation."""
        self._queue.append((date_value, value))
        self._median.add(value)

    def snapshot(self, target_date: dt.date) -> tuple[int, dt.date | None, float | None]:
        """Prune expired observations and return count, last date, and median."""
        self._prune(target_date)
        last_date = self._queue[-1][0] if self._queue else None
        return len(self._median), last_date, self._median.median()

    def _prune(self, target_date: dt.date) -> None:
        if self._window_years is None:
            return
        cutoff = _subtract_years(target_date, self._window_years)
        while self._queue and self._queue[0][0] < cutoff:
            _, value = self._queue.popleft()
            self._median.remove(value)


def _subtract_years(value: dt.date, years: int) -> dt.date:
    """Subtract calendar years while handling leap day deterministically."""
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _condition_group(code: str | None) -> str:
    if code is None or code == "":
        return "UNKNOWN"
    return CONDITION_GROUP.get(code, f"COND:{code}")


def _class_key(race_type_code: str | None, condition_code: str | None, grade_code: str | None) -> str:
    """Return the transparent v0 class key used only for class-time adjustment."""
    race_type = race_type_code or "-"
    condition = _condition_group(condition_code)
    grade = grade_code or "-"
    return f"TYPE:{race_type}|CONDGRP:{condition}|GRADE:{grade}"


def _is_normal_result(abnormal_code: str | None, finish: int | None, time_sec: float | None) -> bool:
    return (
        abnormal_code in NORMAL_ABNORMAL_CODES
        and finish is not None
        and finish > 0
        and time_sec is not None
        and time_sec > 0.0
    )


def _median(values: Iterable[float]) -> float | None:
    materialized = list(values)
    if not materialized:
        return None
    return float(statistics.median(materialized))


def _load_race_observations(source: sqlite3.Connection) -> list[dict[str, Any]]:
    """Create one post-race observation row per race from Index Base."""
    race_rows = source.execute(
        """
        SELECT race_key,race_date,year,venue_code,surface_code,distance_m,
               race_type_code,race_condition_code,grade_code,availability_class
        FROM race_context
        ORDER BY race_date,race_key
        """
    ).fetchall()
    observations: list[dict[str, Any]] = []
    for race in race_rows:
        result_rows = source.execute(
            """
            SELECT finish,abnormal_code,time_sec
            FROM runner_result
            WHERE race_key=?
            ORDER BY finish,horse_no
            """,
            (race["race_key"],),
        ).fetchall()
        valid = [row for row in result_rows if _is_normal_result(row["abnormal_code"], row["finish"], row["time_sec"])]
        valid.sort(key=lambda row: (int(row["finish"]), float(row["time_sec"])))
        valid_count = len(valid)
        winner_time = min((float(row["time_sec"]) for row in valid), default=None)
        representative_time = None
        if valid_count >= 3:
            representative_time = float(statistics.median(float(row["time_sec"]) for row in valid[:3]))

        status = "OK"
        if race["availability_class"] != "PRE_RACE":
            status = "EXCLUDED_FALLBACK_CONTEXT"
        elif race["race_type_code"] == "20":
            status = "EXCLUDED_OBSTACLE"
        elif race["surface_code"] is None or race["surface_code"] == "":
            status = "EXCLUDED_MISSING_SURFACE"
        elif race["distance_m"] is None or int(race["distance_m"]) <= 0:
            status = "EXCLUDED_INVALID_DISTANCE"
        elif representative_time is None:
            status = "EXCLUDED_LT3_VALID_FINISHERS"

        observations.append(
            {
                "race_key": race["race_key"],
                "race_date": race["race_date"],
                "date": _parse_date(race["race_date"]),
                "year": int(race["year"]),
                "venue_code": race["venue_code"],
                "surface_code": race["surface_code"],
                "distance_m": race["distance_m"],
                "race_type_code": race["race_type_code"],
                "race_condition_code": race["race_condition_code"],
                "condition_group_code": _condition_group(race["race_condition_code"]),
                "grade_code": race["grade_code"],
                "class_key_v0": _class_key(race["race_type_code"], race["race_condition_code"], race["grade_code"]),
                "race_context_availability": race["availability_class"],
                "valid_finisher_count": valid_count,
                "winner_time_sec": winner_time,
                "representative_time_sec": representative_time,
                "calculation_status": status,
            }
        )
    return observations


def _course_key(observation: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(observation["venue_code"]),
        str(observation["surface_code"]),
        int(observation["distance_m"]),
    )


def _group_by_date(observations: list[dict[str, Any]]) -> list[tuple[dt.date, list[dict[str, Any]]]]:
    grouped: list[tuple[dt.date, list[dict[str, Any]]]] = []
    for date_value, rows in itertools.groupby(observations, key=lambda item: item["date"]):
        grouped.append((date_value, list(rows)))
    return grouped


def _build_expected_for_method(
    observations: list[dict[str, Any]],
    method: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build past-only ExpectedTime and same-day post-result track-bias candidates."""
    window_years = ROLLING_YEARS[method]
    course_history: dict[tuple[str, str, int], TimeAwareMedianSeries] = {}
    class_history: dict[str, TimeAwareMedianSeries] = {}
    expected_rows: list[dict[str, Any]] = []
    day_bias_rows: list[dict[str, Any]] = []

    for race_date, day_rows in _group_by_date(observations):
        day_expected: list[dict[str, Any]] = []

        # Baselines for every race on the day are frozen before any same-day result is added.
        for observation in day_rows:
            if observation["calculation_status"] != "OK":
                row = {
                    "baseline_method": method,
                    "race_key": observation["race_key"],
                    "course_history_count": 0,
                    "course_history_last_date": None,
                    "course_base_time_sec": None,
                    "class_history_count": 0,
                    "class_history_last_date": None,
                    "class_adjustment_sec": None,
                    "expected_time_sec": None,
                    "race_bias_sec": None,
                    "calculation_status": observation["calculation_status"],
                }
                expected_rows.append(row)
                day_expected.append(row)
                continue

            course_key = _course_key(observation)
            course_series = course_history.setdefault(course_key, TimeAwareMedianSeries(window_years))
            class_series = class_history.setdefault(
                str(observation["class_key_v0"]), TimeAwareMedianSeries(window_years)
            )
            course_count, course_last_date, course_base = course_series.snapshot(race_date)
            class_count, class_last_date, class_adjustment = class_series.snapshot(race_date)

            expected_time = None
            race_bias = None
            status = "OK"
            if course_base is None:
                status = "MISSING_COURSE_HISTORY"
            elif class_adjustment is None:
                status = "MISSING_CLASS_HISTORY"
            else:
                expected_time = course_base + class_adjustment
                race_bias = float(observation["representative_time_sec"]) - expected_time

            row = {
                "baseline_method": method,
                "race_key": observation["race_key"],
                "course_history_count": course_count,
                "course_history_last_date": course_last_date.isoformat() if course_last_date else None,
                "course_base_time_sec": course_base,
                "class_history_count": class_count,
                "class_history_last_date": class_last_date.isoformat() if class_last_date else None,
                "class_adjustment_sec": class_adjustment,
                "expected_time_sec": expected_time,
                "race_bias_sec": race_bias,
                "calculation_status": status,
            }
            expected_rows.append(row)
            day_expected.append(row)

        # DayTrackBias is a historical-result feature: it is calculated only after all day baselines are frozen.
        bias_groups: dict[tuple[str, str], list[float]] = collections.defaultdict(list)
        observation_by_key = {str(item["race_key"]): item for item in day_rows}
        for row in day_expected:
            if row["race_bias_sec"] is None:
                continue
            observation = observation_by_key[str(row["race_key"])]
            group_key = (str(observation["venue_code"]), str(observation["surface_code"]))
            bias_groups[group_key].append(float(row["race_bias_sec"]))
        for (venue_code, surface_code), values in bias_groups.items():
            raw_bias = float(statistics.median(values))
            count = len(values)
            day_bias_rows.append(
                {
                    "baseline_method": method,
                    "race_date": race_date.isoformat(),
                    "venue_code": venue_code,
                    "surface_code": surface_code,
                    "race_bias_count": count,
                    "raw_median_bias_sec": raw_bias,
                    "shrink_k2_bias_sec": raw_bias * count / (count + 2.0),
                    "shrink_k4_bias_sec": raw_bias * count / (count + 4.0),
                    "shrink_k8_bias_sec": raw_bias * count / (count + 8.0),
                }
            )

        # Only now can the day's completed results enter histories for later dates.
        expected_by_key = {str(row["race_key"]): row for row in day_expected}
        for observation in day_rows:
            if observation["calculation_status"] != "OK":
                continue
            representative_time = observation["representative_time_sec"]
            if representative_time is None:
                continue
            course_key = _course_key(observation)
            course_series = course_history.setdefault(course_key, TimeAwareMedianSeries(window_years))
            expected_row = expected_by_key[str(observation["race_key"])]
            course_base = expected_row["course_base_time_sec"]
            if course_base is not None:
                residual = float(representative_time) - float(course_base)
                class_series = class_history.setdefault(
                    str(observation["class_key_v0"]), TimeAwareMedianSeries(window_years)
                )
                class_series.add(race_date, residual)
            course_series.add(race_date, float(representative_time))

    return expected_rows, day_bias_rows


def _insert_observations(connection: sqlite3.Connection, observations: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO race_runperf_observation(
          race_key,race_date,year,venue_code,surface_code,distance_m,race_type_code,
          race_condition_code,condition_group_code,grade_code,class_key_v0,
          race_context_availability,valid_finisher_count,winner_time_sec,
          representative_time_sec,calculation_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    rows = [
        (
            item["race_key"], item["race_date"], item["year"], item["venue_code"],
            item["surface_code"], item["distance_m"], item["race_type_code"],
            item["race_condition_code"], item["condition_group_code"], item["grade_code"],
            item["class_key_v0"], item["race_context_availability"], item["valid_finisher_count"],
            item["winner_time_sec"], item["representative_time_sec"], item["calculation_status"],
        )
        for item in observations
    ]
    connection.executemany(sql, rows)


def _insert_expected(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    connection.executemany(
        """
        INSERT INTO race_expected_time(
          baseline_method,race_key,course_history_count,course_history_last_date,
          course_base_time_sec,class_history_count,class_history_last_date,
          class_adjustment_sec,expected_time_sec,race_bias_sec,calculation_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                row["baseline_method"], row["race_key"], row["course_history_count"],
                row["course_history_last_date"], row["course_base_time_sec"],
                row["class_history_count"], row["class_history_last_date"],
                row["class_adjustment_sec"], row["expected_time_sec"], row["race_bias_sec"],
                row["calculation_status"],
            )
            for row in rows
        ],
    )


def _insert_day_bias(connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    connection.executemany(
        """
        INSERT INTO race_day_track_bias(
          baseline_method,race_date,venue_code,surface_code,race_bias_count,
          raw_median_bias_sec,shrink_k2_bias_sec,shrink_k4_bias_sec,shrink_k8_bias_sec
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [
            (
                row["baseline_method"], row["race_date"], row["venue_code"], row["surface_code"],
                row["race_bias_count"], row["raw_median_bias_sec"], row["shrink_k2_bias_sec"],
                row["shrink_k4_bias_sec"], row["shrink_k8_bias_sec"],
            )
            for row in rows
        ],
    )


def _race_weight_means(source: sqlite3.Connection) -> dict[str, float]:
    rows = source.execute(
        """
        SELECT race_key,AVG(carried_weight_kg) AS mean_weight
        FROM runner_pre
        WHERE carried_weight_kg IS NOT NULL AND carried_weight_kg>0
        GROUP BY race_key
        """
    ).fetchall()
    return {str(row["race_key"]): float(row["mean_weight"]) for row in rows if row["mean_weight"] is not None}


def _build_runner_features(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    observations: list[dict[str, Any]],
    methods: tuple[str, ...],
) -> int:
    """Stream runner results once and materialize candidate inputs for each baseline method."""
    observation_by_key = {str(item["race_key"]): item for item in observations}
    expected_lookup: dict[tuple[str, str], float | None] = {}
    for row in target.execute("SELECT baseline_method,race_key,expected_time_sec FROM race_expected_time"):
        expected_lookup[(str(row["baseline_method"]), str(row["race_key"]))] = row["expected_time_sec"]
    day_bias_lookup: dict[tuple[str, str, str, str], tuple[float, float, float, float]] = {}
    for row in target.execute(
        """
        SELECT baseline_method,race_date,venue_code,surface_code,raw_median_bias_sec,
               shrink_k2_bias_sec,shrink_k4_bias_sec,shrink_k8_bias_sec
        FROM race_day_track_bias
        """
    ):
        key = (
            str(row["baseline_method"]), str(row["race_date"]),
            str(row["venue_code"]), str(row["surface_code"]),
        )
        day_bias_lookup[key] = (
            float(row["raw_median_bias_sec"]), float(row["shrink_k2_bias_sec"]),
            float(row["shrink_k4_bias_sec"]), float(row["shrink_k8_bias_sec"]),
        )
    weight_means = _race_weight_means(source)

    insert_sql = """
        INSERT INTO runner_runperf_features(
          baseline_method,race_key,horse_no,horse_id,finish,abnormal_code,actual_time_sec,
          valid_finisher_count,winner_time_sec,margin_sec,margin_per_1000m_sec,
          finish_percentile,carried_weight_kg,race_mean_carried_weight_kg,weight_relative_kg,
          expected_time_sec,day_bias_raw_sec,day_bias_k2_sec,day_bias_k4_sec,day_bias_k8_sec,
          time_residual_no_bias_sec,time_residual_raw_bias_sec,time_residual_k2_bias_sec,
          time_residual_k4_bias_sec,time_residual_k8_bias_sec,jrdb_raw_score,jrdb_idm,
          calculation_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    source_rows = source.execute(
        """
        SELECT x.race_key,x.horse_no,x.horse_id,x.finish,x.abnormal_code,x.time_sec,
               x.raw_score,x.idm,p.carried_weight_kg
        FROM runner_result x
        LEFT JOIN runner_pre p ON p.race_key=x.race_key AND p.horse_no=x.horse_no
        ORDER BY x.race_key,x.horse_no
        """
    )
    batch: list[tuple[Any, ...]] = []
    inserted = 0
    for row in source_rows:
        race_key = str(row["race_key"])
        observation = observation_by_key.get(race_key)
        if observation is None:
            continue
        normal = _is_normal_result(row["abnormal_code"], row["finish"], row["time_sec"])
        valid_count = int(observation["valid_finisher_count"])
        actual_time = float(row["time_sec"]) if row["time_sec"] is not None else None
        winner_time = observation["winner_time_sec"]
        distance_m = observation["distance_m"]
        margin = None
        margin_per_1000m = None
        finish_percentile = None
        if normal and actual_time is not None and winner_time is not None:
            margin = max(0.0, actual_time - float(winner_time))
            if distance_m is not None and int(distance_m) > 0:
                margin_per_1000m = margin * 1000.0 / int(distance_m)
            if valid_count <= 1:
                finish_percentile = 1.0
            elif row["finish"] is not None:
                finish_percentile = max(0.0, min(1.0, (valid_count - int(row["finish"])) / (valid_count - 1.0)))

        carried_weight = float(row["carried_weight_kg"]) if row["carried_weight_kg"] is not None else None
        mean_weight = weight_means.get(race_key)
        weight_relative = None
        if carried_weight is not None and mean_weight is not None:
            weight_relative = carried_weight - mean_weight

        for method in methods:
            expected_time = expected_lookup.get((method, race_key))
            bias_key = (
                method,
                str(observation["race_date"]),
                str(observation["venue_code"]),
                str(observation["surface_code"]),
            )
            bias_values = day_bias_lookup.get(bias_key)
            raw_bias = bias_values[0] if bias_values else None
            k2_bias = bias_values[1] if bias_values else None
            k4_bias = bias_values[2] if bias_values else None
            k8_bias = bias_values[3] if bias_values else None

            residual_no_bias = None
            residual_raw = None
            residual_k2 = None
            residual_k4 = None
            residual_k8 = None
            status = "OK"
            if not normal:
                if row["abnormal_code"] not in NORMAL_ABNORMAL_CODES:
                    status = "EXCLUDED_ABNORMAL"
                else:
                    status = "EXCLUDED_NO_VALID_TIME_OR_FINISH"
            elif observation["calculation_status"] != "OK":
                status = str(observation["calculation_status"])
            elif expected_time is None:
                status = "MISSING_EXPECTED_TIME"
            elif actual_time is None:
                status = "EXCLUDED_NO_VALID_TIME_OR_FINISH"
            else:
                residual_no_bias = float(expected_time) - actual_time
                if raw_bias is not None:
                    residual_raw = float(expected_time) - (actual_time - raw_bias)
                    residual_k2 = float(expected_time) - (actual_time - float(k2_bias))
                    residual_k4 = float(expected_time) - (actual_time - float(k4_bias))
                    residual_k8 = float(expected_time) - (actual_time - float(k8_bias))

            batch.append(
                (
                    method, race_key, int(row["horse_no"]), row["horse_id"], row["finish"],
                    row["abnormal_code"], actual_time, valid_count, winner_time, margin,
                    margin_per_1000m, finish_percentile, carried_weight, mean_weight, weight_relative,
                    expected_time, raw_bias, k2_bias, k4_bias, k8_bias, residual_no_bias,
                    residual_raw, residual_k2, residual_k4, residual_k8, row["raw_score"], row["idm"], status,
                )
            )
            inserted += 1
            if len(batch) >= 10000:
                target.executemany(insert_sql, batch)
                batch.clear()
    if batch:
        target.executemany(insert_sql, batch)
    return inserted


def build(index_db: Path, output_db: Path, schema_path: Path, methods: tuple[str, ...]) -> dict[str, Any]:
    """Build one RunPerf feature SQLite and return compact build metadata."""
    unknown = [method for method in methods if method not in ROLLING_YEARS]
    if unknown:
        raise ValueError(f"Unknown baseline methods: {unknown}")
    if output_db.exists():
        output_db.unlink()

    started_at = dt.datetime.now().isoformat(timespec="seconds")
    source = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    target = sqlite3.connect(output_db)
    target.row_factory = sqlite3.Row
    try:
        target.executescript(schema_path.read_text(encoding="utf-8"))
        target.execute(
            """
            INSERT INTO meta_runperf_build(
              build_id,builder_version,schema_version,source_index_db_path,source_index_db_sha256,
              started_at,status,methods_json
            ) VALUES (1,?,?,?,?,?,?,?)
            """,
            (
                VERSION, SCHEMA_VERSION, str(index_db), _sha256(index_db), started_at,
                "RUNNING", json.dumps(methods),
            ),
        )
        observations = _load_race_observations(source)
        _insert_observations(target, observations)

        expected_count = 0
        day_bias_count = 0
        for method in methods:
            expected_rows, day_bias_rows = _build_expected_for_method(observations, method)
            _insert_expected(target, expected_rows)
            _insert_day_bias(target, day_bias_rows)
            expected_count += len(expected_rows)
            day_bias_count += len(day_bias_rows)
            target.commit()

        runner_count = _build_runner_features(source, target, observations, methods)
        finished_at = dt.datetime.now().isoformat(timespec="seconds")
        target.execute(
            """
            UPDATE meta_runperf_build
            SET finished_at=?,status='SUCCESS',race_observation_count=?,expected_time_count=?,
                day_bias_count=?,runner_feature_count=?,message=?
            WHERE build_id=1
            """,
            (
                finished_at, len(observations), expected_count, day_bias_count, runner_count,
                "RunPerf candidate inputs built without fitting coefficients or market data.",
            ),
        )
        target.commit()
        return {
            "status": "SUCCESS",
            "builder_version": VERSION,
            "methods": list(methods),
            "race_observation_count": len(observations),
            "expected_time_count": expected_count,
            "day_bias_count": day_bias_count,
            "runner_feature_count": runner_count,
        }
    except Exception as exc:
        target.rollback()
        try:
            target.execute(
                "UPDATE meta_runperf_build SET status='FAILED',finished_at=?,message=? WHERE build_id=1",
                (dt.datetime.now().isoformat(timespec="seconds"), str(exc)),
            )
            target.commit()
        except sqlite3.Error:
            pass
        raise
    finally:
        source.close()
        target.close()


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schema" / "jrdb_runperf_schema_v0_1.sql"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=_default_schema_path())
    parser.add_argument(
        "--methods",
        default=",".join(DEFAULT_METHODS),
        help="Comma-separated: EXPANDING,ROLLING_2Y,ROLLING_3Y,ROLLING_5Y",
    )
    args = parser.parse_args()
    methods = tuple(item.strip().upper() for item in args.methods.split(",") if item.strip())
    report = build(args.index_db, args.out, args.schema, methods)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
