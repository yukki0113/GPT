#!/usr/bin/env python3
"""Build JRDB Analysis Lite directly from annual Raw ZIPs.

This is the remote-friendly companion to build_jrdb_analysis.py. It avoids a
dependency on the large Core SQLite while preserving the same Analysis v1
fact-table shape. Current scope: BAC/KYI/SED/CYB/UKC.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import zipfile
from pathlib import Path

VERSION = "0.1-poc"
SCHEMA_VERSION = "v1"


def text(raw: bytes, offset: int, width: int) -> str:
    return raw[offset : offset + width].decode("cp932", "replace").strip()


def num(raw: bytes, offset: int, width: int) -> int | None:
    value = text(raw, offset, width).replace(",", "")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def date_from_name(name: str, year: int) -> str | None:
    match = re.fullmatch(r"[A-Z]+(\d{6})\.txt", Path(name).name, re.IGNORECASE)
    if not match:
        return None
    yymmdd = match.group(1)
    if int(yymmdd[:2]) != year % 100:
        return None
    try:
        return dt.date(year, int(yymmdd[2:4]), int(yymmdd[4:6])).isoformat()
    except ValueError:
        return None


def canonical_members(zf: zipfile.ZipFile, kind: str) -> list[str]:
    pattern = re.compile(rf"^{kind}\d{{6}}\.txt$", re.IGNORECASE)
    return sorted(
        [name for name in zf.namelist() if pattern.fullmatch(Path(name).name)],
        key=lambda name: Path(name).name.upper(),
    )


def parse_ukc_profile(raw: bytes) -> dict[str, object]:
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


def build(raw_root: Path, years: list[int], out: Path, schema: Path) -> dict[str, object]:
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing DB: {out}")

    conn = sqlite3.connect(out)
    conn.executescript(schema.read_text(encoding="utf-8"))
    started = dt.datetime.now().isoformat(timespec="seconds")
    build_id = conn.execute(
        "INSERT INTO meta_analysis_build(builder_version,schema_version,started_at,status) VALUES(?,?,?,?)",
        (VERSION, SCHEMA_VERSION, started, "RUNNING"),
    ).lastrowid

    races: dict[str, dict[str, object]] = {}
    entries: dict[tuple[str, int | None], dict[str, object]] = {}
    results: dict[tuple[str, int | None], dict[str, object]] = {}
    training: dict[tuple[str, int | None], int | None] = {}
    horses: dict[str, dict[str, object]] = {}

    for year in sorted(years):
        with zipfile.ZipFile(raw_root / "UKC" / f"UKC_{year}.zip") as zf:
            for member in canonical_members(zf, "UKC"):
                for raw in zf.read(member).splitlines():
                    if len(raw) != 290:
                        continue
                    horse_id = text(raw, 0, 8)
                    profile = parse_ukc_profile(raw)
                    old = horses.get(horse_id)
                    if old is None or str(profile["data_date"]) >= str(old["data_date"]):
                        horses[horse_id] = profile

        with zipfile.ZipFile(raw_root / "BAC" / f"BAC_{year}.zip") as zf:
            for member in canonical_members(zf, "BAC"):
                race_date = date_from_name(member, year)
                for raw in zf.read(member).splitlines():
                    race_key = text(raw, 0, 8)
                    races.setdefault(
                        race_key,
                        {
                            "race_date": race_date,
                            "year": year,
                            "venue_code": text(raw, 0, 2),
                            "race_no": num(raw, 6, 2),
                            "distance": num(raw, 20, 4),
                            "track_type": text(raw, 24, 1),
                            "condition_code": text(raw, 29, 2),
                            "grade_code": text(raw, 35, 1),
                        },
                    )

        with zipfile.ZipFile(raw_root / "KYI" / f"KYI_{year}.zip") as zf:
            for member in canonical_members(zf, "KYI"):
                for raw in zf.read(member).splitlines():
                    race_key = text(raw, 0, 8)
                    horse_no = num(raw, 8, 2)
                    entries.setdefault(
                        (race_key, horse_no),
                        {
                            "horse_id": text(raw, 10, 8),
                            "horse_name": text(raw, 18, 36),
                            "jockey_name": text(raw, 171, 12),
                            "running_style": text(raw, 89, 1),
                            "distance_aptitude": text(raw, 90, 1),
                            "uptrend": text(raw, 91, 1),
                        },
                    )

        with zipfile.ZipFile(raw_root / "SED" / f"SED_{year}.zip") as zf:
            for member in canonical_members(zf, "SED"):
                race_date = date_from_name(member, year)
                for raw in zf.read(member).splitlines():
                    race_key = text(raw, 0, 8)
                    horse_no = num(raw, 8, 2)
                    if race_key not in races:
                        # Match the established Core BAC->SED fallback principle.
                        races[race_key] = {
                            "race_date": race_date,
                            "year": year,
                            "venue_code": text(raw, 0, 2),
                            "race_no": num(raw, 6, 2),
                            "distance": num(raw, 62, 4),
                            "track_type": text(raw, 66, 1),
                            "condition_code": "",
                            "grade_code": "",
                        }
                    results.setdefault(
                        (race_key, horse_no),
                        {
                            "finish": num(raw, 140, 2),
                            "abnormal_code": text(raw, 142, 1),
                            "final_win_odds": num(raw, 174, 6),
                            "final_win_popularity": num(raw, 180, 2),
                            "win_payout": num(raw, 341, 7),
                            "place_payout": num(raw, 348, 7),
                        },
                    )

        with zipfile.ZipFile(raw_root / "CYB" / f"CYB_{year}.zip") as zf:
            for member in canonical_members(zf, "CYB"):
                for raw in zf.read(member).splitlines():
                    training.setdefault((text(raw, 0, 8), num(raw, 8, 2)), num(raw, 29, 3))

    rows = []
    missing_profile_rows = 0
    for key, entry in entries.items():
        race_key, horse_no = key
        race = races.get(race_key)
        result = results.get(key)
        if race is None or result is None:
            continue
        profile = horses.get(str(entry["horse_id"]), {})
        if not profile:
            missing_profile_rows += 1
        birth_year = profile.get("birth_year")
        age = int(race["year"]) - int(birth_year) if birth_year else None
        rows.append(
            (
                race["race_date"], race["year"], race["venue_code"], race["race_no"],
                race["track_type"], race["distance"], race["condition_code"], race["grade_code"],
                race_key, horse_no, entry["horse_id"], entry["horse_name"], profile.get("sex_code"), age,
                profile.get("sire_name"), profile.get("broodmare_sire_name"),
                profile.get("sire_line_code"), profile.get("broodmare_sire_line_code"),
                entry["jockey_name"], entry["running_style"], entry["distance_aptitude"], entry["uptrend"],
                training.get(key), result["finish"], result["abnormal_code"], result["final_win_odds"],
                result["final_win_popularity"], result["win_payout"], result["place_payout"],
            )
        )

    conn.executemany(
        "INSERT INTO fact_entry_result_lite VALUES(" + ",".join("?" * 29) + ")",
        rows,
    )
    conn.commit()
    conn.execute("ANALYZE")
    conn.commit()
    conn.execute(
        "UPDATE meta_analysis_build SET finished_at=?,status='SUCCESS',row_count=? WHERE build_id=?",
        (dt.datetime.now().isoformat(timespec="seconds"), len(rows), build_id),
    )
    conn.commit()
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    sire_nonblank = conn.execute(
        "SELECT count(*) FROM fact_entry_result_lite WHERE trim(coalesce(sire_name,''))<>''"
    ).fetchone()[0]
    bms_nonblank = conn.execute(
        "SELECT count(*) FROM fact_entry_result_lite WHERE trim(coalesce(broodmare_sire_name,''))<>''"
    ).fetchone()[0]
    conn.close()
    return {
        "rows": len(rows),
        "races": len(races),
        "entries": len(entries),
        "results": len(results),
        "training": len(training),
        "horses": len(horses),
        "missing_profile_rows": missing_profile_rows,
        "sire_nonblank": sire_nonblank,
        "broodmare_sire_nonblank": bms_nonblank,
        "integrity_check": integrity,
        "size_bytes": out.stat().st_size,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, required=True)
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_analysis_schema_v1.sql",
    )
    args = ap.parse_args()
    result = build(args.raw_root, args.years, args.db, args.schema)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
