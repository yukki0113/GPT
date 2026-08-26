#!/usr/bin/env python3
"""Build a compact row-level SQLite for flexible JRDB PWA aggregation."""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path

VERSION = "0.1"
SCHEMA_VERSION = "0.1"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "schema"
            / "jrdb_pwa_fact_lite_schema_v0_1.sql"
        ),
    )
    return parser.parse_args()


def validate_source(analysis_path: Path) -> tuple[int, str, str]:
    """Validate the Analysis Lite source and return row count and period."""
    if not analysis_path.exists():
        raise SystemExit(f"Analysis DB not found: {analysis_path}")

    connection = sqlite3.connect(analysis_path)
    try:
        table_row = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='fact_entry_result_lite'"
        ).fetchone()
        if table_row is None:
            raise SystemExit("fact_entry_result_lite was not found in Analysis DB")

        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise SystemExit(f"Analysis integrity_check failed: {integrity}")

        row_count = connection.execute(
            "SELECT COUNT(*) FROM fact_entry_result_lite"
        ).fetchone()[0]
        period = connection.execute(
            "SELECT MIN(race_date), MAX(race_date) FROM fact_entry_result_lite"
        ).fetchone()
    finally:
        connection.close()

    if row_count <= 0:
        raise SystemExit("Analysis contains no rows")
    if period is None or period[0] is None or period[1] is None:
        raise SystemExit("Analysis period could not be resolved")

    return int(row_count), str(period[0]), str(period[1])


def insert_dictionary(
    output: sqlite3.Connection,
    source_alias: str,
    table_name: str,
    source_column: str,
) -> None:
    """Create a compact integer dictionary for a repeated text dimension."""
    rows = output.execute(
        f"SELECT DISTINCT {source_column} "
        f"FROM {source_alias}.fact_entry_result_lite "
        f"WHERE trim(coalesce({source_column}, '')) <> '' "
        f"ORDER BY {source_column}"
    ).fetchall()

    values: list[tuple[int, str]] = []
    for index, row in enumerate(rows, start=1):
        values.append((index, str(row[0])))

    output.executemany(
        f"INSERT INTO {table_name}(id, name) VALUES(?, ?)",
        values,
    )


def build_fact(output: sqlite3.Connection) -> None:
    """Insert one compact row for each Analysis entry/result row."""
    output.execute(
        """
        INSERT INTO fact_stats_entry(
          race_date_int,
          year,
          venue_code,
          race_no,
          track_type,
          distance,
          race_condition_code,
          track_condition_code,
          grade_code,
          frame_no,
          sex_code,
          age,
          sire_id,
          bms_id,
          sire_line_code,
          bms_line_code,
          jockey_id,
          running_style,
          distance_aptitude,
          uptrend,
          training_index,
          final_win_popularity,
          finish,
          win_payout,
          place_payout
        )
        SELECT
          CAST(REPLACE(source.race_date, '-', '') AS INTEGER),
          source.year,
          CAST(source.venue_code AS INTEGER),
          source.race_no,
          CAST(source.track_type AS INTEGER),
          source.distance,
          source.race_condition_code,
          CASE
            WHEN source.track_condition_code IS NULL OR source.track_condition_code = ''
              THEN NULL
            ELSE CAST(source.track_condition_code AS INTEGER)
          END,
          CASE
            WHEN source.grade_code IS NULL OR source.grade_code = ''
              THEN 0
            ELSE CAST(source.grade_code AS INTEGER)
          END,
          source.frame_no,
          CASE
            WHEN source.sex_code IS NULL OR source.sex_code = ''
              THEN NULL
            ELSE CAST(source.sex_code AS INTEGER)
          END,
          source.age,
          sire.id,
          bms.id,
          CASE
            WHEN source.sire_line_code IS NULL OR source.sire_line_code = ''
              THEN NULL
            ELSE CAST(source.sire_line_code AS INTEGER)
          END,
          CASE
            WHEN source.broodmare_sire_line_code IS NULL
              OR source.broodmare_sire_line_code = ''
              THEN NULL
            ELSE CAST(source.broodmare_sire_line_code AS INTEGER)
          END,
          jockey.id,
          CASE
            WHEN source.running_style IS NULL OR source.running_style = ''
              THEN NULL
            ELSE CAST(source.running_style AS INTEGER)
          END,
          CASE
            WHEN source.distance_aptitude IS NULL OR source.distance_aptitude = ''
              THEN NULL
            ELSE CAST(source.distance_aptitude AS INTEGER)
          END,
          CASE
            WHEN source.uptrend IS NULL OR source.uptrend = ''
              THEN NULL
            ELSE CAST(source.uptrend AS INTEGER)
          END,
          CASE
            WHEN source.training_index IS NULL
              THEN NULL
            ELSE CAST(source.training_index AS INTEGER)
          END,
          source.final_win_popularity,
          source.finish,
          source.win_payout,
          source.place_payout
        FROM analysis.fact_entry_result_lite AS source
        LEFT JOIN dim_sire AS sire
          ON sire.name = source.sire_name
        LEFT JOIN dim_bms AS bms
          ON bms.name = source.broodmare_sire_name
        LEFT JOIN dim_jockey AS jockey
          ON jockey.name = source.jockey_name
        """
    )


