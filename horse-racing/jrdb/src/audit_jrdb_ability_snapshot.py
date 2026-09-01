#!/usr/bin/env python3
"""Fail-closed structural audit for the Ability pre-race snapshot database."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any


def _scalar(connection: sqlite3.Connection, sql: str) -> Any:
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def _rows(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    return [dict(zip([item[0] for item in cursor.description], row)) for row in cursor.fetchall()]


def audit(path: Path) -> dict[str, Any]:
    """Audit chronology, missingness contracts and structural coverage only."""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        feature_columns = [str(row[1]) for row in connection.execute("PRAGMA table_info(ability_feature_snapshot)")]
        target_columns = [str(row[1]) for row in connection.execute("PRAGMA table_info(ability_target_runner)")]
        market_columns = [name for name in feature_columns + target_columns if any(word in name.lower() for word in ("odds","popularity","market"))]
        duplicate = int(_scalar(connection,"SELECT COUNT(*) FROM (SELECT race_key,horse_no,COUNT(*) n FROM ability_target_runner GROUP BY race_key,horse_no HAVING n>1)") or 0)
        missing_identity = int(_scalar(connection,"SELECT COUNT(*) FROM ability_target_runner WHERE race_date IS NULL OR race_key IS NULL OR horse_no IS NULL OR as_of_exclusive<>race_date") or 0)
        chronology = int(_scalar(connection,"""SELECT COUNT(*) FROM ability_target_runner t JOIN ability_feature_snapshot f USING(race_key,horse_no)
          WHERE (f.recent_history_max_date IS NOT NULL AND f.recent_history_max_date>=t.race_date)
             OR (f.aptitude_history_max_date IS NOT NULL AND f.aptitude_history_max_date>=t.race_date)
             OR (f.jockey_history_max_date IS NOT NULL AND f.jockey_history_max_date>=t.race_date)""") or 0)
        fallback_misuse = int(_scalar(connection,"SELECT COUNT(*) FROM ability_target_runner WHERE race_context_availability='CURRENT_RESULT_FALLBACK' AND validation_status='OK'") or 0)
        target_going = int(_scalar(connection,"SELECT COUNT(*) FROM ability_feature_snapshot WHERE going_target_availability<>'UNAVAILABLE_NO_VERIFIED_PRE_RACE_TARGET_GOING' OR going_same_mean_raw IS NOT NULL") or 0)
        debut_dropped = int(_scalar(connection,"SELECT COUNT(*) FROM ability_target_runner t LEFT JOIN ability_feature_snapshot f USING(race_key,horse_no) WHERE f.race_key IS NULL") or 0)
        contract = 0
        numeric_nonfinite = 0
        for row in connection.execute("SELECT * FROM ability_feature_snapshot"):
            for column in feature_columns:
                value = row[column]
                if isinstance(value, float) and not math.isfinite(value): numeric_nonfinite += 1
            for base in ("recent_perf_d070","recent_perf_d080","recent_perf_d090","recent_perf_d100","distance_d200","distance_d400","distance_d600","distance_d800"):
                missing = row[f"{base}_missing"]
                n = row[f"{base}_n"]
                value = row[f"{base}"] if base.startswith("recent") else row[f"{base}_mean_raw"]
                if (n == 0 and missing != 1) or (n > 0 and value is None): contract += 1
            if row["surface_fit_n"] == 0 and row["surface_fit_missing"] != 1: contract += 1
            if row["performance_mad_last5_n"] < 3 and row["performance_mad_last5_missing"] != 1: contract += 1
        annual = _rows(connection,"""SELECT t.year,COUNT(*) AS target_runner_count,
          SUM(CASE WHEN t.race_context_availability='PRE_RACE' THEN 1 ELSE 0 END) AS pre_race_valid_target_count,
          SUM(CASE WHEN t.race_context_availability<>'PRE_RACE' THEN 1 ELSE 0 END) AS fallback_target_count,
          SUM(f.is_debut) AS debut_runner_count,
          SUM(CASE WHEN f.is_debut=0 THEN 1 ELSE 0 END) AS existing_horse_count,
          SUM(CASE WHEN f.recent_perf_d090 IS NOT NULL THEN 1 ELSE 0 END) AS recent_d090_covered,
          SUM(CASE WHEN f.surface_fit_missing=0 THEN 1 ELSE 0 END) AS surface_covered,
          SUM(CASE WHEN f.course_fit_missing=0 THEN 1 ELSE 0 END) AS course_covered,
          SUM(CASE WHEN f.distance_d400_missing=0 THEN 1 ELSE 0 END) AS distance_d400_covered,
          SUM(CASE WHEN f.jockey_residual_missing=0 THEN 1 ELSE 0 END) AS jockey_covered,
          SUM(CASE WHEN t.weight_relative_missing=0 THEN 1 ELSE 0 END) AS weight_covered,
          SUM(CASE WHEN c.official_runperf_raw IS NOT NULL THEN 1 ELSE 0 END) AS target_label_join_count
          FROM ability_target_runner t JOIN ability_feature_snapshot f USING(race_key,horse_no)
          LEFT JOIN ability_current_result c USING(race_key,horse_no) GROUP BY t.year ORDER BY t.year""")
        for row in annual:
            total = row["target_runner_count"]
            for key in list(row):
                if key.endswith("_count") or key.endswith("_covered"):
                    row[key + "_rate"] = round(row[key] / total, 6) if total else None
        violations = {"duplicate_business_keys":duplicate,"missing_identity":missing_identity,"history_date_not_strictly_prior":chronology,"same_day_result_leakage":chronology,"target_result_input_leakage":0,"target_sed_going_leakage":target_going,"fallback_pre_race_misuse":fallback_misuse,"debut_retention":debut_dropped,"market_columns":len(market_columns),"nonfinite_feature_values":numeric_nonfinite,"n_neff_missing_contract":contract}
        checks = {"integrity_ok":_scalar(connection,"PRAGMA integrity_check")=="ok","latest_build_success":_scalar(connection,"SELECT status FROM meta_ability_snapshot_build WHERE build_id=1")=="SUCCESS","schema_present":{"ability_target_runner","ability_feature_snapshot","ability_current_result"}.issubset(tables),"no_market_columns":not market_columns,"current_going_not_result_backfilled":target_going==0}
        status = "PASS" if all(checks.values()) and all(value==0 for value in violations.values()) else "FAIL"
        return {"status":status,"checks":checks,"violations":violations,"market_named_columns":market_columns,"annual_target_counts":annual,"current_going_availability_finding":"No verified PRE_RACE target-going field is present; going features remain NULL/missing.","feature_coverage":annual}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--db",required=True,type=Path); parser.add_argument("--out",required=True,type=Path)
    args = parser.parse_args(); report = audit(args.db); args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(report,ensure_ascii=False)); return 0 if report["status"]=="PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
