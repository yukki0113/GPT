#!/usr/bin/env python3
"""Upgrade Analysis Lite v1.1 to v1.2 and backfill KYI prev1 links."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from jrdb_raw import Parser, iter_archive_records

VERSION = "1.1-production"


def upgrade_database(db_path: Path, raw_root: Path, years: list[int]) -> dict[str, Any]:
    """Upgrade one Analysis DB while reading KYI only through Common Reader."""
    connection = sqlite3.connect(db_path)
    try:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(fact_entry_result_lite)"
            )
        }
        if "prev_result_key_1" not in columns:
            connection.execute(
                "ALTER TABLE fact_entry_result_lite "
                "ADD COLUMN prev_result_key_1 TEXT"
            )
        if "prev_race_key_1" not in columns:
            connection.execute(
                "ALTER TABLE fact_entry_result_lite "
                "ADD COLUMN prev_race_key_1 TEXT"
            )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta_analysis_ingest_batch(
              batch_id INTEGER PRIMARY KEY,
              target_date TEXT NOT NULL,
              builder_version TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              status TEXT NOT NULL,
              source_manifest TEXT,
              source_sha256s TEXT,
              race_count INTEGER,
              row_count INTEGER,
              replaced_row_count INTEGER,
              message TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_analysis_ingest_date
              ON meta_analysis_ingest_batch(target_date,status);
            """
        )

        parser = Parser()
        total = 0
        batch: list[tuple[str | None, str | None, str, int | None]] = []
        for year in sorted(years):
            archive = raw_root / "KYI" / f"KYI_{year}.zip"
            for _member, raw in iter_archive_records(archive, "KYI"):
                parsed = parser.kyi(raw)
                race_key = str(parsed.get("race_key_raw") or "")
                horse_no_value = parsed.get("horse_no")
                horse_no = (
                    int(horse_no_value)
                    if isinstance(horse_no_value, (int, float))
                    else None
                )
                previous = parsed.get("previous") or []
                first_previous = previous[0] if previous else {}
                prev_result = str(first_previous.get("result_key") or "") or None
                prev_race = str(first_previous.get("race_key_raw") or "") or None
                if prev_result or prev_race:
                    batch.append((prev_result, prev_race, race_key, horse_no))
                    total += 1
                if len(batch) >= 50000:
                    connection.executemany(
                        "UPDATE fact_entry_result_lite "
                        "SET prev_result_key_1=?, prev_race_key_1=? "
                        "WHERE race_key=? AND horse_no=?",
                        batch,
                    )
                    batch = []
        if batch:
            connection.executemany(
                "UPDATE fact_entry_result_lite "
                "SET prev_result_key_1=?, prev_race_key_1=? "
                "WHERE race_key=? AND horse_no=?",
                batch,
            )

        connection.commit()
        filled = connection.execute(
            "SELECT COUNT(*) FROM fact_entry_result_lite "
            "WHERE prev_result_key_1 IS NOT NULL "
            "OR prev_race_key_1 IS NOT NULL"
        ).fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()

    return {
        "updated_candidates": total,
        "filled_rows": filled,
        "integrity_check": integrity,
        "size_bytes": db_path.stat().st_size,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = upgrade_database(args.db, args.raw_root, args.years)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
