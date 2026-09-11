#!/usr/bin/env python3
"""Core contract for Training Edge v0.2 development scoring.

This module freezes the feature blocks, preprocessing, Ridge implementation,
raw Edge definition, and percentile calibration transform selected on 2026-09-11.
It does not fit a production model by itself and does not authorize deployment.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

VERSION = "0.2-dev-20260911"
RIDGE_ALPHA = 1.0
RIDGE_SOLVER = "lsqr"

C_NUMERIC = (
    "kyi_training_score",
    "finish_index",
    "jrdb_final_segment_index",
    "jrdb_workout_index_cha",
)

C_CATEGORICAL = (
    "kyi_training_arrow_code",
)

A_NUMERIC = (
    "final_self_pct",
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
    "rest_bucket",
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

CAB_NUMERIC = C_NUMERIC + A_NUMERIC + B_NUMERIC
CAB_CATEGORICAL = C_CATEGORICAL + B_CATEGORICAL

# These fields are deliberately outside the core score.
EXCLUDED_CORE_FIELDS = (
    "trainer_code",
    "trainer_name",
    "week_ago_workout_index",
    "jrdb_workout_index_cyb",
    "training_evaluation_code",
)


def rest_bucket(days_since_last_run: object) -> str:
    """Map race-gap days into the fixed v0.2 rotation bucket."""
    if days_since_last_run is None:
        return "missing"

    try:
        days = float(days_since_last_run)
    except (TypeError, ValueError):
        return "missing"

    if np.isnan(days):
        return "missing"
    if days <= 20:
        return "<=20"
    if days <= 34:
        return "21-34"
    if days <= 62:
        return "35-62"
    if days <= 119:
        return "63-119"
    return "120+"


def build_model_pipeline(numeric_columns: tuple[str, ...], categorical_columns: tuple[str, ...]) -> Pipeline:
    """Create the frozen preprocessing + Ridge pipeline for one model family."""
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
    model = Ridge(alpha=RIDGE_ALPHA, solver=RIDGE_SOLVER)
    return Pipeline(
        [
            ("preprocess", preprocessing),
            ("ridge", model),
        ]
    )


def build_c_model() -> Pipeline:
    """Create the C-only JRDB processed-training baseline model."""
    return build_model_pipeline(C_NUMERIC, C_CATEGORICAL)


def build_cab_model() -> Pipeline:
    """Create the C + A + generic-B model used by Training Edge v0.2."""
    return build_model_pipeline(CAB_NUMERIC, CAB_CATEGORICAL)


def training_edge_raw(c_prediction: float, cab_prediction: float) -> float:
    """Return the incremental A+B prediction beyond C."""
    return float(cab_prediction) - float(c_prediction)


def load_calibration(path: Path) -> dict[str, Any]:
    """Load and validate the frozen development percentile calibration."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "training-edge-v0.2-calibration":
        raise ValueError("unexpected Training Edge calibration schema")
    if payload.get("version") != VERSION:
        raise ValueError("Training Edge calibration version mismatch")
    return payload


def training_edge_percentile(raw_value: float, calibration: dict[str, Any]) -> float:
    """Map raw Edge to the frozen empirical development percentile.

    Linear interpolation is used between integer-percentile knots. Values beyond
    the observed development range are clipped to 0 or 100.
    """
    knots = calibration.get("percentile_knots")
    if not isinstance(knots, dict):
        raise ValueError("percentile_knots are missing from calibration")

    percentile_values: list[float] = []
    raw_values: list[float] = []
    for percentile in range(101):
        key = str(percentile)
        if key not in knots:
            raise ValueError(f"missing percentile knot: {key}")
        percentile_values.append(float(percentile))
        raw_values.append(float(knots[key]))

    result = np.interp(
        float(raw_value),
        np.asarray(raw_values, dtype=float),
        np.asarray(percentile_values, dtype=float),
        left=0.0,
        right=100.0,
    )
    return float(result)


def training_edge_direction(raw_value: float, epsilon: float = 1e-12) -> str:
    """Return negative, neutral, or positive from the scientific raw Edge sign."""
    value = float(raw_value)
    if value > epsilon:
        return "positive"
    if value < -epsilon:
        return "negative"
    return "neutral"
