#!/usr/bin/env python3
"""Build a compact JRDB race-name lookup from BAC Raw for PWA Fact Lite."""
from __future__ import annotations

import argparse
import re
import sqlite3
import zipfile
from pathlib import Path

from jrdb_raw import Parser, iter_archive_records

VERSION = "0.2"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    return parser.parse_args()


def analysis_race_keys(path: Path) -> set[str]:
    """Return race keys present in the Analysis Lite source."""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT DISTINCT race_key FROM fact_entry_result_lite "
            "WHERE race_key IS NOT NULL AND TRIM(race_key) <> ''"
        ).fetchall()
    finally:
        connection.close()
    return {str(row[0]) for row in rows}


def discover_bac_archives(raw_root: Path) -> list[Path]:
    """Discover annual and daily BAC ZIP files below raw_root."""
    archives = []
    for path in raw_root.rglob("*.zip"):
        name = path.name.upper()
        if re.fullmatch(r"BAC_\d{4}\.ZIP", name) or re.fullmatch(
            r"BAC\d{6}\.ZIP", name
        ):
            archives.append(path)
    return sorted(archives)


def read_archive(path: Path, target_keys: set[str]) -> dict[str, str]:
    """Read race names from one BAC ZIP through the Common JRDB Reader."""
    # Preserve the existing fail-fast ZIP integrity gate before parsing records.
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"Bad ZIP member in {path}: {bad_member}")

    parser = Parser()
    names: dict[str, str] = {}
    for _member, raw in iter_archive_records(path, "BAC"):
        parsed = parser.bac(raw)
        race_key = str(parsed.get("race_key_raw") or "")
        if race_key not in target_keys:
            continue
        race_name = str(parsed.get("race_name") or "")
        existing = names.get(race_key)
        if existing is not None and existing != race_name:
            raise RuntimeError(
                f"Conflicting race_name for {race_key}: "
                f"{existing!r} vs {race_name!r}"
            )
        names[race_key] = race_name
    return names


def main() -> None:
    """Build and validate the race-name lookup SQLite."""
    args = parse_args()
    if args.db.exists():
        raise SystemExit(f"Refusing to overwrite existing DB: {args.db}")
    if not args.analysis.exists():
        raise SystemExit(f"Analysis DB not found: {args.analysis}")
    if not args.raw_root.exists():
        raise SystemExit(f"Raw root not found: {args.raw_root}")

    target_keys = analysis_race_keys(args.analysis)
    archives = discover_bac_archives(args.raw_root)
    if not archives:
        raise SystemExit("No BAC archives found")

    race_names: dict[str, str] = {}
    for archive in archives:
        for race_key, race_name in read_archive(archive, target_keys).items():
            existing = race_names.get(race_key)
            if existing is not None and existing != race_name:
                raise SystemExit(
                    f"Conflicting race_name for {race_key}: "
                    f"{existing!r} vs {race_name!r}"
                )
            race_names[race_key] = race_name

    missing_keys = target_keys - set(race_names)
    if missing_keys:
        sample = ", ".join(sorted(missing_keys)[:10])
        raise SystemExit(
            f"BAC coverage incomplete: missing={len(missing_keys)} sample={sample}"
        )

    connection = sqlite3.connect(args.db)
    try:
        connection.execute(
            "CREATE TABLE race_name_lookup("
            "race_key TEXT PRIMARY KEY, race_name TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO race_name_lookup(race_key, race_name) VALUES(?, ?)",
            sorted(race_names.items()),
        )
        connection.execute(
            "CREATE INDEX ix_race_name_lookup_name ON race_name_lookup(race_name)"
        )
        connection.commit()
        connection.execute("VACUUM")
        connection.commit()

        total = connection.execute(
            "SELECT COUNT(*) FROM race_name_lookup"
        ).fetchone()[0]
        named = connection.execute(
            "SELECT COUNT(*) FROM race_name_lookup WHERE TRIM(race_name) <> ''"
        ).fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()

    print({
        "builder_version": VERSION,
        "analysis_race_count": len(target_keys),
        "lookup_race_count": total,
        "named_race_count": named,
        "archive_count": len(archives),
        "size_bytes": args.db.stat().st_size,
        "integrity_check": integrity,
    })


if __name__ == "__main__":
    main()
