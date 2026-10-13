#!/usr/bin/env python3
"""Audit JRA BAC course-condition combinations for Course Profile Master Phase 1."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import duckdb

def rows(cursor):
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]

def scalar(con, sql):
    return con.execute(sql).fetchone()[0]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    parquet_glob = str(args.input_root / "bac" / "year=*" / "*.parquet")
    con = duckdb.connect()
    try:
        escaped_glob = parquet_glob.replace("'", "''")
        con.execute(f"CREATE TEMP VIEW bac_raw AS SELECT * FROM read_parquet('{escaped_glob}', union_by_name=true)")
        con.execute("""
            CREATE TEMP VIEW bac_jra AS
            SELECT * FROM bac_raw
            WHERE venue_code IN ('01','02','03','04','05','06','07','08','09','10')
        """)
        con.execute("""
            CREATE TEMP VIEW bac_latest AS
            SELECT * EXCLUDE (_rn)
            FROM (
              SELECT *,
                     ROW_NUMBER() OVER (
                       PARTITION BY race_key_raw
                       ORDER BY source_member_date DESC NULLS LAST,
                                source_record_ordinal DESC NULLS LAST
                     ) AS _rn
              FROM bac_jra
            )
            WHERE _rn = 1
        """)
        result = {
            "schema_version": "jra-course-profile-phase1-bac-audit-v1",
            "input_glob": parquet_glob,
            "raw_row_count": scalar(con, "SELECT COUNT(*) FROM bac_raw"),
            "jra_raw_row_count": scalar(con, "SELECT COUNT(*) FROM bac_jra"),
            "jra_distinct_race_count": scalar(con, "SELECT COUNT(DISTINCT race_key_raw) FROM bac_jra"),
            "jra_latest_row_count": scalar(con, "SELECT COUNT(*) FROM bac_latest"),
            "duplicate_race_key_count": scalar(con, """
                SELECT COUNT(*) FROM (
                  SELECT race_key_raw FROM bac_jra
                  GROUP BY race_key_raw HAVING COUNT(*) > 1
                )
            """),
            "correction_course_change_race_count": scalar(con, """
                SELECT COUNT(*) FROM (
                  SELECT race_key_raw
                  FROM bac_jra
                  GROUP BY race_key_raw
                  HAVING COUNT(DISTINCT concat_ws('|',
                    coalesce(venue_code,'<NULL>'),
                    coalesce(surface_code,'<NULL>'),
                    coalesce(distance_raw,'<NULL>'),
                    coalesce(turn_code,'<NULL>'),
                    coalesce(layout_code,'<NULL>'),
                    coalesce(course_code,'<NULL>')
                  )) > 1
                )
            """),
            "blank_or_null": {},
            "invalid_code_counts": {},
        }
        for col in ("venue_code","distance_raw","surface_code","turn_code","layout_code","course_code"):
            result["blank_or_null"][col] = scalar(
                con, f"SELECT COUNT(*) FROM bac_latest WHERE {col} IS NULL OR trim(cast({col} AS VARCHAR)) = ''"
            )
        result["invalid_code_counts"] = {
            "surface_code": scalar(con, "SELECT COUNT(*) FROM bac_latest WHERE surface_code IS NOT NULL AND trim(surface_code) <> '' AND surface_code NOT IN ('1','2','3')"),
            "turn_code": scalar(con, "SELECT COUNT(*) FROM bac_latest WHERE turn_code IS NOT NULL AND trim(turn_code) <> '' AND turn_code NOT IN ('1','2','3','9')"),
            "layout_code": scalar(con, "SELECT COUNT(*) FROM bac_latest WHERE layout_code IS NOT NULL AND trim(layout_code) <> '' AND layout_code NOT IN ('1','2','3','9')"),
            "course_code": scalar(con, "SELECT COUNT(*) FROM bac_latest WHERE course_code IS NOT NULL AND trim(course_code) <> '' AND course_code NOT IN ('1','2','3','4','5','6')"),
        }
        result["year_coverage"] = rows(con.execute("""
            SELECT year, COUNT(*) AS raw_rows, COUNT(DISTINCT race_key_raw) AS distinct_races
            FROM bac_jra GROUP BY year ORDER BY year
        """))
        result["distinct_course_combinations"] = rows(con.execute("""
            SELECT venue_code, surface_code, try_cast(distance_raw AS INTEGER) AS distance_m,
                   turn_code, layout_code, course_code,
                   COUNT(*) AS race_count, MIN(race_date) AS first_race_date, MAX(race_date) AS last_race_date
            FROM bac_latest
            GROUP BY ALL
            ORDER BY venue_code, surface_code, distance_m, turn_code, layout_code, course_code
        """))
        result["base_conditions_with_multiple_shapes"] = rows(con.execute("""
            WITH g AS (
              SELECT venue_code, surface_code, try_cast(distance_raw AS INTEGER) AS distance_m,
                     COUNT(DISTINCT concat_ws('|',
                       coalesce(turn_code,'<NULL>'),
                       coalesce(layout_code,'<NULL>'),
                       coalesce(course_code,'<NULL>')
                     )) AS shape_variant_count,
                     COUNT(*) AS race_count
              FROM bac_latest GROUP BY 1,2,3
            )
            SELECT * FROM g WHERE shape_variant_count > 1
            ORDER BY venue_code, surface_code, distance_m
        """))
        result["duplicate_race_examples"] = rows(con.execute("""
            SELECT race_key_raw, COUNT(*) AS version_count,
                   MIN(source_member_date) AS first_source_member_date,
                   MAX(source_member_date) AS last_source_member_date
            FROM bac_jra
            GROUP BY race_key_raw
            HAVING COUNT(*) > 1
            ORDER BY version_count DESC, race_key_raw
            LIMIT 50
        """))
        result["correction_course_change_examples"] = rows(con.execute("""
            SELECT race_key_raw, source_member_date, venue_code, surface_code,
                   distance_raw, turn_code, layout_code, course_code
            FROM bac_jra
            WHERE race_key_raw IN (
              SELECT race_key_raw FROM bac_jra
              GROUP BY race_key_raw
              HAVING COUNT(DISTINCT concat_ws('|',
                coalesce(venue_code,'<NULL>'),
                coalesce(surface_code,'<NULL>'),
                coalesce(distance_raw,'<NULL>'),
                coalesce(turn_code,'<NULL>'),
                coalesce(layout_code,'<NULL>'),
                coalesce(course_code,'<NULL>')
              )) > 1
            )
            ORDER BY race_key_raw, source_member_date
            LIMIT 200
        """))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "status":"PASS",
            "output":str(args.output),
            "jra_latest_row_count":result["jra_latest_row_count"],
            "distinct_course_combination_count":len(result["distinct_course_combinations"]),
            "base_condition_multi_shape_count":len(result["base_conditions_with_multiple_shapes"]),
            "correction_course_change_race_count":result["correction_course_change_race_count"],
        }, ensure_ascii=False))
        return 0
    finally:
        con.close()

if __name__ == "__main__":
    raise SystemExit(main())
