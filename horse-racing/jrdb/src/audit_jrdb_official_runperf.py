#!/usr/bin/env python3
"""Fail-closed audit for the official JRDB RunPerf v0.1 SQLite materialization."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
FIRST_MODEL_YEAR = 2013
COEFFICIENT_TOLERANCE = 1.0e-6
DOCUMENTED_HOLDOUT_COEFFICIENTS = {
    2024: (0.6046142161, 0.0250611457, 0.0947088164),
    2025: (0.6045819996, 0.0252398396, 0.0942773218),
}


def _sha256(path: Path) -> str:
    """Return a SHA-256 checksum for a local database."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scalar(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    """Return the first scalar result, including nullable values."""
    row = connection.execute(sql, params).fetchone()
    if row is None:
        return None
    return row[0]


def _rows(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Return a SQL result with explicit JSON-ready column names."""
    cursor = connection.execute(sql, params)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _is_finite(value: Any) -> bool:
    """Return whether a nullable database value is finite."""
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _expected_snapshot_target(year: int) -> int:
    """Return the exact permitted snapshot year, including the warm-up exception."""
    if year < FIRST_MODEL_YEAR:
        return FIRST_MODEL_YEAR
    return year


def _resolve_source_path(build: sqlite3.Row | None, source_override: Path | None) -> Path | None:
    """Use an explicit source only when provided; otherwise use build provenance."""
    if source_override is not None:
        return source_override
    if build is None or build["source_runperf_db_path"] is None:
        return None
    return Path(str(build["source_runperf_db_path"]))


def _source_reconciliation(
    official: sqlite3.Connection,
    source_path: Path | None,
    expected_sha256: str | None,
) -> dict[str, Any]:
    """Compare source row/status coverage when the recorded candidate DB is available."""
    result: dict[str, Any] = {
        "source_available": False,
        "source_sha256_matches": None,
        "source_row_count": None,
        "source_status_mismatches": None,
        "source_component_mismatches": None,
    }
    if source_path is None or not source_path.is_file():
        return result
    result["source_available"] = True
    if expected_sha256:
        result["source_sha256_matches"] = _sha256(source_path) == expected_sha256
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    try:
        result["source_row_count"] = int(
            _scalar(
                source,
                "SELECT COUNT(*) FROM runner_runperf_features WHERE baseline_method='EXPANDING'",
            )
            or 0
        )
        # The source and official databases are separate immutable inputs.  A compact
        # in-memory key map avoids mutating the read-only official connection with ATTACH.
        source_rows = source.execute(
            """
            SELECT race_key,horse_no,calculation_status,expected_time_sec,day_bias_raw_sec,
                   time_residual_raw_bias_sec,margin_per_1000m_sec
            FROM runner_runperf_features WHERE baseline_method='EXPANDING'
            """
        ).fetchall()
        source_by_key = {(str(row[0]), int(row[1])): row for row in source_rows}
        status_mismatches = 0
        component_mismatches = 0
        for row in official.execute(
            """
            SELECT race_key,horse_no,source_calculation_status,expected_time_sec,day_bias_raw_sec,
                   time_raw_bias_sec,margin_score
            FROM official_runperf
            """
        ):
            source_row = source_by_key.get((str(row[0]), int(row[1])))
            if source_row is None or str(row[2]) != str(source_row[2]):
                status_mismatches += 1
                continue
            expected_values = (source_row[3], source_row[4], source_row[5])
            actual_values = (row[3], row[4], row[5])
            if any(
                (left is None) != (right is None)
                or (left is not None and abs(float(left) - float(right)) > 1.0e-9)
                for left, right in zip(actual_values, expected_values)
            ):
                component_mismatches += 1
                continue
            source_margin = source_row[6]
            expected_margin = None if source_margin is None else -float(source_margin)
            if (row[6] is None) != (expected_margin is None):
                component_mismatches += 1
            elif row[6] is not None and abs(float(row[6]) - float(expected_margin)) > 1.0e-9:
                component_mismatches += 1
        result["source_status_mismatches"] = status_mismatches
        result["source_component_mismatches"] = component_mismatches
    finally:
        source.close()
    return result


