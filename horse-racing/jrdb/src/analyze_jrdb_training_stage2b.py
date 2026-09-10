#!/usr/bin/env python3
"""Stage 2b: formal stable/rotation/training-pattern validation.

The protocol is frozen in docs/Training_Pattern_Stage2b_Protocol_20260911.md.
This program reads development data through 2023 only. 2024-2025 is not selected.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
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
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

VERSION = "0.1.0"
RIDGE_ALPHA = 1.0
SHRINKAGE_LAMBDA = 50.0
MIN_PRIOR_RUNPERF = 3
MIN_PRIOR_COMPARABLE_WORKOUT = 3
TEST_YEARS = tuple(range(2018, 2024))
TRAIN_FROM = 2013
MAX_YEAR = 2023
MATERIAL_REVERSAL = -0.0025

M0_NUMERIC = (
    "kyi_training_score",
    "finish_index",
    "jrdb_final_segment_index",
    "jrdb_workout_index_cha",
    "final_self_pct",
)
M0_CATEGORICAL = (
    "kyi_training_arrow_code",
    "rest_bucket",
)

B_NUMERIC = (
    "days_before_race",
    "workout_count",
    "previous_days_since_last_run",
    "gap_log_change",
    "return_after_63d_break",
    "return_after_120d_break",
    "pair_work_present",
    "used_slope",
    "used_wood",
    "used_dirt",
    "used_turf",
    "used_pool",
    "used_jump",
    "used_polytrack",
)
B_CATEGORICAL = (
    "previous_rest_bucket",
    "course_code",
    "effort_code",
    "chase_state_code",
    "rider_type_code",
    "b_furlong_count",
    "pair_result_code",
    "pair_effort_code",
    "pair_class_code",
    "training_type_code",
    "training_course_type_code",
    "training_distance_code",
    "training_focus_code",
    "training_volume_code",
    "week_ago_course_code",
    "course_x_rest",
    "effort_x_rest",
    "training_type_x_rest",
    "weekago_to_final_course",
)

PATTERN_FAMILIES: dict[str, tuple[str, ...]] = {
    "trainer_course": ("course_code",),
    "trainer_effort": ("effort_code",),
    "trainer_training_type": ("training_type_code",),
    "trainer_training_course_type": ("training_course_type_code",),
    "trainer_rest": ("rest_bucket",),
    "trainer_course_rest": ("course_code", "rest_bucket"),
    "trainer_effort_rest": ("effort_code", "rest_bucket"),
    "trainer_training_type_rest": ("training_type_code", "rest_bucket"),
    "trainer_training_volume": ("training_volume_code",),
    "trainer_weekago_to_final": ("weekago_to_final_course",),
}
PATTERN_COLUMNS = tuple(f"pattern_{name}" for name in PATTERN_FAMILIES)

INTERACTION_BASE = (
    "return_after_63d_break",
    "return_after_120d_break",
    "used_polytrack",
    "used_slope",
    "used_wood",
)
INTERACTION_COLUMNS = tuple(f"self_x_{name}" for name in INTERACTION_BASE) + tuple(
    f"self_x_pattern_{name}" for name in PATTERN_FAMILIES
)

REQUIRED_SOURCE_COLUMNS = (
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
    "jrdb_workout_index_cha",
    "jrdb_final_segment_index",
    "finish_index",
    "kyi_training_score",
    "kyi_training_arrow_code",
    "official_runperf_raw",
)

MODEL_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "M0": (M0_NUMERIC, M0_CATEGORICAL),
    "M1": (M0_NUMERIC + B_NUMERIC, M0_CATEGORICAL + B_CATEGORICAL),
    "M2": (M0_NUMERIC + PATTERN_COLUMNS, M0_CATEGORICAL),
    "M3": (M0_NUMERIC + B_NUMERIC + PATTERN_COLUMNS, M0_CATEGORICAL + B_CATEGORICAL),
    "M4": (
        M0_NUMERIC + B_NUMERIC + PATTERN_COLUMNS + INTERACTION_COLUMNS,
        M0_CATEGORICAL + B_CATEGORICAL,
    ),
}


def _rest_bucket(value: object) -> str:
    """Map a race gap to the fixed Training Edge v0.1 rest buckets."""
    if value is None or pd.isna(value):
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


def _cat(value: object) -> str:
    """Create a stable categorical representation including missing values."""
    if value is None or pd.isna(value):
        return "<MISSING>"
    text = str(value).strip()
    if not text:
        return "<MISSING>"
    return text


def _load_source(db_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load the Stage 2b source while hard-stopping at development year 2023."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        table_info = connection.execute("PRAGMA table_info(training_runner)").fetchall()
        available = {str(row[1]) for row in table_info}
        missing = [name for name in REQUIRED_SOURCE_COLUMNS if name not in available]
        if missing:
            raise RuntimeError(f"required Training Research columns are missing: {missing}")

        columns = ",".join(REQUIRED_SOURCE_COLUMNS)
        frame = pd.read_sql_query(
            f"SELECT {columns} FROM training_runner WHERE year BETWEEN 2010 AND 2023 "
            "ORDER BY race_date,race_key,horse_no",
            connection,
        )
        source_total = int(connection.execute("SELECT COUNT(*) FROM training_runner").fetchone()[0])
        source_max = int(connection.execute("SELECT MAX(year) FROM training_runner").fetchone()[0])
    finally:
        connection.close()

    if frame.empty:
        raise RuntimeError("development source is empty")
    selected_max = int(frame["year"].max())
    if selected_max > MAX_YEAR:
        raise RuntimeError("holdout guard failed: selected rows exceed 2023")

    audit = {
        "source_table_rows": source_total,
        "source_max_year": source_max,
        "selected_rows": int(len(frame)),
        "selected_min_year": int(frame["year"].min()),
        "selected_max_year": selected_max,
        "available_columns": sorted(available),
        "missing_required_columns": missing,
        "holdout_rows_selected": int((frame["year"] >= 2024).sum()),
    }
    return frame, audit


def _materialize_time_aware(frame: pd.DataFrame) -> pd.DataFrame:
    """Build strictly-prior horse baselines, workout verticals and gap history."""
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
    current_gaps = ordered["days_since_last_run"].to_numpy()

    start = 0
    while start < row_count:
        end = start + 1
        target_date = race_dates[start]
        while end < row_count and race_dates[end] == target_date:
            end += 1

        # Snapshot all rows before the date is allowed into history.
        for index in range(start, end):
            horse_id = _cat(horse_ids[index])
            if horse_id == "<MISSING>":
                continue

            run_values = run_history.get(horse_id)
            if run_values:
                prior_run_count[index] = len(run_values)
                prior_run_median[index] = float(statistics.median(run_values))

            if horse_id in last_gap:
                previous_gap[index] = last_gap[horse_id]

            final_time = final_times[index]
            course_code = course_codes[index]
            furlong_value = furlongs[index]
            if pd.isna(final_time) or pd.isna(course_code) or pd.isna(furlong_value):
                continue
            key = (horse_id, _cat(course_code), int(furlong_value))
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

        # Update history only after every row on this date has been snapshotted.
        for index in range(start, end):
            horse_id = _cat(horse_ids[index])
            if horse_id == "<MISSING>":
                continue

            runperf_value = runperf_values[index]
            if pd.notna(runperf_value):
                bisect.insort(run_history[horse_id], float(runperf_value))

            current_gap = current_gaps[index]
            if pd.notna(current_gap):
                last_gap[horse_id] = float(current_gap)

            final_time = final_times[index]
            course_code = course_codes[index]
            furlong_value = furlongs[index]
            if pd.isna(final_time) or pd.isna(course_code) or pd.isna(furlong_value):
                continue
            key = (horse_id, _cat(course_code), int(furlong_value))
            bisect.insort(workout_history[key], float(final_time))

        start = end

    ordered["prior_runperf_count"] = prior_run_count
    ordered["prior_runperf_median"] = prior_run_median
    ordered["performance_delta"] = ordered["official_runperf_raw"] - ordered["prior_runperf_median"]
    ordered["prior_comparable_workout_count"] = comparable_count
    ordered["final_self_pct"] = final_self_pct
    ordered["previous_days_since_last_run"] = previous_gap
    return ordered


def _materialize_generic_b(frame: pd.DataFrame) -> pd.DataFrame:
    """Build the predeclared generic rotation and training-process features."""
    work = frame.copy()
    work["rest_bucket"] = work["days_since_last_run"].map(_rest_bucket)
    work["previous_rest_bucket"] = work["previous_days_since_last_run"].map(_rest_bucket)

    current_gap = pd.to_numeric(work["days_since_last_run"], errors="coerce")
    previous_gap = pd.to_numeric(work["previous_days_since_last_run"], errors="coerce")
    work["gap_log_change"] = np.log1p(current_gap) - np.log1p(previous_gap)
    work["return_after_63d_break"] = ((current_gap <= 35) & (previous_gap >= 63)).astype(float)
    work["return_after_120d_break"] = ((current_gap <= 35) & (previous_gap >= 120)).astype(float)

    pair_columns = ["pair_result_code", "pair_effort_code", "pair_class_code"]
    pair_present = np.zeros(len(work), dtype=bool)
    for column in pair_columns:
        values = work[column].map(_cat)
        pair_present = pair_present | (values != "<MISSING>").to_numpy()
    work["pair_work_present"] = pair_present.astype(float)

    work["b_furlong_count"] = work["furlong_count"].map(_cat)
    work["course_x_rest"] = work["course_code"].map(_cat) + "|" + work["rest_bucket"].map(_cat)
    work["effort_x_rest"] = work["effort_code"].map(_cat) + "|" + work["rest_bucket"].map(_cat)
    work["training_type_x_rest"] = work["training_type_code"].map(_cat) + "|" + work["rest_bucket"].map(_cat)
    work["weekago_to_final_course"] = work["week_ago_course_code"].map(_cat) + "->" + work["course_code"].map(_cat)

    categorical = set(M0_CATEGORICAL) | set(B_CATEGORICAL)
    categorical.add("trainer_code")
    categorical.add("trainer_name")
    for dimensions in PATTERN_FAMILIES.values():
        for column in dimensions:
            categorical.add(column)
    for column in categorical:
        if column in work.columns:
            work[column] = work[column].map(_cat)

    return work


def _eligible_mask(frame: pd.DataFrame) -> pd.Series:
    """Return the frozen A/v0.1 eligibility mask, independent of calendar split."""
    return (
        (frame["prior_runperf_count"] >= MIN_PRIOR_RUNPERF)
        & (frame["prior_comparable_workout_count"] >= MIN_PRIOR_COMPARABLE_WORKOUT)
        & frame["performance_delta"].notna()
        & frame["final_self_pct"].notna()
    )


def _pattern_key(row: pd.Series, dimensions: tuple[str, ...]) -> tuple[str, ...]:
    """Build one trainer-pattern key from normalized categorical values."""
    values = [_cat(row["trainer_code"])]
    for dimension in dimensions:
        values.append(_cat(row[dimension]))
    return tuple(values)


def _build_pattern_mapping(history: pd.DataFrame, dimensions: tuple[str, ...]) -> dict[tuple[str, ...], float]:
    """Estimate trainer-relative pattern effects with fixed lambda=50 shrinkage."""
    if history.empty:
        return {}

    trainer_stats = history.groupby("trainer_code", dropna=False)["performance_delta"].agg(["mean", "count"])
    group_columns = ["trainer_code"] + list(dimensions)
    group_stats = history.groupby(group_columns, dropna=False)["performance_delta"].agg(["mean", "count"]).reset_index()

    mapping: dict[tuple[str, ...], float] = {}
    for _, row in group_stats.iterrows():
        trainer = _cat(row["trainer_code"])
        if trainer not in trainer_stats.index:
            continue
        trainer_mean = float(trainer_stats.loc[trainer, "mean"])
        group_mean = float(row["mean"])
        count = float(row["count"])
        weight = count / (count + SHRINKAGE_LAMBDA)
        key_values = [trainer]
        for dimension in dimensions:
            key_values.append(_cat(row[dimension]))
        mapping[tuple(key_values)] = weight * (group_mean - trainer_mean)
    return mapping


def _materialize_pattern_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Encode each calendar year using outcomes from strictly earlier years only."""
    work = frame.copy()
    for column in PATTERN_COLUMNS:
        work[column] = 0.0

    eligible_history = work.loc[_eligible_mask(work)].copy()
    for target_year in range(TRAIN_FROM, MAX_YEAR + 1):
        target_indexes = work.index[work["year"] == target_year]
        if len(target_indexes) == 0:
            continue
        history = eligible_history.loc[eligible_history["year"] < target_year]

        for family, dimensions in PATTERN_FAMILIES.items():
            mapping = _build_pattern_mapping(history, dimensions)
            output_column = f"pattern_{family}"
            encoded: list[float] = []
            for index in target_indexes:
                row = work.loc[index]
                key = _pattern_key(row, dimensions)
                encoded.append(float(mapping.get(key, 0.0)))
            work.loc[target_indexes, output_column] = encoded

    return work


