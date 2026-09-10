#!/usr/bin/env python3
"""Extract the frozen Training Edge v0.1 2024-2025 holdout projection.

This utility performs projection only. It does not calculate, summarize, rank, or
otherwise inspect predictive outcomes. The resulting SQLite is intended to be
combined with the 2010-2023 development Lite DB by the frozen holdout evaluator.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

VERSION = "0.1.0"
SCHEMA_VERSION = "training-edge-holdout-lite-v0.1"
HOLDOUT_FROM = 2024
HOLDOUT_TO = 2025

REQUIRED_COLUMNS = (
    "race_date",
    "year",
    "data_split",
    "race_key",
    "horse_no",
    "horse_id",
    "course_code",
    "furlong_count",
    "final_segment_sec",
    "official_runperf_raw",
    "runperf_score_status",
    "kyi_training_score",
    "kyi_training_arrow_code",
    "finish_index",
    "jrdb_final_segment_index",
    "jrdb_workout_index_cha",
    "days_since_last_run",
)


def _sha256(path: Path) -> str:
    """Return SHA-256 for one local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_columns(connection: sqlite3.Connection) -> set[str]:
    """Return source training_runner column names."""
    rows = connection.execute("PRAGMA table_info(training_runner)").fetchall()
    return {str(row[1]) for row in rows}


def extract(source: Path, output: Path, source_git_commit: str) -> dict[str, object]:
    """Project only the frozen v0.1 holdout columns and years into a compact SQLite."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    if not source_git_commit or source_git_commit == "UNKNOWN":
        raise ValueError("source_git_commit must be an exact Git commit")

    generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    connection = sqlite3.connect(output)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=FILE")
        connection.execute("ATTACH DATABASE ? AS src", (str(source),))

        source_columns = _source_columns(connection.execute("SELECT 1").connection)
        # PRAGMA without a schema qualifier reads the main DB, so inspect src explicitly.
        source_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA src.table_info(training_runner)").fetchall()
        }
        missing = [column for column in REQUIRED_COLUMNS if column not in source_columns]
        if missing:
            raise ValueError(f"source training_runner is missing required columns: {missing}")

        year_bounds = connection.execute(
            "SELECT MIN(year),MAX(year) FROM src.training_runner"
        ).fetchone()
        if year_bounds is None or year_bounds[0] is None or year_bounds[1] is None:
            raise ValueError("source training_runner has no year coverage")
        if int(year_bounds[0]) > HOLDOUT_FROM or int(year_bounds[1]) < HOLDOUT_TO:
            raise ValueError(f"source does not cover complete {HOLDOUT_FROM}-{HOLDOUT_TO} holdout")

        selected_columns = ",".join(REQUIRED_COLUMNS)
        connection.execute(
            f"""
            CREATE TABLE training_holdout AS
            SELECT {selected_columns}
            FROM src.training_runner
            WHERE year BETWEEN ? AND ?
            ORDER BY race_date,race_key,horse_no
            """,
            (HOLDOUT_FROM, HOLDOUT_TO),
        )

        connection.execute(
            "CREATE UNIQUE INDEX ux_training_holdout_race_horse "
            "ON training_holdout(race_key,horse_no)"
        )
        connection.execute(
            "CREATE INDEX ix_training_holdout_horse_date "
            "ON training_holdout(horse_id,race_date)"
        )
        connection.execute(
            "CREATE INDEX ix_training_holdout_horse_comparable "
            "ON training_holdout(horse_id,course_code,furlong_count,race_date)"
        )
        connection.execute("CREATE INDEX ix_training_holdout_year ON training_holdout(year)")

        connection.execute(
            """
            CREATE TABLE holdout_extract_metadata(
              extractor_version TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              source_git_commit TEXT NOT NULL,
              holdout_from INTEGER NOT NULL,
              holdout_to INTEGER NOT NULL,
              generated_at TEXT NOT NULL,
              row_count INTEGER NOT NULL
            )
            """
        )
        row_count = int(connection.execute("SELECT COUNT(*) FROM training_holdout").fetchone()[0])
        connection.execute(
            "INSERT INTO holdout_extract_metadata VALUES(?,?,?,?,?,?,?)",
            (
                VERSION,
                SCHEMA_VERSION,
                source_git_commit,
                HOLDOUT_FROM,
                HOLDOUT_TO,
                generated_at,
                row_count,
            ),
        )
        connection.commit()
        connection.execute("DETACH DATABASE src")
        connection.execute("ANALYZE")
        connection.commit()

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

        duplicate_count = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM (
                  SELECT race_key,horse_no,COUNT(*) AS n
                  FROM training_holdout
                  GROUP BY race_key,horse_no
                  HAVING n>1
                )
                """
            ).fetchone()[0]
        )
        if duplicate_count != 0:
            raise RuntimeError(f"duplicate race_key+horse_no groups: {duplicate_count}")
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
        "extractor_version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "holdout_from": HOLDOUT_FROM,
        "holdout_to": HOLDOUT_TO,
        "row_count": row_count,
        "output": str(output),
        "size_bytes": output.stat().st_size,
        "sha256": _sha256(output),
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-git-commit", required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()

    result = extract(args.source, args.out, args.source_git_commit)
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
