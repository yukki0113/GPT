#!/usr/bin/env python3
"""Materialize official Existing-Horse Ability v0.1 with annual as-of model snapshots."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import ElasticNet

from compare_jrdb_ability_models import _feature_vector, _fold_preprocess

BUILDER_VERSION = "build_jrdb_official_existing_ability_v0_1"
SCHEMA_VERSION = "jrdb_official_existing_ability_schema_v0_1"
MODEL_VERSION = "Existing_Horse_Ability_v0_1"
FIRST_MODEL_YEAR = 2013
RECENT = "070"
BANDWIDTH = 200
APTITUDE_K = 0
JOCKEY_K = 0
ALPHA = 0.01
L1_RATIO = 0.5
MAX_ITER = 10000
TOLERANCE = 1e-6
RANDOM_STATE = 0


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    """Calculate a deterministic SHA-256 digest for one source database."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _load_all_rows(database: Path) -> list[dict[str, Any]]:
    """Load all target rows and any separate evaluation labels from the Ability snapshot."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
              t.race_date,t.race_key,t.horse_no,t.horse_id,t.year,
              t.race_context_availability,t.weight_relative,
              f.*,
              c.score_status AS target_score_status,
              c.official_runperf_raw
            FROM ability_target_runner t
            JOIN ability_feature_snapshot f USING(race_key,horse_no)
            LEFT JOIN ability_current_result c USING(race_key,horse_no)
            ORDER BY t.year,t.race_date,t.race_key,t.horse_no
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _complete_feature_names(values: list[float | None], names: list[str]) -> list[str]:
    """Return one name per frozen numeric model column without changing values.

    The frozen comparison vector has always contained an explicit final
    ``log1p_career`` missing flag.  Because career count is structurally
    present for eligible existing horses, that column is the constant value
    zero.  The original comparison helper omitted only the metadata label for
    this already-present 22nd column.  Naming it here preserves the exact
    trained matrix and coefficients while making annual model snapshots fully
    self-describing.
    """
    if len(names) + 1 == len(values):
        names = [*names, "log1p_career_missing"]
    if len(names) != len(values):
        raise ValueError(
            "Ability feature-name/value length mismatch: "
            f"names={len(names)} values={len(values)}"
        )
    return names


def _feature_matrix(rows: list[dict[str, Any]]) -> tuple[np.ndarray, list[str]]:
    """Build the exact frozen Existing-Horse Ability v0.1 feature matrix."""
    vectors: list[list[float | None]] = []
    feature_names: list[str] | None = None
    for row in rows:
        values, names = _feature_vector(row, RECENT, BANDWIDTH, APTITUDE_K, JOCKEY_K)
        names = _complete_feature_names(values, names)
        vectors.append(values)
        if feature_names is None:
            feature_names = names
        elif feature_names != names:
            raise ValueError("Ability feature-name drift detected")
    if feature_names is None:
        raise ValueError("cannot build feature matrix from zero rows")
    return np.asarray(vectors, dtype=float), feature_names


def _fit_snapshot(
    training_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
) -> tuple[np.ndarray, dict[str, Any]]:
    """Fit the frozen Elastic Net on prior-year labels and score one target year."""
    if not training_rows:
        raise ValueError("no prior labeled rows for Ability model snapshot")
    if not target_rows:
        raise ValueError("no target rows for Ability model snapshot")

    x_train_raw, feature_names = _feature_matrix(training_rows)
    x_target_raw, target_names = _feature_matrix(target_rows)
    if target_names != feature_names:
        raise ValueError("training/target feature-name mismatch")

    y_train = np.asarray([float(row["official_runperf_raw"]) for row in training_rows], dtype=float)
    x_train, x_target, preprocessing = _fold_preprocess(x_train_raw, x_target_raw)

    model = ElasticNet(
        alpha=ALPHA,
        l1_ratio=L1_RATIO,
        fit_intercept=True,
        max_iter=MAX_ITER,
        tol=TOLERANCE,
        random_state=RANDOM_STATE,
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_target)
    if not np.all(np.isfinite(predictions)):
        raise ValueError("non-finite Existing-Horse Ability prediction")
    if not math.isfinite(float(model.intercept_)):
        raise ValueError("non-finite Existing-Horse Ability intercept")
    if not np.all(np.isfinite(model.coef_)):
        raise ValueError("non-finite Existing-Horse Ability coefficients")

    snapshot = {
        "feature_names": feature_names,
        "train_medians": preprocessing["train_medians"],
        "train_means": preprocessing["train_means"],
        "train_stds": preprocessing["train_stds"],
        "zero_variance_columns": preprocessing["zero_variance_columns"],
        "intercept": float(model.intercept_),
        "coefficients": [float(value) for value in model.coef_],
    }
    return predictions, snapshot


def build(source_db: Path, output_db: Path, schema_path: Path) -> dict[str, Any]:
    """Create one complete Existing-Horse Ability v0.1 materialization database."""
    if output_db.exists():
        output_db.unlink()

    rows = _load_all_rows(source_db)
    if not rows:
        raise ValueError("Ability snapshot contains no target rows")

    started_at = _utc_now()
    output_db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output_db)
    try:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        source_year_min = min(int(row["year"]) for row in rows)
        source_year_max = max(int(row["year"]) for row in rows)
        connection.execute(
            """
            INSERT INTO meta_official_existing_ability_build(
              build_id,builder_version,schema_version,model_version,
              source_ability_snapshot_db_path,source_ability_snapshot_db_sha256,
              started_at,status,source_year_min,source_year_max,source_target_runner_count
            ) VALUES(1,?,?,?,?,?,?,?, ?,?,?)
            """,
            (
                BUILDER_VERSION,
                SCHEMA_VERSION,
                MODEL_VERSION,
                str(source_db),
                _sha256(source_db),
                started_at,
                "BUILDING",
                source_year_min,
                source_year_max,
                len(rows),
            ),
        )

        materialized: dict[tuple[str, int], tuple[Any, ...]] = {}
        model_years = sorted({int(row["year"]) for row in rows if int(row["year"]) >= FIRST_MODEL_YEAR})

        for row in rows:
            year = int(row["year"])
            career_count = int(row["career_scored_run_count"])
            context = str(row["race_context_availability"])
            if year < FIRST_MODEL_YEAR:
                status = "PRE_MODEL_WARMUP"
                provenance = "Existing-Horse Ability v0.1 unavailable before first model year"
            elif context != "PRE_RACE":
                status = "PRE_RACE_CONTEXT_UNAVAILABLE"
                provenance = "Target race context is not valid PRE_RACE"
            elif career_count < 1:
                status = "DEBUT_MODEL_PENDING"
                provenance = "Dedicated Debut Ability model not yet published"
            else:
                status = "PENDING_MODEL_SCORE"
                provenance = "Awaiting annual Existing-Horse Ability v0.1 model snapshot"
            materialized[(str(row["race_key"]), int(row["horse_no"]))] = (
                str(row["race_key"]),
                str(row["race_date"]),
                year,
                int(row["horse_no"]),
                row.get("horse_id"),
                career_count,
                context,
                status,
                None,
                None,
                None,
                provenance,
            )

        for target_year in model_years:
            training_rows = [
                row
                for row in rows
                if int(row["year"]) < target_year
                and str(row["race_context_availability"]) == "PRE_RACE"
                and int(row["career_scored_run_count"]) >= 1
                and row.get("target_score_status") == "OK"
                and row.get("official_runperf_raw") is not None
            ]
            target_rows = [
                row
                for row in rows
                if int(row["year"]) == target_year
                and str(row["race_context_availability"]) == "PRE_RACE"
                and int(row["career_scored_run_count"]) >= 1
            ]
            if not target_rows:
                continue
            if not training_rows:
                raise ValueError(f"no training labels before Ability target year {target_year}")

            training_through_year = max(int(row["year"]) for row in training_rows)
            if training_through_year >= target_year:
                raise ValueError("Ability annual model chronology violation")

            predictions, snapshot = _fit_snapshot(training_rows, target_rows)
            connection.execute(
                """
                INSERT INTO ability_model_snapshot(
                  target_year,training_through_year,training_row_count,
                  feature_names_json,train_medians_json,train_means_json,train_stds_json,
                  zero_variance_columns_json,intercept,coefficients_json,
                  recent_decay,distance_bandwidth_m,aptitude_shrink_k,jockey_shrink_k,
                  alpha,l1_ratio,max_iter,tolerance,random_state,fitter_version,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    target_year,
                    training_through_year,
                    len(training_rows),
                    json.dumps(snapshot["feature_names"], ensure_ascii=False),
                    json.dumps(snapshot["train_medians"], ensure_ascii=False, allow_nan=False),
                    json.dumps(snapshot["train_means"], ensure_ascii=False, allow_nan=False),
                    json.dumps(snapshot["train_stds"], ensure_ascii=False, allow_nan=False),
                    json.dumps(snapshot["zero_variance_columns"], ensure_ascii=False),
                    snapshot["intercept"],
                    json.dumps(snapshot["coefficients"], ensure_ascii=False, allow_nan=False),
                    RECENT,
                    BANDWIDTH,
                    APTITUDE_K,
                    JOCKEY_K,
                    ALPHA,
                    L1_RATIO,
                    MAX_ITER,
                    TOLERANCE,
                    RANDOM_STATE,
                    "sklearn.ElasticNet",
                    _utc_now(),
                ),
            )

            for row, prediction in zip(target_rows, predictions, strict=True):
                key = (str(row["race_key"]), int(row["horse_no"]))
                materialized[key] = (
                    str(row["race_key"]),
                    str(row["race_date"]),
                    target_year,
                    int(row["horse_no"]),
                    row.get("horse_id"),
                    int(row["career_scored_run_count"]),
                    str(row["race_context_availability"]),
                    "OK",
                    float(prediction),
                    target_year,
                    training_through_year,
                    f"{MODEL_VERSION}|year={target_year}|train_through={training_through_year}",
                )

        connection.executemany(
            """
            INSERT INTO official_existing_ability(
              race_key,race_date,year,horse_no,horse_id,career_scored_run_count,
              race_context_availability,score_status,ability_raw,
              model_snapshot_target_year,training_through_year,score_provenance
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            list(materialized.values()),
        )

        scored_count = connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE score_status='OK'"
        ).fetchone()[0]
        debut_count = connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE score_status='DEBUT_MODEL_PENDING'"
        ).fetchone()[0]
        context_count = connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE score_status='PRE_RACE_CONTEXT_UNAVAILABLE'"
        ).fetchone()[0]
        warmup_count = connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE score_status='PRE_MODEL_WARMUP'"
        ).fetchone()[0]
        pending_count = connection.execute(
            "SELECT COUNT(*) FROM official_existing_ability WHERE score_status='PENDING_MODEL_SCORE'"
        ).fetchone()[0]
        if pending_count:
            raise ValueError(f"unresolved pending Ability rows: {pending_count}")

        finished_at = _utc_now()
        connection.execute(
            """
            UPDATE meta_official_existing_ability_build
            SET finished_at=?,status='COMPLETE',materialized_runner_count=?,scored_runner_count=?,
                debut_unscored_count=?,context_unavailable_count=?,warmup_unscored_count=?,message=?
            WHERE build_id=1
            """,
            (
                finished_at,
                len(materialized),
                scored_count,
                debut_count,
                context_count,
                warmup_count,
                "Existing-Horse Ability v0.1 annual as-of materialization complete",
            ),
        )
        connection.commit()
        return {
            "status": "COMPLETE",
            "source_runner_count": len(rows),
            "materialized_runner_count": len(materialized),
            "scored_runner_count": int(scored_count),
            "debut_unscored_count": int(debut_count),
            "context_unavailable_count": int(context_count),
            "warmup_unscored_count": int(warmup_count),
            "model_years": model_years,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ability-snapshot-db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_official_existing_ability_schema_v0_1.sql",
    )
    args = parser.parse_args()
    result = build(args.ability_snapshot_db, args.out, args.schema)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
