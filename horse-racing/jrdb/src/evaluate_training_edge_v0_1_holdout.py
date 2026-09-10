#!/usr/bin/env python3
"""Evaluate the frozen Training Edge v0.1 on the one-shot 2024-2025 holdout.

The protocol is defined by docs/Training_Edge_v0_1_Freeze_20260911.md.
This evaluator intentionally exposes no tuning arguments for features, buckets,
history thresholds, preprocessing, Ridge alpha, or scoring direction.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

VERSION = "0.1.0"
FROZEN_ALPHA = 1.0
MIN_PRIOR_RUNPERF = 3
MIN_PRIOR_COMPARABLE_WORKOUT = 3
DEVELOPMENT_FROM = 2013
DEVELOPMENT_TO = 2023
HOLDOUT_FROM = 2024
HOLDOUT_TO = 2025

BASE_NUMERIC = (
    "kyi_training_score",
    "finish_index",
    "jrdb_final_segment_index",
    "jrdb_workout_index_cha",
)
BASE_CATEGORICAL = ("kyi_training_arrow_code",)
FULL_NUMERIC = BASE_NUMERIC + ("final_self_pct",)
FULL_CATEGORICAL = BASE_CATEGORICAL + ("rest_bucket",)

SOURCE_COLUMNS = (
    "race_date",
    "year",
    "race_key",
    "horse_no",
    "horse_id",
    "course_code",
    "furlong_count",
    "final_segment_sec",
    "official_runperf_raw",
    "kyi_training_score",
    "kyi_training_arrow_code",
    "finish_index",
    "jrdb_final_segment_index",
    "jrdb_workout_index_cha",
    "days_since_last_run",
)


def _load_table(db_path: Path, table: str) -> pd.DataFrame:
    """Load only the columns frozen for v0.1 evaluation."""
    connection = sqlite3.connect(db_path)
    try:
        columns = ",".join(SOURCE_COLUMNS)
        frame = pd.read_sql_query(
            f"SELECT {columns} FROM {table} ORDER BY race_date,race_key,horse_no",
            connection,
        )
    finally:
        connection.close()
    return frame


def _rest_bucket(value: object) -> str:
    """Map days since last run into the frozen context buckets."""
    if value is None:
        return "missing"
    try:
        if math.isnan(float(value)):
            return "missing"
    except (TypeError, ValueError):
        return "missing"
    days = float(value)
    if days <= 20:
        return "<=20"
    if days <= 34:
        return "21-34"
    if days <= 62:
        return "35-62"
    if days <= 119:
        return "63-119"
    return "120+"


def _materialize_time_aware_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build strictly-prior horse RunPerf baseline and comparable-workout percentile."""
    ordered = frame.sort_values(["race_date", "race_key", "horse_no"], kind="stable").reset_index(drop=True)
    row_count = len(ordered)

    prior_run_count = np.zeros(row_count, dtype=np.int32)
    prior_run_median = np.full(row_count, np.nan, dtype=float)
    comparable_count = np.zeros(row_count, dtype=np.int32)
    final_self_pct = np.full(row_count, np.nan, dtype=float)

    run_history: dict[str, list[float]] = defaultdict(list)
    workout_history: dict[tuple[str, str, int], list[float]] = defaultdict(list)

    race_dates = ordered["race_date"].to_numpy()
    horse_ids = ordered["horse_id"].to_numpy()
    course_codes = ordered["course_code"].to_numpy()
    furlongs = ordered["furlong_count"].to_numpy()
    final_times = ordered["final_segment_sec"].to_numpy()
    runperf_values = ordered["official_runperf_raw"].to_numpy()

    start = 0
    while start < row_count:
        end = start + 1
        target_date = race_dates[start]
        while end < row_count and race_dates[end] == target_date:
            end += 1

        # Snapshot every row before any same-day result/workout is added.
        for index in range(start, end):
            horse_id = horse_ids[index]
            run_values = run_history.get(horse_id)
            if run_values:
                prior_run_count[index] = len(run_values)
                size = len(run_values)
                if size % 2 == 1:
                    prior_run_median[index] = run_values[size // 2]
                else:
                    prior_run_median[index] = (
                        run_values[size // 2 - 1] + run_values[size // 2]
                    ) / 2.0

            final_time = final_times[index]
            course_code = course_codes[index]
            furlong_value = furlongs[index]
            if pd.isna(final_time) or course_code is None or pd.isna(furlong_value):
                continue
            key = (str(horse_id), str(course_code), int(furlong_value))
            comparable_values = workout_history.get(key)
            if not comparable_values:
                continue
            comparable_count[index] = len(comparable_values)
            current = float(final_time)
            lower = bisect.bisect_left(comparable_values, current)
            upper = bisect.bisect_right(comparable_values, current)
            greater_count = len(comparable_values) - upper
            tie_count = upper - lower
            final_self_pct[index] = (
                greater_count + 0.5 * tie_count
            ) / len(comparable_values)

        # Only after every row on the date has been snapshotted may the date enter history.
        for index in range(start, end):
            horse_id = str(horse_ids[index])
            runperf_value = runperf_values[index]
            if pd.notna(runperf_value):
                bisect.insort(run_history[horse_id], float(runperf_value))

            final_time = final_times[index]
            course_code = course_codes[index]
            furlong_value = furlongs[index]
            if pd.isna(final_time) or course_code is None or pd.isna(furlong_value):
                continue
            key = (horse_id, str(course_code), int(furlong_value))
            bisect.insort(workout_history[key], float(final_time))

        start = end

    ordered["prior_runperf_count"] = prior_run_count
    ordered["prior_runperf_median"] = prior_run_median
    ordered["performance_delta"] = (
        ordered["official_runperf_raw"] - ordered["prior_runperf_median"]
    )
    ordered["prior_comparable_workout_count"] = comparable_count
    ordered["final_self_pct"] = final_self_pct
    ordered["rest_bucket"] = ordered["days_since_last_run"].map(_rest_bucket)
    return ordered


def _build_model(full: bool) -> Pipeline:
    """Create the frozen processed-only or full Ridge pipeline."""
    numeric_columns = list(BASE_NUMERIC)
    categorical_columns = list(BASE_CATEGORICAL)
    if full:
        numeric_columns = list(FULL_NUMERIC)
        categorical_columns = list(FULL_CATEGORICAL)

    numeric_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessing = ColumnTransformer(
        [
            ("numeric", numeric_pipeline, numeric_columns),
            ("categorical", categorical_pipeline, categorical_columns),
        ]
    )
    return Pipeline(
        [
            ("preprocess", preprocessing),
            ("ridge", Ridge(alpha=FROZEN_ALPHA)),
        ]
    )


def _eligible(frame: pd.DataFrame, year_from: int, year_to: int) -> pd.DataFrame:
    """Apply the frozen history and label eligibility rules."""
    mask = (
        frame["year"].between(year_from, year_to)
        & (frame["prior_runperf_count"] >= MIN_PRIOR_RUNPERF)
        & (frame["prior_comparable_workout_count"] >= MIN_PRIOR_COMPARABLE_WORKOUT)
        & frame["performance_delta"].notna()
        & frame["final_self_pct"].notna()
    )
    return frame.loc[mask].copy()


def _safe_spearman(prediction: np.ndarray, target: pd.Series) -> float | None:
    """Return Spearman correlation when defined."""
    result = spearmanr(prediction, target.to_numpy()).statistic
    if result is None or not np.isfinite(result):
        return None
    return float(result)


def _model_metrics(frame: pd.DataFrame, prediction: np.ndarray) -> dict[str, object]:
    """Calculate frozen holdout metrics for one population."""
    target = frame["performance_delta"]
    return {
        "n": int(len(frame)),
        "spearman": _safe_spearman(prediction, target),
        "rmse": float(mean_squared_error(target, prediction) ** 0.5),
    }


def _decile_metrics(frame: pd.DataFrame, prediction: np.ndarray) -> dict[str, object]:
    """Calculate year-relative score deciles and frozen top-minus-bottom spreads."""
    work = frame[["year", "performance_delta"]].copy()
    work["prediction"] = prediction
    work["decile"] = 0

    for year, indexes in work.groupby("year", sort=True).groups.items():
        year_scores = work.loc[indexes, "prediction"]
        ranks = year_scores.rank(method="first")
        deciles = pd.qcut(ranks, 10, labels=False, duplicates="drop") + 1
        work.loc[indexes, "decile"] = deciles.astype(int)

    rows: list[dict[str, object]] = []
    for decile, group in work.groupby("decile", sort=True):
        rows.append(
            {
                "decile": int(decile),
                "n": int(len(group)),
                "mean_delta": float(group["performance_delta"].mean()),
                "median_delta": float(group["performance_delta"].median()),
                "positive_rate": float((group["performance_delta"] > 0).mean()),
            }
        )

    by_decile = {int(row["decile"]): row for row in rows}
    bottom = by_decile[1]
    top = by_decile[10]
    spread = {
        "mean_delta": float(top["mean_delta"] - bottom["mean_delta"]),
        "median_delta": float(top["median_delta"] - bottom["median_delta"]),
        "positive_rate": float(top["positive_rate"] - bottom["positive_rate"]),
    }
    return {
        "deciles": rows,
        "top10": top,
        "bottom10": bottom,
        "top_minus_bottom": spread,
    }


def evaluate(development_db: Path, holdout_db: Path) -> dict[str, object]:
    """Fit once on 2013-2023 and evaluate the frozen package on 2024-2025."""
    development = _load_table(development_db, "training_runner")
    holdout = _load_table(holdout_db, "training_holdout")

    if int(development["year"].max()) != DEVELOPMENT_TO:
        raise ValueError("development DB must end at 2023")
    holdout_years = sorted(int(value) for value in holdout["year"].dropna().unique())
    if holdout_years != [HOLDOUT_FROM, HOLDOUT_TO]:
        raise ValueError(f"holdout DB must contain exactly 2024 and 2025, got {holdout_years}")

    combined = pd.concat([development, holdout], ignore_index=True)
    combined = _materialize_time_aware_features(combined)
    training = _eligible(combined, DEVELOPMENT_FROM, DEVELOPMENT_TO)
    holdout_eligible = _eligible(combined, HOLDOUT_FROM, HOLDOUT_TO)

    if training.empty or holdout_eligible.empty:
        raise ValueError("eligible training or holdout population is empty")

    baseline_model = _build_model(full=False)
    full_model = _build_model(full=True)
    baseline_model.fit(training, training["performance_delta"])
    full_model.fit(training, training["performance_delta"])

    baseline_prediction = baseline_model.predict(holdout_eligible)
    full_prediction = full_model.predict(holdout_eligible)

    result: dict[str, Any] = {
        "status": "success",
        "evaluator_version": VERSION,
        "protocol": "Training Edge v0.1 pre-holdout freeze 2026-09-11",
        "ridge_alpha": FROZEN_ALPHA,
        "development_eligible_n": int(len(training)),
        "holdout_eligible_n": int(len(holdout_eligible)),
        "processed_only": {},
        "frozen_full": {},
    }

    for label, prediction in (
        ("processed_only", baseline_prediction),
        ("frozen_full", full_prediction),
    ):
        model_result: dict[str, Any] = {}
        for year in (HOLDOUT_FROM, HOLDOUT_TO):
            year_mask = holdout_eligible["year"] == year
            year_frame = holdout_eligible.loc[year_mask].copy()
            year_prediction = prediction[year_mask.to_numpy()]
            year_result = _model_metrics(year_frame, year_prediction)
            year_result.update(_decile_metrics(year_frame, year_prediction))
            model_result[str(year)] = year_result

        pooled_result = _model_metrics(holdout_eligible, prediction)
        pooled_result.update(_decile_metrics(holdout_eligible, prediction))
        model_result["pooled_2024_2025"] = pooled_result
        result[label] = model_result

    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-db", type=Path, required=True)
    parser.add_argument("--holdout-db", type=Path, required=True)
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.development_db, args.holdout_db)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
