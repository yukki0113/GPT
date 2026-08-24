#!/usr/bin/env python3
"""JRDB Core Builder v1.2 additive wrapper.

Runs the proven v1.1.2 Core Builder unchanged against the v1.2 schema, then
adds full UKC horse profile current/history tables. This deliberately avoids
refactoring the validated v1.1.2 normalization/duplicate logic.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

from jrdb_ukc import parse_ukc_record, profile_values

VERSION = "1.2-production"
SCHEMA_VERSION = "v1.2"
CANONICAL_UKC = re.compile(r"^UKC\d{6}\.txt$", re.IGNORECASE)

PROFILE_COLUMNS = (
    "horse_id",
    "horse_name",
    "sex_code",
    "coat_color_code",
    "horse_symbol_code",
    "sire_name",
    "dam_name",
    "broodmare_sire_name",
    "birth_date",
    "sire_birth_year",
    "dam_birth_year",
    "broodmare_sire_birth_year",
    "owner_name",
    "owner_group_code",
    "breeder_name",
    "breeding_place",
    "deregistered_flag",
    "data_date",
    "sire_line_code",
    "broodmare_sire_line_code",
    "semantic_hash",
    "source_file_id",
    "source_record_no",
    "valid_from",
)

HISTORY_COLUMNS = (
    "horse_id",
    "valid_from",
    "valid_to",
    "semantic_hash",
    "horse_name",
    "sex_code",
    "coat_color_code",
    "horse_symbol_code",
    "sire_name",
    "dam_name",
    "broodmare_sire_name",
    "birth_date",
    "sire_birth_year",
    "dam_birth_year",
    "broodmare_sire_birth_year",
    "owner_name",
    "owner_group_code",
    "breeder_name",
    "breeding_place",
    "deregistered_flag",
    "data_date",
    "sire_line_code",
    "broodmare_sire_line_code",
    "source_file_id",
    "source_record_no",
)


def _date_from_filename(filename: str, year: int) -> str | None:
    m = re.fullmatch(r"UKC(\d{6})\.txt", Path(filename).name, re.IGNORECASE)
    if not m:
        return None
    yymmdd = m.group(1)
    if int(yymmdd[:2]) != year % 100:
        return None
    try:
        return dt.date(year, int(yymmdd[2:4]), int(yymmdd[4:6])).isoformat()
    except ValueError:
        return None


def _run_v112(args: argparse.Namespace) -> None:
    script = Path(__file__).with_name("build_jrdb_core.py")
    cmd = [
        sys.executable,
        str(script),
        "--years",
        *[str(y) for y in args.years],
        "--raw-root",
        str(args.raw_root),
        "--db",
        str(args.db),
        "--schema",
        str(args.schema),
    ]
    subprocess.run(cmd, check=True)


def _source_file_map(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    rows = conn.execute(
        "SELECT msf.source_file_id, ma.year, msf.filename "
        "FROM meta_source_file msf JOIN meta_archive ma ON ma.archive_id=msf.archive_id "
        "WHERE msf.source_kind='UKC' AND msf.is_canonical=1"
    )
    return {(str(row[1]), row[2].upper()): row[0] for row in rows}


def _insert_history(conn: sqlite3.Connection, old: sqlite3.Row, valid_to: str) -> None:
    values = (
        old["horse_id"],
        old["valid_from"],
        valid_to,
        old["semantic_hash"],
        old["horse_name"],
        old["sex_code"],
        old["coat_color_code"],
        old["horse_symbol_code"],
        old["sire_name"],
        old["dam_name"],
        old["broodmare_sire_name"],
        old["birth_date"],
        old["sire_birth_year"],
        old["dam_birth_year"],
        old["broodmare_sire_birth_year"],
        old["owner_name"],
        old["owner_group_code"],
        old["breeder_name"],
        old["breeding_place"],
        old["deregistered_flag"],
        old["data_date"],
        old["sire_line_code"],
        old["broodmare_sire_line_code"],
        old["source_file_id"],
        old["source_record_no"],
    )
    conn.execute(
        f"INSERT INTO horse_profile_history({','.join(HISTORY_COLUMNS)}) "
        f"VALUES({','.join('?' for _ in HISTORY_COLUMNS)})",
        values,
    )


def enrich_ukc_profiles(db: Path, raw_root: Path, years: list[int]) -> dict[str, int]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    source_files = _source_file_map(conn)
    stats = {"records": 0, "inserted_current": 0, "history_rows": 0, "unchanged": 0}

    try:
        for year in sorted(years):
            archive = raw_root / "UKC" / f"UKC_{year}.zip"
            if not archive.exists():
                continue
            with zipfile.ZipFile(archive) as zf:
                members = sorted(
                    (n for n in zf.namelist() if CANONICAL_UKC.fullmatch(Path(n).name)),
                    key=lambda n: Path(n).name.upper(),
                )
                for member in members:
                    filename = Path(member).name.upper()
                    valid_from = _date_from_filename(filename, year)
                    source_file_id = source_files.get((str(year), filename))
                    if valid_from is None or source_file_id is None:
                        continue
                    for record_no, raw in enumerate(zf.read(member).splitlines(), 1):
                        rec = parse_ukc_record(raw)
                        stats["records"] += 1
                        old = conn.execute(
                            "SELECT * FROM horse_profile_current WHERE horse_id=?",
                            (rec.horse_id,),
                        ).fetchone()
                        base = profile_values(rec)
                        new_values = base + (source_file_id, record_no, valid_from)
                        if old is None:
                            conn.execute(
                                f"INSERT INTO horse_profile_current({','.join(PROFILE_COLUMNS)}) "
                                f"VALUES({','.join('?' for _ in PROFILE_COLUMNS)})",
                                new_values,
                            )
                            stats["inserted_current"] += 1
                        elif old["semantic_hash"] == rec.semantic_hash():
                            stats["unchanged"] += 1
                        else:
                            _insert_history(conn, old, valid_from)
                            assignments = ",".join(f"{c}=?" for c in PROFILE_COLUMNS[1:])
                            conn.execute(
                                f"UPDATE horse_profile_current SET {assignments} WHERE horse_id=?",
                                new_values[1:] + (rec.horse_id,),
                            )
                            stats["history_rows"] += 1
        conn.execute(
            "UPDATE meta_ingest_run SET builder_version=?, schema_version=? WHERE ingest_run_id=(SELECT MAX(ingest_run_id) FROM meta_ingest_run)",
            (VERSION, SCHEMA_VERSION),
        )
        conn.commit()
        return stats
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, required=True)
    ap.add_argument("--raw-root", type=Path, default=Path("00_raw_local"))
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_core_schema_v1_2.sql",
    )
    ap.add_argument(
        "--skip-core-build",
        action="store_true",
        help="Enrich an already-built v1.2-schema DB; intended for controlled tests only.",
    )
    args = ap.parse_args()

    if not args.skip_core_build:
        if args.db.exists():
            raise SystemExit(f"Refusing to overwrite existing DB: {args.db}")
        _run_v112(args)

    stats = enrich_ukc_profiles(args.db, args.raw_root, args.years)
    print("UKC profile enrichment complete:", stats)


if __name__ == "__main__":
    main()
