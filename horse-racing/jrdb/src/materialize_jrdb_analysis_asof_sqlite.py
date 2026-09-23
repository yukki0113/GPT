#!/usr/bin/env python3
"""Materialize an as-of-safe Analysis SQLite for Historical RaceNote.

The historical enrichment engine needs the target entry only to resolve the
runner's stable identity, sire, and jockey. It must never receive target-day
result or market values. This adapter keeps every completed row before the
target date and projects target-day rows to that minimal identity surface.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

TABLE = "fact_entry_result_lite"
TARGET_IDENTITY_COLUMNS = {
    "race_key", "race_date", "venue_code", "race_no", "horse_no",
    "horse_id", "horse_name", "sire_name", "jockey_name",
}


def materialize(source: Path, target_date: str, output: Path) -> dict:
    if output.exists():
        raise ValueError(f"refusing to overwrite: {output}")
    source_db = sqlite3.connect(source)
    destination = sqlite3.connect(output)
    try:
        row = source_db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
        ).fetchone()
        if not row or not row[0]:
            raise ValueError(f"source lacks {TABLE}")
        destination.execute(row[0])
        columns = [item[1] for item in destination.execute(f"PRAGMA table_info({TABLE})")]
        missing = TARGET_IDENTITY_COLUMNS - set(columns)
        if missing:
            raise ValueError(f"Analysis schema lacks identity columns: {sorted(missing)}")
        destination.execute("ATTACH DATABASE ? AS source", (str(source),))
        destination.execute(
            f"INSERT INTO {TABLE} SELECT * FROM source.{TABLE} WHERE race_date < ?",
            (target_date,),
        )
        projected = ", ".join(
            name if name in TARGET_IDENTITY_COLUMNS else "NULL" for name in columns
        )
        destination.execute(
            f"INSERT INTO {TABLE} ({', '.join(columns)}) "
            f"SELECT {projected} FROM source.{TABLE} WHERE race_date = ?",
            (target_date,),
        )
        destination.execute(
            f"CREATE INDEX ix_analysis_asof_horse_history "
            f"ON {TABLE}(horse_id, race_date DESC, race_no DESC)"
        )
        destination.commit()
        forbidden = [name for name in columns if name not in TARGET_IDENTITY_COLUMNS]
        target_non_null = sum(
            destination.execute(
                f"SELECT count(*) FROM {TABLE} WHERE race_date=? AND {name} IS NOT NULL",
                (target_date,),
            ).fetchone()[0]
            for name in forbidden
        )
        result = {
            "status": "PASS",
            "target_date": target_date,
            "rows_before_target": destination.execute(
                f"SELECT count(*) FROM {TABLE} WHERE race_date < ?", (target_date,)
            ).fetchone()[0],
            "target_identity_rows": destination.execute(
                f"SELECT count(*) FROM {TABLE} WHERE race_date = ?", (target_date,)
            ).fetchone()[0],
            "target_identity_columns": sorted(TARGET_IDENTITY_COLUMNS),
            "target_forbidden_non_null_values": target_non_null,
            "integrity_check": destination.execute("PRAGMA integrity_check").fetchone()[0],
        }
        if target_non_null or result["integrity_check"] != "ok":
            raise ValueError(f"as-of materialization audit failed: {result}")
        return result
    finally:
        destination.close()
        source_db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize as-of-safe Analysis for RaceNote")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    result = materialize(args.source, args.target_date, args.out)
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
