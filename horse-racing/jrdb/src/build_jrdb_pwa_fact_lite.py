#!/usr/bin/env python3
"""Build a compact row-level SQLite for flexible JRDB PWA aggregation."""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path

VERSION = "0.2"
SCHEMA_VERSION = "0.2"


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
            / "jrdb_pwa_fact_lite_schema_v0_2.sql"
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

        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(fact_entry_result_lite)"
            )
        }
        required_columns = {
            "race_date",
            "year",
            "venue_code",
            "race_no",
            "race_key",
            "track_type",
            "distance",
            "prev_race_key_1",
        }
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            raise SystemExit(
                "Analysis is missing required columns: "
                + ", ".join(missing_columns)
            )

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


def source_columns(output: sqlite3.Connection) -> set[str]:
    """Return columns available in the attached Analysis fact table."""
    return {
        row[1]
        for row in output.execute(
            "PRAGMA analysis.table_info(fact_entry_result_lite)"
        )
    }


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


def insert_race_dictionary(
    output: sqlite3.Connection,
    has_race_name: bool,
) -> None:
    """Create one race dimension row per race key.

    Analysis Lite v1.2 has no race_name column. In that case the dimension is
    still created so Fact Lite v0.2 remains usable; race-name search becomes
    available automatically after a source Analysis carrying race_name is used.
    """
    if has_race_name:
        rows = output.execute(
            "SELECT race_key, MAX(NULLIF(TRIM(race_name), '')) AS race_name "
            "FROM analysis.fact_entry_result_lite "
            "GROUP BY race_key ORDER BY race_key"
        ).fetchall()
    else:
        rows = output.execute(
            "SELECT race_key, NULL AS race_name "
            "FROM analysis.fact_entry_result_lite "
            "GROUP BY race_key ORDER BY race_key"
        ).fetchall()

    values: list[tuple[int, str, str | None]] = []
    for index, row in enumerate(rows, start=1):
        name = None if row[1] is None else str(row[1])
        values.append((index, str(row[0]), name))

    output.executemany(
        "INSERT INTO dim_race(id, race_key, race_name) VALUES(?, ?, ?)",
        values,
    )


def build_fact(output: sqlite3.Connection) -> None:
    """Insert one compact row for each Analysis entry/result row."""
    output.execute(
        """
        INSERT INTO fact_stats_entry(
          race_date_int,
          year,
          month,
          venue_code,
          race_no,
          race_id,
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
          place_payout,
          prev_distance_delta,
          prev_class_code
        )
        SELECT
          CAST(REPLACE(source.race_date, '-', '') AS INTEGER),
          source.year,
          CAST(SUBSTR(source.race_date, 6, 2) AS INTEGER),
          CAST(source.venue_code AS INTEGER),
          source.race_no,
          race.id,
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
          source.place_payout,
          CASE
            WHEN previous.distance IS NULL OR source.distance IS NULL
              THEN NULL
            ELSE source.distance - previous.distance
          END,
          CASE
            WHEN previous.race_key IS NULL THEN NULL
            WHEN TRIM(COALESCE(previous.grade_code, '')) = '1' THEN 11
            WHEN TRIM(COALESCE(previous.grade_code, '')) = '2' THEN 10
            WHEN TRIM(COALESCE(previous.grade_code, '')) = '3' THEN 9
            WHEN TRIM(COALESCE(previous.grade_code, '')) = '4' THEN 12
            WHEN TRIM(COALESCE(previous.grade_code, '')) = '6' THEN 8
            WHEN TRIM(COALESCE(previous.race_condition_code, '')) = 'A1' THEN 1
            WHEN TRIM(COALESCE(previous.race_condition_code, '')) = 'A2' THEN 2
            WHEN TRIM(COALESCE(previous.race_condition_code, '')) = 'A3' THEN 3
            WHEN TRIM(COALESCE(previous.race_condition_code, '')) IN ('04', '05') THEN 4
            WHEN TRIM(COALESCE(previous.race_condition_code, '')) IN ('08', '09', '10') THEN 5
            WHEN TRIM(COALESCE(previous.race_condition_code, '')) IN ('15', '16') THEN 6
            WHEN TRIM(COALESCE(previous.race_condition_code, '')) = 'OP' THEN 7
            ELSE 13
          END
        FROM analysis.fact_entry_result_lite AS source
        JOIN dim_race AS race
          ON race.race_key = source.race_key
        LEFT JOIN dim_sire AS sire
          ON sire.name = source.sire_name
        LEFT JOIN dim_bms AS bms
          ON bms.name = source.broodmare_sire_name
        LEFT JOIN dim_jockey AS jockey
          ON jockey.name = source.jockey_name
        LEFT JOIN (
          SELECT
            race_key,
            MAX(distance) AS distance,
            MAX(race_condition_code) AS race_condition_code,
            MAX(grade_code) AS grade_code
          FROM analysis.fact_entry_result_lite
          GROUP BY race_key
        ) AS previous
          ON previous.race_key = source.prev_race_key_1
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
        columns = source_columns(output)
        insert_dictionary(output, "analysis", "dim_sire", "sire_name")
        insert_dictionary(output, "analysis", "dim_bms", "broodmare_sire_name")
        insert_dictionary(output, "analysis", "dim_jockey", "jockey_name")
        insert_race_dictionary(output, "race_name" in columns)
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
        "race_count": output.execute("SELECT COUNT(*) FROM dim_race").fetchone()[0],
        "race_name_count": output.execute(
            "SELECT COUNT(*) FROM dim_race "
            "WHERE TRIM(COALESCE(race_name, '')) <> ''"
        ).fetchone()[0],
        "prev_distance_rows": output.execute(
            "SELECT COUNT(*) FROM fact_stats_entry "
            "WHERE prev_distance_delta IS NOT NULL"
        ).fetchone()[0],
        "prev_class_rows": output.execute(
            "SELECT COUNT(*) FROM fact_stats_entry "
            "WHERE prev_class_code IS NOT NULL"
        ).fetchone()[0],
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
