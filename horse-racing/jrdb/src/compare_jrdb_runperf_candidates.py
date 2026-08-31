#!/usr/bin/env python3
"""Compare JRDB RunPerf candidate families with strict development walk-forward.

The comparator intentionally evaluates a completed historical run by how well its
score transfers to the horse's literal next start. 2024-2025 are locked holdout and
are rejected by this development comparator.

T1-T3 coefficients are re-estimated for every test year using only pairs whose
next-start year is earlier than the test year. Odds/popularity are absent from the
RunPerf database and are never read here.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from numpy.typing import NDArray

VERSION = "0.1.0"
WARMUP_START_YEAR = 2010
DEFAULT_DEVELOPMENT_START_YEAR = 2013
DEFAULT_DEVELOPMENT_END_YEAR = 2023
LOCKED_HOLDOUT_START_YEAR = 2024
DEFAULT_BASELINE_METHODS: tuple[str, ...] = (
    "EXPANDING",
    "ROLLING_2Y",
    "ROLLING_3Y",
    "ROLLING_5Y",
)
TIME_VARIANTS: dict[str, str] = {
    "NO_BIAS": "time_no_bias",
    "RAW": "time_raw_bias",
    "K2": "time_k2_bias",
    "K4": "time_k4_bias",
    "K8": "time_k8_bias",
}


@dataclasses.dataclass(frozen=True)
class YearData:
    """One target-year bucket of literal next-start pairs."""

    year: int
    race_ids: NDArray[np.int64]
    prev_finish_percentile: NDArray[np.float64]
    prev_margin_score: NDArray[np.float64]
    prev_weight_relative_kg: NDArray[np.float64]
    time_no_bias: NDArray[np.float64]
    time_raw_bias: NDArray[np.float64]
    time_k2_bias: NDArray[np.float64]
    time_k4_bias: NDArray[np.float64]
    time_k8_bias: NDArray[np.float64]
    prev_jrdb_raw_score: NDArray[np.float64]
    prev_jrdb_idm: NDArray[np.float64]
    target_finish_percentile: NDArray[np.float64]
    target_margin_score: NDArray[np.float64]
    target_finish: NDArray[np.float64]
    same_surface_distance_400m: NDArray[np.bool_]

    def feature(self, name: str) -> NDArray[np.float64]:
        """Return one numeric previous-run feature by stable internal name."""
        value: Any = getattr(self, name)
        return np.asarray(value, dtype=np.float64)


class _YearBucket:
    """Mutable loader bucket converted to compact numpy arrays after SQL streaming."""

    def __init__(self, year: int) -> None:
        self.year: int = year
        self.race_keys: list[str] = []
        self.prev_finish_percentile: list[float] = []
        self.prev_margin_score: list[float] = []
        self.prev_weight_relative_kg: list[float] = []
        self.time_no_bias: list[float] = []
        self.time_raw_bias: list[float] = []
        self.time_k2_bias: list[float] = []
        self.time_k4_bias: list[float] = []
        self.time_k8_bias: list[float] = []
        self.prev_jrdb_raw_score: list[float] = []
        self.prev_jrdb_idm: list[float] = []
        self.target_finish_percentile: list[float] = []
        self.target_margin_score: list[float] = []
        self.target_finish: list[float] = []
        self.same_surface_distance_400m: list[bool] = []

    def append(self, row: sqlite3.Row) -> None:
        """Append one SQL pair row while normalizing NULL to NaN."""
        self.race_keys.append(str(row["next_race_key"]))
        self.prev_finish_percentile.append(_float_or_nan(row["prev_finish_percentile"]))
        self.prev_margin_score.append(_float_or_nan(row["prev_margin_score"]))
        self.prev_weight_relative_kg.append(_float_or_nan(row["prev_weight_relative_kg"]))
        self.time_no_bias.append(_float_or_nan(row["time_no_bias"]))
        self.time_raw_bias.append(_float_or_nan(row["time_raw_bias"]))
        self.time_k2_bias.append(_float_or_nan(row["time_k2_bias"]))
        self.time_k4_bias.append(_float_or_nan(row["time_k4_bias"]))
        self.time_k8_bias.append(_float_or_nan(row["time_k8_bias"]))
        self.prev_jrdb_raw_score.append(_float_or_nan(row["prev_jrdb_raw_score"]))
        self.prev_jrdb_idm.append(_float_or_nan(row["prev_jrdb_idm"]))
        self.target_finish_percentile.append(_float_or_nan(row["next_finish_percentile"]))
        self.target_margin_score.append(_float_or_nan(row["next_margin_score"]))
        self.target_finish.append(_float_or_nan(row["next_finish"]))

        same_condition: bool = False
        prev_surface: Any = row["prev_surface_code"]
        next_surface: Any = row["next_surface_code"]
        prev_distance: Any = row["prev_distance_m"]
        next_distance: Any = row["next_distance_m"]
        if prev_surface is not None and next_surface is not None and str(prev_surface) == str(next_surface):
            if prev_distance is not None and next_distance is not None:
                if abs(int(prev_distance) - int(next_distance)) <= 400:
                    same_condition = True
        self.same_surface_distance_400m.append(same_condition)

    def freeze(self) -> YearData:
        """Convert Python lists to numpy arrays and encode target race keys as integers."""
        race_id_by_key: dict[str, int] = {}
        race_ids: list[int] = []
        next_id: int = 0
        for race_key in self.race_keys:
            race_id: int | None = race_id_by_key.get(race_key)
            if race_id is None:
                race_id = next_id
                race_id_by_key[race_key] = race_id
                next_id += 1
            race_ids.append(race_id)

        return YearData(
            year=self.year,
            race_ids=np.asarray(race_ids, dtype=np.int64),
            prev_finish_percentile=np.asarray(self.prev_finish_percentile, dtype=np.float64),
            prev_margin_score=np.asarray(self.prev_margin_score, dtype=np.float64),
            prev_weight_relative_kg=np.asarray(self.prev_weight_relative_kg, dtype=np.float64),
            time_no_bias=np.asarray(self.time_no_bias, dtype=np.float64),
            time_raw_bias=np.asarray(self.time_raw_bias, dtype=np.float64),
            time_k2_bias=np.asarray(self.time_k2_bias, dtype=np.float64),
            time_k4_bias=np.asarray(self.time_k4_bias, dtype=np.float64),
            time_k8_bias=np.asarray(self.time_k8_bias, dtype=np.float64),
            prev_jrdb_raw_score=np.asarray(self.prev_jrdb_raw_score, dtype=np.float64),
            prev_jrdb_idm=np.asarray(self.prev_jrdb_idm, dtype=np.float64),
            target_finish_percentile=np.asarray(self.target_finish_percentile, dtype=np.float64),
            target_margin_score=np.asarray(self.target_margin_score, dtype=np.float64),
            target_finish=np.asarray(self.target_finish, dtype=np.float64),
            same_surface_distance_400m=np.asarray(self.same_surface_distance_400m, dtype=np.bool_),
        )


def _float_or_nan(value: Any) -> float:
    """Convert nullable SQLite numeric value to float/NaN."""
    if value is None:
        return math.nan
    return float(value)


def _load_year_data(
    connection: sqlite3.Connection,
    baseline_method: str,
    development_end_year: int,
) -> dict[int, YearData]:
    """Load literal next-start pairs for one baseline method through development end."""
    sql: str = """
        WITH ordered AS (
          SELECT
            o.race_date AS prev_race_date,
            o.year AS prev_year,
            o.surface_code AS prev_surface_code,
            o.distance_m AS prev_distance_m,
            f.race_key AS prev_race_key,
            f.horse_id AS horse_id,
            f.finish_percentile AS prev_finish_percentile,
            CASE
              WHEN f.margin_per_1000m_sec IS NULL THEN NULL
              ELSE -f.margin_per_1000m_sec
            END AS prev_margin_score,
            f.weight_relative_kg AS prev_weight_relative_kg,
            f.time_residual_no_bias_sec AS time_no_bias,
            f.time_residual_raw_bias_sec AS time_raw_bias,
            f.time_residual_k2_bias_sec AS time_k2_bias,
            f.time_residual_k4_bias_sec AS time_k4_bias,
            f.time_residual_k8_bias_sec AS time_k8_bias,
            f.jrdb_raw_score AS prev_jrdb_raw_score,
            f.jrdb_idm AS prev_jrdb_idm,
            LEAD(f.race_key) OVER w AS next_race_key,
            LEAD(o.race_date) OVER w AS next_race_date,
            LEAD(o.year) OVER w AS next_year,
            LEAD(o.surface_code) OVER w AS next_surface_code,
            LEAD(o.distance_m) OVER w AS next_distance_m,
            LEAD(f.finish_percentile) OVER w AS next_finish_percentile,
            LEAD(
              CASE
                WHEN f.margin_per_1000m_sec IS NULL THEN NULL
                ELSE -f.margin_per_1000m_sec
              END
            ) OVER w AS next_margin_score,
            LEAD(f.finish) OVER w AS next_finish
          FROM runner_runperf_features f
          JOIN race_runperf_observation o ON o.race_key=f.race_key
          WHERE f.baseline_method=?
            AND f.horse_id IS NOT NULL
            AND f.horse_id<>''
            AND o.year<=?
          WINDOW w AS (
            PARTITION BY f.horse_id
            ORDER BY o.race_date,f.race_key,f.horse_no
          )
        )
        SELECT *
        FROM ordered
        WHERE next_year BETWEEN ? AND ?
          AND next_finish_percentile IS NOT NULL
        ORDER BY next_year,next_race_date,next_race_key,horse_id
    """
    cursor: sqlite3.Cursor = connection.execute(
        sql,
        (
            baseline_method,
            development_end_year,
            WARMUP_START_YEAR,
            development_end_year,
        ),
    )
    buckets: dict[int, _YearBucket] = {}
    for row in cursor:
        next_year: int = int(row["next_year"])
        bucket: _YearBucket | None = buckets.get(next_year)
        if bucket is None:
            bucket = _YearBucket(next_year)
            buckets[next_year] = bucket
        bucket.append(row)

    frozen: dict[int, YearData] = {}
    for year, bucket in buckets.items():
        frozen[year] = bucket.freeze()
    return frozen


def _rankdata(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return average ranks for finite one-dimensional values."""
    if values.ndim != 1:
        raise ValueError("rankdata expects a one-dimensional array")
    if values.size == 0:
        return np.asarray([], dtype=np.float64)
    unique_values: NDArray[np.float64]
    inverse: NDArray[np.int64]
    counts: NDArray[np.int64]
    unique_values, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    del unique_values
    ends: NDArray[np.float64] = np.cumsum(counts, dtype=np.float64)
    starts: NDArray[np.float64] = ends - counts + 1.0
    average_ranks: NDArray[np.float64] = (starts + ends) / 2.0
    return average_ranks[inverse]


