#!/usr/bin/env python3
"""Evaluate the frozen existing-horse Ability v0.1 candidate on 2024-2025.

This module is intentionally not a model-search tool.  It evaluates exactly the
candidate frozen in Ability_Development_Decision_v0_1.md, with chronological
annual refits and the same preprocessing/metric helpers used in development.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import ElasticNet, Ridge

from compare_jrdb_ability_models import _feature_vector, _fold_preprocess, _metric

HOLDOUT_YEARS = (2024, 2025)
RECENT = "070"
BANDWIDTH = 200
APTITUDE_K = 0
JOCKEY_K = 0
ELASTIC_ALPHA = 0.01
ELASTIC_L1_RATIO = 0.5
RIDGE_ALPHA = 10.0


def _is_finite_number(value: Any) -> bool:
    """Return True only for finite numeric metric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _json_safe(value: Any) -> Any:
    """Recursively normalize non-finite diagnostics to explicit JSON null."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _load_rows(database: Path) -> list[dict[str, Any]]:
    """Load only chronologically eligible existing-horse rows through 2025."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
              t.race_date,t.race_key,t.horse_no,t.year,t.surface_code,t.distance_m,
              t.race_context_availability,t.weight_relative,
              f.*,c.official_runperf_raw
            FROM ability_target_runner t
            JOIN ability_feature_snapshot f USING(race_key,horse_no)
            JOIN ability_current_result c USING(race_key,horse_no)
            WHERE t.year BETWEEN 2010 AND 2025
              AND t.race_context_availability='PRE_RACE'
              AND f.career_scored_run_count>=1
              AND c.score_status='OK'
              AND c.official_runperf_raw IS NOT NULL
            ORDER BY t.year,t.race_date,t.race_key,t.horse_no
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    """Build the exact frozen D070/200m/k0/k0 A1 feature matrix."""
    values = [
        _feature_vector(
            row,
            RECENT,
            BANDWIDTH,
            APTITUDE_K,
            JOCKEY_K,
        )[0]
        for row in rows
    ]
    return np.asarray(values, dtype=float)


def _metric_is_finite(metric: dict[str, Any]) -> bool:
    """Check all required primary components for one annual metric result."""
    required = ("spearman_all", "within_race_spearman", "primary")
    return all(_is_finite_number(metric.get(name)) for name in required)


def _evaluate_year(rows: list[dict[str, Any]], year: int) -> dict[str, Any]:
    """Fit on prior years and evaluate the frozen candidate on one target year."""
    train_rows = [row for row in rows if int(row["year"]) < year]
    test_rows = [row for row in rows if int(row["year"]) == year]
    if not train_rows:
        raise ValueError(f"no training rows for Ability holdout year {year}")
    if not test_rows:
        raise ValueError(f"no test rows for Ability holdout year {year}")

    train_year_max = max(int(row["year"]) for row in train_rows)
    if train_year_max >= year:
        raise ValueError("Ability holdout chronology violation")

    x_train_raw = _matrix(train_rows)
    x_test_raw = _matrix(test_rows)
    y_train = np.asarray([float(row["official_runperf_raw"]) for row in train_rows], dtype=float)
    y_test = np.asarray([float(row["official_runperf_raw"]) for row in test_rows], dtype=float)
    races = np.asarray([row["race_key"] for row in test_rows])

    x_train, x_test, preprocessing = _fold_preprocess(x_train_raw, x_test_raw)

    elastic = ElasticNet(
        alpha=ELASTIC_ALPHA,
        l1_ratio=ELASTIC_L1_RATIO,
        fit_intercept=True,
        max_iter=10000,
        tol=1e-6,
        random_state=0,
    )
    elastic.fit(x_train, y_train)
    a1_prediction = elastic.predict(x_test)

    ridge = Ridge(alpha=RIDGE_ALPHA, solver="lsqr", fit_intercept=True)
    ridge.fit(x_train, y_train)
    ridge_prediction = ridge.predict(x_test)

    finite_prediction_mask = np.isfinite(a1_prediction)
    predicted_count = int(np.sum(finite_prediction_mask))
    if predicted_count != len(test_rows):
        raise ValueError(f"non-finite frozen Ability predictions in {year}")

    recent = np.asarray(
        [
            np.nan if row.get("recent_perf_d070") is None else float(row["recent_perf_d070"])
            for row in test_rows
        ],
        dtype=float,
    )
    paired_mask = np.isfinite(recent)
    paired_count = int(np.sum(paired_mask))
    if paired_count < 2:
        raise ValueError(f"insufficient paired A0 rows in Ability holdout year {year}")

    # Gate comparisons use the same paired cohort for A1, A0, and Ridge.
    a1_metric = _metric(a1_prediction[paired_mask], y_test[paired_mask], races[paired_mask])
    a0_metric = _metric(recent[paired_mask], y_test[paired_mask], races[paired_mask])
    ridge_metric = _metric(ridge_prediction[paired_mask], y_test[paired_mask], races[paired_mask])
    a1_full_metric = _metric(a1_prediction, y_test, races)

    if not _metric_is_finite(a1_metric):
        raise ValueError(f"non-finite frozen A1 primary metric in {year}")
    if not _metric_is_finite(a0_metric):
        raise ValueError(f"non-finite A0 primary metric in {year}")
    if not _metric_is_finite(ridge_metric):
        raise ValueError(f"non-finite Ridge diagnostic primary metric in {year}")

    delta = float(a1_metric["primary"]) - float(a0_metric["primary"])
    return {
        "year": year,
        "train_row_count": len(train_rows),
        "test_row_count": len(test_rows),
        "train_year_max": train_year_max,
        "a1_predicted_row_count": predicted_count,
        "a0_evaluable_row_count": paired_count,
        "paired_row_count": paired_count,
        "a1_prediction_coverage": predicted_count / len(test_rows),
        "paired_coverage": paired_count / len(test_rows),
        "a1": a1_metric,
        "a1_all_eligible": a1_full_metric,
        "a0_d070": a0_metric,
        "ridge_diagnostic": ridge_metric,
        "delta_primary_a1_minus_a0": delta,
        "preprocessing": preprocessing,
        "elastic_net": {
            "alpha": ELASTIC_ALPHA,
            "l1_ratio": ELASTIC_L1_RATIO,
            "intercept": float(elastic.intercept_),
            "coefficients": [float(value) for value in elastic.coef_],
            "coefficient_count": int(np.count_nonzero(elastic.coef_)),
        },
        "ridge": {
            "alpha": RIDGE_ALPHA,
            "intercept": float(ridge.intercept_),
            "coefficients": [float(value) for value in ridge.coef_],
            "coefficient_count": int(np.count_nonzero(ridge.coef_)),
        },
    }


