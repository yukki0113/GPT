#!/usr/bin/env python3
"""Validate JRA CourseStats Phase 4 outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

RATE_COLUMNS = [
    "overall_top3_rate",
    "high_pace_rate", "middle_pace_rate", "slow_pace_rate",
    "front_win_rate", "front_top3_rate",
    "stalker_win_rate", "stalker_top3_rate",
    "midpack_win_rate", "midpack_top3_rate",
    "closer_win_rate", "closer_top3_rate",
    "avg_winner_last3f_percentile", "avg_top3_last3f_percentile",
    "avg_all_last3f_percentile",
    "inside_draw_win_rate", "inside_draw_top3_rate",
    "middle_draw_win_rate", "middle_draw_top3_rate",
    "outside_draw_win_rate", "outside_draw_top3_rate",
]
DEFINITION_VERSION = "jra-course-stats-definition-v0.1"\nPOPULATION_FILTER_ID = "ALL_FLAT_RESULTS_V0_1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course-stats", required=True, type=Path)
    ap.add_argument("--geometry-stats", required=True, type=Path)
    ap.add_argument("--period-from", required=True)
    ap.add_argument("--period-to-exclusive", required=True)
    ap.add_argument("--min-geometry-races", type=int, default=30)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    con = duckdb.connect()
    checks: list[tuple[str, bool]] = []
    try:
        cp = str(args.course_stats).replace("'", "''")
        gp = str(args.geometry_stats).replace("'", "''")
        con.execute(f"CREATE TEMP VIEW c AS SELECT * FROM read_parquet('{cp}')")
        con.execute(f"CREATE TEMP VIEW g AS SELECT * FROM read_parquet('{gp}')")

        def count(sql: str) -> int:
            return int(con.execute(sql).fetchone()[0])

        checks.extend([
            ("course_nonempty", count("SELECT COUNT(*) FROM c") > 0),
            ("geometry_nonempty", count("SELECT COUNT(*) FROM g") > 0),
            ("course_key_not_null", count("SELECT COUNT(*) FROM c WHERE course_key IS NULL") == 0),
            ("no_obstacle_course_key", count("SELECT COUNT(*) FROM c WHERE course_key LIKE 'JRA:%:O:%'") == 0),
            ("course_unique", count("SELECT COUNT(*) FROM (SELECT course_key, COUNT(*) n FROM c GROUP BY 1 HAVING n>1)") == 0),
            ("geometry_unique", count("SELECT COUNT(*) FROM (SELECT course_key, geometry_key, COUNT(*) n FROM g GROUP BY 1,2 HAVING n>1)") == 0),
            ("positive_course_samples", count("SELECT COUNT(*) FROM c WHERE sample_race_count<=0 OR sample_runner_count<=0") == 0),
            ("positive_geometry_samples", count("SELECT COUNT(*) FROM g WHERE sample_race_count<=0 OR sample_runner_count<=0") == 0),
            ("definition_course", count(f"SELECT COUNT(*) FROM c WHERE stats_definition_version <> '{DEFINITION_VERSION}'") == 0),
            ("definition_geometry", count(f"SELECT COUNT(*) FROM g WHERE stats_definition_version <> '{DEFINITION_VERSION}'") == 0),
            ("population_course", count(f"SELECT COUNT(*) FROM c WHERE population_filter_id <> '{POPULATION_FILTER_ID}'") == 0),
            ("population_geometry", count(f"SELECT COUNT(*) FROM g WHERE population_filter_id <> '{POPULATION_FILTER_ID}'") == 0),
            ("period_course", count(f"SELECT COUNT(*) FROM c WHERE period_from <> '{args.period_from}' OR period_to_exclusive <> '{args.period_to_exclusive}'") == 0),
            ("period_geometry", count(f"SELECT COUNT(*) FROM g WHERE period_from <> '{args.period_from}' OR period_to_exclusive <> '{args.period_to_exclusive}'") == 0),
            ("geometry_eligibility", count(f"SELECT COUNT(*) FROM g WHERE eligible_for_use <> (sample_race_count >= {args.min_geometry_races})") == 0),
            ("late_speed_delta_range", count("SELECT COUNT(*) FROM c WHERE late_speed_importance_delta IS NOT NULL AND (late_speed_importance_delta < -1 OR late_speed_importance_delta > 1)") == 0),
        ])
        for col in RATE_COLUMNS:
            checks.append((
                f"rate_range_{col}",
                count(f"SELECT COUNT(*) FROM c WHERE {col} IS NOT NULL AND ({col}<0 OR {col}>1)") == 0,
            ))
            checks.append((
                f"geometry_rate_range_{col}",
                count(f"SELECT COUNT(*) FROM g WHERE {col} IS NOT NULL AND ({col}<0 OR {col}>1)") == 0,
            ))

        report = {
            "schema_version": "jra-course-stats-phase4-validation-v0.1",
            "status": "PASS" if all(ok for _, ok in checks) else "FAIL",
            "course_stats_rows": count("SELECT COUNT(*) FROM c"),
            "geometry_stats_rows": count("SELECT COUNT(*) FROM g"),
            "geometry_eligible_rows": count("SELECT COUNT(*) FROM g WHERE eligible_for_use"),
            "checks": [{"name": name, "pass": ok} for name, ok in checks],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] == "PASS" else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