def main() -> None:
    """Build and validate the PWA Fact Lite SQLite artifact."""
    args = parse_args()

    if args.db.exists():
        raise SystemExit(f"Refusing to overwrite existing DB: {args.db}")
    if not args.schema.exists():
        raise SystemExit(f"Schema file not found: {args.schema}")

    source_row_count, period_from, period_to = validate_source(args.analysis)

    output = sqlite3.connect(args.db)
    output.execute("PRAGMA journal_mode=OFF")
    output.execute("PRAGMA synchronous=OFF")
    output.executescript(args.schema.read_text(encoding="utf-8"))

    build_id = output.execute(
        "INSERT INTO meta_pwa_fact_build(" 
        "builder_version, schema_version, source_analysis, started_at, status, "
        "row_count, period_from, period_to"
        ") VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        (
            VERSION,
            SCHEMA_VERSION,
            str(args.analysis),
            dt.datetime.now().isoformat(timespec="seconds"),
            "RUNNING",
            source_row_count,
            period_from,
            period_to,
        ),
    ).lastrowid

    output.execute("ATTACH DATABASE ? AS analysis", (str(args.analysis),))
    try:
        insert_dictionary(output, "analysis", "dim_sire", "sire_name")
        insert_dictionary(output, "analysis", "dim_bms", "broodmare_sire_name")
        insert_dictionary(output, "analysis", "dim_jockey", "jockey_name")
        build_fact(output)
        output.commit()
    finally:
        output.execute("DETACH DATABASE analysis")

    built_row_count = output.execute(
        "SELECT COUNT(*) FROM fact_stats_entry"
    ).fetchone()[0]
    if built_row_count != source_row_count:
        raise SystemExit(
            "Fact row count mismatch: "
            f"source={source_row_count} built={built_row_count}"
        )

    output.execute(
        "UPDATE meta_pwa_fact_build "
        "SET finished_at=?, status='SUCCESS' WHERE build_id=?",
        (dt.datetime.now().isoformat(timespec="seconds"), build_id),
    )
    output.commit()

    output.execute("VACUUM")
    output.commit()

    integrity = output.execute("PRAGMA integrity_check").fetchone()[0]
    result = {
        "builder_version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "rows": built_row_count,
        "period_from": period_from,
        "period_to": period_to,
        "sire_count": output.execute("SELECT COUNT(*) FROM dim_sire").fetchone()[0],
        "bms_count": output.execute("SELECT COUNT(*) FROM dim_bms").fetchone()[0],
        "jockey_count": output.execute("SELECT COUNT(*) FROM dim_jockey").fetchone()[0],
        "size_bytes": args.db.stat().st_size,
        "integrity_check": integrity,
    }
    print(result)
    output.close()


if __name__ == "__main__":
    main()