def _pearson(x: NDArray[np.float64], y: NDArray[np.float64]) -> float | None:
    """Return Pearson correlation, or None when variance/sample size is insufficient."""
    if x.size < 3 or y.size < 3:
        return None
    x_std: float = float(np.std(x))
    y_std: float = float(np.std(y))
    if x_std <= 1.0e-12 or y_std <= 1.0e-12:
        return None
    matrix: NDArray[np.float64] = np.corrcoef(x, y)
    value: float = float(matrix[0, 1])
    if not math.isfinite(value):
        return None
    return value


def _spearman(x: NDArray[np.float64], y: NDArray[np.float64]) -> float | None:
    """Return Spearman rank correlation without scipy dependency."""
    if x.size < 3 or y.size < 3:
        return None
    x_rank: NDArray[np.float64] = _rankdata(x)
    y_rank: NDArray[np.float64] = _rankdata(y)
    return _pearson(x_rank, y_rank)


def _top_pick_metrics(
    scores: NDArray[np.float64],
    data: YearData,
    valid_mask: NDArray[np.bool_],
) -> dict[str, Any]:
    """Evaluate highest-score horse per target race when at least 3 candidates exist."""
    indices: NDArray[np.int64] = np.flatnonzero(valid_mask)
    if indices.size == 0:
        return {
            "race_count_ge3": 0,
            "top_pick_win_rate": None,
            "top_pick_top3_rate": None,
        }

    race_ids: NDArray[np.int64] = data.race_ids[indices]
    order: NDArray[np.int64] = np.argsort(race_ids, kind="stable")
    sorted_indices: NDArray[np.int64] = indices[order]
    sorted_races: NDArray[np.int64] = race_ids[order]

    evaluated_races: int = 0
    wins: int = 0
    top3: int = 0
    start: int = 0
    while start < sorted_indices.size:
        end: int = start + 1
        race_id: int = int(sorted_races[start])
        while end < sorted_indices.size and int(sorted_races[end]) == race_id:
            end += 1
        if end - start >= 3:
            group_indices: NDArray[np.int64] = sorted_indices[start:end]
            group_scores: NDArray[np.float64] = scores[group_indices]
            best_local: int = int(np.argmax(group_scores))
            best_index: int = int(group_indices[best_local])
            finish_value: float = float(data.target_finish[best_index])
            evaluated_races += 1
            if finish_value == 1.0:
                wins += 1
            if finish_value <= 3.0:
                top3 += 1
        start = end

    win_rate: float | None = None
    top3_rate: float | None = None
    if evaluated_races > 0:
        win_rate = wins / evaluated_races
        top3_rate = top3 / evaluated_races
    return {
        "race_count_ge3": evaluated_races,
        "top_pick_win_rate": win_rate,
        "top_pick_top3_rate": top3_rate,
    }


