#!/usr/bin/env python3
"""Build JRDB Analysis Lite v1.2 directly from annual Raw ZIPs.

Production rebuild path using BAC/KYI/SED/CYB/UKC. Fixed-width byte positions
are owned by ``jrdb_raw``; this module owns only Analysis Lite joins and output.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
from pathlib import Path

from jrdb_analysis_raw_adapter import (
    parse_bac,
    parse_cyb,
    parse_kyi,
    parse_sed,
    parse_ukc,
)
from jrdb_raw import iter_archive_records

VERSION = "1.2-production"
SCHEMA_VERSION = "v1.2"
FACT_COLUMNS = (
    "race_date","year","venue_code","race_no","track_type","distance",
    "race_condition_code","track_condition_code","grade_code","race_key","horse_no",
    "frame_no","horse_id","horse_name","sex_code","age","sire_name",
    "broodmare_sire_name","sire_line_code","broodmare_sire_line_code","jockey_name",
    "running_style","distance_aptitude","uptrend","training_index","finish",
    "abnormal_code","final_win_odds","final_win_popularity","win_payout","place_payout",
    "prev_result_key_1","prev_race_key_1",
)


def date_from_name(name: str, year: int) -> str | None:
    match = re.fullmatch(r"[A-Z]+(\d{6})\.txt", Path(name).name, re.IGNORECASE)
    if match is None:
        return None
    value = match.group(1)
    if int(value[:2]) != year % 100:
        return None
    try:
        return dt.date(year, int(value[2:4]), int(value[4:6])).isoformat()
    except ValueError:
        return None


def build(raw_root: Path, years: list[int], out: Path, schema: Path) -> dict[str, object]:
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing DB: {out}")

    connection = sqlite3.connect(out)
    connection.execute("PRAGMA journal_mode=MEMORY")
    connection.execute("PRAGMA synchronous=OFF")
    connection.executescript(schema.read_text(encoding="utf-8"))
    started = dt.datetime.now().isoformat(timespec="seconds")
    build_id = connection.execute(
        "INSERT INTO meta_analysis_build(builder_version,schema_version,started_at,status) VALUES(?,?,?,?)",
        (VERSION, SCHEMA_VERSION, started, "RUNNING"),
    ).lastrowid

    races: dict[str, dict[str, object]] = {}
    entries: dict[tuple[str, int | None], dict[str, object]] = {}
    results: dict[tuple[str, int | None], dict[str, object]] = {}
    training: dict[tuple[str, int | None], int | None] = {}
    horses: dict[str, dict[str, object]] = {}

    for year in sorted(years):
        for member, raw in iter_archive_records(raw_root / "UKC" / f"UKC_{year}.zip", "UKC"):
            horse_id, profile = parse_ukc(raw)
            old = horses.get(horse_id)
            if old is None or str(profile["data_date"]) >= str(old["data_date"]):
                horses[horse_id] = profile

        for member, raw in iter_archive_records(raw_root / "BAC" / f"BAC_{year}.zip", "BAC"):
            race_date = date_from_name(member, year)
            if race_date is None:
                continue
            race = parse_bac(raw, race_date, year)
            race_key = raw[:8].decode("ascii", "replace").strip()
            races.setdefault(race_key, race)

        for _member, raw in iter_archive_records(raw_root / "KYI" / f"KYI_{year}.zip", "KYI"):
            key, entry = parse_kyi(raw)
            entries.setdefault(key, entry)

        for member, raw in iter_archive_records(raw_root / "SED" / f"SED_{year}.zip", "SED"):
            race_date = date_from_name(member, year)
            if race_date is None:
                continue
            key, result, fallback_race = parse_sed(raw, race_date, year)
            race_key = key[0]
            if race_key not in races:
                races[race_key] = fallback_race
            elif not races[race_key]["track_condition_code"]:
                races[race_key]["track_condition_code"] = fallback_race["track_condition_code"]
            results.setdefault(key, result)

        for _member, raw in iter_archive_records(raw_root / "CYB" / f"CYB_{year}.zip", "CYB"):
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
        age = int(race["year"]) - int(birth_year) if birth_year else None
        rows.append((
            race["race_date"], race["year"], race["venue_code"], race["race_no"], race["track_type"], race["distance"],
            race["race_condition_code"], race["track_condition_code"], race["grade_code"], key[0], key[1], entry["frame_no"],
            entry["horse_id"], entry["horse_name"], profile.get("sex_code"), age, profile.get("sire_name"),
            profile.get("broodmare_sire_name"), profile.get("sire_line_code"), profile.get("broodmare_sire_line_code"),
            entry["jockey_name"], entry["running_style"], entry["distance_aptitude"], entry["uptrend"], training.get(key),
            result["finish"], result["abnormal_code"], result["final_win_odds"], result["final_win_popularity"],
            result["win_payout"], result["place_payout"], entry["prev_result_key_1"], entry["prev_race_key_1"],
        ))

    sql = f"INSERT INTO fact_entry_result_lite({','.join(FACT_COLUMNS)}) VALUES({','.join('?' for _ in FACT_COLUMNS)})"
    connection.executemany(sql, rows)
    connection.execute("ANALYZE")
    connection.execute(
        "UPDATE meta_analysis_build SET finished_at=?,status='SUCCESS',row_count=? WHERE build_id=?",
        (dt.datetime.now().isoformat(timespec="seconds"), len(rows), build_id),
    )
    connection.commit()
    connection.execute("VACUUM")

    result = {
        "rows": len(rows),
        "missing_profile_rows": missing_profiles,
        "prev1_nonblank": connection.execute(
            "SELECT count(*) FROM fact_entry_result_lite WHERE prev_result_key_1 IS NOT NULL OR prev_race_key_1 IS NOT NULL"
        ).fetchone()[0],
        "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
        "size_bytes": out.stat().st_size,
    }
    connection.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_analysis_schema_v1_2.sql",
    )
    args = parser.parse_args()
    for key, value in build(args.raw_root, args.years, args.db, args.schema).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
