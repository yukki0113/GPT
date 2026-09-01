#!/usr/bin/env python3
"""Evaluate the frozen RunPerf v0.1 candidate on the 2024-2025 holdout.

The candidate is intentionally not configurable from the CLI. This prevents the
holdout workflow from becoming another candidate search after development.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from compare_jrdb_runperf_candidates import (
    WARMUP_START_YEAR,
    YearData,
    _evaluate_scores,
    _feature_matrix,
    _load_year_data,
    _solve_ols,
    _year_normal_equations,
)

VERSION = "0.1.0"
BASELINE_METHOD = "EXPANDING"
SELECTED_CANDIDATE = "T1|EXPANDING|RAW"
SELECTED_FEATURES: tuple[str, ...] = ("time_raw_bias", "prev_margin_score")
HOLDOUT_YEARS: tuple[int, ...] = (2024, 2025)
MIN_COVERAGE = 0.95

DIRECT_DIAGNOSTICS: dict[str, str] = {
    "B0": "prev_finish_percentile",
    "B1": "prev_margin_score",
    "T0|EXPANDING|RAW": "time_raw_bias",
    "J0": "prev_jrdb_raw_score",
    "J1": "prev_jrdb_idm",
}


def _fit_snapshot(
    year_data: dict[int, YearData],
    target_year: int,
) -> tuple[NDArray[np.float64], int, dict[str, int]]:
    """Fit T1 coefficients from literal-next-start pairs strictly before target year."""
    width = len(SELECTED_FEATURES) + 1
    cumulative_xtx: NDArray[np.float64] = np.zeros((width, width), dtype=np.float64)
    cumulative_xty: NDArray[np.float64] = np.zeros(width, dtype=np.float64)
    training_pair_count = 0
    pair_count_by_target_year: dict[str, int] = {}

    for year in range(WARMUP_START_YEAR, target_year):
        data = year_data.get(year)
        if data is None:
            pair_count_by_target_year[str(year)] = 0
            continue
        xtx, xty, row_count = _year_normal_equations(data, SELECTED_FEATURES)
        cumulative_xtx += xtx
        cumulative_xty += xty
        training_pair_count += row_count
        pair_count_by_target_year[str(year)] = row_count

    if training_pair_count < width:
        raise ValueError(f"insufficient prior-year training pairs for {target_year}")
    beta = _solve_ols(cumulative_xtx, cumulative_xty)
    return beta, training_pair_count, pair_count_by_target_year


def _score_selected(data: YearData, beta: NDArray[np.float64]) -> NDArray[np.float64]:
    """Apply one frozen as-of T1 coefficient snapshot to a holdout year."""
    x_test = _feature_matrix(data, SELECTED_FEATURES)
    scores: NDArray[np.float64] = np.full(
        data.target_finish_percentile.size,
        np.nan,
        dtype=np.float64,
    )
    valid_x = np.all(np.isfinite(x_test), axis=1)
    if int(np.sum(valid_x)) > 0:
        scores[valid_x] = beta[0] + x_test[valid_x] @ beta[1:]
    return scores


def _finite_positive(value: Any) -> bool:
    """Return True only for a finite strictly positive numeric value."""
    if value is None:
        return False
    numeric = float(value)
    return math.isfinite(numeric) and numeric > 0.0


def _mean(values: list[float]) -> float:
    """Return arithmetic mean for a non-empty list."""
    if not values:
        raise ValueError("cannot average an empty list")
    return float(sum(values) / len(values))


def _classify(year_rows: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Apply the frozen pre-holdout validation classification."""
    reasons: list[str] = []
    if len(year_rows) != len(HOLDOUT_YEARS):
        return "FAIL", ["missing holdout year evaluation"]

    primary_deltas: list[float] = []
    positive_year_count = 0
    coefficient_gate = True
    coverage_gate = True

    for row in year_rows:
        delta = row.get("delta_primary_vs_B1")
        if delta is None or not math.isfinite(float(delta)):
            return "FAIL", [f"non-finite primary delta in {row.get('year')}"]
        numeric_delta = float(delta)
        primary_deltas.append(numeric_delta)
        if numeric_delta > 0.0:
            positive_year_count += 1

        selected = row.get("selected") or {}
        coverage = selected.get("coverage")
        if coverage is None or not math.isfinite(float(coverage)) or float(coverage) < MIN_COVERAGE:
            coverage_gate = False

        snapshot = row.get("coefficient_snapshot") or {}
        coefficients = snapshot.get("coefficients") or {}
        for feature in SELECTED_FEATURES:
            if not _finite_positive(coefficients.get(feature)):
                coefficient_gate = False

    mean_delta = _mean(primary_deltas)
    if not coefficient_gate:
        reasons.append("one or more selected T1 coefficients are non-positive or non-finite")
    if not coverage_gate:
        reasons.append(f"selected-candidate coverage fell below {MIN_COVERAGE:.2f}")
    if mean_delta <= 0.0:
        reasons.append("mean holdout primary delta versus B1 is non-positive")

    if reasons:
        return "FAIL", reasons
    if positive_year_count == len(HOLDOUT_YEARS):
        return "PASS_STRONG", ["T1 primary score exceeded B1 in both holdout years"]
    return "PASS_MIXED", ["T1 beat B1 on the two-year mean but not in both individual years"]


