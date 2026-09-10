#!/usr/bin/env python3
"""Build JRDB Training Research Base v0.1 from audited Index Base and Official RunPerf.

The builder projects Common Reader facts already materialized by Index Base. It does
not parse fixed-width records and deliberately excludes odds, popularity and payouts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

VERSION = "0.1.0"
SCHEMA_VERSION = "v0.1"
RUNPERF_FORMULA = "T1|EXPANDING|RAW"
RUNPERF_VERSION = "Official RunPerf v0.1"


def _default_schema() -> Path:
    return Path(__file__).resolve().parents[1] / "schema" / "jrdb_training_research_schema_v0_1.sql"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scalar(connection: sqlite3.Connection, sql: str) -> object:
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def _combined_record_hash(*values: object) -> bytes:
    """Trace all contributing neutral records with one compact composite digest."""
    digest = hashlib.sha256()
    for value in values:
        text = "" if value is None else str(value)
        digest.update(len(text).to_bytes(4, "big"))
        digest.update(text.encode("ascii"))
    return digest.digest()


def build(index_db: Path, official_db: Path, output: Path, schema: Path, source_git_commit: str) -> dict:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    if not index_db.is_file() or not official_db.is_file():
        raise FileNotFoundError("index and official RunPerf databases are required")
    if not source_git_commit or source_git_commit == "UNKNOWN":
        raise ValueError("source_git_commit must be an exact Git commit")

    generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    connection = sqlite3.connect(output)
    connection.create_function("combined_record_hash", -1, _combined_record_hash, deterministic=True)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.executescript(schema.read_text(encoding="utf-8"))
        connection.execute("ATTACH DATABASE ? AS idx", (str(index_db),))
        connection.execute("ATTACH DATABASE ? AS off", (str(official_db),))

        source_min = int(_scalar(connection, "SELECT MIN(year) FROM idx.race_context"))
        source_max = int(_scalar(connection, "SELECT MAX(year) FROM idx.race_context"))
        if (source_min, source_max) != (2010, 2025):
            raise ValueError(f"expected exact 2010..2025 coverage, got {source_min}..{source_max}")

        build_id = connection.execute(
            """INSERT INTO meta_training_research_build(
                 builder_version,schema_version,source_git_commit,
                 source_index_db_sha256,source_official_runperf_db_sha256,
                 runperf_formula,runperf_version,period_from,period_to,
                 holdout_from,holdout_to,generated_at,status
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (VERSION, SCHEMA_VERSION, source_git_commit, _sha256(index_db),
             _sha256(official_db), RUNPERF_FORMULA, RUNPERF_VERSION,
             "2010-01-01", "2025-12-31", "2024-01-01", "2025-12-31",
             generated_at, "RUNNING"),
        ).lastrowid

        connection.execute(
            """INSERT INTO source_archive
               SELECT source_kind,year,member_count,archive_size_bytes,archive_sha256
               FROM idx.meta_index_base_source"""
        )

        connection.execute(
            """
            INSERT INTO training_runner
            WITH ordered AS (
              SELECT p.*,
                     ROW_NUMBER() OVER (
                       PARTITION BY NULLIF(p.horse_id,'')
                       ORDER BY r.race_date,r.race_key,p.horse_no
                     ) AS career_run_count_calc,
                     LAG(r.race_date) OVER (
                       PARTITION BY NULLIF(p.horse_id,'')
                       ORDER BY r.race_date,r.race_key,p.horse_no
                     ) AS previous_race_date
              FROM idx.runner_pre p
              JOIN idx.race_context r USING(race_key)
            ), finisher AS (
              SELECT race_key,
                     SUM(CASE WHEN finish IS NOT NULL AND finish>0 THEN 1 ELSE 0 END) AS valid_count
              FROM idx.runner_result GROUP BY race_key
            )
            SELECT
              r.race_date,r.year,
              CASE WHEN r.year<=2012 THEN 'WARMUP'
                   WHEN r.year<=2023 THEN 'DEVELOPMENT' ELSE 'HOLDOUT' END,
              r.race_key,p.horse_no,NULLIF(p.horse_id,''),NULLIF(p.horse_name,''),
              NULLIF(p.trainer_code,''),NULLIF(p.trainer_name,''),
              NULLIF(p.jockey_code,''),NULLIF(p.jockey_name,''),
              r.venue_code,NULLIF(r.surface_code,''),r.distance_m,
              NULLIF(r.race_type_code,''),NULLIF(r.race_condition_code,''),NULLIF(r.grade_code,''),
              p.carried_weight_kg,s.body_weight_kg,p.rotation_interval,
              CASE WHEN p.previous_race_date IS NULL THEN NULL
                   ELSE CAST(julianday(r.race_date)-julianday(p.previous_race_date) AS INTEGER) END,
              p.career_run_count_calc,p.career_run_count_calc-1,
              w.training_date,
              CASE WHEN w.training_date IS NULL THEN NULL
                   ELSE CAST(julianday(r.race_date)-julianday(w.training_date) AS INTEGER) END,
              w.workout_count,NULLIF(w.course_code,''),NULLIF(w.effort_code,''),
              NULLIF(w.chase_state_code,''),NULLIF(w.rider_type_code,''),w.furlong_count,
              w.first_segment_sec,w.middle_segment_sec,w.final_segment_sec,
              NULLIF(w.pair_result_code,''),NULLIF(w.pair_effort_code,''),w.pair_age,NULLIF(w.pair_class_code,''),
              w.jrdb_first_segment_index,w.jrdb_middle_segment_index,w.jrdb_final_segment_index,w.jrdb_workout_index,
              NULLIF(y.training_type_code,''),NULLIF(y.training_course_type_code,''),
              y.used_slope,y.used_wood,y.used_dirt,y.used_turf,y.used_pool,y.used_jump,y.used_polytrack,
              NULLIF(y.training_distance_code,''),NULLIF(y.training_focus_code,''),NULLIF(y.training_volume_code,''),
              y.week_ago_workout_index,NULLIF(y.week_ago_course_code,''),
              y.jrdb_workout_index,y.finish_index,NULLIF(y.finish_change_code,''),NULLIF(y.training_evaluation_code,''),
              p.training_score,NULLIF(p.training_arrow_code,''),
              s.finish,f.valid_count,
              CASE WHEN s.finish>0 AND f.valid_count>1 AND s.finish<=f.valid_count
                   THEN CAST(f.valid_count-s.finish AS REAL)/(f.valid_count-1) ELSE NULL END,
              o.runperf_raw,o.score_status,?, ?,o.score_provenance,
              r.source_kind,r.source_member,p.source_member,w.source_member,y.source_member,s.source_member,
              combined_record_hash(r.record_hash,p.record_hash,w.record_hash,y.record_hash,s.record_hash)
            FROM ordered p
            JOIN idx.race_context r USING(race_key)
            LEFT JOIN idx.runner_result s ON s.race_key=p.race_key AND s.horse_no=p.horse_no
            LEFT JOIN finisher f ON f.race_key=p.race_key
            LEFT JOIN idx.workout_main w ON w.race_key=p.race_key AND w.horse_no=p.horse_no
            LEFT JOIN idx.training_analysis y ON y.race_key=p.race_key AND y.horse_no=p.horse_no
            LEFT JOIN off.official_runperf o ON o.race_key=p.race_key AND o.horse_no=p.horse_no
            WHERE r.year BETWEEN 2010 AND 2025
            """,
            (RUNPERF_FORMULA, RUNPERF_VERSION),
        )
        runner_count = int(_scalar(connection, "SELECT COUNT(*) FROM training_runner"))
        finished_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        connection.execute(
            "UPDATE meta_training_research_build SET finished_at=?,status='COMPLETE',runner_count=? WHERE build_id=?",
            (finished_at, runner_count, build_id),
        )
        connection.commit()
        connection.execute("DETACH DATABASE idx")
        connection.execute("DETACH DATABASE off")
        connection.execute("ANALYZE")
        connection.commit()
        integrity = _scalar(connection, "PRAGMA integrity_check")
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
    except Exception:
        connection.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass

    return {
        "status": "success",
        "builder_version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "runner_count": runner_count,
        "output": str(output),
        "size_bytes": output.stat().st_size,
        "sha256": _sha256(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--official-runperf-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-git-commit", required=True)
    parser.add_argument("--schema", type=Path, default=_default_schema())
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    result = build(args.index_db, args.official_runperf_db, args.out, args.schema, args.source_git_commit)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