def _evaluate_scores(scores: NDArray[np.float64], data: YearData) -> dict[str, Any]:
    """Evaluate one candidate score against independent next-start outcomes."""
    finite_score: NDArray[np.bool_] = np.isfinite(scores)
    finite_finish: NDArray[np.bool_] = np.isfinite(data.target_finish_percentile)
    valid_finish: NDArray[np.bool_] = finite_score & finite_finish
    total_pairs: int = int(data.target_finish_percentile.size)
    evaluated_pairs: int = int(np.sum(valid_finish))

    spearman_finish: float | None = None
    pearson_finish: float | None = None
    if evaluated_pairs >= 3:
        spearman_finish = _spearman(scores[valid_finish], data.target_finish_percentile[valid_finish])
        pearson_finish = _pearson(scores[valid_finish], data.target_finish_percentile[valid_finish])

    valid_margin: NDArray[np.bool_] = valid_finish & np.isfinite(data.target_margin_score)
    spearman_margin: float | None = None
    if int(np.sum(valid_margin)) >= 3:
        spearman_margin = _spearman(scores[valid_margin], data.target_margin_score[valid_margin])

    same_finish: NDArray[np.bool_] = valid_finish & data.same_surface_distance_400m
    same_spearman_finish: float | None = None
    if int(np.sum(same_finish)) >= 3:
        same_spearman_finish = _spearman(scores[same_finish], data.target_finish_percentile[same_finish])

    same_margin: NDArray[np.bool_] = valid_margin & data.same_surface_distance_400m
    same_spearman_margin: float | None = None
    if int(np.sum(same_margin)) >= 3:
        same_spearman_margin = _spearman(scores[same_margin], data.target_margin_score[same_margin])

    top_metrics: dict[str, Any] = _top_pick_metrics(scores, data, valid_finish)
    coverage: float | None = None
    if total_pairs > 0:
        coverage = evaluated_pairs / total_pairs

    year_primary: float | None = _mean_optional([spearman_finish, spearman_margin])
    same_primary: float | None = _mean_optional([same_spearman_finish, same_spearman_margin])
    return {
        "year": data.year,
        "pair_count": total_pairs,
        "evaluated_pair_count": evaluated_pairs,
        "coverage": coverage,
        "spearman_next_finish": spearman_finish,
        "pearson_next_finish": pearson_finish,
        "spearman_next_margin": spearman_margin,
        "primary_rank_score": year_primary,
        "same_surface_distance_400m_count": int(np.sum(same_finish)),
        "same_spearman_next_finish": same_spearman_finish,
        "same_spearman_next_margin": same_spearman_margin,
        "same_primary_rank_score": same_primary,
        **top_metrics,
    }


