#!/usr/bin/env python3
"""Apply one PACI+SED update to a temporary Analysis SQLite and audit it."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from update_jrdb_analysis_incremental import (
    ensure_v13,
    parse_paci_sed,
    sha256_file,
    update_rows,
)


FACT = "fact_entry_result_lite"
KEY = ("race_key", "horse_no")


def _canon(value: object) -> str:
    if value is None:
        return "N:"
    if isinstance(value, float):
        return f"F:{value:.17g}"
    return f"S:{value}"


def _non_target_snapshot(connection: sqlite3.Connection, target_date: str) -> dict[str, Any]:
    columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{FACT}")')]
    if not columns:
        raise RuntimeError("Analysis fact table is missing")
    names = ",".join(f'"{column}"' for column in columns)
    order = ",".join(f'"{column}"' for column in KEY)
    digest = hashlib.sha256(("|".join(columns) + "\n").encode())
    rows = 0
    cursor = connection.execute(
        f'SELECT {names} FROM "{FACT}" WHERE race_date != ? ORDER BY {order}',
        (target_date,),
    )
    for row in cursor:
        digest.update("\x1f".join(_canon(value) for value in row).encode())
        digest.update(b"\n")
        rows += 1
    return {"rows": rows, "sha256": digest.hexdigest()}


def _audit_as_of(connection: sqlite3.Connection, target_date: str) -> int:
    """Reject result keys dated on/after their target race date when available."""
    cutoff = target_date.replace("-", "")
    bad = 0
    for (result_key,) in connection.execute(
        f'SELECT prev_result_key_1 FROM "{FACT}" WHERE race_date=? '
        "AND prev_result_key_1 IS NOT NULL",
        (target_date,),
    ):
        value = str(result_key)
        suffix = value[-8:]
        if suffix.isdigit() and suffix >= cutoff:
            bad += 1
    if bad:
        raise RuntimeError(f"as-of violation rows for {target_date}: {bad}")
    return bad


def _latest_batch(connection: sqlite3.Connection, target_date: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT status,batch_id,row_count,source_sha256s FROM meta_analysis_ingest_batch "
        "WHERE target_date=? ORDER BY batch_id DESC LIMIT 1",
        (target_date,),
    ).fetchone()
    if row is None or row[0] != "SUCCESS":
        raise RuntimeError(f"latest ingest is not SUCCESS for {target_date}")
    source_sha256s = json.loads(row[3])
    return {"batch_id": int(row[1]), "row_count": int(row[2]), "source_sha256s": source_sha256s}


def update_paci_sed(db_path: Path, paci: Path, sed: Path) -> dict[str, Any]:
    """Run the existing date replacement while proving all other fact rows unchanged."""
    target, rows, metadata = parse_paci_sed(paci, sed)
    target_date = target.isoformat()
    expected_sha = {"PACI": sha256_file(paci), "SED": sha256_file(sed)}
    if metadata.get("source_sha256s") != expected_sha:
        raise RuntimeError("PACI/SED input SHA mismatch before update")

    connection = sqlite3.connect(db_path)
    try:
        ensure_v13(connection)
        before = _non_target_snapshot(connection, target_date)
        update = update_rows(connection, target, rows, metadata)
        after = _non_target_snapshot(connection, target_date)
        if before != after:
            raise RuntimeError("non-target Analysis rows changed")
        target_rows = int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{FACT}" WHERE race_date=?', (target_date,)
            ).fetchone()[0]
        )
        if target_rows != len(rows):
            raise RuntimeError(f"target row count mismatch: {target_rows} != {len(rows)}")
        duplicates = int(
            connection.execute(
                f'SELECT COUNT(*) FROM (SELECT race_key,horse_no FROM "{FACT}" '
                "GROUP BY race_key,horse_no HAVING COUNT(*) > 1)"
            ).fetchone()[0]
        )
        if duplicates:
            raise RuntimeError(f"duplicate canonical keys: {duplicates}")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Analysis integrity_check failed")
        batch = _latest_batch(connection, target_date)
        if batch["source_sha256s"] != expected_sha:
            raise RuntimeError("ingest audit source SHA mismatch")
        as_of_violations = _audit_as_of(connection, target_date)
        return {
            "status": "PASS",
            "target_date": target_date,
            "update": update,
            "target_rows": target_rows,
            "non_target_snapshot": before,
            "duplicate_canonical_keys": duplicates,
            "as_of_violations": as_of_violations,
            "input_sha256s": expected_sha,
            "ingest_batch": batch,
            "integrity_check": "ok",
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--sed", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(update_paci_sed(args.db, args.paci, args.sed), ensure_ascii=False))


if __name__ == "__main__":
    main()
