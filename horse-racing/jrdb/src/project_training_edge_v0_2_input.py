#!/usr/bin/env python3
"""Project a versioned Training Edge v0.2 evaluation input SQLite.

This projector intentionally does not modify or extend Training Research Base v0.1.
It reads audited Index Base + Official RunPerf and materializes only the chronology,
workout/process and processed-JRDB fields required by the v0.2 scorer/evaluator.

The output can therefore include 2026+ evidence while the confirmed v0.1 mother ship
remains the immutable 2010-2025 research artifact.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
SCHEMA = "training-edge-v0.2-input-v0.1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scalar(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = connection.execute(sql, params).fetchone()
    return None if row is None else row[0]


def project(
    index_db: Path,
    official_db: Path,
    output_db: Path,
    from_year: int,
    to_year: int,
    source_git_commit: str,
) -> dict[str, Any]:
    """Materialize a compact chronological scorer/evaluation input."""
    if output_db.exists():
        raise FileExistsError(f"refusing to overwrite: {output_db}")
    if not index_db.is_file():
        raise FileNotFoundError(index_db)
    if not official_db.is_file():
        raise FileNotFoundError(official_db)
    if from_year > to_year:
        raise ValueError("from_year must be <= to_year")
    if not source_git_commit or source_git_commit == "UNKNOWN":
        raise ValueError("source_git_commit must be an exact Git commit")

    connection = sqlite3.connect(output_db)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("ATTACH DATABASE ? AS idx", (str(index_db),))
        connection.execute("ATTACH DATABASE ? AS off", (str(official_db),))

        index_min = int(_scalar(connection, "SELECT MIN(year) FROM idx.race_context"))
        index_max = int(_scalar(connection, "SELECT MAX(year) FROM idx.race_context"))
        official_min = int(_scalar(connection, "SELECT MIN(year) FROM off.official_runperf"))
        official_max = int(_scalar(connection, "SELECT MAX(year) FROM off.official_runperf"))
        if index_min > from_year or index_max < to_year:
            raise ValueError(
                f"Index Base does not cover requested {from_year}..{to_year}: "
                f"got {index_min}..{index_max}"
            )
        if official_min > from_year or official_max < to_year:
            raise ValueError(
                f"Official RunPerf does not cover requested {from_year}..{to_year}: "
                f"got {official_min}..{official_max}"
            )

        connection.executescript(
            """
            CREATE TABLE meta_training_edge_v0_2_input(
              build_id INTEGER PRIMARY KEY,
              projector_version TEXT NOT NULL,
              schema_name TEXT NOT NULL,
              source_git_commit TEXT NOT NULL,
              source_index_sha256 TEXT NOT NULL,
              source_official_sha256 TEXT NOT NULL,
              from_year INTEGER NOT NULL,
              to_year INTEGER NOT NULL,
              generated_at TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              status TEXT NOT NULL
            );

            CREATE TABLE training_edge_input(
              race_date TEXT NOT NULL,
              year INTEGER NOT NULL,
              race_key TEXT NOT NULL,
              horse_no INTEGER NOT NULL,
              horse_id TEXT,
              trainer_code TEXT,
              trainer_name TEXT,
              days_since_last_run INTEGER,
              training_date TEXT,
              days_before_race INTEGER,
              workout_count INTEGER,
              course_code TEXT,
              effort_code TEXT,
              chase_state_code TEXT,
              rider_type_code TEXT,
              furlong_count INTEGER,
              final_segment_sec REAL,
              pair_result_code TEXT,
              pair_effort_code TEXT,
              pair_class_code TEXT,
              jrdb_final_segment_index INTEGER,
              jrdb_workout_index_cha INTEGER,
              training_type_code TEXT,
              training_course_type_code TEXT,
              used_slope INTEGER,
              used_wood INTEGER,
              used_dirt INTEGER,
              used_turf INTEGER,
              used_pool INTEGER,
              used_jump INTEGER,
              used_polytrack INTEGER,
              training_distance_code TEXT,
              training_focus_code TEXT,
              training_volume_code TEXT,
              week_ago_course_code TEXT,
              finish_index INTEGER,
              kyi_training_score REAL,
              kyi_training_arrow_code TEXT,
              official_runperf_raw REAL,
              runperf_score_status TEXT,
              PRIMARY KEY(race_key, horse_no)
            );
            """
        )

        connection.execute(
            """
            INSERT INTO training_edge_input
            WITH ordered AS (
              SELECT
                p.race_key,p.horse_no,p.horse_id,p.trainer_code,p.trainer_name,
                p.training_score,p.training_arrow_code,r.race_date,r.year,
                LAG(r.race_date) OVER (
                  PARTITION BY NULLIF(p.horse_id,'')
                  ORDER BY r.race_date,r.race_key,p.horse_no
                ) AS previous_race_date
              FROM idx.runner_pre p
              JOIN idx.race_context r USING(race_key)
              WHERE r.year BETWEEN ? AND ?
            )
            SELECT
              o.race_date,o.year,o.race_key,o.horse_no,NULLIF(o.horse_id,''),
              NULLIF(o.trainer_code,''),NULLIF(o.trainer_name,''),
              CASE WHEN o.previous_race_date IS NULL THEN NULL
                   ELSE CAST(julianday(o.race_date)-julianday(o.previous_race_date) AS INTEGER) END,
              w.training_date,
              CASE WHEN w.training_date IS NULL THEN NULL
                   ELSE CAST(julianday(o.race_date)-julianday(w.training_date) AS INTEGER) END,
              w.workout_count,NULLIF(w.course_code,''),NULLIF(w.effort_code,''),
              NULLIF(w.chase_state_code,''),NULLIF(w.rider_type_code,''),w.furlong_count,
              w.final_segment_sec,NULLIF(w.pair_result_code,''),NULLIF(w.pair_effort_code,''),
              NULLIF(w.pair_class_code,''),w.jrdb_final_segment_index,w.jrdb_workout_index,
              NULLIF(y.training_type_code,''),NULLIF(y.training_course_type_code,''),
              y.used_slope,y.used_wood,y.used_dirt,y.used_turf,y.used_pool,y.used_jump,y.used_polytrack,
              NULLIF(y.training_distance_code,''),NULLIF(y.training_focus_code,''),
              NULLIF(y.training_volume_code,''),NULLIF(y.week_ago_course_code,''),
              y.finish_index,o.training_score,NULLIF(o.training_arrow_code,''),
              rp.runperf_raw,rp.score_status
            FROM ordered o
            LEFT JOIN idx.workout_main w
              ON w.race_key=o.race_key AND w.horse_no=o.horse_no
            LEFT JOIN idx.training_analysis y
              ON y.race_key=o.race_key AND y.horse_no=o.horse_no
            LEFT JOIN off.official_runperf rp
              ON rp.race_key=o.race_key AND rp.horse_no=o.horse_no
            ORDER BY o.race_date,o.race_key,o.horse_no
            """,
            (from_year, to_year),
        )

        connection.execute(
            "CREATE INDEX ix_training_edge_input_date "
            "ON training_edge_input(race_date,race_key,horse_no)"
        )
        connection.execute(
            "CREATE INDEX ix_training_edge_input_horse "
            "ON training_edge_input(horse_id,race_date,race_key)"
        )
        connection.execute(
            "CREATE INDEX ix_training_edge_input_comparable "
            "ON training_edge_input(horse_id,course_code,furlong_count,race_date,race_key)"
        )

        row_count = int(_scalar(connection, "SELECT COUNT(*) FROM training_edge_input"))
        if row_count == 0:
            raise ValueError("projection produced zero rows")
        min_year = int(_scalar(connection, "SELECT MIN(year) FROM training_edge_input"))
        max_year = int(_scalar(connection, "SELECT MAX(year) FROM training_edge_input"))
        if (min_year, max_year) != (from_year, to_year):
            raise ValueError(
                f"projected year range mismatch: expected {from_year}..{to_year}, "
                f"got {min_year}..{max_year}"
            )
        duplicate_count = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM (
                  SELECT race_key,horse_no,COUNT(*) n
                  FROM training_edge_input GROUP BY race_key,horse_no HAVING n>1
                )
                """,
            )
        )
        if duplicate_count != 0:
            raise ValueError(f"duplicate race_key+horse_no rows: {duplicate_count}")
        future_training = int(
            _scalar(
                connection,
                "SELECT COUNT(*) FROM training_edge_input "
                "WHERE training_date IS NOT NULL AND training_date>race_date",
            )
        )
        if future_training != 0:
            raise ValueError(f"training-after-race rows: {future_training}")

        generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO meta_training_edge_v0_2_input(
              build_id,projector_version,schema_name,source_git_commit,
              source_index_sha256,source_official_sha256,from_year,to_year,
              generated_at,row_count,status
            ) VALUES(1,?,?,?,?,?,?,?,?,?,'COMPLETE')
            """,
            (
                VERSION,SCHEMA,source_git_commit,_sha256(index_db),_sha256(official_db),
                from_year,to_year,generated_at,row_count,
            ),
        )
        connection.commit()
        connection.execute("ANALYZE")
        connection.commit()

        integrity = str(_scalar(connection, "PRAGMA integrity_check"))
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

        by_year = {
            str(year): int(count)
            for year, count in connection.execute(
                "SELECT year,COUNT(*) FROM training_edge_input GROUP BY year ORDER BY year"
            ).fetchall()
        }
        return {
            "status": "success",
            "projector_version": VERSION,
            "schema": SCHEMA,
            "source_git_commit": source_git_commit,
            "from_year": from_year,
            "to_year": to_year,
            "row_count": row_count,
            "by_year": by_year,
            "duplicate_business_keys": duplicate_count,
            "future_training_rows": future_training,
            "integrity_check": integrity,
            "output": str(output_db),
            "size_bytes": output_db.stat().st_size,
            "sha256": _sha256(output_db),
        }
    except Exception:
        connection.close()
        output_db.unlink(missing_ok=True)
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--official-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--from-year", type=int, default=2010)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--source-git-commit", required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()

    result = project(
        index_db=args.index_db,
        official_db=args.official_db,
        output_db=args.out,
        from_year=args.from_year,
        to_year=args.to_year,
        source_git_commit=args.source_git_commit,
    )
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