def _mean_optional(values: Iterable[float | None]) -> float | None:
    """Return arithmetic mean over non-null finite values."""
    clean: list[float] = []
    for value in values:
        if value is not None and math.isfinite(value):
            clean.append(float(value))
    if not clean:
        return None
    return float(sum(clean) / len(clean))


def _std_optional(values: Iterable[float | None]) -> float | None:
    """Return population standard deviation over non-null finite values."""
    clean: list[float] = []
    for value in values:
        if value is not None and math.isfinite(value):
            clean.append(float(value))
    if not clean:
        return None
    return float(np.std(np.asarray(clean, dtype=np.float64)))


def _direct_candidate(
    candidate_name: str,
    family: str,
    baseline_method: str | None,
    time_variant: str | None,
    year_data: dict[int, YearData],
    development_start_year: int,
    development_end_year: int,
    feature_name: str,
) -> dict[str, Any]:
    """Evaluate an unfitted transparent one-column candidate by year."""
    yearly: list[dict[str, Any]] = []
    for year in range(development_start_year, development_end_year + 1):
        data: YearData | None = year_data.get(year)
        if data is None:
            continue
        scores: NDArray[np.float64] = data.feature(feature_name)
        yearly.append(_evaluate_scores(scores, data))
    return _aggregate_candidate(candidate_name, family, baseline_method, time_variant, yearly, [])