def audit(
    database_path: Path,
    source_runperf_db: Path | None = None,
    include_db_sha256: bool = True,
) -> dict[str, Any]:
    """Return a fail-closed official RunPerf audit report."""
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        integrity = _scalar(connection, "PRAGMA integrity_check")
        build = connection.execute(
            "SELECT * FROM meta_official_runperf_build ORDER BY build_id DESC LIMIT 1"
        ).fetchone()
        build_dict = dict(build) if build is not None else None
        duplicate_business_keys = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM (
                  SELECT race_key,horse_no,COUNT(*) AS row_count
                  FROM official_runperf GROUP BY race_key,horse_no HAVING row_count>1
                )
                """,
            )
            or 0
        )
        source_counts = _rows(
            connection,
            """
            SELECT year,source_calculation_status,COUNT(*) AS row_count
            FROM official_runperf GROUP BY year,source_calculation_status
            ORDER BY year,source_calculation_status
            """,
        )
        yearly = _rows(
            connection,
            """
            SELECT year,score_status,score_provenance,COUNT(*) AS row_count,
                   SUM(CASE WHEN score_status='OK' THEN 1 ELSE 0 END) AS scored_row_count
            FROM official_runperf GROUP BY year,score_status,score_provenance
            ORDER BY year,score_status,score_provenance
            """,
        )
        annual_coverage = _rows(
            connection,
            """
            SELECT year,COUNT(*) AS source_rows,
                   SUM(CASE WHEN score_status='OK' THEN 1 ELSE 0 END) AS scored_rows
            FROM official_runperf GROUP BY year ORDER BY year
            """,
        )
        for row in annual_coverage:
            row["coverage"] = round(row["scored_rows"] / row["source_rows"], 6) if row["source_rows"] else None

        arithmetic_violations = 0
        nonfinite_coefficients = 0
        nonfinite_components = 0
        provenance_violations = 0
        warmup_violations = 0
        for row in connection.execute(
            """
            SELECT * FROM official_runperf WHERE score_status='OK'
            """
        ):
            values = (
                row["expected_time_sec"], row["day_bias_raw_sec"], row["time_raw_bias_sec"],
                row["margin_score"], row["runperf_raw"], row["coefficient_intercept"],
                row["coefficient_beta_time"], row["coefficient_beta_margin"],
            )
            if not all(_is_finite(value) for value in values):
                nonfinite_components += 1
                continue
            expected_score = (
                float(row["coefficient_intercept"])
                + float(row["coefficient_beta_time"]) * float(row["time_raw_bias_sec"])
                + float(row["coefficient_beta_margin"]) * float(row["margin_score"])
            )
            if abs(float(row["runperf_raw"]) - expected_score) > 1.0e-9:
                arithmetic_violations += 1
            expected_target = _expected_snapshot_target(int(row["year"]))
            if int(row["coefficient_snapshot_target_year"]) != expected_target:
                provenance_violations += 1
            if int(row["coefficient_asof_through_year"]) != expected_target - 1:
                provenance_violations += 1
            if int(row["year"]) < FIRST_MODEL_YEAR:
                if row["score_provenance"] != "WARMUP_RETROSPECTIVE_2013_SNAPSHOT":
                    warmup_violations += 1
            elif row["score_provenance"] != "ANNUAL_ASOF_LITERAL_NEXT_START":
                provenance_violations += 1

        snapshot_rows = _rows(
            connection,
            "SELECT * FROM runperf_coefficient_snapshot ORDER BY target_year",
        )
        for row in snapshot_rows:
            values = (row["intercept"], row["beta_time_raw_bias"], row["beta_margin_score"])
            if not all(_is_finite(value) for value in values):
                nonfinite_coefficients += 1
            if int(row["coefficient_asof_through_year"]) != int(row["target_year"]) - 1:
                provenance_violations += 1
        future_coefficient_backfill = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM official_runperf
                WHERE score_status='OK'
                  AND coefficient_snapshot_target_year > CASE WHEN year<2013 THEN 2013 ELSE year END
                """,
            )
            or 0
        )
        excluded_rows_with_score = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM official_runperf
                WHERE score_status<>'OK' AND runperf_raw IS NOT NULL
                """,
            )
            or 0
        )
        market_named_columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info(official_runperf)")
            if "odds" in str(row[1]).lower() or "popularity" in str(row[1]).lower()
        ]
        horse_date_not_orderable = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*) FROM official_runperf
                WHERE horse_id IS NOT NULL AND horse_id<>'' AND (race_date IS NULL OR race_date='')
                """,
            )
            or 0
        )
        index_names = {str(row[1]) for row in connection.execute("PRAGMA index_list(official_runperf)")}

        holdout_coefficient_mismatches: list[dict[str, Any]] = []
        source_year_max = int(build_dict["source_year_max"]) if build_dict is not None else 0
        for target_year, documented in DOCUMENTED_HOLDOUT_COEFFICIENTS.items():
            if source_year_max < target_year:
                continue
            row = connection.execute(
                """
                SELECT intercept,beta_time_raw_bias,beta_margin_score
                FROM runperf_coefficient_snapshot WHERE target_year=?
                """,
                (target_year,),
            ).fetchone()
            if row is None:
                holdout_coefficient_mismatches.append({"target_year": target_year, "reason": "missing"})
                continue
            actual = tuple(float(value) for value in row)
            if any(abs(left - right) > COEFFICIENT_TOLERANCE for left, right in zip(actual, documented)):
                holdout_coefficient_mismatches.append(
                    {"target_year": target_year, "actual": actual, "documented": documented}
                )

        source_path = _resolve_source_path(build, source_runperf_db)
        reconciliation = _source_reconciliation(
            connection,
            source_path,
            build_dict.get("source_runperf_db_sha256") if build_dict else None,
        )
        source_count_matches = (
            reconciliation["source_row_count"] is not None
            and build_dict is not None
            and int(reconciliation["source_row_count"]) == int(build_dict["source_runner_count"])
            and int(build_dict["materialized_runner_count"]) == int(build_dict["source_runner_count"])
        )
        checks = {
            "integrity_ok": integrity == "ok",
            "latest_build_success": build_dict is not None and build_dict.get("status") == "SUCCESS",
            "source_available": reconciliation["source_available"],
            "source_sha256_matches": reconciliation["source_sha256_matches"] is not False,
            "source_count_matches": source_count_matches,
            "source_statuses_match": reconciliation["source_status_mismatches"] == 0,
            "source_components_match": reconciliation["source_component_mismatches"] == 0,
            "no_duplicate_business_keys": duplicate_business_keys == 0,
            "arithmetic_ok": arithmetic_violations == 0,
            "coefficient_finite": nonfinite_coefficients == 0,
            "scored_components_finite": nonfinite_components == 0,
            "snapshot_chronology_ok": provenance_violations == 0,
            "warmup_provenance_ok": warmup_violations == 0,
            "future_coefficient_backfill_zero": future_coefficient_backfill == 0,
            "excluded_rows_unscored": excluded_rows_with_score == 0,
            "no_market_columns": not market_named_columns,
            "horse_date_orderable": horse_date_not_orderable == 0 and "ix_official_runperf_horse" in index_names,
            "holdout_coefficients_match_documentation": not holdout_coefficient_mismatches,
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        return {
            "audit_version": VERSION,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "database": {
                "path": str(database_path),
                "size_bytes": database_path.stat().st_size,
                "sha256": _sha256(database_path) if include_db_sha256 else None,
                "integrity_check": integrity,
            },
            "build": build_dict,
            "source_reconciliation": reconciliation,
            "source_status_counts": source_counts,
            "yearly_status_counts": yearly,
            "annual_coverage": annual_coverage,
            "coefficient_snapshots": snapshot_rows,
            "violations": {
                "duplicate_business_keys": duplicate_business_keys,
                "arithmetic": arithmetic_violations,
                "nonfinite_coefficients": nonfinite_coefficients,
                "nonfinite_scored_components": nonfinite_components,
                "snapshot_provenance": provenance_violations,
                "warmup_provenance": warmup_violations,
                "future_coefficient_backfill": future_coefficient_backfill,
                "excluded_rows_with_score": excluded_rows_with_score,
                "market_named_columns": market_named_columns,
                "horse_date_not_orderable": horse_date_not_orderable,
                "holdout_coefficient_mismatches": holdout_coefficient_mismatches,
            },
            "checks": checks,
        }
    finally:
        connection.close()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--source-runperf-db", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-db-hash", action="store_true")
    args = parser.parse_args()
    report = audit(args.db, args.source_runperf_db, include_db_sha256=not args.no_db_hash)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
