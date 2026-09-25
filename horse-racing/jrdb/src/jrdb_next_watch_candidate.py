#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build leakage-safe RaceReviewDB next-watch candidate features.

This Turn-2 builder intentionally does not resolve or read next-start outcomes.
All within-horse features use only rows strictly preceding the source start in
horse chronology.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import duckdb


SOURCE_FROM = "2026-05-01"
SOURCE_TO = "2026-09-22"
DISCOVERY_TO = "2026-07-31"
HOLDOUT_FROM = "2026-08-01"
ARTIFACT_TYPE = "jrdb_next_watch_candidate_signals"
FEATURE_VERSION = "next-watch-candidate-v0.1"


class CandidateBuildError(RuntimeError):
    """Raised when the Turn-2 candidate dataset fails its contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CandidateBuildError(f"JSON object required: {path}")
    return value


def extract_current(current_zip: Path, work_root: Path) -> Path:
    """Extract RaceReviewDB CURRENT and return its unique v0_1 root."""
    target = work_root / "current"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    with zipfile.ZipFile(current_zip) as archive:
        archive.extractall(target)

    candidates: list[Path] = []
    for current_path in target.rglob("current.json"):
        current = _read_json(current_path)
        if current.get("artifact_type") == "jrdb_postrace_review":
            candidates.append(current_path.parent)
    if len(candidates) != 1:
        raise CandidateBuildError(
            f"unique RaceReviewDB root required: {candidates}"
        )
    return candidates[0]


def relation_paths(
    root: Path,
    manifest: dict[str, object],
    relation: str,
) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise CandidateBuildError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, dict):
        raise CandidateBuildError(f"relation missing: {relation}")

    paths: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise CandidateBuildError(f"missing Parquet object: {path}")
        paths.append(path)
    if not paths:
        raise CandidateBuildError(f"no Parquet objects: {relation}")
    return paths


def _table_sql(paths: list[Path]) -> tuple[str, list[str]]:
    marks = ", ".join("?" for _ in paths)
    return (
        "read_parquet(["
        + marks
        + "], union_by_name=true, hive_partitioning=false)",
        [str(path) for path in paths],
    )


def build_candidate(
    current_root: Path,
    output_path: Path,
) -> dict[str, object]:
    """Build source-start features without any target/next-start information."""
    current = _read_json(current_root / "current.json")
    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise CandidateBuildError("RaceReviewDB CURRENT manifest missing")
    manifest = _read_json(current_root / manifest_ref)

    if manifest.get("validation_status") != "PASS":
        raise CandidateBuildError("RaceReviewDB manifest is not PASS")
    if str(manifest.get("period_to") or "") < SOURCE_TO:
        raise CandidateBuildError(
            f"RaceReviewDB period_to too old: {manifest.get('period_to')}"
        )

    hp_paths = relation_paths(
        current_root, manifest, "fact_horse_performance"
    )
    rr_paths = relation_paths(
        current_root, manifest, "fact_race_review"
    )
    rc_paths = relation_paths(
        current_root, manifest, "fact_race_context"
    )

    hp_sql, hp_params = _table_sql(hp_paths)
    rr_sql, rr_params = _table_sql(rr_paths)
    rc_sql, rc_params = _table_sql(rc_paths)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    try:
        query = f"""
        COPY (
          WITH hp_valid AS (
            SELECT
              *,
              -horse_adjusted_delta_per_1000m AS performance_signal,
              CASE
                WHEN distance_m < 1400 THEN 'SPRINT'
                WHEN distance_m < 1800 THEN 'MILE'
                WHEN distance_m < 2200 THEN 'MIDDLE'
                ELSE 'LONG'
              END AS distance_category
            FROM {hp_sql}
            WHERE horse_id IS NOT NULL
              AND TRIM(horse_id) <> ''
              AND COALESCE(finish, 0) > 0
              AND COALESCE(time_sec, 0) > 0
              AND COALESCE(surface_code, '') <> '3'
          ),
          hp_history AS (
            SELECT
              *,
              LAG(race_date, 1) OVER horse_order AS previous_start_date,
              COUNT(*) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
              ) AS prior_start_count,
              AVG(performance_signal) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
              ) AS prior3_performance_mean,
              AVG(performance_signal) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
              ) AS prior5_performance_mean,
              MAX(performance_signal) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
              ) AS prior5_performance_best,
              AVG(last3f_speed_percentile) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
              ) AS prior3_last3f_pct_mean,
              AVG(closing_gain_sec) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
              ) AS prior5_closing_gain_mean
            FROM hp_valid
            WINDOW horse_order AS (
              PARTITION BY horse_id
              ORDER BY race_date, race_key, horse_no
            )
          ),
          source AS (
            SELECT
              h.*,
              CASE
                WHEN h.race_date <= DATE '{DISCOVERY_TO}'
                  THEN 'DISCOVERY'
                ELSE 'HOLDOUT'
              END AS evaluation_period,
              date_diff(
                'day',
                h.previous_start_date,
                h.race_date
              ) AS days_since_previous_start,
              h.performance_signal - h.prior3_performance_mean
                AS performance_vs_prior3,
              h.performance_signal - h.prior5_performance_mean
                AS performance_vs_prior5,
              h.performance_signal - h.prior5_performance_best
                AS performance_vs_prior5_best,
              CASE
                WHEN h.prior5_performance_best IS NULL THEN NULL
                WHEN h.performance_signal > h.prior5_performance_best THEN TRUE
                ELSE FALSE
              END AS is_recent5_performance_best,
              h.last3f_speed_percentile - h.prior3_last3f_pct_mean
                AS last3f_pct_vs_prior3,
              h.closing_gain_sec - h.prior5_closing_gain_mean
                AS closing_gain_vs_prior5
            FROM hp_history h
            WHERE h.race_date BETWEEN
              DATE '{SOURCE_FROM}' AND DATE '{SOURCE_TO}'
          )
          SELECT
            s.*,
            r.time_delta_sec AS race_time_delta_sec,
            r.time_delta_per_1000m AS race_time_delta_per_1000m,
            r.standard_confidence AS race_standard_confidence,
            r.standard_sample_count AS race_standard_sample_count,
            r.standard_scope_level AS race_standard_scope_level,
            c.race_pace_code,
            c.race_pace_code_conflict,
            c.first3f_reference_sec,
            c.last3f_reference_sec,
            c.pace_balance_sec,
            c.pace_balance_percentile,
            c.pace_sample_count,
            c.pace_scope_level,
            '{FEATURE_VERSION}' AS candidate_feature_version,
            '{manifest.get("generation_id")}' AS source_generation_id
          FROM source s
          JOIN {rr_sql} r USING (race_key)
          JOIN {rc_sql} c USING (race_key)
          ORDER BY s.race_date, s.race_key, s.horse_no
        ) TO ? (
          FORMAT PARQUET,
          COMPRESSION ZSTD
        )
        """
        params: list[object] = [
            *hp_params,
            *rr_params,
            *rc_params,
            str(output_path),
        ]
        connection.execute(query, params)

        audit_sql = """
        SELECT
          COUNT(*) AS row_count,
          COUNT(DISTINCT race_horse_key) AS distinct_source_key,
          COUNT(DISTINCT horse_id) AS distinct_horse_count,
          CAST(MIN(race_date) AS VARCHAR) AS min_source_date,
          CAST(MAX(race_date) AS VARCHAR) AS max_source_date,
          SUM(CASE WHEN evaluation_period = 'DISCOVERY' THEN 1 ELSE 0 END)
            AS discovery_rows,
          SUM(CASE WHEN evaluation_period = 'HOLDOUT' THEN 1 ELSE 0 END)
            AS holdout_rows,
          SUM(CASE WHEN horse_id IS NULL OR TRIM(horse_id) = '' THEN 1 ELSE 0 END)
            AS empty_horse_id_rows,
          SUM(CASE WHEN finish IS NULL OR finish <= 0 THEN 1 ELSE 0 END)
            AS invalid_finish_rows,
          SUM(CASE WHEN time_sec IS NULL OR time_sec <= 0 THEN 1 ELSE 0 END)
            AS invalid_time_rows,
          SUM(CASE WHEN surface_code = '3' THEN 1 ELSE 0 END)
            AS jump_rows,
          SUM(
            CASE
              WHEN previous_start_date IS NOT NULL
               AND previous_start_date >= race_date
              THEN 1 ELSE 0
            END
          ) AS history_date_leak_rows
        FROM read_parquet(?)
        """
        names = [
            item[0]
            for item in connection.execute(
                audit_sql, [str(output_path)]
            ).description
        ]
        values = connection.execute(
            audit_sql, [str(output_path)]
        ).fetchone()
        if values is None:
            raise CandidateBuildError("candidate audit returned no row")
        audit = dict(zip(names, values))

        duplicates = int(audit["row_count"]) - int(
            audit["distinct_source_key"]
        )
        hard_errors: list[str] = []
        if duplicates != 0:
            hard_errors.append(f"duplicate source keys: {duplicates}")
        for field in (
            "empty_horse_id_rows",
            "invalid_finish_rows",
            "invalid_time_rows",
            "jump_rows",
            "history_date_leak_rows",
        ):
            if int(audit[field]) != 0:
                hard_errors.append(f"{field}: {audit[field]}")
        if audit["min_source_date"] < SOURCE_FROM:
            hard_errors.append("source lower bound violation")
        if audit["max_source_date"] > SOURCE_TO:
            hard_errors.append("source upper bound violation")
        if int(audit["discovery_rows"]) <= 0:
            hard_errors.append("empty Discovery population")
        if int(audit["holdout_rows"]) <= 0:
            hard_errors.append("empty Holdout population")

        nulls = connection.execute(
            """
            SELECT
              SUM(performance_signal IS NULL),
              SUM(last3f_speed_percentile IS NULL),
              SUM(closing_gain_sec IS NULL),
              SUM(prior3_performance_mean IS NULL),
              SUM(prior5_performance_mean IS NULL),
              SUM(prior3_last3f_pct_mean IS NULL),
              SUM(prior5_closing_gain_mean IS NULL)
            FROM read_parquet(?)
            """,
            [str(output_path)],
        ).fetchone()

        return {
            "status": "PASS" if not hard_errors else "FAIL",
            "artifact_type": ARTIFACT_TYPE,
            "candidate_feature_version": FEATURE_VERSION,
            "source_generation_id": manifest.get("generation_id"),
            "source_period_from": SOURCE_FROM,
            "source_period_to": SOURCE_TO,
            "discovery_to": DISCOVERY_TO,
            "holdout_from": HOLDOUT_FROM,
            "row_count": int(audit["row_count"]),
            "distinct_source_key": int(audit["distinct_source_key"]),
            "distinct_horse_count": int(audit["distinct_horse_count"]),
            "min_source_date": audit["min_source_date"],
            "max_source_date": audit["max_source_date"],
            "discovery_rows": int(audit["discovery_rows"]),
            "holdout_rows": int(audit["holdout_rows"]),
            "hard_errors": hard_errors,
            "null_counts": {
                "performance_signal": int(nulls[0]),
                "last3f_speed_percentile": int(nulls[1]),
                "closing_gain_sec": int(nulls[2]),
                "prior3_performance_mean": int(nulls[3]),
                "prior5_performance_mean": int(nulls[4]),
                "prior3_last3f_pct_mean": int(nulls[5]),
                "prior5_closing_gain_mean": int(nulls[6]),
            },
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    current_root = extract_current(args.current_zip, args.work_root)
    summary = build_candidate(current_root, args.output)
    summary["output_file"] = args.output.name
    summary["output_size_bytes"] = args.output.stat().st_size
    summary["output_sha256"] = _sha256(args.output)

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