def _feature_matrix(data: YearData, feature_names: Sequence[str]) -> NDArray[np.float64]:
    """Build a 2D matrix for a small fitted T-family specification."""
    columns: list[NDArray[np.float64]] = []
    for feature_name in feature_names:
        columns.append(data.feature(feature_name))
    return np.column_stack(columns)


def _year_normal_equations(
    data: YearData,
    feature_names: Sequence[str],
) -> tuple[NDArray[np.float64], NDArray[np.float64], int]:
    """Return X'X and X'y for OLS with an intercept using one target year."""
    x_raw: NDArray[np.float64] = _feature_matrix(data, feature_names)
    y: NDArray[np.float64] = data.target_finish_percentile
    valid: NDArray[np.bool_] = np.isfinite(y)
    valid &= np.all(np.isfinite(x_raw), axis=1)
    row_count: int = int(np.sum(valid))
    width: int = len(feature_names) + 1
    if row_count == 0:
        return (
            np.zeros((width, width), dtype=np.float64),
            np.zeros(width, dtype=np.float64),
            0,
        )
    x: NDArray[np.float64] = np.column_stack(
        [np.ones(row_count, dtype=np.float64), x_raw[valid]]
    )
    y_valid: NDArray[np.float64] = y[valid]
    xtx: NDArray[np.float64] = x.T @ x
    xty: NDArray[np.float64] = x.T @ y_valid
    return xtx, xty, row_count


def _solve_ols(xtx: NDArray[np.float64], xty: NDArray[np.float64]) -> NDArray[np.float64]:
    """Solve tiny OLS normal equations with Moore-Penrose inverse for collinearity."""
    return np.linalg.pinv(xtx, rcond=1.0e-12) @ xty