def _materialize_interactions(frame: pd.DataFrame) -> pd.DataFrame:
    """Build the predeclared A x B numeric interactions."""
    work = frame.copy()
    self_value = pd.to_numeric(work["final_self_pct"], errors="coerce")
    for source in INTERACTION_BASE:
        numeric = pd.to_numeric(work[source], errors="coerce")
        work[f"self_x_{source}"] = self_value * numeric
    for family in PATTERN_FAMILIES:
        source = f"pattern_{family}"
        work[f"self_x_pattern_{family}"] = self_value * pd.to_numeric(work[source], errors="coerce")
    return work


def _build_model(numeric_columns: tuple[str, ...], categorical_columns: tuple[str, ...]) -> Pipeline:
    """Create one fixed Ridge pipeline for a predeclared Stage 2b model family."""
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
            ("numeric", numeric_pipeline, list(numeric_columns)),
            ("categorical", categorical_pipeline, list(categorical_columns)),
        ]
    )
    return Pipeline(
        [
            ("preprocess", preprocessing),
            ("ridge", Ridge(alpha=RIDGE_ALPHA)),
        ]
    )


def _safe_spearman(prediction: np.ndarray, target: pd.Series) -> float | None:
    """Return Spearman rank correlation when finite."""
    statistic = spearmanr(prediction, target.to_numpy()).statistic
    if statistic is None or not np.isfinite(statistic):
        return None
    return float(statistic)


