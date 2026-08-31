#!/usr/bin/env python3
"""Audit JRDB RunPerf feature SQLite for chronology and arithmetic invariants."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

VERSION = "0.1.0"


def _scalar(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = connection.execute(sql, params).fetchone()
    return None if row is None else row[0]


def _rows(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def audit(db_path: Path, include_db_sha256: bool = True) -> dict[str, Any]:
    """Return a compact chronology/coverage/invariant report."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        integrity = _scalar(connection, "PRAGMA integrity_check")
        build = connection.execute(
            "SELECT * FROM meta_runperf_build ORDER BY build_id DESC LIMIT 1"
        ).fetchone()
        build_dict = dict(build) if build is not None else None

        method_rows = _rows(
            connection,
            """
            SELECT
              baseline_method,
              COUNT(*) AS race_rows,
              SUM(CASE WHEN expected_time_sec IS NOT NULL THEN 1 ELSE 0 END) AS expected_rows,
              SUM(CASE WHEN calculation_status='OK' THEN 1 ELSE 0 END) AS ok_rows,
              MIN(course_history_last_date) AS min_course_history_last_date,
              MAX(course_history_last_date) AS max_course_history_last_date
            FROM race_expected_time
            GROUP BY baseline_method
            ORDER BY baseline_method
            """,
        )
        for row in method_rows:
            row["expected_rate"] = _rate(int(row["expected_rows"]), int(row["race_rows"]))

        yearly = _rows(
            connection,
            """
            SELECT
              o.year,
              f.baseline_method,
              COUNT(*) AS runner_rows,
              SUM(CASE WHEN f.calculation_status='OK' THEN 1 ELSE 0 END) AS ok_runner_rows,
              SUM(CASE WHEN f.finish_percentile IS NOT NULL THEN 1 ELSE 0 END) AS b0_rows,
              SUM(CASE WHEN f.margin_per_1000m_sec IS NOT NULL THEN 1 ELSE 0 END) AS b1_rows,
              SUM(CASE WHEN f.time_residual_k4_bias_sec IS NOT NULL THEN 1 ELSE 0 END) AS t0_k4_rows,
              SUM(CASE WHEN f.jrdb_raw_score IS NOT NULL THEN 1 ELSE 0 END) AS j0_rows,
              SUM(CASE WHEN f.jrdb_idm IS NOT NULL THEN 1 ELSE 0 END) AS j1_rows
            FROM runner_runperf_features f
            JOIN race_runperf_observation o ON o.race_key=f.race_key
            GROUP BY o.year,f.baseline_method
            ORDER BY o.year,f.baseline_method
            """,
        )

        chronology_violations = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM race_expected_time e
                JOIN race_runperf_observation o ON o.race_key=e.race_key
                WHERE (e.course_history_last_date IS NOT NULL AND e.course_history_last_date >= o.race_date)
                   OR (e.class_history_last_date IS NOT NULL AND e.class_history_last_date >= o.race_date)
                """,
            )
            or 0
        )
        duplicate_expected = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM (
                  SELECT baseline_method,race_key,COUNT(*) c
                  FROM race_expected_time
                  GROUP BY baseline_method,race_key
                  HAVING c>1
                )
                """,
            )
            or 0
        )
        duplicate_runner = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM (
                  SELECT baseline_method,race_key,horse_no,COUNT(*) c
                  FROM runner_runperf_features
                  GROUP BY baseline_method,race_key,horse_no
                  HAVING c>1
                )
                """,
            )
            or 0
        )
        negative_margin = int(
            _scalar(connection, "SELECT COUNT(*) FROM runner_runperf_features WHERE margin_sec < -0.000001") or 0
        )
        percentile_out_of_range = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM runner_runperf_features
                WHERE finish_percentile IS NOT NULL
                  AND (finish_percentile < -0.000001 OR finish_percentile > 1.000001)
                """,
            )
            or 0
        )
        winner_margin_nonzero = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM runner_runperf_features
                WHERE finish=1 AND margin_sec IS NOT NULL AND ABS(margin_sec) > 0.000001
                """,
            )
            or 0
        )
        residual_arithmetic_violations = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM runner_runperf_features
                WHERE time_residual_raw_bias_sec IS NOT NULL
                  AND ABS(time_residual_raw_bias_sec -
                          (expected_time_sec - (actual_time_sec - day_bias_raw_sec))) > 0.000001
                """,
            )
            or 0
        )
        market_named_columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info(runner_runperf_features)").fetchall()
            if "odds" in str(row[1]).lower() or "popularity" in str(row[1]).lower()
        ]

        checks = {
            "integrity_ok": integrity == "ok",
            "latest_build_success": build_dict is not None and build_dict.get("status") == "SUCCESS",
            "strict_past_only_history": chronology_violations == 0,
            "no_duplicate_keys": duplicate_expected == 0 and duplicate_runner == 0,
            "nonnegative_margin": negative_margin == 0,
            "finish_percentile_in_range": percentile_out_of_range == 0,
            "winner_margin_zero": winner_margin_nonzero == 0,
            "residual_arithmetic_ok": residual_arithmetic_violations == 0,
            "no_market_columns": len(market_named_columns) == 0,
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        return {
            "audit_version": VERSION,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "database": {
                "path": str(db_path),
                "size_bytes": db_path.stat().st_size,
                "sha256": _sha256(db_path) if include_db_sha256 else None,
                "integrity_check": integrity,
            },
            "build": build_dict,
            "methods": method_rows,
            "yearly": yearly,
            "violations": {
                "chronology": chronology_violations,
                "duplicate_expected": duplicate_expected,
                "duplicate_runner": duplicate_runner,
                "negative_margin": negative_margin,
                "percentile_out_of_range": percentile_out_of_range,
                "winner_margin_nonzero": winner_margin_nonzero,
                "residual_arithmetic": residual_arithmetic_violations,
                "market_named_columns": market_named_columns,
            },
            "checks": checks,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-db-hash", action="store_true")
    args = parser.parse_args()
    report = audit(args.db, include_db_sha256=not args.no_db_hash)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