def _fitted_candidate(
    candidate_name: str,
    family: str,
    baseline_method: str,
    time_variant: str,
    year_data: dict[int, YearData],
    development_start_year: int,
    development_end_year: int,
    feature_names: Sequence[str],
) -> dict[str, Any]:
    """Fit T1-T3 with prior-year-only OLS and evaluate each held-out development year."""
    moments: dict[int, tuple[NDArray[np.float64], NDArray[np.float64], int]] = {}
    for year in range(WARMUP_START_YEAR, development_end_year + 1):
        data: YearData | None = year_data.get(year)
        if data is None:
            continue
        moments[year] = _year_normal_equations(data, feature_names)

    width: int = len(feature_names) + 1
    cumulative_xtx: NDArray[np.float64] = np.zeros((width, width), dtype=np.float64)
    cumulative_xty: NDArray[np.float64] = np.zeros(width, dtype=np.float64)
    cumulative_rows: int = 0
    yearly: list[dict[str, Any]] = []
    coefficient_history: list[dict[str, Any]] = []

    for year in range(WARMUP_START_YEAR, development_end_year + 1):
        if year >= development_start_year:
            data: YearData | None = year_data.get(year)
            if data is not None and cumulative_rows >= width:
                beta: NDArray[np.float64] = _solve_ols(cumulative_xtx, cumulative_xty)
                x_test: NDArray[np.float64] = _feature_matrix(data, feature_names)
                scores: NDArray[np.float64] = np.full(data.target_finish_percentile.size, np.nan, dtype=np.float64)
                valid_x: NDArray[np.bool_] = np.all(np.isfinite(x_test), axis=1)
                if int(np.sum(valid_x)) > 0:
                    scores[valid_x] = beta[0] + x_test[valid_x] @ beta[1:]
                metrics: dict[str, Any] = _evaluate_scores(scores, data)
                metrics["training_pair_count"] = cumulative_rows
                yearly.append(metrics)
                coefficient_history.append(
                    {
                        "test_year": year,
                        "training_pair_count": cumulative_rows,
                        "intercept": float(beta[0]),
                        "coefficients": {
                            feature_names[index]: float(beta[index + 1])
                            for index in range(len(feature_names))
                        },
                    }
                )

        current_moments: tuple[NDArray[np.float64], NDArray[np.float64], int] | None = moments.get(year)
        if current_moments is not None:
            cumulative_xtx += current_moments[0]
            cumulative_xty += current_moments[1]
            cumulative_rows += current_moments[2]

    return _aggregate_candidate(
        candidate_name,
        family,
        baseline_method,
        time_variant,
        yearly,
        coefficient_history,
    )


