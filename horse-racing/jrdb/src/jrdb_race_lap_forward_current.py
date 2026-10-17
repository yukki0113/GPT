#!/usr/bin/env python3
"""Validate canonical RaceLap forward-current and its forecast as-of boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jrdb_race_lap_contract import DATASET_SCHEMA_VERSION, LOGIC_VERSION
from jrdb_race_lap_store import RaceLapStore


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate(parquet: Path, manifest: Path, target_date: str,
             analysis_period_to: str) -> dict:
    m = json.loads(manifest.read_text(encoding="utf-8"))
    if m.get("schema_version") != "jrdb-race-lap-forward-current-0.1":
        raise ValueError("RaceLap current schema mismatch")
    if m.get("status") != "CURRENT":
        raise ValueError("RaceLap current not accepted")
    if m.get("validation_status") != "PASS":
        raise ValueError("RaceLap validation not PASS")
    if m.get("dataset_schema_version") != DATASET_SCHEMA_VERSION:
        raise ValueError("RaceLap dataset schema mismatch")
    if m.get("shape_logic_version") != LOGIC_VERSION:
        raise ValueError("RaceLap shape logic mismatch")
    if m.get("period_to") != analysis_period_to:
        raise ValueError(f"stale/misaligned RaceLap: {m.get('period_to')} vs Analysis {analysis_period_to}")
    if not m["period_to"] < target_date:
        raise ValueError("RaceLap target-date leakage")
    if m.get("parquet_size_bytes") != parquet.stat().st_size:
        raise ValueError("RaceLap size mismatch")
    digest = sha(parquet)
    if m.get("parquet_sha256") != digest:
        raise ValueError("RaceLap SHA mismatch")
    store = RaceLapStore(parquet)
    meta = store.metadata()
    if meta["max_race_date"] != m["period_to"] or meta["min_race_date"] != m["period_from"]:
        raise ValueError("RaceLap store date range mismatch")
    if meta["race_count"] != m["race_count"]:
        raise ValueError("RaceLap store row count mismatch")
    return {"status": "PASS", "generation_id": m["generation_id"],
            "race_count": meta["race_count"], "race_lap_sha256": digest,
            "race_lap_period_to": m["period_to"], "analysis_period_to": analysis_period_to,
            "target_date": target_date}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--target-date", required=True)
    ap.add_argument("--analysis-period-to", required=True)
    args = ap.parse_args()
    print(json.dumps(validate(args.parquet, args.manifest, args.target_date, args.analysis_period_to),sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
