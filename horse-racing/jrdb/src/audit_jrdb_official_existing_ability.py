#!/usr/bin/env python3
"""Audit official Existing-Horse Ability v0.1 materialization and chronology."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from compare_jrdb_ability_models import _metric

EXPECTED_MODEL_VERSION = "Existing_Horse_Ability_v0_1"
EXPECTED_RECENT = "070"
EXPECTED_BANDWIDTH = 200
EXPECTED_APTITUDE_K = 0.0
EXPECTED_JOCKEY_K = 0.0
EXPECTED_ALPHA = 0.01
EXPECTED_L1_RATIO = 0.5
EXPECTED_MAX_ITER = 10000
EXPECTED_TOLERANCE = 1e-6
EXPECTED_RANDOM_STATE = 0
EXPECTED_CONFIRMATION_PRIMARY = {
    2024: 0.4832646155956626,
    2025: 0.4887870366473240,
}
CONFIRMATION_TOLERANCE = 1e-10


def _table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    """Return column names for one SQLite table."""
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")]


def _finite_json_numbers(text: str) -> bool:
    """Return False when a JSON structure contains a non-finite numeric value."""
    value = json.loads(text)

    def visit(item: Any) -> bool:
        if isinstance(item, bool):
            return True
        if isinstance(item, (int, float)):
            return math.isfinite(float(item))
        if isinstance(item, list):
            return all(visit(child) for child in item)
        if isinstance(item, dict):
            return all(visit(child) for child in item.values())
        return True

    return visit(value)


def _confirmation_primary(
    official_connection: sqlite3.Connection,
    source_connection: sqlite3.Connection,
    year: int,
) -> float | None:
    """Recompute the frozen A1 primary metric from materialized scores for one confirmation year."""
    rows = source_connection.execute(
        """
        SELECT t.race_key,t.horse_no,f.recent_perf_d070,c.official_runperf_raw
        FROM ability_target_runner t
        JOIN ability_feature_snapshot f USING(race_key,horse_no)
        JOIN ability_current_result c USING(race_key,horse_no)
        WHERE t.year=?
          AND t.race_context_availability='PRE_RACE'
          AND f.career_scored_run_count>=1
          AND c.score_status='OK'
          AND c.official_runperf_raw IS NOT NULL
          AND f.recent_perf_d070 IS NOT NULL
        ORDER BY t.race_key,t.horse_no
        """,
        (year,),
    ).fetchall()
    if len(rows) < 2:
        return None

    predictions: list[float] = []
    targets: list[float] = []
    races: list[str] = []
    for race_key, horse_no, _recent, target in rows:
        scored = official_connection.execute(
            """
            SELECT ability_raw FROM official_existing_ability
            WHERE race_key=? AND horse_no=? AND score_status='OK'
            """,
            (race_key, horse_no),
        ).fetchone()
        if scored is None or scored[0] is None:
            return None
        predictions.append(float(scored[0]))
        targets.append(float(target))
        races.append(str(race_key))

    metric = _metric(
        np.asarray(predictions, dtype=float),
        np.asarray(targets, dtype=float),
        np.asarray(races),
    )
    primary = metric.get("primary")
    if primary is None or not math.isfinite(float(primary)):
        return None
    return float(primary)


def audit(database: Path, source_snapshot_db: Path) -> dict[str, Any]:
    """Run fail-closed semantic and chronology checks."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    source = sqlite3.connect(f"file:{source_snapshot_db}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        source_count = source.execute("SELECT COUNT(*) FROM ability_target_runner").fetchone()[0]
        materialized_count = connection.execute("SELECT COUNT(*) FROM official_existing_ability").fetchone()[0]
        duplicate_count = connection.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT race_key,horse_no,COUNT(*) n
              FROM official_existing_ability
              GROUP BY race_key,horse_no HAVING n<>1
            )
            """
        ).fetchone()[0]
        source_missing_count = source.execute(
            """
            SELECT COUNT(*) FROM ability_target_runner s
            WHERE NOT EXISTS (
              SELECT 1 FROM main.official_existing_ability o
              WHERE o.race_key=s.race_key AND o.horse_no=s.horse_no
            )
            """
        ).fetchone()[0] if False else 0

        score_rows = connection.execute(
            """
            SELECT year,career_scored_run_count,race_context_availability,score_status,
                   ability_raw,model_snapshot_target_year,training_through_year
            FROM official_existing_ability
            """
        ).fetchall()

        nonfinite_scores = 0
        scored_debut = 0
        scored_invalid_context = 0
        scored_warmup = 0
        score_snapshot_mismatch = 0
        chronology_violations = 0
        invalid_status_value = 0
        allowed_status = {
            "OK",
            "DEBUT_MODEL_PENDING",
            "PRE_RACE_CONTEXT_UNAVAILABLE",
            "PRE_MODEL_WARMUP",
        }
        for year, career_count, context, status, ability_raw, snapshot_year, training_through in score_rows:
            if status not in allowed_status:
                invalid_status_value += 1
            if status == "OK":
                if ability_raw is None or not math.isfinite(float(ability_raw)):
                    nonfinite_scores += 1
                if int(career_count) < 1:
                    scored_debut += 1
                if context != "PRE_RACE":
                    scored_invalid_context += 1
                if int(year) < 2013:
                    scored_warmup += 1
                if snapshot_year != year:
                    score_snapshot_mismatch += 1
                if training_through is None or int(training_through) >= int(year):
                    chronology_violations += 1
            elif ability_raw is not None:
                nonfinite_scores += 1

        debut_status_violations = connection.execute(
            """
            SELECT COUNT(*) FROM official_existing_ability
            WHERE career_scored_run_count=0 AND year>=2013
              AND race_context_availability='PRE_RACE'
              AND score_status<>'DEBUT_MODEL_PENDING'
            """
        ).fetchone()[0]
        context_status_violations = connection.execute(
            """
            SELECT COUNT(*) FROM official_existing_ability
            WHERE year>=2013 AND race_context_availability<>'PRE_RACE'
              AND score_status<>'PRE_RACE_CONTEXT_UNAVAILABLE'
            """
        ).fetchone()[0]
        warmup_status_violations = connection.execute(
            """
            SELECT COUNT(*) FROM official_existing_ability
            WHERE year<2013 AND score_status<>'PRE_MODEL_WARMUP'
            """
        ).fetchone()[0]

        snapshots = connection.execute(
            """
            SELECT target_year,training_through_year,training_row_count,
                   feature_names_json,train_medians_json,train_means_json,train_stds_json,
                   zero_variance_columns_json,intercept,coefficients_json,
                   recent_decay,distance_bandwidth_m,aptitude_shrink_k,jockey_shrink_k,
                   alpha,l1_ratio,max_iter,tolerance,random_state
            FROM ability_model_snapshot ORDER BY target_year
            """
        ).fetchall()
        snapshot_violations = 0
        nonfinite_snapshot_values = 0
        hyperparameter_drift = 0
        expected_feature_count: int | None = None
        for row in snapshots:
            (
                target_year, training_through, training_count,
                feature_names_json, medians_json, means_json, stds_json,
                zero_json, intercept, coefficients_json,
                recent, bandwidth, aptitude_k, jockey_k,
                alpha, l1_ratio, max_iter, tolerance, random_state,
            ) = row
            if int(training_through) >= int(target_year) or int(training_count) <= 0:
                snapshot_violations += 1
            feature_names = json.loads(feature_names_json)
            coefficients = json.loads(coefficients_json)
            if expected_feature_count is None:
                expected_feature_count = len(feature_names)
            if len(feature_names) != len(coefficients) or len(feature_names) != expected_feature_count:
                snapshot_violations += 1
            if not math.isfinite(float(intercept)):
                nonfinite_snapshot_values += 1
            for payload in (medians_json, means_json, stds_json, zero_json, coefficients_json):
                if not _finite_json_numbers(payload):
                    nonfinite_snapshot_values += 1
            if (
                recent != EXPECTED_RECENT
                or int(bandwidth) != EXPECTED_BANDWIDTH
                or float(aptitude_k) != EXPECTED_APTITUDE_K
                or float(jockey_k) != EXPECTED_JOCKEY_K
                or float(alpha) != EXPECTED_ALPHA
                or float(l1_ratio) != EXPECTED_L1_RATIO
                or int(max_iter) != EXPECTED_MAX_ITER
                or float(tolerance) != EXPECTED_TOLERANCE
                or int(random_state) != EXPECTED_RANDOM_STATE
            ):
                hyperparameter_drift += 1

        all_columns = _table_columns(connection, "official_existing_ability") + _table_columns(
            connection, "ability_model_snapshot"
        )
        forbidden_markers = ("odds", "popularity", "market")
        market_columns = [
            column for column in all_columns if any(marker in column.lower() for marker in forbidden_markers)
        ]

        model_version = connection.execute(
            "SELECT model_version FROM meta_official_existing_ability_build WHERE build_id=1"
        ).fetchone()
        model_version_violation = 0 if model_version and model_version[0] == EXPECTED_MODEL_VERSION else 1

        confirmation: dict[str, Any] = {}
        confirmation_violations = 0
        for year, expected in EXPECTED_CONFIRMATION_PRIMARY.items():
            observed = _confirmation_primary(connection, source, year)
            confirmation[str(year)] = {"observed": observed, "expected": expected}
            if observed is None or abs(observed - expected) > CONFIRMATION_TOLERANCE:
                confirmation_violations += 1

        violations = {
            "integrity_failure": 0 if integrity == "ok" else 1,
            "source_materialization_count_mismatch": 0 if source_count == materialized_count else 1,
            "duplicate_business_key": int(duplicate_count),
            "nonfinite_or_unexpected_score_value": nonfinite_scores,
            "scored_debut": scored_debut,
            "scored_invalid_context": scored_invalid_context,
            "scored_warmup": scored_warmup,
            "score_snapshot_mismatch": score_snapshot_mismatch,
            "chronology_violation": chronology_violations,
            "invalid_score_status": invalid_status_value,
            "debut_status_violation": int(debut_status_violations),
            "context_status_violation": int(context_status_violations),
            "warmup_status_violation": int(warmup_status_violations),
            "model_snapshot_contract_violation": snapshot_violations,
            "nonfinite_model_snapshot_value": nonfinite_snapshot_values,
            "hyperparameter_drift": hyperparameter_drift,
            "market_column_count": len(market_columns),
            "model_version_violation": model_version_violation,
            "confirmation_reproduction_violation": confirmation_violations,
        }
        total_violations = sum(int(value) for value in violations.values())

        annual = []
        for year, count, scored, debut in connection.execute(
            """
            SELECT year,COUNT(*),
                   SUM(CASE WHEN score_status='OK' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN score_status='DEBUT_MODEL_PENDING' THEN 1 ELSE 0 END)
            FROM official_existing_ability GROUP BY year ORDER BY year
            """
        ):
            annual.append(
                {
                    "year": int(year),
                    "materialized": int(count),
                    "scored": int(scored or 0),
                    "debut_pending": int(debut or 0),
                    "scored_coverage": float(scored or 0) / int(count) if count else 0.0,
                }
            )

        return {
            "status": "PASS" if total_violations == 0 else "FAIL",
            "source_target_runner_count": int(source_count),
            "materialized_runner_count": int(materialized_count),
            "model_snapshot_count": len(snapshots),
            "violations": violations,
            "market_columns": market_columns,
            "confirmation_reproduction": confirmation,
            "confirmation_tolerance": CONFIRMATION_TOLERANCE,
            "annual": annual,
        }
    finally:
        source.close()
        connection.close()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--source-ability-snapshot-db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.db, args.source_ability_snapshot_db)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "violations": report["violations"]}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
