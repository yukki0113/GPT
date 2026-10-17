#!/usr/bin/env python3
"""Incrementally advance an immutable JRDB RaceLap Parquet generation.

No network calls. Accept a verified previous Parquet and exact completed-day
SED archives (SED+SRB); reuse the canonical JRDB RaceLap parser and schema.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from jrdb_race_lap_contract import COLUMN_TYPES, DATASET_SCHEMA_VERSION, LOGIC_VERSION
from jrdb_race_lap_dataset import build_rows
from jrdb_race_lap_store import RaceLapStore


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _encoded(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _rows(path: Path) -> dict[str, dict]:
    import duckdb
    connection = duckdb.connect(":memory:")
    try:
        columns = ", ".join(f'"{x}"' for x in COLUMN_TYPES)
        cursor = connection.execute(
            f"SELECT {columns} FROM read_parquet(?, hive_partitioning=false)", [str(path)]
        )
        names = [x[0] for x in cursor.description]
        result = {}
        for values in cursor.fetchall():
            row = dict(zip(names, values, strict=True))
            key = row["race_key"]
            if key in result:
                raise ValueError(f"duplicate previous race_key: {key}")
            result[key] = row
        return result
    finally:
        connection.close()


def refresh(previous: Path, archives: list[Path], output_root: Path, generation_id: str,
            expected_dates: list[str] | None = None) -> dict:
    import duckdb
    import re
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,127}", generation_id):
        raise ValueError("invalid generation_id")
    previous = previous.resolve()
    archives = [p.resolve() for p in archives]
    if not archives or len(set(archives)) != len(archives):
        raise ValueError("at least one unique incoming SED archive is required")
    if not previous.is_file():
        raise FileNotFoundError(previous)
    prior_store = RaceLapStore(previous)
    previous_rows = _rows(previous)
    delta_rows = build_rows(archives)
    if expected_dates is not None:
        expected = set(expected_dates)
        actual = {r["race_date"] for r in delta_rows}
        if actual != expected:
            raise ValueError(f"delta race dates differ: expected={sorted(expected)}, actual={sorted(actual)}")
    if any(row["race_date"] < prior_store.metadata()["min_race_date"] for row in delta_rows):
        raise ValueError("delta precedes existing dataset")
    new_rows = []
    identical = 0
    for row in delta_rows:
        old = previous_rows.get(row["race_key"])
        if old is not None:
            if _encoded(old) != _encoded(row):
                raise ValueError(f"CONFLICT existing race_key changed: {row['race_key']}")
            identical += 1
        else:
            if row["race_date"] <= prior_store.metadata()["max_race_date"]:
                raise ValueError(f"non-forward backfill requires explicit repair: {row['race_key']}")
            new_rows.append(row)
    if not new_rows:
        return {"status": "NOOP_IDENTICAL_RETRY", "generation_id": generation_id,
                "previous_sha256": _sha(previous), "parquet_sha256": _sha(previous),
                "race_count": len(previous_rows), "identical_count": identical,
                "new_count": 0, "validation_status": "PASS"}
    target = output_root / "generations" / generation_id
    if target.exists():
        raise FileExistsError(f"immutable generation exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".racelap-forward-", dir=target.parent) as tmp:
        stage = Path(tmp)
        parquet = stage / "race_lap.parquet"
        con = duckdb.connect(":memory:")
        try:
            declarations = ", ".join(f'"{k}" {v}' for k, v in COLUMN_TYPES.items())
            con.execute(f"CREATE TABLE delta ({declarations})")
            names = list(COLUMN_TYPES)
            con.executemany(
                f"INSERT INTO delta VALUES ({', '.join('?' for _ in names)})",
                [[r[k] for k in names] for r in new_rows],
            )
            source = str(previous).replace("'", "''")
            destination = str(parquet).replace("'", "''")
            columns = ", ".join(f'"{c}"' for c in names)
            con.execute(
                f"COPY (SELECT {columns} FROM read_parquet('{source}', hive_partitioning=false) "
                f"UNION ALL SELECT {columns} FROM delta ORDER BY race_date, race_key) "
                f"TO '{destination}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        finally:
            con.close()
        result_store = RaceLapStore(parquet)
        new_full = _rows(parquet)
        if len(new_full) != len(previous_rows) + len(new_rows):
            raise ValueError("row count mismatch")
        for key, old in previous_rows.items():
            if _encoded(new_full[key]) != _encoded(old):
                raise ValueError(f"previous row not preserved: {key}")
        expected_coverage = prior_store.metadata()
        result_meta = result_store.metadata()
        if result_meta["race_count"] != len(previous_rows) + len(new_rows):
            raise ValueError("RaceLapStore validation mismatch")
        sha = _sha(parquet)
        audit = {
            "status": "CANDIDATE_PASS",
            "generation_id": generation_id,
            "previous_sha256": _sha(previous),
            "input_archives": [{"name": p.name, "sha256": _sha(p)} for p in archives],
            "identical_count": identical,
            "new_count": len(new_rows),
            "previous_count": len(previous_rows),
            "race_count": len(new_full),
            "previous_rows_preserved": True,
            "duplicate_key_rows": 0,
            "parquet_sha256": sha,
            "parquet_size_bytes": parquet.stat().st_size,
            "period_from": result_meta["min_race_date"],
            "period_to": result_meta["max_race_date"],
            "dataset_schema_version": DATASET_SCHEMA_VERSION,
            "shape_logic_version": LOGIC_VERSION,
            "validation_status": "PASS",
        }
        (stage / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest = dict(audit)
        manifest["schema_version"] = "jrdb-race-lap-forward-current-0.1"
        manifest["status"] = "CANDIDATE_PASS"
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.rename(stage, target)
    return audit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--previous", type=Path, required=True)
    ap.add_argument("--sed", type=Path, action="append", required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--generation-id", required=True)
    ap.add_argument("--expected-date", action="append")
    args = ap.parse_args()
    report = refresh(args.previous, args.sed, args.output_root, args.generation_id, args.expected_date)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
