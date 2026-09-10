#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Upgrade JRDB Analysis Lite v1.2 to v1.3 by backfilling BAC WIN5 leg numbers.

v1.3 adds ``win5_leg_no`` to ``fact_entry_result_lite``.
The field is sourced only from BAC:
- blank => not a WIN5 target race
- 1..5 => leg number inside that day's WIN5 sequence

Historical sources:
- <= 2025: RAW_ROOT/BAC/BAC_YYYY.zip
- >= 2026: RAW_ROOT/PACI/PACIyymmdd.zip

Only race keys that already exist in the Analysis DB are updated. The migration
does not add or remove fact rows.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

from jrdb_raw import Parser, iter_archive_records

VERSION = "1.0-production"
TARGET_SCHEMA_VERSION = "v1.3"
SOURCE_SCHEMA_VERSION = "v1.2"


def now() -> str:
    """Return a second-resolution local timestamp for build metadata."""
    return dt.datetime.now().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    """Return SHA-256 for one source archive."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """Return SQLite column names for a table."""
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table})")
    }


def source_years(connection: sqlite3.Connection) -> list[int]:
    """Return the distinct years currently represented by Analysis facts."""
    return [
        int(row[0])
        for row in connection.execute(
            "SELECT DISTINCT year FROM fact_entry_result_lite "
            "WHERE year IS NOT NULL ORDER BY year"
        )
    ]


def source_dates(connection: sqlite3.Connection, year: int) -> list[str]:
    """Return ISO race dates present in Analysis for one year."""
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT DISTINCT race_date FROM fact_entry_result_lite "
            "WHERE year=? ORDER BY race_date",
            (year,),
        )
    ]


def normalize_leg(value: object, source: str, race_key: str) -> int | None:
    """Validate the JRDB BAC WIN5 field without guessing unexpected values."""
    if value is None:
        return None
    try:
        leg = int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            f"{source}: invalid WIN5 leg {value!r} for race_key={race_key}"
        ) from error
    if leg < 1 or leg > 5:
        raise RuntimeError(
            f"{source}: WIN5 leg must be 1..5, got {leg} for race_key={race_key}"
        )
    return leg


def collect_annual_bac(
    raw_root: Path,
    year: int,
    existing_race_keys: set[str],
) -> tuple[dict[str, int], dict[str, object]]:
    """Collect WIN5 race keys from one annual BAC archive."""
    archive = raw_root / "BAC" / f"BAC_{year}.zip"
    if not archive.exists():
        raise FileNotFoundError(archive)

    parser = Parser()
    mapping: dict[str, int] = {}
    race_records = 0
    for member, record in iter_archive_records(archive, "BAC"):
        race_records += 1
        parsed = parser.bac(record)
        race_key = str(parsed["race_key_raw"])
        if race_key not in existing_race_keys:
            continue
        leg = normalize_leg(parsed.get("win5_leg_no"), member, race_key)
        if leg is None:
            continue
        old = mapping.get(race_key)
        if old is not None and old != leg:
            raise RuntimeError(
                f"{archive}: conflicting WIN5 legs for {race_key}: {old} vs {leg}"
            )
        mapping[race_key] = leg

    return mapping, {
        "archive": str(archive),
        "sha256": sha256_file(archive),
        "race_records": race_records,
        "win5_races": len(mapping),
    }


def collect_paci_date(
    raw_root: Path,
    race_date: str,
    existing_race_keys: set[str],
) -> tuple[dict[str, int], dict[str, object]]:
    """Collect WIN5 race keys from one daily PACI archive."""
    date = dt.datetime.strptime(race_date, "%Y-%m-%d").date()
    archive = raw_root / "PACI" / f"PACI{date:%y%m%d}.zip"
    if not archive.exists():
        raise FileNotFoundError(archive)

    parser = Parser()
    mapping: dict[str, int] = {}
    race_records = 0
    for member, record in iter_archive_records(archive, "BAC"):
        race_records += 1
        parsed = parser.bac(record)
        race_key = str(parsed["race_key_raw"])
        if race_key not in existing_race_keys:
            continue
        leg = normalize_leg(parsed.get("win5_leg_no"), member, race_key)
        if leg is None:
            continue
        old = mapping.get(race_key)
        if old is not None and old != leg:
            raise RuntimeError(
                f"{archive}: conflicting WIN5 legs for {race_key}: {old} vs {leg}"
            )
        mapping[race_key] = leg

    return mapping, {
        "archive": str(archive),
        "sha256": sha256_file(archive),
        "race_records": race_records,
        "win5_races": len(mapping),
    }


def merge_mapping(target: dict[str, int], source: dict[str, int]) -> None:
    """Merge a source mapping while rejecting conflicting leg assignments."""
    for race_key, leg in source.items():
        old = target.get(race_key)
        if old is not None and old != leg:
            raise RuntimeError(
                f"conflicting WIN5 legs for {race_key}: {old} vs {leg}"
            )
        target[race_key] = leg


def validate_leg_sequence(
    connection: sqlite3.Connection,
) -> tuple[int, list[dict[str, object]]]:
    """Validate that each WIN5 date contains exactly one leg 1..5 when present."""
    rows = connection.execute(
        """
        SELECT race_date, win5_leg_no, COUNT(DISTINCT race_key)
        FROM fact_entry_result_lite
        WHERE win5_leg_no IS NOT NULL
        GROUP BY race_date, win5_leg_no
        ORDER BY race_date, win5_leg_no
        """
    ).fetchall()

    by_date: dict[str, dict[int, int]] = {}
    for race_date, leg, race_count in rows:
        by_date.setdefault(str(race_date), {})[int(leg)] = int(race_count)

    anomalies: list[dict[str, object]] = []
    for race_date, legs in by_date.items():
        if set(legs) != {1, 2, 3, 4, 5}:
            anomalies.append({"race_date": race_date, "legs": legs})
            continue
        if any(count != 1 for count in legs.values()):
            anomalies.append({"race_date": race_date, "legs": legs})

    return len(by_date), anomalies


def migrate(db: Path, raw_root: Path) -> dict[str, object]:
    """Apply the v1.2 -> v1.3 schema/data migration and return an audit report."""
    if not db.exists():
        raise FileNotFoundError(db)

    connection = sqlite3.connect(db)
    try:
        columns_before = table_columns(connection, "fact_entry_result_lite")
        required = {"race_key", "horse_no", "race_date", "year"}
        missing = required - columns_before
        if missing:
            raise RuntimeError(
                "Analysis fact table is missing required columns: "
                + ", ".join(sorted(missing))
            )
        if "win5_leg_no" in columns_before:
            raise RuntimeError("win5_leg_no already exists; refusing double migration")

        row_count_before = int(
            connection.execute(
                "SELECT COUNT(*) FROM fact_entry_result_lite"
            ).fetchone()[0]
        )
        distinct_races_before = int(
            connection.execute(
                "SELECT COUNT(DISTINCT race_key) FROM fact_entry_result_lite"
            ).fetchone()[0]
        )
        existing_race_keys = {
            str(row[0])
            for row in connection.execute(
                "SELECT DISTINCT race_key FROM fact_entry_result_lite"
            )
        }

        years = source_years(connection)
        mapping: dict[str, int] = {}
        sources: list[dict[str, object]] = []

        for year in years:
            if year <= 2025:
                year_mapping, meta = collect_annual_bac(
                    raw_root,
                    year,
                    existing_race_keys,
                )
                merge_mapping(mapping, year_mapping)
                sources.append({"year": year, "mode": "annual_bac", **meta})
                continue

            for race_date in source_dates(connection, year):
                date_mapping, meta = collect_paci_date(
                    raw_root,
                    race_date,
                    existing_race_keys,
                )
                merge_mapping(mapping, date_mapping)
                sources.append(
                    {"year": year, "date": race_date, "mode": "paci", **meta}
                )

        started_at = now()
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                "ALTER TABLE fact_entry_result_lite "
                "ADD COLUMN win5_leg_no INTEGER "
                "CHECK(win5_leg_no IS NULL OR win5_leg_no BETWEEN 1 AND 5)"
            )
            connection.executemany(
                "UPDATE fact_entry_result_lite "
                "SET win5_leg_no=? WHERE race_key=?",
                [(leg, race_key) for race_key, leg in mapping.items()],
            )
            connection.execute(
                """
                INSERT INTO meta_analysis_build(
                    builder_version,
                    schema_version,
                    source_core_sha256,
                    started_at,
                    finished_at,
                    status,
                    row_count
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    f"upgrade_jrdb_analysis_v1_2_to_v1_3/{VERSION}",
                    TARGET_SCHEMA_VERSION,
                    None,
                    started_at,
                    now(),
                    "SUCCESS",
                    row_count_before,
                ),
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

        row_count_after = int(
            connection.execute(
                "SELECT COUNT(*) FROM fact_entry_result_lite"
            ).fetchone()[0]
        )
        distinct_races_after = int(
            connection.execute(
                "SELECT COUNT(DISTINCT race_key) FROM fact_entry_result_lite"
            ).fetchone()[0]
        )
        if row_count_after != row_count_before:
            raise RuntimeError(
                f"row count changed: before={row_count_before} after={row_count_after}"
            )
        if distinct_races_after != distinct_races_before:
            raise RuntimeError(
                "distinct race count changed: "
                f"before={distinct_races_before} after={distinct_races_after}"
            )

        invalid_values = int(
            connection.execute(
                "SELECT COUNT(*) FROM fact_entry_result_lite "
                "WHERE win5_leg_no IS NOT NULL "
                "AND win5_leg_no NOT BETWEEN 1 AND 5"
            ).fetchone()[0]
        )
        race_inconsistency = int(
            connection.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT race_key
                    FROM fact_entry_result_lite
                    GROUP BY race_key
                    HAVING COUNT(DISTINCT COALESCE(win5_leg_no, -1)) <> 1
                )
                """
            ).fetchone()[0]
        )
        win5_races = int(
            connection.execute(
                "SELECT COUNT(DISTINCT race_key) "
                "FROM fact_entry_result_lite WHERE win5_leg_no IS NOT NULL"
            ).fetchone()[0]
        )
        win5_rows = int(
            connection.execute(
                "SELECT COUNT(*) FROM fact_entry_result_lite "
                "WHERE win5_leg_no IS NOT NULL"
            ).fetchone()[0]
        )
        leg_distribution = {
            int(row[0]): int(row[1])
            for row in connection.execute(
                "SELECT win5_leg_no, COUNT(DISTINCT race_key) "
                "FROM fact_entry_result_lite "
                "WHERE win5_leg_no IS NOT NULL "
                "GROUP BY win5_leg_no ORDER BY win5_leg_no"
            )
        }
        win5_dates, sequence_anomalies = validate_leg_sequence(connection)
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])

        if invalid_values != 0:
            raise RuntimeError(f"invalid WIN5 values found: {invalid_values}")
        if race_inconsistency != 0:
            raise RuntimeError(
                f"race-level WIN5 inconsistency found: {race_inconsistency}"
            )
        if sequence_anomalies:
            raise RuntimeError(
                "WIN5 leg sequence anomalies: "
                + json.dumps(sequence_anomalies[:10], ensure_ascii=False)
            )
        if integrity != "ok":
            raise RuntimeError(f"integrity_check failed: {integrity}")

        return {
            "source_schema_version": SOURCE_SCHEMA_VERSION,
            "target_schema_version": TARGET_SCHEMA_VERSION,
            "rows_before": row_count_before,
            "rows_after": row_count_after,
            "distinct_races_before": distinct_races_before,
            "distinct_races_after": distinct_races_after,
            "win5_dates": win5_dates,
            "win5_races": win5_races,
            "win5_rows": win5_rows,
            "leg_distribution_races": leg_distribution,
            "invalid_values": invalid_values,
            "race_level_inconsistency": race_inconsistency,
            "sequence_anomalies": sequence_anomalies,
            "integrity_check": integrity,
            "source_count": len(sources),
            "sources": sources,
        }
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Upgrade JRDB Analysis Lite v1.2 to v1.3 (WIN5 backfill)"
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path)
    return parser.parse_args()


def main() -> None:
    """Run migration and emit a machine-readable audit."""
    args = parse_args()
    result = migrate(args.db, args.raw_root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.audit_json is not None:
        args.audit_json.parent.mkdir(parents=True, exist_ok=True)
        args.audit_json.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