def evaluate(database: Path) -> dict[str, Any]:
    """Execute the frozen 2024-2025 existing-horse Ability confirmation."""
    rows = _load_rows(database)
    if not rows:
        raise ValueError("no eligible Ability rows through 2025")

    annual = [_evaluate_year(rows, year) for year in HOLDOUT_YEARS]
    deltas = [float(item["delta_primary_a1_minus_a0"]) for item in annual]
    mean_delta = float(np.mean(deltas))

    technical_ok = all(
        item["train_year_max"] < item["year"]
        and item["a1_prediction_coverage"] == 1.0
        and _is_finite_number(item["delta_primary_a1_minus_a0"])
        for item in annual
    )

    if not technical_ok:
        classification = "FAIL"
    elif mean_delta <= 0:
        classification = "FAIL"
    elif all(delta > 0 for delta in deltas):
        classification = "PASS_STRONG"
    else:
        classification = "PASS_MIXED"

    return _json_safe(
        {
            "status": "PASS" if technical_ok else "FAIL",
            "protocol_version": "Ability_Holdout_Protocol_v0_1",
            "candidate": "ElasticNet:R:070:200:0:0:0.01:0.5",
            "baseline": "A0_D070",
            "ridge_diagnostic_candidate": "Ridge:R:070:200:0:0:10.0:",
            "holdout_years": list(HOLDOUT_YEARS),
            "holdout_touched": True,
            "2024_2025_predictive_metrics_inspected": True,
            "model_promoted": False,
            "source_eligible_rows_through_2025": len(rows),
            "annual": annual,
            "annual_delta_primary_a1_minus_a0": [
                {"year": item["year"], "delta_primary": item["delta_primary_a1_minus_a0"]}
                for item in annual
            ],
            "mean_delta_primary_a1_minus_a0": mean_delta,
            "technical_gates_pass": technical_ok,
            "classification": classification,
            "frozen_config": {
                "recent": RECENT,
                "bandwidth": BANDWIDTH,
                "aptitude_k": APTITUDE_K,
                "jockey_k": JOCKEY_K,
                "elastic_alpha": ELASTIC_ALPHA,
                "elastic_l1_ratio": ELASTIC_L1_RATIO,
                "ridge_alpha": RIDGE_ALPHA,
            },
        }
    )


def main() -> int:
    """Evaluate a built Ability snapshot DB and write strict JSON evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    report = evaluate(args.db)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "classification": report["classification"],
                "mean_delta_primary_a1_minus_a0": report["mean_delta_primary_a1_minus_a0"],
                "annual_delta_primary_a1_minus_a0": report["annual_delta_primary_a1_minus_a0"],
            },
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
