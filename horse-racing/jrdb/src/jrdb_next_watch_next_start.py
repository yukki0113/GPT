#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve immediate next JRA starts for RaceReviewDB Next-Watch Turn 3.

This builder consumes the immutable Turn-2 candidate artifact and the same
RaceReviewDB CURRENT generation. It never rebuilds source features.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import duckdb


ARTIFACT_TYPE = "jrdb_next_watch_next_start"
OUTCOME_VERSION = "next-watch-next-start-v0.1"


class NextStartBuildError(RuntimeError):
    """Raised when Turn-3 next-start resolution violates its contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NextStartBuildError(f"JSON object required: {path}")
    return value


def _extract_zip(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)


def _race_review_root(current_zip: Path, work_root: Path) -> Path:
    target = work_root / "current"
    _extract_zip(current_zip, target)
    roots: list[Path] = []
    for pointer in target.rglob("current.json"):
        current = _read_json(pointer)
        if current.get("artifact_type") == "jrdb_postrace_review":
            roots.append(pointer.parent)
    if len(roots) != 1:
        raise NextStartBuildError(f"unique RaceReviewDB root required: {roots}")
    return roots[0]


def _candidate_paths(turn2_zip: Path, work_root: Path) -> tuple[Path, dict[str, object]]:
    target = work_root / "turn2"
    _extract_zip(turn2_zip, target)
    candidates = list(target.rglob("next_watch_candidate_signals.parquet"))
    audits = list(target.rglob("candidate_signals_audit.json"))
    if len(candidates) != 1 or len(audits) != 1:
        raise NextStartBuildError(
            f"unique Turn2 candidate/audit required: {candidates} / {audits}"
        )
    audit = _read_json(audits[0])
    if audit.get("status") != "PASS":
        raise NextStartBuildError("Turn2 checkpoint is not PASS")
    return candidates[0], audit


def _relation_paths(
    root: Path,
    manifest: dict[str, object],
    relation: str,
) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise NextStartBuildError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, dict):
        raise NextStartBuildError(f"relation missing: {relation}")

    paths: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise NextStartBuildError(f"missing Parquet object: {path}")
        paths.append(path)
    if not paths:
        raise NextStartBuildError(f"no Parquet objects: {relation}")
    return paths


def _table_sql(paths: list[Path]) -> tuple[str, list[str]]:
    marks = ", ".join("?" for _ in paths)
    return (
        "read_parquet(["
        + marks
        + "], union_by_name=true, hive_partitioning=false)",
        [str(path) for path in paths],
    )


def _literal(path: Path) -> str:
    return str(path).replace("'", "''")


def build(
    *,
    turn2_zip: Path,
    current_zip: Path,
    work_root: Path,
    outcome_path: Path,
    fact_path: Path,
) -> dict[str, object]:
    """Build one next-start row per Turn-2 source row."""
    candidate_path, turn2_audit = _candidate_paths(turn2_zip, work_root)
    current_root = _race_review_root(current_zip, work_root)

    current = _read_json(current_root / "current.json")
    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise NextStartBuildError("RaceReviewDB CURRENT manifest missing")
    manifest = _read_json(current_root / manifest_ref)
    if manifest.get("validation_status") != "PASS":
        raise NextStartBuildError("RaceReviewDB CURRENT manifest is not PASS")

    expected_generation = str(turn2_audit.get("source_generation_id") or "")
    actual_generation = str(manifest.get("generation_id") or "")
    if expected_generation != actual_generation:
        raise NextStartBuildError(
            "Turn2 / RaceReviewDB generation mismatch: "
            f"{expected_generation} != {actual_generation}"
        )

    hp_paths = _relation_paths(
        current_root, manifest, "fact_horse_performance"
    )
    hp_sql, hp_params = _table_sql(hp_paths)

    outcome_path.parent.mkdir(parents=True, exist_ok=True)
    fact_path.parent.mkdir(parents=True, exist_ok=True)

    candidate_sql = _literal(candidate_path)
    outcome_sql = _literal(outcome_path)
    fact_sql = _literal(fact_path)
    horizon = str(manifest.get("period_to") or "")

    connection = duckdb.connect(":memory:")
    try:
        outcome_query = f"""
        COPY (
          WITH source AS (
            SELECT
              race_horse_key AS source_race_horse_key,
              race_key AS source_race_key,
              horse_no AS source_horse_no,
              horse_id,
              horse_name AS source_horse_name,
              race_date AS source_date,
              finish AS source_finish,
              evaluation_period
            FROM read_parquet('{candidate_sql}')
          ),
          all_starts AS (
            SELECT
              race_horse_key,
              race_key,
              horse_no,
              horse_id,
              horse_name,
              race_date,
              finish,
              time_sec,
              winner_gap_sec,
              venue_code,
              surface_code,
              distance_m,
              declared_class_group,
              last3f_rank,
              last3f_speed_percentile,
              horse_adjusted_delta_per_1000m,
              time_class_equivalent,
              performance_label
            FROM {hp_sql}
            WHERE horse_id IS NOT NULL
              AND TRIM(horse_id) <> ''
          ),
          ranked AS (
            SELECT
              s.*,
              t.race_horse_key AS next_race_horse_key,
              t.race_key AS next_race_key,
              t.horse_no AS next_horse_no,
              t.horse_name AS next_horse_name,
              t.race_date AS next_date,
              t.finish AS next_finish_raw,
              t.time_sec AS next_time_sec,
              t.winner_gap_sec AS next_winner_gap_sec,
              t.venue_code AS next_venue_code,
              t.surface_code AS next_surface_code,
              t.distance_m AS next_distance_m,
              t.declared_class_group AS next_declared_class_group,
              t.last3f_rank AS next_last3f_rank,
              t.last3f_speed_percentile AS next_last3f_speed_percentile,
              t.horse_adjusted_delta_per_1000m
                AS next_horse_adjusted_delta_per_1000m,
              t.time_class_equivalent AS next_time_class_equivalent,
              t.performance_label AS next_performance_label,
              ROW_NUMBER() OVER (
                PARTITION BY s.source_race_horse_key
                ORDER BY t.race_date, t.race_key, t.horse_no
              ) AS next_rank
            FROM source s
            LEFT JOIN all_starts t
              ON t.horse_id = s.horse_id
             AND t.race_date > s.source_date
          ),
          chosen AS (
            SELECT *
            FROM ranked
            WHERE next_rank = 1
          )
          SELECT
            source_race_horse_key,
            source_race_key,
            source_horse_no,
            horse_id,
            source_horse_name,
            source_date,
            source_finish,
            evaluation_period,
            next_race_horse_key,
            next_race_key,
            next_horse_no,
            next_horse_name,
            next_date,
            next_finish_raw,
            next_time_sec,
            next_winner_gap_sec,
            next_venue_code,
            next_surface_code,
            next_distance_m,
            next_declared_class_group,
            next_last3f_rank,
            next_last3f_speed_percentile,
            next_horse_adjusted_delta_per_1000m,
            next_time_class_equivalent,
            next_performance_label,
            CASE
              WHEN next_date IS NULL THEN 'NO_NEXT_START_BY_HORIZON'
              WHEN COALESCE(next_surface_code, '') = '3'
                THEN 'RESOLVED_JUMP'
              WHEN COALESCE(next_finish_raw, 0) <= 0
                OR COALESCE(next_time_sec, 0) <= 0
                THEN 'RESOLVED_INVALID_RESULT'
              ELSE 'RESOLVED_FLAT_VALID'
            END AS next_start_status,
            CASE
              WHEN next_date IS NOT NULL
                THEN date_diff('day', source_date, next_date)
              ELSE NULL
            END AS days_to_next_start,
            CASE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 0
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE ELSE FALSE
            END AS phase1_eligible,
            CASE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 0
               AND COALESCE(next_time_sec, 0) > 0
              THEN next_finish_raw
              ELSE NULL
            END AS next_finish,
            CASE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) = 1
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 1
               AND COALESCE(next_time_sec, 0) > 0
              THEN FALSE
              ELSE NULL
            END AS next_win,
            CASE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) BETWEEN 1 AND 3
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 3
               AND COALESCE(next_time_sec, 0) > 0
              THEN FALSE
              ELSE NULL
            END AS next_top3,
            CASE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) BETWEEN 1 AND 5
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 5
               AND COALESCE(next_time_sec, 0) > 0
              THEN FALSE
              ELSE NULL
            END AS next_top5,
            CASE
              WHEN COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 0
               AND COALESCE(next_time_sec, 0) > 0
              THEN source_finish - next_finish_raw
              ELSE NULL
            END AS finish_improvement,
            '{OUTCOME_VERSION}' AS next_start_outcome_version,
            '{actual_generation}' AS source_generation_id,
            DATE '{horizon}' AS observation_horizon
          FROM chosen
          ORDER BY source_date, source_race_key, source_horse_no
        ) TO '{outcome_sql}' (
          FORMAT PARQUET,
          COMPRESSION ZSTD
        )
        """
        connection.execute(outcome_query, hp_params)

        fact_query = f"""
        COPY (
          SELECT
            c.*,
            o.next_race_horse_key,
            o.next_race_key,
            o.next_horse_no,
            o.next_horse_name,
            o.next_date,
            o.next_start_status,
            o.days_to_next_start,
            o.phase1_eligible,
            o.next_finish,
            o.next_win,
            o.next_top3,
            o.next_top5,
            o.finish_improvement,
            o.next_time_sec,
            o.next_winner_gap_sec,
            o.next_venue_code,
            o.next_surface_code,
            o.next_distance_m,
            o.next_declared_class_group,
            o.next_last3f_rank,
            o.next_last3f_speed_percentile,
            o.next_horse_adjusted_delta_per_1000m,
            o.next_time_class_equivalent,
            o.next_performance_label,
            o.next_start_outcome_version,
            o.observation_horizon
          FROM read_parquet('{candidate_sql}') c
          JOIN read_parquet('{outcome_sql}') o
            ON c.race_horse_key = o.source_race_horse_key
          ORDER BY c.race_date, c.race_key, c.horse_no
        ) TO '{fact_sql}' (
          FORMAT PARQUET,
          COMPRESSION ZSTD
        )
        """
        connection.execute(fact_query)

        audit_row = connection.execute(
            f"""
            SELECT
              COUNT(*) AS row_count,
              COUNT(DISTINCT source_race_horse_key) AS distinct_source_key,
              SUM(CASE WHEN next_start_status = 'RESOLVED_FLAT_VALID'
                       THEN 1 ELSE 0 END) AS resolved_flat_valid,
              SUM(CASE WHEN next_start_status = 'RESOLVED_JUMP'
                       THEN 1 ELSE 0 END) AS resolved_jump,
              SUM(CASE WHEN next_start_status = 'RESOLVED_INVALID_RESULT'
                       THEN 1 ELSE 0 END) AS resolved_invalid,
              SUM(CASE WHEN next_start_status = 'NO_NEXT_START_BY_HORIZON'
                       THEN 1 ELSE 0 END) AS no_next_by_horizon,
              SUM(CASE WHEN phase1_eligible THEN 1 ELSE 0 END)
                AS phase1_eligible_rows,
              SUM(CASE
                    WHEN next_date IS NOT NULL
                     AND next_date <= source_date
                    THEN 1 ELSE 0 END) AS nonfuture_target_rows,
              SUM(CASE
                    WHEN next_date IS NOT NULL
                     AND days_to_next_start <= 0
                    THEN 1 ELSE 0 END) AS nonpositive_gap_rows,
              MIN(CASE WHEN next_date IS NOT NULL
                       THEN days_to_next_start ELSE NULL END)
                AS min_days_to_next,
              MAX(CASE WHEN next_date IS NOT NULL
                       THEN days_to_next_start ELSE NULL END)
                AS max_days_to_next
            FROM read_parquet('{outcome_sql}')
            """
        ).fetchone()
        if audit_row is None:
            raise NextStartBuildError("Turn3 audit returned no row")

        names = [
            "row_count",
            "distinct_source_key",
            "resolved_flat_valid",
            "resolved_jump",
            "resolved_invalid",
            "no_next_by_horizon",
            "phase1_eligible_rows",
            "nonfuture_target_rows",
            "nonpositive_gap_rows",
            "min_days_to_next",
            "max_days_to_next",
        ]
        audit = dict(zip(names, audit_row))

        candidate_count = int(turn2_audit.get("row_count") or 0)
        hard_errors: list[str] = []
        if int(audit["row_count"]) != candidate_count:
            hard_errors.append(
                f"row_count mismatch: {audit['row_count']} != {candidate_count}"
            )
        if int(audit["distinct_source_key"]) != candidate_count:
            hard_errors.append("duplicate/missing source keys")
        if int(audit["nonfuture_target_rows"]) != 0:
            hard_errors.append(
                f"nonfuture target rows: {audit['nonfuture_target_rows']}"
            )
        if int(audit["nonpositive_gap_rows"]) != 0:
            hard_errors.append(
                f"nonpositive target gaps: {audit['nonpositive_gap_rows']}"
            )

        fact_count = connection.execute(
            f"SELECT COUNT(*) FROM read_parquet('{fact_sql}')"
        ).fetchone()[0]
        if int(fact_count) != candidate_count:
            hard_errors.append(
                f"joined fact mismatch: {fact_count} != {candidate_count}"
            )

        discovery = connection.execute(
            f"""
            SELECT
              COUNT(*) AS n,
              SUM(CASE WHEN phase1_eligible THEN 1 ELSE 0 END) AS eligible
            FROM read_parquet('{outcome_sql}')
            WHERE evaluation_period = 'DISCOVERY'
            """
        ).fetchone()
        holdout = connection.execute(
            f"""
            SELECT
              COUNT(*) AS n,
              SUM(CASE WHEN phase1_eligible THEN 1 ELSE 0 END) AS eligible
            FROM read_parquet('{outcome_sql}')
            WHERE evaluation_period = 'HOLDOUT'
            """
        ).fetchone()

        return {
            "status": "PASS" if not hard_errors else "FAIL",
            "artifact_type": ARTIFACT_TYPE,
            "next_start_outcome_version": OUTCOME_VERSION,
            "source_generation_id": actual_generation,
            "observation_horizon": horizon,
            "turn2_row_count": candidate_count,
            "row_count": int(audit["row_count"]),
            "distinct_source_key": int(audit["distinct_source_key"]),
            "resolved_flat_valid": int(audit["resolved_flat_valid"]),
            "resolved_jump": int(audit["resolved_jump"]),
            "resolved_invalid": int(audit["resolved_invalid"]),
            "no_next_by_horizon": int(audit["no_next_by_horizon"]),
            "phase1_eligible_rows": int(audit["phase1_eligible_rows"]),
            "min_days_to_next": audit["min_days_to_next"],
            "max_days_to_next": audit["max_days_to_next"],
            "discovery_rows": int(discovery[0]),
            "discovery_phase1_eligible": int(discovery[1] or 0),
            "holdout_rows": int(holdout[0]),
            "holdout_phase1_eligible": int(holdout[1] or 0),
            "joined_fact_rows": int(fact_count),
            "hard_errors": hard_errors,
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn2-zip", type=Path, required=True)
    parser.add_argument("--current-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--outcome-output", type=Path, required=True)
    parser.add_argument("--fact-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    summary = build(
        turn2_zip=args.turn2_zip,
        current_zip=args.current_zip,
        work_root=args.work_root,
        outcome_path=args.outcome_output,
        fact_path=args.fact_output,
    )
    summary["outcome_file"] = args.outcome_output.name
    summary["outcome_size_bytes"] = args.outcome_output.stat().st_size
    summary["outcome_sha256"] = _sha256(args.outcome_output)
    summary["fact_file"] = args.fact_output.name
    summary["fact_size_bytes"] = args.fact_output.stat().st_size
    summary["fact_sha256"] = _sha256(args.fact_output)

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
