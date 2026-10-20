#!/usr/bin/env python3
"""Materialize a leak-safe historical RaceLap CURRENT snapshot from an accepted later CURRENT.

This is deterministic transport only. It preserves rows whose race_date is on or
before the requested completed-day cutoff and writes a CURRENT-compatible bundle
that can be validated by jrdb_race_lap_forward_current.py.
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path

from jrdb_race_lap_contract import DATASET_SCHEMA_VERSION, LOGIC_VERSION
from jrdb_race_lap_store import RaceLapStore


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def build(source_bundle: Path, cutoff: str, output_bundle: Path, generation_id: str) -> dict:
    import duckdb
    source_bundle=Path(source_bundle).resolve()
    output_bundle=Path(output_bundle).resolve()
    if output_bundle.exists():
        raise FileExistsError(f"output exists: {output_bundle}")
    source_manifest=json.loads((source_bundle/"manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("status")!="CURRENT" or source_manifest.get("validation_status")!="PASS":
        raise ValueError("source RaceLap is not accepted CURRENT")
    if source_manifest.get("dataset_schema_version")!=DATASET_SCHEMA_VERSION:
        raise ValueError("source dataset schema mismatch")
    if source_manifest.get("shape_logic_version")!=LOGIC_VERSION:
        raise ValueError("source shape logic mismatch")
    if not source_manifest.get("period_from") <= cutoff <= source_manifest.get("period_to"):
        raise ValueError("cutoff outside source range")
    source_parquet=source_bundle/"race_lap.parquet"
    output_bundle.mkdir(parents=True)
    out=output_bundle/"race_lap.parquet"
    con=duckdb.connect(":memory:")
    try:
        con.execute("SET threads=1")
        src=str(source_parquet).replace("'","''")
        dst=str(out).replace("'","''")
        cut=cutoff.replace("'","''")
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{src}', hive_partitioning=false) "
            f"WHERE race_date <= '{cut}' ORDER BY race_date, race_key) "
            f"TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con.close()
    store=RaceLapStore(out)
    meta=store.metadata()
    if meta["max_race_date"] != cutoff:
        raise ValueError(f"cutoff has no terminal race rows: {meta['max_race_date']} != {cutoff}")
    manifest={
        "schema_version":"jrdb-race-lap-forward-current-0.1",
        "status":"CURRENT",
        "validation_status":"PASS",
        "generation_id":generation_id,
        "dataset_schema_version":DATASET_SCHEMA_VERSION,
        "shape_logic_version":LOGIC_VERSION,
        "period_from":meta["min_race_date"],
        "period_to":meta["max_race_date"],
        "race_count":meta["race_count"],
        "parquet_sha256":sha256(out),
        "parquet_size_bytes":out.stat().st_size,
        "source_generation_id":source_manifest.get("generation_id"),
        "source_parquet_sha256":source_manifest.get("parquet_sha256"),
        "materialization_policy":"AS_OF_COMPLETED_DAY_INCLUSIVE",
        "future_rows_removed":int(source_manifest.get("race_count",0))-int(meta["race_count"]),
    }
    (output_bundle/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (output_bundle/"audit.json").write_text(json.dumps({
        "status":"PASS",
        "operation":"RACELAP_ASOF_SNAPSHOT",
        "cutoff":cutoff,
        "source_generation_id":source_manifest.get("generation_id"),
        "source_period_to":source_manifest.get("period_to"),
        "output_generation_id":generation_id,
        "race_count":meta["race_count"],
        "future_rows_removed":manifest["future_rows_removed"],
        "parquet_sha256":manifest["parquet_sha256"],
    },ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return manifest


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-bundle",type=Path,required=True)
    ap.add_argument("--cutoff",required=True)
    ap.add_argument("--output-bundle",type=Path,required=True)
    ap.add_argument("--generation-id",required=True)
    a=ap.parse_args()
    print(json.dumps(build(a.source_bundle,a.cutoff,a.output_bundle,a.generation_id),ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
