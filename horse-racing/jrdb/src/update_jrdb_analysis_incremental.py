#!/usr/bin/env python3
"""Incrementally replace completed JRDB dates in Analysis Lite v1.2.

Supported input modes:

1. Daily-kind Raw layout (2026+ fetcher output)
   RAW_ROOT/BAC/BACyymmdd.zip
   RAW_ROOT/KYI/KYIyymmdd.zip
   RAW_ROOT/SED/SEDyymmdd.zip
   RAW_ROOT/CYB/CYByymmdd.zip
   RAW_ROOT/UKC/UKCyymmdd.zip

2. PACI + SED pair (recommended manual/ChatGPT operation)
   PACIyymmdd.zip contains BAC/KYI/CYB/UKC and related pre-race members.
   SEDyymmdd.zip provides completed results and actual track condition.

Fixed-width byte positions are owned by ``jrdb_raw``.  This module keeps only
Analysis Lite joining, as-of and SQLite update semantics.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import zipfile
from pathlib import Path

from jrdb_analysis_raw_adapter import (
    parse_bac,
    parse_cyb,
    parse_kyi,
    parse_sed,
    parse_ukc,
)
from jrdb_raw import race_key as common_race_key, read_fixed_records

VERSION = "1.2-production"
SCHEMA_VERSION = "v1.2"
REQUIRED_KINDS = ("BAC", "KYI", "SED", "CYB", "UKC")
PACI_KINDS = ("BAC", "KYI", "CYB", "UKC")
FACT_COLUMNS = (
    "race_date","year","venue_code","race_no","track_type","distance",
    "race_condition_code","track_condition_code","grade_code","race_key","horse_no",
    "frame_no","horse_id","horse_name","sex_code","age","sire_name",
    "broodmare_sire_name","sire_line_code","broodmare_sire_line_code","jockey_name",
    "running_style","distance_aptitude","uptrend","training_index","finish",
    "abnormal_code","final_win_odds","final_win_popularity","win_payout","place_payout",
    "prev_result_key_1","prev_race_key_1",
)


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value.replace("-", "").replace("/", ""), "%Y%m%d").date()


def infer_date_from_name(path: Path, prefix: str) -> dt.date:
    match = re.fullmatch(rf"{prefix}(\d{{6}})\.zip", path.name, re.IGNORECASE)
    if not match:
        raise ValueError(f"Cannot infer date from {path.name}; expected {prefix}yymmdd.zip")
    yymmdd = match.group(1)
    yy = int(yymmdd[:2])
    year = 2000 + yy if yy < 80 else 1900 + yy
    return dt.date(year, int(yymmdd[2:4]), int(yymmdd[4:6]))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def daily_zip(raw_root: Path, kind: str, date: dt.date) -> Path:
    return raw_root / kind / f"{kind}{date:%y%m%d}.zip"


def read_member(path: Path, kind: str, date: dt.date) -> list[bytes]:
    if not path.exists():
        raise FileNotFoundError(path)
    expected = f"{kind}{date:%y%m%d}.txt".upper()
    with zipfile.ZipFile(path) as archive:
        matches = [name for name in archive.namelist() if Path(name).name.upper() == expected]
        if len(matches) != 1:
            raise ValueError(f"{path}: expected exactly one {expected}, found {len(matches)}")
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"{path}: bad ZIP member {bad}")
        source = archive.read(matches[0])
        records = read_fixed_records(archive, matches[0], kind)
        if source and not records:
            raise ValueError(f"{path}: invalid fixed-width {kind} member {matches[0]}")
        return records


def _parse_lines(lines: dict[str, list[bytes]], date: dt.date) -> tuple[list[tuple], dict[str, object]]:
    races: dict[str, dict[str, object]] = {}
    entries: dict[tuple[str, int | None], dict[str, object]] = {}
    results: dict[tuple[str, int | None], dict[str, object]] = {}
    training: dict[tuple[str, int | None], int | None] = {}
    horses: dict[str, dict[str, object]] = {}

    for raw in lines["UKC"]:
        horse_id, profile = parse_ukc(raw)
        old = horses.get(horse_id)
        if old is None or str(profile["data_date"]) >= str(old["data_date"]):
            horses[horse_id] = profile

    race_date = date.isoformat()
    for raw in lines["BAC"]:
        race = parse_bac(raw, race_date, date.year)
        race_key = common_race_key(raw)
        races.setdefault(race_key, race)

    for raw in lines["KYI"]:
        key, entry = parse_kyi(raw)
        entries.setdefault(key, entry)

    for raw in lines["SED"]:
        key, result, fallback_race = parse_sed(raw, race_date, date.year)
        race_key = key[0]
        if race_key not in races:
            races[race_key] = fallback_race
        elif not races[race_key]["track_condition_code"]:
            races[race_key]["track_condition_code"] = fallback_race["track_condition_code"]
        results.setdefault(key, result)

    for raw in lines["CYB"]:
        key, value = parse_cyb(raw)
        training.setdefault(key, value)

    rows: list[tuple] = []
    missing_profiles = 0
    for key, entry in entries.items():
        race = races.get(key[0])
        result = results.get(key)
        if race is None or result is None:
            continue
        profile = horses.get(str(entry["horse_id"]), {})
        if not profile:
            missing_profiles += 1
        birth_year = profile.get("birth_year")
        age = date.year - int(birth_year) if birth_year else None
        rows.append((
            race["race_date"], race["year"], race["venue_code"], race["race_no"], race["track_type"], race["distance"],
            race["race_condition_code"], race["track_condition_code"], race["grade_code"], key[0], key[1], entry["frame_no"],
            entry["horse_id"], entry["horse_name"], profile.get("sex_code"), age, profile.get("sire_name"),
            profile.get("broodmare_sire_name"), profile.get("sire_line_code"), profile.get("broodmare_sire_line_code"),
            entry["jockey_name"], entry["running_style"], entry["distance_aptitude"], entry["uptrend"], training.get(key),
            result["finish"], result["abnormal_code"], result["final_win_odds"], result["final_win_popularity"],
            result["win_payout"], result["place_payout"], entry["prev_result_key_1"], entry["prev_race_key_1"],
        ))

    if not rows:
        raise ValueError(f"{date}: no joinable completed rows")
    return rows, {
        "race_count": len({row[9] for row in rows}),
        "row_count": len(rows),
        "missing_profile_rows": missing_profiles,
        "kind_line_counts": {kind: len(values) for kind, values in lines.items()},
    }


def parse_day(raw_root: Path, date: dt.date) -> tuple[list[tuple], dict[str, object]]:
    archives = {kind: daily_zip(raw_root, kind, date) for kind in REQUIRED_KINDS}
    lines = {kind: read_member(path, kind, date) for kind, path in archives.items()}
    rows, meta = _parse_lines(lines, date)
    meta.update({
        "source_mode": "daily-kind",
        "source_sha256s": {kind: sha256_file(path) for kind, path in archives.items()},
        "source_manifest": {kind: str(path) for kind, path in archives.items()},
    })
    return rows, meta


def parse_paci_sed(paci: Path, sed: Path) -> tuple[dt.date, list[tuple], dict[str, object]]:
    if not paci.exists():
        raise FileNotFoundError(paci)
    if not sed.exists():
        raise FileNotFoundError(sed)
    date = infer_date_from_name(paci, "PACI")
    sed_date = infer_date_from_name(sed, "SED")
    if sed_date != date:
        raise ValueError(f"PACI/SED date mismatch: {date} vs {sed_date}")

    lines = {kind: read_member(paci, kind, date) for kind in PACI_KINDS}
    lines["SED"] = read_member(sed, "SED", date)
    rows, meta = _parse_lines(lines, date)
    meta.update({
        "source_mode": "PACI+SED",
        "source_sha256s": {"PACI": sha256_file(paci), "SED": sha256_file(sed)},
        "source_manifest": {"PACI": str(paci), "SED": str(sed)},
    })
    return date, rows, meta


def ensure_v12(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(fact_entry_result_lite)")}
    missing = {"prev_result_key_1", "prev_race_key_1"} - columns
    if missing:
        raise RuntimeError(f"Analysis DB is not v1.2; missing columns: {sorted(missing)}")
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "meta_analysis_ingest_batch" not in tables:
        raise RuntimeError("Analysis DB is not v1.2; missing meta_analysis_ingest_batch")


def update_rows(conn: sqlite3.Connection, date: dt.date, rows: list[tuple], meta: dict[str, object]) -> dict[str, object]:
    started = now()
    batch_id = conn.execute(
        "INSERT INTO meta_analysis_ingest_batch(target_date,builder_version,schema_version,started_at,status,source_manifest,source_sha256s,race_count,row_count) VALUES(?,?,?,?,?,?,?,?,?)",
        (date.isoformat(), VERSION, SCHEMA_VERSION, started, "RUNNING", json.dumps(meta["source_manifest"], ensure_ascii=False), json.dumps(meta["source_sha256s"]), meta["race_count"], meta["row_count"]),
    ).lastrowid
    conn.commit()
    try:
        old_count = conn.execute("SELECT count(*) FROM fact_entry_result_lite WHERE race_date=?", (date.isoformat(),)).fetchone()[0]
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM fact_entry_result_lite WHERE race_date=?", (date.isoformat(),))
        sql = f"INSERT INTO fact_entry_result_lite({','.join(FACT_COLUMNS)}) VALUES({','.join('?' for _ in FACT_COLUMNS)})"
        conn.executemany(sql, rows)
        inserted = conn.execute("SELECT count(*) FROM fact_entry_result_lite WHERE race_date=?", (date.isoformat(),)).fetchone()[0]
        if inserted != len(rows):
            raise RuntimeError(f"inserted row mismatch: expected {len(rows)}, got {inserted}")
        conn.execute("COMMIT")
        message = f"missing_profile_rows={meta['missing_profile_rows']}; source_mode={meta['source_mode']}"
        conn.execute(
            "UPDATE meta_analysis_ingest_batch SET finished_at=?,status='SUCCESS',replaced_row_count=?,message=? WHERE batch_id=?",
            (now(), old_count, message, batch_id),
        )
        conn.commit()
        return {"date": date.isoformat(), "old_rows": old_count, "new_rows": len(rows), **meta}
    except Exception as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute(
            "UPDATE meta_analysis_ingest_batch SET finished_at=?,status='ERROR',message=? WHERE batch_id=?",
            (now(), f"{type(exc).__name__}: {exc}", batch_id),
        )
        conn.commit()
        raise


def update_date(conn: sqlite3.Connection, raw_root: Path, date: dt.date) -> dict[str, object]:
    rows, meta = parse_day(raw_root, date)
    return update_rows(conn, date, rows, meta)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--dates", nargs="+")
    parser.add_argument("--paci", type=Path, help="PACIyymmdd.zip; use together with --sed")
    parser.add_argument("--sed", type=Path, help="SEDyymmdd.zip; use together with --paci")
    args = parser.parse_args()

    daily_mode = args.raw_root is not None or args.dates is not None
    paci_mode = args.paci is not None or args.sed is not None
    if daily_mode and paci_mode:
        parser.error("Use either --raw-root/--dates or --paci/--sed, not both")
    if paci_mode:
        if args.paci is None or args.sed is None:
            parser.error("PACI mode requires both --paci and --sed")
    elif args.raw_root is None or not args.dates:
        parser.error("Daily-kind mode requires --raw-root and --dates")

    conn = sqlite3.connect(args.db)
    try:
        ensure_v12(conn)
        output = []
        if paci_mode:
            date, rows, meta = parse_paci_sed(args.paci, args.sed)
            output.append(update_rows(conn, date, rows, meta))
        else:
            for value in args.dates:
                output.append(update_date(conn, args.raw_root, parse_date(value)))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        print(json.dumps({"updates": output, "integrity_check": integrity}, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