def _metric_block(frame: pd.DataFrame, prediction: np.ndarray) -> dict[str, Any]:
    """Calculate rank, RMSE and year-relative decile diagnostics."""
    target = frame["performance_delta"]
    work = frame[["year", "performance_delta"]].copy()
    work["prediction"] = prediction
    work["decile"] = 0

    for _, indexes in work.groupby("year", sort=True).groups.items():
        year_scores = work.loc[indexes, "prediction"]
        ranks = year_scores.rank(method="first")
        deciles = pd.qcut(ranks, 10, labels=False, duplicates="drop") + 1
        work.loc[indexes, "decile"] = deciles.astype(int)

    decile_rows: list[dict[str, Any]] = []
    for decile, group in work.groupby("decile", sort=True):
        decile_rows.append(
            {
                "decile": int(decile),
                "n": int(len(group)),
                "mean_delta": float(group["performance_delta"].mean()),
                "median_delta": float(group["performance_delta"].median()),
                "positive_rate": float((group["performance_delta"] > 0).mean()),
            }
        )

    by_decile = {int(row["decile"]): row for row in decile_rows}
    bottom = by_decile[1]
    top = by_decile[10]
    spread = {
        "mean_delta": float(top["mean_delta"] - bottom["mean_delta"]),
        "median_delta": float(top["median_delta"] - bottom["median_delta"]),
        "positive_rate": float(top["positive_rate"] - bottom["positive_rate"]),
    }
    return {
        "n": int(len(frame)),
        "spearman": _safe_spearman(prediction, target),
        "rmse": float(mean_squared_error(target, prediction) ** 0.5),
        "deciles": decile_rows,
        "top10": top,
        "bottom10": bottom,
        "top_minus_bottom": spread,
    }


