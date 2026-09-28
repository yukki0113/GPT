#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upgrade Analysis Lite v1.3 SQLite to a v1.4 shadow candidate.

The v1.3 fact rows/results remain authoritative. This upgrader only backfills
race-context columns needed by RaceNote Trend:
- meeting_no
- meeting_day
- race_name
- course_code

BAC sources may come from annual Raw ZIPs and/or PACI ZIPs. The output is a
shadow SQLite candidate intended for Parquet migration/audit before promotion.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from jrdb_raw import Parser, iter_archive_records, race_key as raw_race_key

VERSION = "upgrade-jrdb-analysis-v1_4-shadow-0.1"


class UpgradeError(RuntimeError):
    pass


def _meeting_parts(race_key: str) -> tuple[int | None, int | None]:
    if len(race_key) < 8:
        return None, None
    meeting = int(race_key[4]) if race_key[4].isdigit() else None
    try:
        day = int(race_key[5].lower(), 16)
    except ValueError:
        day = None
    return meeting, day


def _iter_bac_sources(annual_root: Path | None, paci_root: Path | None) -> Iterable[Path]:
    if annual_root is not None and annual_root.exists():
        yield from sorted(annual_root.rglob("BAC_*.zip"))
    if paci_root is not None and paci_root.exists():
        yield from sorted(paci_root.rglob("PACI*.zip"))


def _load_bac_map(paths: Iterable[Path]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    parser = Parser()
    mapping: dict[str, dict[str, Any]] = {}
    files = []
    record_count = 0
    for path in paths:
        local_count = 0
        for _member, record in iter_archive_records(path, "BAC"):
            key = raw_race_key(record)
            parsed = parser.bac(record)
            mapping[key] = {
                "race_name": str(parsed.get("race_name") or "").strip() or None,
                "course_code": str(parsed.get("course_code") or "").strip() or None,
                "source_file": path.name,
            }
            local_count += 1
        files.append({"path": str(path), "bac_records": local_count})
        record_count += local_count
    return mapping, {
        "files": files,
        "file_count": len(files),
        "bac_record_count": record_count,
        "distinct_race_keys": len(mapping),
    }


def _columns(conn: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in conn.execute("PRAGMA table_info(fact_entry_result_lite)")}


def _source_signature(conn: sqlite3.Connection) -> dict[str, Any]:
    row_count = int(conn.execute("SELECT COUNT(*) FROM fact_entry_result_lite").fetchone()[0])
    race_count = int(conn.execute("SELECT COUNT(DISTINCT race_key) FROM fact_entry_result_lite").fetchone()[0])
    horse_key_count = int(conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT race_key, horse_no, COUNT(*) c FROM fact_entry_result_lite "
        "GROUP BY race_key, horse_no HAVING c=1)"
    ).fetchone()[0])
    period = conn.execute("SELECT MIN(race_date), MAX(race_date) FROM fact_entry_result_lite").fetchone()
    return {
        "row_count": row_count,
        "race_count": race_count,
        "unique_race_horse_keys": horse_key_count,
        "period_from": period[0],
        "period_to": period[1],
    }


def upgrade(
    source: Path,
    output: Path,
    *,
    annual_root: Path | None,
    paci_root: Path | None,
) -> dict[str, Any]:
    if not source.is_file():
        raise UpgradeError(f"source SQLite not found: {source}")
    if output.exists():
        raise UpgradeError(f"refusing to overwrite output: {output}")

    source_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        required = {"race_key", "race_date", "horse_no"}
        missing = required - _columns(source_conn)
        if missing:
            raise UpgradeError(f"source Analysis missing columns: {sorted(missing)}")
        source_signature = _source_signature(source_conn)
    finally:
        source_conn.close()

    bac_map, bac_report = _load_bac_map(_iter_bac_sources(annual_root, paci_root))
    if not bac_map:
        raise UpgradeError("no BAC records were loaded")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)

    conn = sqlite3.connect(output)
    try:
        columns = _columns(conn)
        for name, ddl in (
            ("meeting_no", "INTEGER"),
            ("meeting_day", "INTEGER"),
            ("race_name", "TEXT"),
            ("course_code", "TEXT"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE fact_entry_result_lite ADD COLUMN {name} {ddl}")

        race_keys = [
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT race_key FROM fact_entry_result_lite ORDER BY race_key"
            )
        ]
        missing_bac: list[str] = []
        mapped = 0
        named = 0
        course = 0
        for key in race_keys:
            meeting_no, meeting_day = _meeting_parts(key)
            bac = bac_map.get(key)
            if bac is None:
                missing_bac.append(key)
                conn.execute(
                    "UPDATE fact_entry_result_lite SET meeting_no=?, meeting_day=? WHERE race_key=?",
                    (meeting_no, meeting_day, key),
                )
                continue
            mapped += 1
            if bac["race_name"]:
                named += 1
            if bac["course_code"]:
                course += 1
            conn.execute(
                "UPDATE fact_entry_result_lite "
                "SET meeting_no=?, meeting_day=?, race_name=?, course_code=? "
                "WHERE race_key=?",
                (meeting_no, meeting_day, bac["race_name"], bac["course_code"], key),
            )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_analysis_local_context_v14 "
            "ON fact_entry_result_lite("
            "year,venue_code,meeting_no,meeting_day,track_type,distance,"
            "race_condition_code,grade_code,course_code)"
        )

        # Metadata is descriptive only; facts/results are unchanged.
        if "meta_analysis_build" in {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }:
            conn.execute(
                "UPDATE meta_analysis_build SET schema_version='v1.4', builder_version=?",
                (VERSION,),
            )
        if "meta_analysis_ingest_batch" in {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }:
            conn.execute(
                "UPDATE meta_analysis_ingest_batch SET schema_version='v1.4'"
            )

        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        output_signature = _source_signature(conn)

        duplicate_keys = int(conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT race_key,horse_no,COUNT(*) c FROM fact_entry_result_lite "
            "GROUP BY race_key,horse_no HAVING c<>1)"
        ).fetchone()[0])
        meeting_missing = int(conn.execute(
            "SELECT COUNT(DISTINCT race_key) FROM fact_entry_result_lite "
            "WHERE meeting_no IS NULL OR meeting_day IS NULL"
        ).fetchone()[0])
    finally:
        conn.close()

    if source_signature != output_signature:
        raise UpgradeError(
            f"source/output signature mismatch: source={source_signature} output={output_signature}"
        )
    if integrity != "ok":
        raise UpgradeError(f"output integrity_check failed: {integrity}")
    if duplicate_keys:
        raise UpgradeError(f"duplicate race/horse keys after upgrade: {duplicate_keys}")
    if meeting_missing:
        raise UpgradeError(f"meeting context missing for {meeting_missing} races")

    report = {
        "status": "PASS",
        "version": VERSION,
        "source": str(source),
        "output": str(output),
        "signature": output_signature,
        "bac": bac_report,
        "coverage": {
            "distinct_races": output_signature["race_count"],
            "bac_mapped_races": mapped,
            "bac_missing_races": len(missing_bac),
            "race_name_nonblank_races": named,
            "course_code_nonblank_races": course,
            "bac_mapping_rate": round(mapped / len(race_keys), 6) if race_keys else 0.0,
        },
        "missing_bac_sample": missing_bac[:100],
        "integrity_check": integrity,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annual-root", type=Path)
    parser.add_argument("--paci-root", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = upgrade(
        args.source,
        args.output,
        annual_root=args.annual_root,
        paci_root=args.paci_root,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
