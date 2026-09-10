#!/usr/bin/env python3
"""Non-predictive build audit for JRDB Training Research Base v0.1."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from jrdb_raw import ReaderAudit, iter_archive_records

VERSION = "0.1.0"
KINDS = ("BAC", "KYI", "CHA", "CYB", "SED", "UKC")
MARKET_TOKENS = ("odds", "popularity", "payout", "market", "tansho", "fukusho")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scalar(db: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    row = db.execute(sql, params).fetchone()
    return None if row is None else row[0]


def _rows(db: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = db.execute(sql)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 8)


def _raw_audit(raw_root: Path, years: list[int]) -> dict[str, Any]:
    reader_audit = ReaderAudit()
    integrity_failures: list[str] = []
    missing_archives: list[str] = []
    record_counts: Counter[str] = Counter()
    for year in years:
        for kind in KINDS:
            archive = raw_root / kind / f"{kind}_{year}.zip"
            if not archive.is_file():
                missing_archives.append(str(archive))
                continue
            try:
                with zipfile.ZipFile(archive) as zf:
                    bad = zf.testzip()
                    if bad is not None:
                        integrity_failures.append(f"{archive}:{bad}")
                for _member, _record in iter_archive_records(archive, kind, reader_audit):
                    record_counts[kind] += 1
            except (OSError, zipfile.BadZipFile) as exc:
                integrity_failures.append(f"{archive}:{exc}")
    return {
        "zip_integrity": "PASS" if not integrity_failures and not missing_archives else "FAIL",
        "missing_archives": missing_archives,
        "integrity_failures": integrity_failures,
        "record_length_errors": dict(reader_audit.record_length_errors),
        "record_counts": dict(record_counts),
    }


def audit(db_path: Path, raw_root: Path | None = None) -> dict[str, Any]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        integrity = _scalar(db, "PRAGMA integrity_check")
        total = int(_scalar(db, "SELECT COUNT(*) FROM training_runner") or 0)
        annual = _rows(db, "SELECT year,COUNT(*) AS rows FROM training_runner GROUP BY year ORDER BY year")
        split_counts = {row[0]: int(row[1]) for row in db.execute(
            "SELECT data_split,COUNT(*) FROM training_runner GROUP BY data_split"
        )}
        columns = [str(row[1]).lower() for row in db.execute("PRAGMA table_info(training_runner)")]
        contaminated = sorted({column for column in columns if any(token in column for token in MARKET_TOKENS)})

        presence = {}
        for label, predicate in {
            "horse_id": "horse_id IS NOT NULL AND horse_id<>''",
            "cha": "cha_record_hash IS NOT NULL",
            "cyb": "cyb_record_hash IS NOT NULL",
            "sed": "sed_record_hash IS NOT NULL",
            "trainer_code": "trainer_code IS NOT NULL AND trainer_code<>''",
            "rotation_rest": "rotation_interval IS NOT NULL OR days_since_last_run IS NOT NULL",
            "cha_final_segment": "final_segment_sec IS NOT NULL",
            "cha_course": "course_code IS NOT NULL AND course_code<>''",
            "cha_furlong": "furlong_count IS NOT NULL",
            "cyb_training_type": "training_type_code IS NOT NULL AND training_type_code<>''",
            "cyb_course_type": "training_course_type_code IS NOT NULL AND training_course_type_code<>''",
            "official_runperf": "runperf_score_status IS NOT NULL",
        }.items():
            count = int(_scalar(db, f"SELECT COUNT(*) FROM training_runner WHERE {predicate}") or 0)
            presence[label] = {"count": count, "rate": _rate(count, total)}

        numeric_columns = [
            "carried_weight_kg","body_weight_kg","rotation_interval","days_since_last_run",
            "days_before_race","workout_count","furlong_count","first_segment_sec",
            "middle_segment_sec","final_segment_sec","jrdb_first_segment_index",
            "jrdb_middle_segment_index","jrdb_final_segment_index","jrdb_workout_index_cha",
            "jrdb_workout_index_cyb","finish_index","week_ago_workout_index",
            "finish_percentile","official_runperf_raw",
        ]
        nonfinite = {}
        for column in numeric_columns:
            count = int(_scalar(db, f"SELECT COUNT(*) FROM training_runner WHERE {column}!={column}") or 0)
            if count:
                nonfinite[column] = count

        duplicate_count = int(_scalar(db, """
            SELECT COUNT(*) FROM (
              SELECT race_key,horse_no,COUNT(*) n FROM training_runner
              GROUP BY race_key,horse_no HAVING n>1
            )
        """) or 0)
        future_training = int(_scalar(db,
            "SELECT COUNT(*) FROM training_runner WHERE training_date>race_date OR days_before_race<0") or 0)
        chronology = int(_scalar(db, """
            SELECT COUNT(*) FROM training_runner
            WHERE days_since_last_run<0 OR prior_run_count<0 OR career_run_count<>prior_run_count+1
        """) or 0)
        outcome_date_ordering = int(_scalar(db, """
            SELECT COUNT(*) FROM training_runner
            WHERE runperf_score_status IS NOT NULL
              AND (race_date IS NULL OR year<>CAST(substr(race_date,1,4) AS INTEGER))
        """) or 0)
        runperf_provenance_missing = int(_scalar(db, """
            SELECT COUNT(*) FROM training_runner
            WHERE runperf_score_status='OK' AND official_runperf_raw IS NOT NULL
              AND (runperf_formula<>'T1|EXPANDING|RAW'
                   OR runperf_version<>'Official RunPerf v0.1'
                   OR runperf_provenance IS NULL OR runperf_provenance='')
        """) or 0)
        source_archive_hash_missing = int(_scalar(db,
            "SELECT COUNT(*) FROM source_archive WHERE archive_sha256 IS NULL OR length(archive_sha256)<>64") or 0)

        index_names = {row[1] for row in db.execute("PRAGMA index_list(training_runner)")}
        required_indices = {
            "ix_training_horse_date","ix_training_horse_comparable","ix_training_trainer_date",
            "ix_training_trainer_course","ix_training_year","ix_training_rest","ix_training_cyb_course_use",
        }
        missing_indices = sorted(required_indices-index_names)

        query_plan = [row[3] for row in db.execute("""
            EXPLAIN QUERY PLAN SELECT final_segment_sec FROM training_runner
            WHERE horse_id=? AND course_code=? AND furlong_count=? AND race_date<?
            ORDER BY race_date
        """, ("TEST","CW",5,"2024-01-01"))]

        raw_report = None
        if raw_root is not None:
            raw_report = _raw_audit(raw_root, list(range(2010, 2026)))

        checks = {
            "sqlite_integrity": integrity == "ok",
            "exact_year_coverage": [row["year"] for row in annual] == list(range(2010, 2026)),
            "duplicate_race_horse": duplicate_count == 0,
            "missing_horse_id": presence["horse_id"]["count"] == total,
            "training_not_after_race": future_training == 0,
            "chronology": chronology == 0,
            "outcome_date_ordering": outcome_date_ordering == 0,
            "runperf_provenance": runperf_provenance_missing == 0,
            "source_archive_hashes": source_archive_hash_missing == 0,
            "nonfinite_numeric": not nonfinite,
            "market_data_contamination": not contaminated,
            "required_indices": not missing_indices,
            "holdout_rows_present": split_counts.get("HOLDOUT",0)>0,
        }
        if raw_report is not None:
            checks["raw_zip_integrity"] = raw_report["zip_integrity"] == "PASS"
            checks["record_length_errors"] = not raw_report["record_length_errors"]

        status = "PASS" if all(checks.values()) else "FAIL"
        return {
            "status": status,
            "audit_version": VERSION,
            "database": {"filename": db_path.name,"size_bytes": db_path.stat().st_size,"sha256": _sha256(db_path)},
            "checks": checks,
            "violations": {
                "duplicate_race_key_horse_no": duplicate_count,
                "missing_horse_id": total-presence["horse_id"]["count"],
                "training_after_race": future_training,
                "chronology": chronology,
                "outcome_date_ordering": outcome_date_ordering,
                "runperf_provenance_missing": runperf_provenance_missing,
                "source_archive_hash_missing": source_archive_hash_missing,
                "nonfinite_numeric": nonfinite,
                "market_columns": contaminated,
                "missing_indices": missing_indices,
            },
            "row_counts": {"total": total,"annual": annual,"warmup_2010_2012": split_counts.get("WARMUP",0),
                           "development_2013_2023": split_counts.get("DEVELOPMENT",0),
                           "holdout_2024_2025": split_counts.get("HOLDOUT",0)},
            "coverage": presence,
            "join_rates": {"cha_to_identity": presence["cha"],"cyb_to_identity": presence["cyb"],
                           "sed_to_identity": presence["sed"]},
            "raw": raw_report,
            "representative_query_plan": query_plan,
            "holdout_policy": {
                "predictive_metrics_computed": False,
                "allowed_audit_only": True,
                "period": "2024-2025",
            },
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.db, args.raw_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "out": str(args.out)}, ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