def _evaluate_models(frame: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """Run annual 2018-2023 walk-forward for M0-M4 and retain OOT predictions."""
    eligible = frame.loc[_eligible_mask(frame) & frame["year"].between(TRAIN_FROM, MAX_YEAR)].copy()
    prediction_rows: list[pd.DataFrame] = []
    yearly: dict[str, dict[str, Any]] = {name: {} for name in MODEL_SPECS}

    for test_year in TEST_YEARS:
        training = eligible.loc[eligible["year"].between(TRAIN_FROM, test_year - 1)].copy()
        testing = eligible.loc[eligible["year"] == test_year].copy()
        if training.empty or testing.empty:
            raise RuntimeError(f"empty fold for {test_year}")

        fold_predictions = testing[["year", "race_key", "horse_no", "performance_delta"]].copy()
        for model_name, spec in MODEL_SPECS.items():
            numeric_columns, categorical_columns = spec
            model = _build_model(numeric_columns, categorical_columns)
            model.fit(training, training["performance_delta"])
            prediction = model.predict(testing)
            yearly[model_name][str(test_year)] = _metric_block(testing, prediction)
            fold_predictions[model_name] = prediction
        prediction_rows.append(fold_predictions)

    pooled_predictions = pd.concat(prediction_rows, ignore_index=True)
    pooled: dict[str, Any] = {}
    pooled_frame = pooled_predictions[["year", "performance_delta"]].copy()
    for model_name in MODEL_SPECS:
        pooled[model_name] = _metric_block(pooled_frame, pooled_predictions[model_name].to_numpy())
    return {"yearly": yearly, "pooled": pooled}, pooled_predictions


def _classify_models(metrics: dict[str, Any]) -> dict[str, Any]:
    """Apply the predeclared Stage 2b incremental decision rule against M0."""
    baseline_yearly = metrics["yearly"]["M0"]
    baseline_pooled = metrics["pooled"]["M0"]
    result: dict[str, Any] = {}

    for model_name in ("M1", "M2", "M3", "M4"):
        yearly_increments: dict[str, float] = {}
        positive_years = 0
        material_reversal_years = 0
        for year in TEST_YEARS:
            key = str(year)
            increment = float(metrics["yearly"][model_name][key]["spearman"] - baseline_yearly[key]["spearman"])
            yearly_increments[key] = increment
            if increment > 0:
                positive_years += 1
            if increment <= MATERIAL_REVERSAL:
                material_reversal_years += 1

        pooled_increment = float(metrics["pooled"][model_name]["spearman"] - baseline_pooled["spearman"])
        rmse_change = float(metrics["pooled"][model_name]["rmse"] - baseline_pooled["rmse"])
        spread_change = float(
            metrics["pooled"][model_name]["top_minus_bottom"]["mean_delta"]
            - baseline_pooled["top_minus_bottom"]["mean_delta"]
        )

        core = True
        if pooled_increment <= 0.0025:
            core = False
        if positive_years < 4:
            core = False
        if material_reversal_years >= 2:
            core = False
        if spread_change < 0:
            core = False
        if rmse_change > 0.0005:
            core = False

        if core:
            classification = "B_CORE_CANDIDATE"
        else:
            coherent = pooled_increment > 0 and positive_years >= 3
            if coherent:
                classification = "B_AUXILIARY_ONLY"
            else:
                classification = "B_EXCLUDE_FROM_INDEX"

        result[model_name] = {
            "classification": classification,
            "pooled_spearman_increment_vs_M0": pooled_increment,
            "positive_spearman_years": positive_years,
            "material_reversal_years": material_reversal_years,
            "material_reversal_threshold": MATERIAL_REVERSAL,
            "pooled_rmse_change_vs_M0": rmse_change,
            "pooled_top_bottom_mean_spread_change_vs_M0": spread_change,
            "yearly_spearman_increment_vs_M0": yearly_increments,
        }
    return result


def _period_pattern_stats(frame: pd.DataFrame, dimensions: tuple[str, ...], year_from: int, year_to: int) -> pd.DataFrame:
    """Return trainer-relative pattern summaries for an interpretability period."""
    period = frame.loc[
        _eligible_mask(frame)
        & frame["year"].between(year_from, year_to)
        & (frame["trainer_code"] != "<MISSING>")
    ].copy()
    if period.empty:
        return pd.DataFrame()

    trainer_mean = period.groupby("trainer_code")["performance_delta"].mean().rename("trainer_mean")
    group_columns = ["trainer_code", "trainer_name"] + list(dimensions)
    grouped = period.groupby(group_columns, dropna=False).agg(
        n=("performance_delta", "size"),
        effect_mean=("performance_delta", "mean"),
        years=("year", "nunique"),
    ).reset_index()
    grouped = grouped.merge(trainer_mean, on="trainer_code", how="left")
    grouped["relative_effect"] = grouped["effect_mean"] - grouped["trainer_mean"]

    yearly_columns = ["trainer_code"] + list(dimensions) + ["year"]
    yearly = period.groupby(yearly_columns, dropna=False)["performance_delta"].mean().reset_index()
    trainer_yearly = period.groupby(["trainer_code", "year"])["performance_delta"].mean().rename("trainer_year_mean").reset_index()
    yearly = yearly.merge(trainer_yearly, on=["trainer_code", "year"], how="left")
    yearly["year_relative"] = yearly["performance_delta"] - yearly["trainer_year_mean"]
    share_columns = ["trainer_code"] + list(dimensions)
    positive_share = yearly.groupby(share_columns, dropna=False)["year_relative"].apply(lambda values: float((values > 0).mean())).rename("positive_year_share").reset_index()
    grouped = grouped.merge(positive_share, on=share_columns, how="left")
    return grouped


def _named_diagnostics(frame: pd.DataFrame) -> dict[str, Any]:
    """Produce bounded discovery/validation examples without driving model selection."""
    diagnostics: dict[str, Any] = {}
    selected_families = {
        "trainer_course": ("course_code",),
        "trainer_effort": ("effort_code",),
        "trainer_training_type": ("training_type_code",),
        "trainer_training_course_type": ("training_course_type_code",),
        "trainer_course_rest": ("course_code", "rest_bucket"),
    }

    for family, dimensions in selected_families.items():
        discovery = _period_pattern_stats(frame, dimensions, 2013, 2017)
        validation = _period_pattern_stats(frame, dimensions, 2018, 2023)
        if discovery.empty or validation.empty:
            diagnostics[family] = []
            continue

        discovery = discovery.loc[
            (discovery["n"] >= 100)
            & (discovery["years"] >= 4)
            & (discovery["relative_effect"] > 0)
            & (discovery["positive_year_share"] >= 0.75)
        ].copy()
        join_columns = ["trainer_code"] + list(dimensions)
        validation_columns = join_columns + ["n", "years", "relative_effect", "positive_year_share"]
        merged = discovery.merge(
            validation[validation_columns],
            on=join_columns,
            how="left",
            suffixes=("_discovery", "_validation"),
        )
        merged = merged.loc[
            (merged["n_validation"] >= 100)
            & (merged["years_validation"] >= 4)
            & (merged["relative_effect_validation"] > 0)
            & (merged["positive_year_share_validation"] >= (2.0 / 3.0))
        ].copy()
        merged = merged.sort_values(
            ["relative_effect_validation", "n_validation"], ascending=[False, False]
        ).head(20)

        rows: list[dict[str, Any]] = []
        for _, row in merged.iterrows():
            item: dict[str, Any] = {
                "trainer_code": _cat(row["trainer_code"]),
                "trainer_name": _cat(row.get("trainer_name")),
                "discovery_n": int(row["n_discovery"]),
                "discovery_relative_effect": float(row["relative_effect_discovery"]),
                "discovery_positive_year_share": float(row["positive_year_share_discovery"]),
                "validation_n": int(row["n_validation"]),
                "validation_relative_effect": float(row["relative_effect_validation"]),
                "validation_positive_year_share": float(row["positive_year_share_validation"]),
            }
            for dimension in dimensions:
                item[dimension] = _cat(row[dimension])
            rows.append(item)
        diagnostics[family] = rows
    return diagnostics


def _model_feature_inventory() -> dict[str, Any]:
    """Return exact predeclared feature families for the audit report."""
    inventory: dict[str, Any] = {}
    for model_name, spec in MODEL_SPECS.items():
        numeric_columns, categorical_columns = spec
        inventory[model_name] = {
            "numeric": list(numeric_columns),
            "categorical": list(categorical_columns),
        }
    return inventory


def analyze(db_path: Path) -> dict[str, Any]:
    """Execute the frozen Stage 2b development-period validation."""
    source, source_audit = _load_source(db_path)
    work = _materialize_time_aware(source)
    work = _materialize_generic_b(work)
    work = _materialize_pattern_features(work)
    work = _materialize_interactions(work)

    metrics, _ = _evaluate_models(work)
    classifications = _classify_models(metrics)
    diagnostics = _named_diagnostics(work)

    eligible = work.loc[_eligible_mask(work) & work["year"].between(TRAIN_FROM, MAX_YEAR)]
    test_population = eligible.loc[eligible["year"].isin(TEST_YEARS)]

    return {
        "status": "success",
        "analysis_version": VERSION,
        "protocol": "Training Pattern Stage 2b pre-analysis freeze 2026-09-11",
        "ridge_alpha": RIDGE_ALPHA,
        "trainer_pattern_shrinkage_lambda": SHRINKAGE_LAMBDA,
        "source_audit": source_audit,
        "holdout_guard": {
            "max_selected_year": int(work["year"].max()),
            "selected_2024_2025_rows": int((work["year"] >= 2024).sum()),
            "2024_2025_status": "OPENED_AND_CONSUMED_BY_V0_1_NOT_USED_FOR_STAGE2B",
        },
        "population": {
            "eligible_2013_2023": int(len(eligible)),
            "oot_test_2018_2023": int(len(test_population)),
            "test_year_counts": {
                str(year): int((test_population["year"] == year).sum()) for year in TEST_YEARS
            },
        },
        "model_features": _model_feature_inventory(),
        "pattern_families": {name: list(dimensions) for name, dimensions in PATTERN_FAMILIES.items()},
        "metrics": metrics,
        "incremental_decision": classifications,
        "named_pattern_diagnostics": diagnostics,
        "controller_boundary": {
            "production_authorized": False,
            "training_edge_v0_1_modified": False,
            "stage2b_is_development_only": True,
            "future_independent_confirmation_required_for_new_B_formula": True,
        },
    }


def _fmt(value: object, digits: int = 5) -> str:
    """Format optional numeric values for Markdown."""
    if value is None:
        return "NA"
    return f"{float(value):.{digits}f}"


def render_markdown(report: dict[str, Any]) -> str:
    """Render a compact, durable Stage 2b evidence report."""
    metrics = report["metrics"]
    decisions = report["incremental_decision"]
    lines = [
        "# JRDB Training Pattern Stage 2b — Development Validation",
        "",
        f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Guard and scope",
        "",
        f"- Source selected through year: **{report['holdout_guard']['max_selected_year']}**",
        f"- 2024-2025 rows selected: **{report['holdout_guard']['selected_2024_2025_rows']}**",
        "- 2024-2025 was already consumed by Training Edge v0.1 and is not reused as an unopened Stage 2b holdout.",
        f"- OOT test population 2018-2023: **{report['population']['oot_test_2018_2023']:,}**",
        "- Comparator M0 is the confirmed Training Edge v0.1 development specification.",
        "",
        "## Pooled out-of-time results",
        "",
        "| Model | Spearman | Δ vs M0 | RMSE | Top-bottom mean spread | Δ spread | Positive years | Decision |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    baseline = metrics["pooled"]["M0"]
    for model_name in MODEL_SPECS:
        current = metrics["pooled"][model_name]
        if model_name == "M0":
            lines.append(
                f"| M0 | {_fmt(current['spearman'])} | — | {_fmt(current['rmse'])} | "
                f"{_fmt(current['top_minus_bottom']['mean_delta'])} | — | — | confirmed baseline |"
            )
            continue
        decision = decisions[model_name]
        lines.append(
            f"| {model_name} | {_fmt(current['spearman'])} | {_fmt(decision['pooled_spearman_increment_vs_M0'])} | "
            f"{_fmt(current['rmse'])} | {_fmt(current['top_minus_bottom']['mean_delta'])} | "
            f"{_fmt(decision['pooled_top_bottom_mean_spread_change_vs_M0'])} | "
            f"{decision['positive_spearman_years']}/6 | **{decision['classification']}** |"
        )

    lines += [
        "",
        "## Spearman by test year",
        "",
        "| Year | M0 | M1 | M2 | M3 | M4 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in TEST_YEARS:
        values = []
        for model_name in MODEL_SPECS:
            values.append(_fmt(metrics["yearly"][model_name][str(year)]["spearman"]))
        lines.append(f"| {year} | " + " | ".join(values) + " |")

    lines += [
        "",
        "## Increment vs M0 by year",
        "",
        "| Year | M1 | M2 | M3 | M4 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for year in TEST_YEARS:
        values = []
        for model_name in ("M1", "M2", "M3", "M4"):
            values.append(_fmt(decisions[model_name]["yearly_spearman_increment_vs_M0"][str(year)]))
        lines.append(f"| {year} | " + " | ".join(values) + " |")

    lines += [
        "",
        "## Model definitions",
        "",
        "- M0: confirmed Training Edge v0.1 baseline (JRDB processed + rest + same-horse vertical).",
        "- M1: M0 + generic rotation/training-process facts.",
        "- M2: M0 + strictly-prior shrunk trainer-pattern effects.",
        "- M3: M0 + generic B + trainer-pattern effects.",
        "- M4: M3 + predeclared same-horse-vertical × B interactions.",
        "",
        "Trainer-pattern effects use only prior calendar years and fixed lambda=50 shrinkage. Trainer identity itself is not one-hot encoded.",
        "",
        "## Named pattern diagnostics",
        "",
        "The following are interpretability diagnostics only; they do not drive the primary model decision.",
    ]

    for family, rows in report["named_pattern_diagnostics"].items():
        lines += ["", f"### {family}", ""]
        if not rows:
            lines.append("No pattern passed the predeclared discovery/validation diagnostic filter.")
            continue
        lines += [
            "| Trainer | Pattern | Discovery n | Discovery effect | Validation n | Validation effect | Validation positive-year share |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for row in rows[:10]:
            pattern_parts = []
            for key, value in row.items():
                if key in {
                    "trainer_code", "trainer_name", "discovery_n", "discovery_relative_effect",
                    "discovery_positive_year_share", "validation_n", "validation_relative_effect",
                    "validation_positive_year_share",
                }:
                    continue
                pattern_parts.append(f"{key}={value}")
            pattern = ", ".join(pattern_parts)
            lines.append(
                f"| {row['trainer_name']} ({row['trainer_code']}) | {pattern} | {row['discovery_n']:,} | "
                f"{_fmt(row['discovery_relative_effect'])} | {row['validation_n']:,} | "
                f"{_fmt(row['validation_relative_effect'])} | {row['validation_positive_year_share']:.1%} |"
            )

    core_models = [name for name, item in decisions.items() if item["classification"] == "B_CORE_CANDIDATE"]
    auxiliary_models = [name for name, item in decisions.items() if item["classification"] == "B_AUXILIARY_ONLY"]
    lines += [
        "",
        "## Controller interpretation boundary",
        "",
        f"- B core candidates by the predeclared rule: `{core_models}`",
        f"- B auxiliary-only models: `{auxiliary_models}`",
        "- This report does not modify Training Edge v0.1 and does not authorize production deployment.",
        "- If B is retained for a new index version, it requires a separately named development cycle and genuinely new forward confirmation.",
        "",
        f"Reference M0 pooled Spearman: `{_fmt(baseline['spearman'])}`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args()

    report = analyze(args.db)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "analysis_version": report["analysis_version"],
        "population": report["population"],
        "incremental_decision": report["incremental_decision"],
        "holdout_guard": report["holdout_guard"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
