#!/usr/bin/env python3
"""Compare JRDB Core v1.2 against a v1.1.2 baseline DB.

Volatile timestamp / ingest-run fields are excluded from semantic metadata
comparison. Existing normalized Core tables must remain identical because v1.2
is an additive UKC profile extension.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

CORE_TABLES = [
    "race",
    "entry",
    "result",
    "training_analysis",
    "workout",
    "result_extension",
    "entry_previous_result",
    "horse_current",
    "horse_history",
    "meta_duplicate",
    "code_master",
]

META_QUERIES = {
    "meta_archive": "SELECT source_kind,archive_name,year,sha256,size_bytes FROM {db}.meta_archive ORDER BY source_kind,archive_name",
    "meta_source_file": "SELECT source_kind,filename,business_date,record_count,sha256,record_length,is_canonical,source_role FROM {db}.meta_source_file ORDER BY source_kind,filename",
    "meta_anomaly": "SELECT severity,anomaly_type,source_kind,business_date,record_no,business_key,detail_json FROM {db}.meta_anomaly ORDER BY severity,anomaly_type,source_kind,business_date,record_no,business_key,detail_json",
    "code_master_version": "SELECT source_name FROM {db}.code_master_version ORDER BY source_name",
}


def scalar(conn: sqlite3.Connection, sql: str):
    return conn.execute(sql).fetchone()[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True, help="v1.1.2 SQLite")
    ap.add_argument("--candidate", type=Path, required=True, help="v1.2 SQLite")
    ap.add_argument("--json", type=Path, help="optional report output")
    args = ap.parse_args()

    conn = sqlite3.connect(args.candidate)
    conn.execute("ATTACH DATABASE ? AS old", (str(args.baseline),))
    report: dict[str, object] = {"tables": {}, "metadata": {}}
    passed = True

    for table in CORE_TABLES:
        old_count = scalar(conn, f"SELECT count(*) FROM old.{table}")
        new_count = scalar(conn, f"SELECT count(*) FROM main.{table}")
        old_minus_new = scalar(conn, f"SELECT count(*) FROM (SELECT * FROM old.{table} EXCEPT SELECT * FROM main.{table})")
        new_minus_old = scalar(conn, f"SELECT count(*) FROM (SELECT * FROM main.{table} EXCEPT SELECT * FROM old.{table})")
        ok = old_count == new_count and old_minus_new == 0 and new_minus_old == 0
        report["tables"][table] = {
            "baseline": old_count,
            "candidate": new_count,
            "old_minus_new": old_minus_new,
            "new_minus_old": new_minus_old,
            "pass": ok,
        }
        passed &= ok

    for name, query in META_QUERIES.items():
        old_rows = conn.execute(query.format(db="old")).fetchall()
        new_rows = conn.execute(query.format(db="main")).fetchall()
        ok = old_rows == new_rows
        report["metadata"][name] = {"baseline": len(old_rows), "candidate": len(new_rows), "pass": ok}
        passed &= ok

    report["candidate_integrity_check"] = scalar(conn, "PRAGMA integrity_check")
    passed &= report["candidate_integrity_check"] == "ok"

    report["horse_profile_current"] = scalar(conn, "SELECT count(*) FROM horse_profile_current")
    report["horse_profile_history"] = scalar(conn, "SELECT count(*) FROM horse_profile_history")
    report["entry_count"] = scalar(conn, "SELECT count(*) FROM entry")
    report["entry_profile_match"] = scalar(conn, "SELECT count(*) FROM entry e JOIN horse_profile_current h ON h.horse_id=e.horse_id")
    report["entry_profile_unmatched"] = scalar(conn, "SELECT count(*) FROM entry e LEFT JOIN horse_profile_current h ON h.horse_id=e.horse_id WHERE h.horse_id IS NULL")
    report["entry_sire_nonblank"] = scalar(conn, "SELECT count(*) FROM entry e JOIN horse_profile_current h ON h.horse_id=e.horse_id WHERE trim(coalesce(h.sire_name,''))<>''")
    report["manual_required"] = scalar(conn, "SELECT count(*) FROM meta_duplicate WHERE resolution='MANUAL_REQUIRED'")
    report["invalid_source_filename_date"] = scalar(conn, "SELECT count(*) FROM meta_anomaly WHERE anomaly_type='INVALID_SOURCE_FILENAME_DATE'")
    report["bac_fallback"] = scalar(conn, "SELECT count(*) FROM race WHERE source_origin='SED_FALLBACK'")
    report["verdict"] = "PASS" if passed else "FAIL"

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
