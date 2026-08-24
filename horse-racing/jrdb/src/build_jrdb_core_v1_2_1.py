#!/usr/bin/env python3
"""JRDB Core Builder v1.2.1 additive wrapper.

Keeps the proven v1.1.2 normalization/duplicate logic and the v1.2 UKC profile
enrichment, then backfills two analysis dimensions from canonical Raw files:
- KYI frame_no: 0-based offset 323, length 1
- SED track_condition_code: 0-based offset 69, length 2
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

from build_jrdb_core_v1_2 import _run_v112, enrich_ukc_profiles

VERSION = "1.2.1-production"
SCHEMA_VERSION = "v1.2.1"


def _text(raw: bytes, offset: int, width: int) -> str:
    return raw[offset : offset + width].decode("cp932", "replace").strip()


def _num(raw: bytes, offset: int, width: int) -> int | None:
    try:
        return int(_text(raw, offset, width))
    except (TypeError, ValueError):
        return None


def _canonical_members(zf: zipfile.ZipFile, kind: str) -> list[str]:
    pattern = re.compile(rf"^{kind}\d{{6}}\.txt$", re.IGNORECASE)
    return sorted(
        [name for name in zf.namelist() if pattern.fullmatch(Path(name).name)],
        key=lambda name: Path(name).name.upper(),
    )


def enrich_analysis_dimensions(db: Path, raw_root: Path, years: list[int]) -> dict[str, int]:
    conn = sqlite3.connect(db)
    stats = {"frame_rows_updated": 0, "track_condition_rows_updated": 0}
    try:
        for year in sorted(years):
            kyi_zip = raw_root / "KYI" / f"KYI_{year}.zip"
            if kyi_zip.exists():
                with zipfile.ZipFile(kyi_zip) as zf:
                    for member in _canonical_members(zf, "KYI"):
                        updates = []
                        for raw in zf.read(member).splitlines():
                            updates.append((_num(raw, 323, 1), _text(raw, 0, 8), _num(raw, 8, 2)))
                        conn.executemany(
                            "UPDATE entry SET frame_no=? WHERE race_key=? AND horse_no=?",
                            updates,
                        )
                        stats["frame_rows_updated"] += len(updates)

            sed_zip = raw_root / "SED" / f"SED_{year}.zip"
            if sed_zip.exists():
                with zipfile.ZipFile(sed_zip) as zf:
                    for member in _canonical_members(zf, "SED"):
                        updates = []
                        for raw in zf.read(member).splitlines():
                            updates.append((_text(raw, 69, 2), _text(raw, 0, 8), _num(raw, 8, 2)))
                        conn.executemany(
                            "UPDATE result SET track_condition_code=? WHERE race_key=? AND horse_no=?",
                            updates,
                        )
                        stats["track_condition_rows_updated"] += len(updates)

        conn.execute(
            "UPDATE meta_ingest_run SET builder_version=?, schema_version=? "
            "WHERE ingest_run_id=(SELECT MAX(ingest_run_id) FROM meta_ingest_run)",
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
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_core_schema_v1_2_1.sql",
    )
    ap.add_argument(
        "--skip-core-build",
        action="store_true",
        help="Enrich an already-built v1.2.1-schema DB; intended for controlled tests only.",
    )
    args = ap.parse_args()

    if not args.skip_core_build:
        if args.db.exists():
            raise SystemExit(f"Refusing to overwrite existing DB: {args.db}")
        _run_v112(args)

    ukc_stats = enrich_ukc_profiles(args.db, args.raw_root, args.years)
    dim_stats = enrich_analysis_dimensions(args.db, args.raw_root, args.years)
    print("UKC profile enrichment complete:", ukc_stats)
    print("Analysis dimension enrichment complete:", dim_stats)


if __name__ == "__main__":
    main()