def _status_counts(connection: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Count RunPerf calculation statuses by holdout source-run year."""
    placeholders = ",".join("?" for _ in HOLDOUT_YEARS)
    sql = f"""
        SELECT o.year AS year, f.calculation_status AS calculation_status, COUNT(*) AS row_count
        FROM runner_runperf_features f
        JOIN race_runperf_observation o ON o.race_key=f.race_key
        WHERE f.baseline_method=?
          AND o.year IN ({placeholders})
        GROUP BY o.year,f.calculation_status
        ORDER BY o.year,f.calculation_status
    """
    parameters: list[Any] = [BASELINE_METHOD]
    parameters.extend(HOLDOUT_YEARS)
    result: dict[str, dict[str, int]] = {}
    for row in connection.execute(sql, parameters):
        year = str(int(row["year"]))
        result.setdefault(year, {})[str(row["calculation_status"])] = int(row["row_count"])
    return result


def evaluate(database_path: Path) -> dict[str, Any]:
    """Evaluate only the frozen T1 specification and fixed diagnostic references."""
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        year_data = _load_year_data(connection, BASELINE_METHOD, max(HOLDOUT_YEARS))
        status_counts = _status_counts(connection)
    finally:
        connection.close()

    yearly: list[dict[str, Any]] = []
    for target_year in HOLDOUT_YEARS:
        data = year_data.get(target_year)
        if data is None:
            raise ValueError(f"holdout year {target_year} has no literal-next-start data")

        beta, training_pair_count, pair_count_by_target_year = _fit_snapshot(year_data, target_year)
        selected_scores = _score_selected(data, beta)
        selected_metrics = _evaluate_scores(selected_scores, data)

        diagnostics: dict[str, dict[str, Any]] = {}
        for candidate_name, feature_name in DIRECT_DIAGNOSTICS.items():
            diagnostics[candidate_name] = _evaluate_scores(data.feature(feature_name), data)

        b1_primary = diagnostics["B1"].get("primary_rank_score")
        selected_primary = selected_metrics.get("primary_rank_score")
        delta_primary: float | None = None
        if b1_primary is not None and selected_primary is not None:
            delta_primary = float(selected_primary) - float(b1_primary)

        b1_same = diagnostics["B1"].get("same_primary_rank_score")
        selected_same = selected_metrics.get("same_primary_rank_score")
        delta_same: float | None = None
        if b1_same is not None and selected_same is not None:
            delta_same = float(selected_same) - float(b1_same)

        coefficients = {
            SELECTED_FEATURES[index]: float(beta[index + 1])
            for index in range(len(SELECTED_FEATURES))
        }
        yearly.append(
            {
                "year": target_year,
                "selected": selected_metrics,
                "diagnostics": diagnostics,
                "delta_primary_vs_B1": delta_primary,
                "delta_same_condition_vs_B1": delta_same,
                "coefficient_snapshot": {
                    "target_year": target_year,
                    "coefficient_asof_through_year": target_year - 1,
                    "training_pair_count": training_pair_count,
                    "pair_count_by_target_year": pair_count_by_target_year,
                    "intercept": float(beta[0]),
                    "coefficients": coefficients,
                },
            }
        )

    classification, classification_reasons = _classify(yearly)
    primary_deltas = [float(row["delta_primary_vs_B1"]) for row in yearly]
    same_deltas = [
        float(row["delta_same_condition_vs_B1"])
        for row in yearly
        if row.get("delta_same_condition_vs_B1") is not None
    ]

    return {
        "status": "PASS",
        "evaluator_version": VERSION,
        "holdout_outcomes_read": True,
        "frozen_specification": {
            "candidate": SELECTED_CANDIDATE,
            "baseline_method": BASELINE_METHOD,
            "features": list(SELECTED_FEATURES),
            "holdout_years": list(HOLDOUT_YEARS),
            "minimum_coverage": MIN_COVERAGE,
            "decision_record": "horse-racing/jrdb/docs/RunPerf_Development_Decision_v0_1.md",
            "holdout_protocol": "horse-racing/jrdb/docs/RunPerf_Holdout_Protocol_v0_1.md",
        },
        "validation_classification": classification,
        "classification_reasons": classification_reasons,
        "mean_delta_primary_vs_B1": _mean(primary_deltas),
        "mean_delta_same_condition_vs_B1": _mean(same_deltas) if same_deltas else None,
        "yearly": yearly,
        "calculation_status_counts": status_counts,
        "diagnostic_reference_policy": (
            "B0/B1/T0/J0/J1 are fixed references only; this evaluator does not rerank the 84 development candidates."
        ),
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = evaluate(args.db)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