def _aggregate_candidate(
    candidate_name: str,
    family: str,
    baseline_method: str | None,
    time_variant: str | None,
    yearly: list[dict[str, Any]],
    coefficient_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate equal-year metrics so high-volume years cannot dominate selection."""
    primary_values: list[float | None] = [row.get("primary_rank_score") for row in yearly]
    same_values: list[float | None] = [row.get("same_primary_rank_score") for row in yearly]
    finish_values: list[float | None] = [row.get("spearman_next_finish") for row in yearly]
    margin_values: list[float | None] = [row.get("spearman_next_margin") for row in yearly]
    win_values: list[float | None] = [row.get("top_pick_win_rate") for row in yearly]
    top3_values: list[float | None] = [row.get("top_pick_top3_rate") for row in yearly]
    coverage_values: list[float | None] = [row.get("coverage") for row in yearly]

    positive_years: int = 0
    evaluated_years: int = 0
    for value in primary_values:
        if value is not None and math.isfinite(value):
            evaluated_years += 1
            if value > 0.0:
                positive_years += 1

    return {
        "candidate": candidate_name,
        "family": family,
        "baseline_method": baseline_method,
        "time_variant": time_variant,
        "development_year_count": evaluated_years,
        "positive_primary_year_count": positive_years,
        "mean_primary_rank_score": _mean_optional(primary_values),
        "std_primary_rank_score": _std_optional(primary_values),
        "mean_spearman_next_finish": _mean_optional(finish_values),
        "mean_spearman_next_margin": _mean_optional(margin_values),
        "mean_same_condition_rank_score": _mean_optional(same_values),
        "mean_top_pick_win_rate": _mean_optional(win_values),
        "mean_top_pick_top3_rate": _mean_optional(top3_values),
        "mean_coverage": _mean_optional(coverage_values),
        "yearly": yearly,
        "coefficient_history": coefficient_history,
    }


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, float, float]:
    """Sort candidates by primary rank validity, then same-condition validity and stability."""
    primary: Any = candidate.get("mean_primary_rank_score")
    same_condition: Any = candidate.get("mean_same_condition_rank_score")
    std_value: Any = candidate.get("std_primary_rank_score")
    primary_value: float = -math.inf
    same_value: float = -math.inf
    stability_value: float = -math.inf
    if primary is not None:
        primary_value = float(primary)
    if same_condition is not None:
        same_value = float(same_condition)
    if std_value is not None:
        stability_value = -float(std_value)
    return primary_value, same_value, stability_value


def _compact_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return ranking fields without large yearly/coefficient payloads."""
    keys: tuple[str, ...] = (
        "candidate",
        "family",
        "baseline_method",
        "time_variant",
        "development_year_count",
        "positive_primary_year_count",
        "mean_primary_rank_score",
        "std_primary_rank_score",
        "mean_spearman_next_finish",
        "mean_spearman_next_margin",
        "mean_same_condition_rank_score",
        "mean_top_pick_win_rate",
        "mean_top_pick_top3_rate",
        "mean_coverage",
    )
    result: dict[str, Any] = {}
    for key in keys:
        result[key] = candidate.get(key)
    return result


def compare(
    database_path: Path,
    development_start_year: int,
    development_end_year: int,
    baseline_methods: Sequence[str],
) -> dict[str, Any]:
    """Run the complete development comparison without touching locked holdout years."""
    if development_start_year < DEFAULT_DEVELOPMENT_START_YEAR:
        raise ValueError("development_start_year must be 2013 or later")
    if development_end_year >= LOCKED_HOLDOUT_START_YEAR:
        raise ValueError("development comparator must not touch locked 2024-2025 holdout")
    if development_end_year < development_start_year:
        raise ValueError("development_end_year must be >= development_start_year")

    connection: sqlite3.Connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    candidates: list[dict[str, Any]] = []
    pair_counts: dict[str, dict[str, int]] = {}
    try:
        first_method: bool = True
        for baseline_method in baseline_methods:
            year_data: dict[int, YearData] = _load_year_data(
                connection,
                baseline_method,
                development_end_year,
            )
            pair_counts[baseline_method] = {}
            for year in range(WARMUP_START_YEAR, development_end_year + 1):
                data: YearData | None = year_data.get(year)
                count: int = 0
                if data is not None:
                    count = int(data.target_finish_percentile.size)
                pair_counts[baseline_method][str(year)] = count

            if first_method:
                candidates.append(
                    _direct_candidate(
                        "B0", "B0", None, None, year_data,
                        development_start_year, development_end_year,
                        "prev_finish_percentile",
                    )
                )
                candidates.append(
                    _direct_candidate(
                        "B1", "B1", None, None, year_data,
                        development_start_year, development_end_year,
                        "prev_margin_score",
                    )
                )
                candidates.append(
                    _direct_candidate(
                        "J0", "J0", None, None, year_data,
                        development_start_year, development_end_year,
                        "prev_jrdb_raw_score",
                    )
                )
                candidates.append(
                    _direct_candidate(
                        "J1", "J1", None, None, year_data,
                        development_start_year, development_end_year,
                        "prev_jrdb_idm",
                    )
                )
                first_method = False

            for variant_name, feature_name in TIME_VARIANTS.items():
                prefix: str = f"{baseline_method}|{variant_name}"
                candidates.append(
                    _direct_candidate(
                        f"T0|{prefix}", "T0", baseline_method, variant_name,
                        year_data, development_start_year, development_end_year,
                        feature_name,
                    )
                )
                candidates.append(
                    _fitted_candidate(
                        f"T1|{prefix}", "T1", baseline_method, variant_name,
                        year_data, development_start_year, development_end_year,
                        [feature_name, "prev_margin_score"],
                    )
                )
                candidates.append(
                    _fitted_candidate(
                        f"T2|{prefix}", "T2", baseline_method, variant_name,
                        year_data, development_start_year, development_end_year,
                        [feature_name, "prev_weight_relative_kg"],
                    )
                )
                candidates.append(
                    _fitted_candidate(
                        f"T3|{prefix}", "T3", baseline_method, variant_name,
                        year_data, development_start_year, development_end_year,
                        [feature_name, "prev_margin_score", "prev_weight_relative_kg"],
                    )
                )
    finally:
        connection.close()

    ranked: list[dict[str, Any]] = sorted(candidates, key=_candidate_sort_key, reverse=True)
    best_by_family: dict[str, dict[str, Any]] = {}
    for candidate in ranked:
        family: str = str(candidate["family"])
        if family not in best_by_family:
            best_by_family[family] = _compact_candidate(candidate)

    benchmark_families: tuple[str, ...] = ("B0", "B1", "J0", "J1")
    benchmarks: dict[str, dict[str, Any]] = {}
    for family in benchmark_families:
        benchmark: dict[str, Any] | None = best_by_family.get(family)
        if benchmark is not None:
            benchmarks[family] = benchmark

    return {
        "status": "PASS",
        "comparator_version": VERSION,
        "protocol": {
            "warmup_years": [WARMUP_START_YEAR, development_start_year - 1],
            "development_years": [development_start_year, development_end_year],
            "locked_holdout_years": [2024, 2025],
            "holdout_touched": False,
            "pair_definition": "literal next chronological start for same horse_id; target must have valid finish percentile",
            "coefficient_fit": "T1-T3 OLS to next-start finish percentile using only target years earlier than each test year",
            "primary_metric": "equal-year mean of Spearman(next finish percentile) and Spearman(next margin score)",
            "same_condition_subset": "same surface and absolute distance change <= 400m",
            "market_inputs": "none",
        },
        "baseline_methods": list(baseline_methods),
        "time_variants": list(TIME_VARIANTS.keys()),
        "pair_counts_by_target_year": pair_counts,
        "candidate_count": len(candidates),
        "top_candidates": [_compact_candidate(candidate) for candidate in ranked[:20]],
        "best_by_family": best_by_family,
        "benchmarks": benchmarks,
        "all_candidates": candidates,
    }


def main() -> None:
    """CLI entry point."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--development-start", type=int, default=DEFAULT_DEVELOPMENT_START_YEAR)
    parser.add_argument("--development-end", type=int, default=DEFAULT_DEVELOPMENT_END_YEAR)
    parser.add_argument(
        "--baseline-methods",
        default=",".join(DEFAULT_BASELINE_METHODS),
        help="Comma-separated baseline methods already materialized in the RunPerf DB.",
    )
    args: argparse.Namespace = parser.parse_args()
    methods: list[str] = []
    for item in str(args.baseline_methods).split(","):
        item_clean: str = item.strip().upper()
        if item_clean:
            methods.append(item_clean)
    if not methods:
        raise SystemExit("at least one baseline method is required")

    report: dict[str, Any] = compare(
        args.db,
        int(args.development_start),
        int(args.development_end),
        methods,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "candidate_count": report["candidate_count"],
        "top_candidates": report["top_candidates"][:5],
        "best_by_family": report["best_by_family"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
