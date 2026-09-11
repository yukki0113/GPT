#!/usr/bin/env python3
"""Evaluate frozen Training Edge v0.2 on unseen-by-v0.2 2026 evidence.

The model design and calibration are frozen before this evaluator is used on 2026
outcomes. Training uses eligible 2013-2025 rows; 2026 is test-only. 2024-2025 are
ordinary prior training history here and are never described as unopened holdout.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_squared_error

from training_edge_v0_2_core import (
    A_NUMERIC,
    B_CATEGORICAL,
    B_NUMERIC,
    C_CATEGORICAL,
    C_NUMERIC,
    VERSION as CORE_VERSION,
    build_c_model,
    build_cab_model,
    load_calibration,
    rest_bucket,
    training_edge_direction,
    training_edge_percentile,
)

VERSION = "0.1.0"
HISTORY_FROM = 2010
TRAIN_FROM = 2013
TRAIN_TO = 2025
TEST_YEAR = 2026
MIN_PRIOR_RUNPERF = 3
MIN_PRIOR_COMPARABLE_WORKOUT = 3

SOURCE_COLUMNS = (
    "race_date",
    "year",
    "race_key",
    "horse_no",
    "horse_id",
    "trainer_code",
    "trainer_name",
    "days_since_last_run",
    "days_before_race",
    "workout_count",
    "course_code",
    "effort_code",
    "chase_state_code",
    "rider_type_code",
    "furlong_count",
    "final_segment_sec",
    "pair_result_code",
    "pair_effort_code",
    "pair_class_code",
    "jrdb_final_segment_index",
    "jrdb_workout_index_cha",
    "training_type_code",
    "training_course_type_code",
    "used_slope",
    "used_wood",
    "used_dirt",
    "used_turf",
    "used_pool",
    "used_jump",
    "used_polytrack",
    "training_distance_code",
    "training_focus_code",
    "training_volume_code",
    "week_ago_course_code",
    "finish_index",
    "kyi_training_score",
    "kyi_training_arrow_code",
    "official_runperf_raw",
    "runperf_score_status",
)


def _cat(value: object) -> str:
    if value is None or pd.isna(value):
        return "<MISSING>"
    text = str(value).strip()
    return text if text else "<MISSING>"


def _load_input(path: Path) -> pd.DataFrame:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        available = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(training_edge_input)")
        }
        missing = [column for column in SOURCE_COLUMNS if column not in available]
        if missing:
            raise ValueError(f"required v0.2 input columns are missing: {missing}")
        columns = ",".join(SOURCE_COLUMNS)
        frame = pd.read_sql_query(
            f"SELECT {columns} FROM training_edge_input "
            "WHERE year BETWEEN 2010 AND 2026 ORDER BY race_date,race_key,horse_no",
            connection,
        )
    finally:
        connection.close()

    if frame.empty:
        raise ValueError("v0.2 evaluation input is empty")
    years = sorted(int(value) for value in frame["year"].dropna().unique())
    if years[0] != HISTORY_FROM or years[-1] != TEST_YEAR:
        raise ValueError(f"input must span {HISTORY_FROM}..{TEST_YEAR}, got {years[0]}..{years[-1]}")
    return frame


def _materialize_time_aware(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.sort_values(["race_date", "race_key", "horse_no"], kind="stable").reset_index(drop=True)
    row_count = len(ordered)

    prior_run_count = np.zeros(row_count, dtype=np.int32)
    prior_run_median = np.full(row_count, np.nan, dtype=float)
    comparable_count = np.zeros(row_count, dtype=np.int32)
    final_self_pct = np.full(row_count, np.nan, dtype=float)
    previous_gap = np.full(row_count, np.nan, dtype=float)

    run_history: dict[str, list[float]] = defaultdict(list)
    workout_history: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    last_gap: dict[str, float] = {}

    race_dates = ordered["race_date"].to_numpy()
    horse_ids = ordered["horse_id"].to_numpy()
    course_codes = ordered["course_code"].to_numpy()
    furlongs = ordered["furlong_count"].to_numpy()
    final_times = ordered["final_segment_sec"].to_numpy()
    runperf_values = ordered["official_runperf_raw"].to_numpy()
    runperf_status = ordered["runperf_score_status"].to_numpy()
    current_gaps = ordered["days_since_last_run"].to_numpy()

    start = 0
    while start < row_count:
        end = start + 1
        target_date = race_dates[start]
        while end < row_count and race_dates[end] == target_date:
            end += 1

        # Snapshot the complete race date before adding any same-day information.
        for index in range(start, end):
            horse_id = _cat(horse_ids[index])
            if horse_id == "<MISSING>":
                continue

            values = run_history.get(horse_id)
            if values:
                prior_run_count[index] = len(values)
                prior_run_median[index] = float(statistics.median(values))

            if horse_id in last_gap:
                previous_gap[index] = last_gap[horse_id]

            final_time = final_times[index]
            course_code = course_codes[index]
            furlong = furlongs[index]
            if pd.isna(final_time) or pd.isna(course_code) or pd.isna(furlong):
                continue
            key = (horse_id, _cat(course_code), int(furlong))
            comparable = workout_history.get(key)
            if not comparable:
                continue
            current = float(final_time)
            lower = bisect.bisect_left(comparable, current)
            upper = bisect.bisect_right(comparable, current)
            comparable_count[index] = len(comparable)
            final_self_pct[index] = (
                len(comparable) - upper + 0.5 * (upper - lower)
            ) / len(comparable)

        for index in range(start, end):
            horse_id = _cat(horse_ids[index])
            if horse_id == "<MISSING>":
                continue

            value = runperf_values[index]
            if str(runperf_status[index]) == "OK" and pd.notna(value):
                bisect.insort(run_history[horse_id], float(value))

            gap = current_gaps[index]
            if pd.notna(gap):
                last_gap[horse_id] = float(gap)

            final_time = final_times[index]
            course_code = course_codes[index]
            furlong = furlongs[index]
            if pd.isna(final_time) or pd.isna(course_code) or pd.isna(furlong):
                continue
            key = (horse_id, _cat(course_code), int(furlong))
            bisect.insort(workout_history[key], float(final_time))
        start = end

    ordered["prior_runperf_count"] = prior_run_count
    ordered["prior_runperf_median"] = prior_run_median
    ordered["performance_delta"] = ordered["official_runperf_raw"] - ordered["prior_runperf_median"]
    ordered["prior_comparable_workout_count"] = comparable_count
    ordered["final_self_pct"] = final_self_pct
    ordered["previous_days_since_last_run"] = previous_gap
    return ordered


def _materialize_b(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["rest_bucket"] = work["days_since_last_run"].map(rest_bucket)
    work["previous_rest_bucket"] = work["previous_days_since_last_run"].map(rest_bucket)

    current_gap = pd.to_numeric(work["days_since_last_run"], errors="coerce")
    previous_gap = pd.to_numeric(work["previous_days_since_last_run"], errors="coerce")
    work["gap_log_change"] = np.log1p(current_gap) - np.log1p(previous_gap)
    work["return_after_63d_break"] = ((current_gap <= 35) & (previous_gap >= 63)).astype(float)
    work["return_after_120d_break"] = ((current_gap <= 35) & (previous_gap >= 120)).astype(float)

    pair_present = np.zeros(len(work), dtype=bool)
    for column in ("pair_result_code", "pair_effort_code", "pair_class_code"):
        pair_present = pair_present | (work[column].map(_cat) != "<MISSING>").to_numpy()
    work["pair_work_present"] = pair_present.astype(float)

    work["b_furlong_count"] = work["furlong_count"].map(_cat)
    work["course_x_rest"] = work["course_code"].map(_cat) + "|" + work["rest_bucket"].map(_cat)
    work["effort_x_rest"] = work["effort_code"].map(_cat) + "|" + work["rest_bucket"].map(_cat)
    work["training_type_x_rest"] = work["training_type_code"].map(_cat) + "|" + work["rest_bucket"].map(_cat)
    work["weekago_to_final_course"] = work["week_ago_course_code"].map(_cat) + "->" + work["course_code"].map(_cat)

    categorical = set(C_CATEGORICAL) | set(B_CATEGORICAL)
    for column in categorical:
        work[column] = work[column].map(_cat)
    return work


def _eligible(frame: pd.DataFrame, year_from: int, year_to: int) -> pd.DataFrame:
    mask = (
        frame["year"].between(year_from, year_to)
        & (frame["prior_runperf_count"] >= MIN_PRIOR_RUNPERF)
        & (frame["prior_comparable_workout_count"] >= MIN_PRIOR_COMPARABLE_WORKOUT)
        & frame["performance_delta"].notna()
        & frame["final_self_pct"].notna()
    )
    return frame.loc[mask].copy()


def _safe_spearman(left: np.ndarray, right: pd.Series | np.ndarray) -> float | None:
    value = spearmanr(np.asarray(left), np.asarray(right)).statistic
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def _decile_summary(values: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    work = pd.DataFrame({"score": values, "target": target})
    ranks = work["score"].rank(method="first")
    work["decile"] = pd.qcut(ranks, 10, labels=False, duplicates="drop") + 1
    rows: list[dict[str, Any]] = []
    for decile, group in work.groupby("decile", sort=True):
        rows.append(
            {
                "decile": int(decile),
                "n": int(len(group)),
                "mean_target": float(group["target"].mean()),
                "median_target": float(group["target"].median()),
                "positive_rate": float((group["target"] > 0).mean()),
            }
        )
    by_decile = {row["decile"]: row for row in rows}
    bottom = by_decile[1]
    top = by_decile[10]
    return {
        "deciles": rows,
        "top_minus_bottom": {
            "mean_target": float(top["mean_target"] - bottom["mean_target"]),
            "median_target": float(top["median_target"] - bottom["median_target"]),
            "positive_rate": float(top["positive_rate"] - bottom["positive_rate"]),
        },
    }


def evaluate(input_db: Path, calibration_path: Path) -> dict[str, Any]:
    frame = _load_input(input_db)
    frame = _materialize_time_aware(frame)
    frame = _materialize_b(frame)

    training = _eligible(frame, TRAIN_FROM, TRAIN_TO)
    test = _eligible(frame, TEST_YEAR, TEST_YEAR)
    if training.empty:
        raise ValueError("2013-2025 training population is empty")
    if test.empty:
        raise ValueError("2026 test population is empty")

    c_model = build_c_model()
    cab_model = build_cab_model()
    c_model.fit(training, training["performance_delta"])
    cab_model.fit(training, training["performance_delta"])

    c_prediction = np.asarray(c_model.predict(test), dtype=float)
    cab_prediction = np.asarray(cab_model.predict(test), dtype=float)
    edge_raw = cab_prediction - c_prediction
    target = test["performance_delta"].to_numpy(dtype=float)
    c_residual = target - c_prediction

    calibration = load_calibration(calibration_path)
    edge_percentile = np.asarray(
        [training_edge_percentile(value, calibration) for value in edge_raw], dtype=float
    )
    directions = [training_edge_direction(value) for value in edge_raw]

    c_spearman = _safe_spearman(c_prediction, target)
    cab_spearman = _safe_spearman(cab_prediction, target)
    edge_residual_spearman = _safe_spearman(edge_raw, c_residual)
    if c_spearman is None or cab_spearman is None or edge_residual_spearman is None:
        raise ValueError("undefined primary Spearman metric")

    result: dict[str, Any] = {
        "status": "success",
        "evaluator_version": VERSION,
        "core_version": CORE_VERSION,
        "protocol": "Training Edge v0.2 frozen unseen-by-v0.2 2026 OOT",
        "training_period": f"{TRAIN_FROM}-{TRAIN_TO}",
        "test_year": TEST_YEAR,
        "training_eligible_n": int(len(training)),
        "test_eligible_n": int(len(test)),
        "test_date_min": str(test["race_date"].min()),
        "test_date_max": str(test["race_date"].max()),
        "c": {
            "spearman": c_spearman,
            "rmse": float(mean_squared_error(target, c_prediction) ** 0.5),
            **_decile_summary(c_prediction, target),
        },
        "cab": {
            "spearman": cab_spearman,
            "rmse": float(mean_squared_error(target, cab_prediction) ** 0.5),
            **_decile_summary(cab_prediction, target),
        },
        "increment": {
            "cab_minus_c_spearman": float(cab_spearman - c_spearman),
            "cab_minus_c_rmse": float(
                (mean_squared_error(target, cab_prediction) ** 0.5)
                - (mean_squared_error(target, c_prediction) ** 0.5)
            ),
        },
        "edge": {
            "raw_vs_c_residual_spearman": edge_residual_spearman,
            "raw_vs_target_spearman": _safe_spearman(edge_raw, target),
            "raw_mean": float(np.mean(edge_raw)),
            "raw_sd": float(np.std(edge_raw, ddof=1)),
            "raw_zero_or_positive_rate": float(np.mean(edge_raw >= 0)),
            "direction_counts": {
                label: int(sum(direction == label for direction in directions))
                for label in ("negative", "neutral", "positive")
            },
            "residual_deciles": _decile_summary(edge_raw, c_residual),
            "percentile_deciles": _decile_summary(edge_percentile, c_residual),
        },
        "guard": {
            "fit_max_year": int(training["year"].max()),
            "test_min_year": int(test["year"].min()),
            "test_max_year": int(test["year"].max()),
            "test_rows_in_fit": 0,
            "v0_1_2024_2025_holdout_reused_as_unopened": False,
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-db", type=Path, required=True)
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "config"
        / "training_edge_v0_2_calibration.json",
    )
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.input_db, args.calibration)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
