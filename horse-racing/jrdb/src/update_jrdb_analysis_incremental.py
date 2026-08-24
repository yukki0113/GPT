#!/usr/bin/env python3
"""Incrementally replace one or more completed JRDB race dates in Analysis Lite v1.2.

Expected Raw layout for 2026+ daily archives:
  RAW_ROOT/BAC/BACyymmdd.zip
  RAW_ROOT/KYI/KYIyymmdd.zip
  RAW_ROOT/SED/SEDyymmdd.zip
  RAW_ROOT/CYB/CYByymmdd.zip
  RAW_ROOT/UKC/UKCyymmdd.zip

A date is replaced atomically only after all required archives parse successfully.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

VERSION = "1.0-production"
SCHEMA_VERSION = "v1.2"
REQUIRED_KINDS = ("BAC", "KYI", "SED", "CYB", "UKC")
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


def text(raw: bytes, offset: int, width: int) -> str:
    return raw[offset:offset+width].decode("cp932", "replace").strip()


def num(raw: bytes, offset: int, width: int) -> int | None:
    value = text(raw, offset, width).replace(",", "")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def daily_zip(raw_root: Path, kind: str, date: dt.date) -> Path:
    return raw_root / kind / f"{kind}{date:%y%m%d}.zip"


def read_member(path: Path, kind: str, date: dt.date) -> list[bytes]:
    if not path.exists():
        raise FileNotFoundError(path)
    expected = f"{kind}{date:%y%m%d}.txt".upper()
    with zipfile.ZipFile(path) as zf:
        matches = [n for n in zf.namelist() if Path(n).name.upper() == expected]
        if len(matches) != 1:
            raise ValueError(f"{path}: expected exactly one {expected}, found {len(matches)}")
        bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"{path}: bad ZIP member {bad}")
        return zf.read(matches[0]).splitlines()


def parse_ukc_profile(raw: bytes) -> dict[str, object]:
    if len(raw) != 290:
        raise ValueError(f"UKC body length must be 290, got {len(raw)}")
    birth_date = text(raw, 157, 8)
    birth_year = int(birth_date[:4]) if len(birth_date) >= 4 and birth_date[:4].isdigit() else None
    return {
        "sex_code": text(raw, 44, 1),
        "birth_year": birth_year,
        "sire_name": text(raw, 49, 36),
        "broodmare_sire_name": text(raw, 121, 36),
        "sire_line_code": text(raw, 276, 4),
        "broodmare_sire_line_code": text(raw, 280, 4),
        "data_date": text(raw, 268, 8),
    }


def parse_day(raw_root: Path, date: dt.date) -> tuple[list[tuple], dict[str, object]]:
    archives = {kind: daily_zip(raw_root, kind, date) for kind in REQUIRED_KINDS}
    lines = {kind: read_member(path, kind, date) for kind, path in archives.items()}

    races: dict[str, dict[str, object]] = {}
    entries: dict[tuple[str,int | None], dict[str, object]] = {}
    results: dict[tuple[str,int | None], dict[str, object]] = {}
    training: dict[tuple[str,int | None], int | None] = {}
    horses: dict[str, dict[str, object]] = {}

    for raw in lines["UKC"]:
        horse_id = text(raw, 0, 8)
        profile = parse_ukc_profile(raw)
        old = horses.get(horse_id)
        if old is None or str(profile["data_date"]) >= str(old["data_date"]):
            horses[horse_id] = profile

    for raw in lines["BAC"]:
        rk = text(raw, 0, 8)
        races.setdefault(rk, {
            "race_date": date.isoformat(), "year": date.year, "venue_code": text(raw,0,2),
            "race_no": num(raw,6,2), "distance": num(raw,20,4), "track_type": text(raw,24,1),
            "race_condition_code": text(raw,29,2), "track_condition_code": None,
            "grade_code": text(raw,35,1),
        })

    for raw in lines["KYI"]:
        rk, hn = text(raw,0,8), num(raw,8,2)
        entries.setdefault((rk,hn), {
            "frame_no": num(raw,323,1), "horse_id": text(raw,10,8), "horse_name": text(raw,18,36),
            "jockey_name": text(raw,171,12), "running_style": text(raw,89,1),
            "distance_aptitude": text(raw,90,1), "uptrend": text(raw,91,1),
            "prev_result_key_1": text(raw,203,16) or None,
            "prev_race_key_1": text(raw,283,8) or None,
        })

    for raw in lines["SED"]:
        rk, hn = text(raw,0,8), num(raw,8,2)
        tc = text(raw,69,2)
        if rk not in races:
            races[rk] = {
                "race_date": date.isoformat(), "year": date.year, "venue_code": text(raw,0,2),
                "race_no": num(raw,6,2), "distance": num(raw,62,4), "track_type": text(raw,66,1),
                "race_condition_code": None, "track_condition_code": tc, "grade_code": None,
            }
        elif not races[rk]["track_condition_code"]:
            races[rk]["track_condition_code"] = tc
        results.setdefault((rk,hn), {
            "finish": num(raw,140,2), "abnormal_code": text(raw,142,1),
            "final_win_odds": num(raw,174,6), "final_win_popularity": num(raw,180,2),
            "win_payout": num(raw,341,7), "place_payout": num(raw,348,7),
        })

    for raw in lines["CYB"]:
        training.setdefault((text(raw,0,8), num(raw,8,2)), num(raw,29,3))

    rows: list[tuple] = []
    missing_profiles = 0
    for key, entry in entries.items():
        race = races.get(key[0]); result = results.get(key)
        if race is None or result is None:
            continue
        profile = horses.get(str(entry["horse_id"]), {})
        if not profile:
            missing_profiles += 1
        by = profile.get("birth_year")
        age = date.year - int(by) if by else None
        rows.append((
            race["race_date"],race["year"],race["venue_code"],race["race_no"],race["track_type"],race["distance"],
            race["race_condition_code"],race["track_condition_code"],race["grade_code"],key[0],key[1],entry["frame_no"],
            entry["horse_id"],entry["horse_name"],profile.get("sex_code"),age,profile.get("sire_name"),
            profile.get("broodmare_sire_name"),profile.get("sire_line_code"),profile.get("broodmare_sire_line_code"),
            entry["jockey_name"],entry["running_style"],entry["distance_aptitude"],entry["uptrend"],training.get(key),
            result["finish"],result["abnormal_code"],result["final_win_odds"],result["final_win_popularity"],
            result["win_payout"],result["place_payout"],entry["prev_result_key_1"],entry["prev_race_key_1"],
        ))

    race_keys = {r[9] for r in rows}
    if not rows:
        raise ValueError(f"{date}: no joinable completed rows")
    meta = {
        "race_count": len(race_keys), "row_count": len(rows), "missing_profile_rows": missing_profiles,
        "source_sha256s": {k: sha256_file(v) for k,v in archives.items()},
        "source_manifest": {k: str(v) for k,v in archives.items()},
    }
    return rows, meta


def ensure_v12(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(fact_entry_result_lite)")}
    missing = {"prev_result_key_1","prev_race_key_1"} - cols
    if missing:
        raise RuntimeError(f"Analysis DB is not v1.2; missing columns: {sorted(missing)}")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "meta_analysis_ingest_batch" not in tables:
        raise RuntimeError("Analysis DB is not v1.2; missing meta_analysis_ingest_batch")


def update_date(conn: sqlite3.Connection, raw_root: Path, date: dt.date) -> dict[str, object]:
    rows, meta = parse_day(raw_root, date)
    started = now()
    batch_id = conn.execute(
        "INSERT INTO meta_analysis_ingest_batch(target_date,builder_version,schema_version,started_at,status,source_manifest,source_sha256s,race_count,row_count) VALUES(?,?,?,?,?,?,?,?,?)",
        (date.isoformat(),VERSION,SCHEMA_VERSION,started,"RUNNING",json.dumps(meta["source_manifest"],ensure_ascii=False),json.dumps(meta["source_sha256s"]),meta["race_count"],meta["row_count"]),
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
        conn.execute(
            "UPDATE meta_analysis_ingest_batch SET finished_at=?,status='SUCCESS',replaced_row_count=?,message=? WHERE batch_id=?",
            (now(),old_count,f"missing_profile_rows={meta['missing_profile_rows']}",batch_id),
        )
        conn.commit()
        return {"date":date.isoformat(),"old_rows":old_count,"new_rows":len(rows),**meta}
    except Exception as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute("UPDATE meta_analysis_ingest_batch SET finished_at=?,status='ERROR',message=? WHERE batch_id=?", (now(),f"{type(exc).__name__}: {exc}",batch_id))
        conn.commit()
        raise


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--dates", nargs="+", required=True)
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    try:
        ensure_v12(conn)
        out=[]
        for value in args.dates:
            out.append(update_date(conn,args.raw_root,parse_date(value)))
        integrity=conn.execute("PRAGMA integrity_check").fetchone()[0]
        print(json.dumps({"updates":out,"integrity_check":integrity},ensure_ascii=False,indent=2))
    finally:
        conn.close()

if __name__ == "__main__":
    main()
