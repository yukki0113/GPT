#!/usr/bin/env python3
"""Audit JRDB independent-index longitudinal base SQLite.

The audit is intentionally lightweight and produces JSON suitable for GitHub Actions
artifacts/comments. It does not mutate the research database.
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
    """Return an audit report for one completed Index Base database."""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        integrity = _scalar(connection, "PRAGMA integrity_check")
        build_rows = _rows(
            connection,
            """
            SELECT build_id,builder_version,schema_version,started_at,finished_at,status,
                   years_json,race_count,race_result_context_count,runner_pre_count,
                   runner_result_count,workout_count,training_count,
                   profile_observation_count,anomaly_count,message
            FROM meta_index_base_build
            ORDER BY build_id
            """,
        )
        latest_build = build_rows[-1] if build_rows else None

        yearly = _rows(
            connection,
            """
            SELECT
              r.year,
              COUNT(DISTINCT r.race_key) AS race_count,
              COUNT(DISTINCT CASE WHEN r.availability_class='PRE_RACE' THEN r.race_key END) AS pre_race_count,
              COUNT(DISTINCT CASE WHEN r.availability_class='CURRENT_RESULT_FALLBACK' THEN r.race_key END) AS fallback_race_count,
              COUNT(DISTINCT p.race_key || ':' || printf('%02d',p.horse_no)) AS runner_pre_count,
              COUNT(DISTINCT x.race_key || ':' || printf('%02d',x.horse_no)) AS runner_result_count,
              COUNT(DISTINCT w.race_key || ':' || printf('%02d',w.horse_no)) AS workout_count,
              COUNT(DISTINCT t.race_key || ':' || printf('%02d',t.horse_no)) AS training_count
            FROM race_context r
            LEFT JOIN runner_pre p ON p.race_key=r.race_key
            LEFT JOIN runner_result x ON x.race_key=r.race_key
            LEFT JOIN workout_main w ON w.race_key=r.race_key
            LEFT JOIN training_analysis t ON t.race_key=r.race_key
            GROUP BY r.year
            ORDER BY r.year
            """,
        )

        # Key coverage is measured from runner_pre because it represents the prediction universe.
        runner_pre_count = int(_scalar(connection, "SELECT COUNT(*) FROM runner_pre") or 0)
        matched_result_count = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM runner_pre p
                JOIN runner_result x
                  ON x.race_key=p.race_key AND x.horse_no=p.horse_no
                """,
            )
            or 0
        )
        horse_id_match_count = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM runner_pre p
                JOIN runner_result x
                  ON x.race_key=p.race_key AND x.horse_no=p.horse_no
                WHERE p.horse_id IS NOT NULL AND p.horse_id<>''
                  AND x.horse_id IS NOT NULL AND x.horse_id<>''
                  AND p.horse_id=x.horse_id
                """,
            )
            or 0
        )
        horse_id_comparable_count = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM runner_pre p
                JOIN runner_result x
                  ON x.race_key=p.race_key AND x.horse_no=p.horse_no
                WHERE p.horse_id IS NOT NULL AND p.horse_id<>''
                  AND x.horse_id IS NOT NULL AND x.horse_id<>''
                """,
            )
            or 0
        )

        prev_link_count = int(
            _scalar(
                connection,
                "SELECT COUNT(*) FROM runner_previous_link WHERE prev_result_key IS NOT NULL",
            )
            or 0
        )
        prev_resolved_count = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM runner_previous_link l
                JOIN runner_result x ON x.result_key=l.prev_result_key
                WHERE l.prev_result_key IS NOT NULL
                """,
            )
            or 0
        )
        prev_link_by_sequence = _rows(
            connection,
            """
            SELECT
              l.sequence,
              SUM(CASE WHEN l.prev_result_key IS NOT NULL THEN 1 ELSE 0 END) AS link_count,
              SUM(CASE WHEN l.prev_result_key IS NOT NULL AND x.result_key IS NOT NULL THEN 1 ELSE 0 END) AS resolved_count
            FROM runner_previous_link l
            LEFT JOIN runner_result x ON x.result_key=l.prev_result_key
            GROUP BY l.sequence
            ORDER BY l.sequence
            """,
        )
        for row in prev_link_by_sequence:
            row["resolution_rate"] = _rate(int(row["resolved_count"]), int(row["link_count"]))

        profile_runner_count = int(
            _scalar(
                connection,
                "SELECT COUNT(*) FROM runner_pre WHERE horse_id IS NOT NULL AND horse_id<>''",
            )
            or 0
        )
        profile_asof_count = int(
            _scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM runner_pre p
                JOIN race_context r ON r.race_key=p.race_key
                WHERE p.horse_id IS NOT NULL AND p.horse_id<>''
                  AND EXISTS (
                    SELECT 1
                    FROM horse_profile_observation h
                    WHERE h.horse_id=p.horse_id
                      AND h.data_date < r.race_date
                  )
                """,
            )
            or 0
        )

        field_completeness = _rows(
            connection,
            """
            SELECT
              r.year,
              COUNT(x.race_key) AS result_rows,
              SUM(CASE WHEN x.time_sec IS NOT NULL THEN 1 ELSE 0 END) AS time_rows,
              SUM(CASE WHEN x.first3f_sec IS NOT NULL THEN 1 ELSE 0 END) AS first3f_rows,
              SUM(CASE WHEN x.last3f_sec IS NOT NULL THEN 1 ELSE 0 END) AS last3f_rows,
              SUM(CASE WHEN x.carried_weight_kg IS NOT NULL THEN 1 ELSE 0 END) AS weight_rows,
              SUM(CASE WHEN x.body_weight_kg IS NOT NULL THEN 1 ELSE 0 END) AS body_weight_rows,
              SUM(CASE WHEN x.corner4 IS NOT NULL THEN 1 ELSE 0 END) AS corner4_rows,
              SUM(CASE WHEN rc.track_condition_code IS NOT NULL AND rc.track_condition_code<>'' THEN 1 ELSE 0 END) AS track_condition_rows
            FROM race_context r
            LEFT JOIN runner_result x ON x.race_key=r.race_key
            LEFT JOIN race_result_context rc ON rc.race_key=r.race_key
            GROUP BY r.year
            ORDER BY r.year
            """,
        )
        for row in field_completeness:
            denominator = int(row["result_rows"])
            for field in (
                "time_rows",
                "first3f_rows",
                "last3f_rows",
                "weight_rows",
                "body_weight_rows",
                "corner4_rows",
                "track_condition_rows",
            ):
                row[field.replace("_rows", "_rate")] = _rate(int(row[field]), denominator)

        duplicate_checks = {
            "runner_pre_duplicate_business_keys": int(
                _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM (
                      SELECT race_key,horse_no,COUNT(*) c
                      FROM runner_pre GROUP BY race_key,horse_no HAVING c>1
                    )
                    """,
                )
                or 0
            ),
            "runner_result_duplicate_business_keys": int(
                _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM (
                      SELECT race_key,horse_no,COUNT(*) c
                      FROM runner_result GROUP BY race_key,horse_no HAVING c>1
                    )
                    """,
                )
                or 0
            ),
            "runner_result_duplicate_result_keys": int(
                _scalar(
                    connection,
                    """
                    SELECT COUNT(*) FROM (
                      SELECT result_key,COUNT(*) c
                      FROM runner_result
                      WHERE result_key IS NOT NULL
                      GROUP BY result_key HAVING c>1
                    )
                    """,
                )
                or 0
            ),
        }

        source_manifest = _rows(
            connection,
            """
            SELECT source_kind,year,archive_path,archive_sha256,archive_size_bytes,member_count
            FROM meta_index_base_source
            ORDER BY year,source_kind
            """,
        )
        anomalies = _rows(
            connection,
            """
            SELECT severity,anomaly_type,source_kind,year,business_key,detail,detected_at
            FROM meta_index_base_anomaly
            ORDER BY anomaly_id
            """,
        )

        fallback_count = int(
            _scalar(
                connection,
                "SELECT COUNT(*) FROM race_context WHERE availability_class='CURRENT_RESULT_FALLBACK'",
            )
            or 0
        )
        workout_count = int(_scalar(connection, "SELECT COUNT(*) FROM workout_main") or 0)
        training_count = int(_scalar(connection, "SELECT COUNT(*) FROM training_analysis") or 0)

        checks = {
            "integrity_ok": integrity == "ok",
            "latest_build_success": latest_build is not None and latest_build.get("status") == "SUCCESS",
            "no_duplicate_business_keys": all(value == 0 for value in duplicate_checks.values()),
            "runner_pre_has_results": matched_result_count > 0,
            "previous_links_resolve": prev_resolved_count > 0 if prev_link_count > 0 else True,
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
            "builds": build_rows,
            "yearly": yearly,
            "coverage": {
                "runner_pre_count": runner_pre_count,
                "matched_result_count": matched_result_count,
                "runner_pre_to_result_match_rate": _rate(matched_result_count, runner_pre_count),
                "horse_id_comparable_count": horse_id_comparable_count,
                "horse_id_match_count": horse_id_match_count,
                "horse_id_match_rate": _rate(horse_id_match_count, horse_id_comparable_count),
                "previous_link_count": prev_link_count,
                "previous_link_resolved_count": prev_resolved_count,
                "previous_link_resolution_rate": _rate(prev_resolved_count, prev_link_count),
                "previous_link_by_sequence": prev_link_by_sequence,
                "profile_runner_count": profile_runner_count,
                "profile_asof_count": profile_asof_count,
                "profile_asof_rate": _rate(profile_asof_count, profile_runner_count),
                "fallback_race_count": fallback_count,
                "workout_count": workout_count,
                "training_count": training_count,
            },
            "field_completeness_by_year": field_completeness,
            "duplicate_checks": duplicate_checks,
            "source_manifest": source_manifest,
            "anomalies": anomalies,
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