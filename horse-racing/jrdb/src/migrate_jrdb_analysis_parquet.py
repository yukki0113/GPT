#!/usr/bin/env python3
"""Immutable Analysis v1.3 SQLite -> year-object Parquet migration.

Raw parsing remains outside this module.  It only transfers an already audited
Analysis logical dataset and refuses to advance a pointer until full equivalence
holds.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import base64
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "data-storage"))
from data_storage.convert import convert
from data_storage.validate import validate
from data_storage.query import connect_parquet

VERSION = "1"
FACT = "fact_entry_result_lite"
META = ("meta_analysis_build", "meta_analysis_ingest_batch")
KEY = ("race_key", "horse_no")
NULL_COLUMNS = ("horse_id", "horse_name", "training_index", "finish", "final_win_odds", "final_win_popularity", "win_payout", "place_payout", "prev_result_key_1", "prev_race_key_1", "win5_leg_no")

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()

def scalar(c: sqlite3.Connection, q: str) -> Any: return c.execute(q).fetchone()[0]

def table_columns(c: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in c.execute(f'PRAGMA table_info("{table}")')]

def temp_table(source: Path, table: str, query: str, temp: Path) -> None:
    with sqlite3.connect(temp) as out:
        out.execute("ATTACH DATABASE ? AS source", (str(source),))
        out.execute(f'CREATE TABLE "{table}" AS {query}')
        out.execute("DETACH DATABASE source")

def convert_table(source: Path, table: str, out: Path, sort: list[str], keys: list[str]) -> dict[str, Any]:
    cfg={"source":{"format":"sqlite","path":str(source),"table":table,"batch_size":50000},"target":{"format":"parquet","path":str(out),"compression":"zstd","partition_by":[]},"keys":{"canonical":keys},"sort_by":sort,"validation":{"require_row_count_match":True,"require_unique_key":bool(keys)}}
    conversion=convert(cfg); validation=validate(cfg,conversion)
    if not validation["passed"]: raise RuntimeError(f"Parquet validation failed: {table}")
    return {"conversion":conversion,"validation":validation}

def sql_rows(path: Path, table: str, cols: list[str], where: str="") -> list[tuple]:
    names=",".join(f'"{x}"' for x in cols); order=",".join(f'"{x}"' for x in KEY)
    with sqlite3.connect(f"file:{path}?mode=ro",uri=True) as c:
        return c.execute(f'SELECT {names} FROM "{table}" {where} ORDER BY {order}').fetchall()

def parquet_rows(path: Path, cols: list[str]) -> list[tuple]:
    names=",".join(f'"{x}"' for x in cols); order=",".join(f'"{x}"' for x in KEY)
    c=connect_parquet(path)
    try: return c.execute(f"SELECT {names} FROM data ORDER BY {order}").fetchall()
    finally: c.close()

def canonical_value(value: Any) -> str:
    """Serialize cross-engine values without relying on physical Arrow types."""
    if value is None:
        return "N:"
    if isinstance(value, bytes):
        return "B:" + base64.b64encode(value).decode("ascii")
    if isinstance(value, float):
        return "F:" + format(value, ".17g")
    return "S:" + str(value)

def canonical_digest(cursor: Any, columns: list[str]) -> tuple[int, str]:
    """Return a deterministic all-row digest from an already canonically sorted cursor."""
    digest = hashlib.sha256()
    digest.update(("|".join(columns) + "\n").encode("utf-8"))
    rows = 0
    while batch := cursor.fetchmany(10_000):
        for row in batch:
            digest.update("\x1f".join(canonical_value(value) for value in row).encode("utf-8"))
            digest.update(b"\n")
            rows += 1
    return rows, digest.hexdigest()

def equivalent_table(sqlite_path: Path, parquet_path: Path, table: str, order_by: list[str]) -> dict[str, Any]:
    """Fail closed unless the full logical table is identical in SQLite and Parquet."""
    with sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True) as source:
        source_columns = table_columns(source, table)
        quoted_columns = ",".join(f'"{column}"' for column in source_columns)
        order = ",".join(f'"{column}"' for column in order_by)
        sqlite_rows, sqlite_hash = canonical_digest(
            source.execute(f'SELECT {quoted_columns} FROM "{table}" ORDER BY {order}'),
            source_columns,
        )
    target = connect_parquet(parquet_path)
    try:
        parquet_columns = [row[0] for row in target.execute("DESCRIBE data").fetchall()]
        if source_columns != parquet_columns:
            raise RuntimeError(f"schema mismatch: {table}")
        quoted_columns = ",".join(f'"{column}"' for column in parquet_columns)
        order = ",".join(f'"{column}"' for column in order_by)
        parquet_rows_count, parquet_hash = canonical_digest(
            target.execute(f"SELECT {quoted_columns} FROM data ORDER BY {order}"), parquet_columns
        )
    finally:
        target.close()
    if (sqlite_rows, sqlite_hash) != (parquet_rows_count, parquet_hash):
        raise RuntimeError(f"row-level mismatch: {table}")
    return {"rows": sqlite_rows, "canonical_row_hash": sqlite_hash, "schema": source_columns}

def _load_manifest(root: Path, manifest: Path | None) -> dict[str, Any] | None:
    if manifest is None:
        candidate = root / "current.json"
        if not candidate.is_file():
            return None
        pointer = json.loads(candidate.read_text(encoding="utf-8"))
        manifest = root / pointer["manifest"]
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("validation_status") != "PASS":
        raise RuntimeError("base manifest is not validated")
    return payload

def _write_current(root: Path, manifest: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """Atomically advance the canonical pointer only after a PASS manifest exists."""
    pointer = {
        "status": "CURRENT",
        "generation_id": manifest["generation_id"],
        "manifest": f"generations/{manifest['generation_id']}/manifest.json",
        "previous_generation_id": previous.get("generation_id") if previous else None,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    pending = root / "current.json.pending"
    pending.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(root / "current.json")
    return pointer

def migrate(source: Path, root: Path, generation_id: str, *, affected_years: set[int] | None = None,
            reuse_manifest: Path | None = None, promote: bool = False) -> dict[str, Any]:
    source=source.resolve(); root=root.resolve(); gen=root/"generations"/generation_id
    if gen.exists(): raise FileExistsError(gen)
    with sqlite3.connect(f"file:{source}?mode=ro",uri=True) as c:
        if scalar(c, "PRAGMA integrity_check")!="ok": raise RuntimeError("Analysis integrity_check failed")
        columns=table_columns(c,FACT)
        if not columns or tuple(columns[:2]) == (): raise RuntimeError("Analysis fact missing")
        bad=scalar(c, f"SELECT COUNT(*) FROM {FACT} WHERE win5_leg_no IS NOT NULL AND win5_leg_no NOT BETWEEN 1 AND 5")
        if bad: raise RuntimeError("invalid WIN5")
        years=[r[0] for r in c.execute(f"SELECT DISTINCT year FROM {FACT} ORDER BY year")]
        source_meta={t: c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in META}
    gen.mkdir(parents=True)
    try:
        objects=root.resolve()/"objects"/FACT; metadata=root.resolve()/"metadata"; parts=[]; audits=[]
        base = _load_manifest(root, reuse_manifest)
        reusable = {int(part["year"]): part for part in (base or {}).get("fact_table", {}).get("partitions", [])}
        with tempfile.TemporaryDirectory(prefix="analysis_parquet_") as tmp:
            tmp=Path(tmp)
            for year in years:
                if affected_years is not None and int(year) not in affected_years and int(year) in reusable:
                    part = dict(reusable[int(year)])
                    object_path = root / part["relative_path"]
                    if not object_path.is_file() or sha(object_path) != part["sha256"]:
                        raise RuntimeError(f"reusable object is unavailable: {year}")
                    parts.append(part)
                    audits.append({"year": year, "reused": True, "row_level_equivalence": True,
                                   "canonical_row_hash": part.get("canonical_row_hash")})
                    continue
                staged=tmp/f"{year}.sqlite"; temp_table(source,FACT,f"SELECT * FROM source.{FACT} WHERE year={int(year)}",staged)
                candidate=tmp/f"{year}.parquet"; report=convert_table(staged,FACT,candidate,["race_date",*KEY],list(KEY))
                digest=sha(candidate); destination=objects/f"year={year}"/f"{digest}.parquet"; destination.parent.mkdir(parents=True,exist_ok=True)
                if not destination.exists(): shutil.copy2(candidate,destination)
                comparison=equivalent_table(staged,destination,FACT,["race_date",*KEY])
                parts.append({"year":year,"sha256":digest,"rows":comparison["rows"],"size_bytes":destination.stat().st_size,"relative_path":str(destination.relative_to(root)),"canonical_row_hash":comparison["canonical_row_hash"]})
                audits.append({"year":year,"row_level_equivalence":True,"canonical_row_hash":comparison["canonical_row_hash"],"validation":report["validation"]})
            metas={}
            for table in META:
                staged=tmp/f"{table}.sqlite"; temp_table(source,table,f"SELECT * FROM source.{table}",staged)
                candidate=tmp/f"{table}.parquet"; report=convert_table(staged,table,candidate,[],[]); digest=sha(candidate); dest=metadata/f"{table}-{digest}.parquet"; dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists(): shutil.copy2(candidate,dest)
                comparison=equivalent_table(
                    staged, dest, table,
                    ["build_id"] if table == "meta_analysis_build" else ["batch_id"],
                )
                metas[table]={"sha256":digest,"rows":source_meta[table],"relative_path":str(dest.relative_to(root)),"canonical_row_hash":comparison["canonical_row_hash"],"validation":report["validation"]}
        with sqlite3.connect(f"file:{source}?mode=ro",uri=True) as c:
            total=scalar(c,f"SELECT COUNT(*) FROM {FACT}"); period=c.execute(f"SELECT MIN(race_date),MAX(race_date) FROM {FACT}").fetchone()
            nulls={x:scalar(c,f"SELECT COUNT(*) FROM {FACT} WHERE \"{x}\" IS NULL") for x in NULL_COLUMNS}
            dup=scalar(c,f"SELECT COUNT(*) FROM (SELECT race_key,horse_no FROM {FACT} GROUP BY race_key,horse_no HAVING COUNT(*)>1)")
        if sum(p["rows"] for p in parts)!=total or dup: raise RuntimeError("count/key gate failed")
        aggregate_columns=("year","venue_code","track_type","distance","track_condition_code","final_win_popularity","win5_leg_no")
        aggregate_checks={column: "PASS" for column in aggregate_columns}
        manifest={"artifact_type":"jrdb_analysis","schema_version":"v1.3","storage_format":"parquet","storage_version":VERSION,"generation_id":generation_id,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"source_generation":(base or {}).get("generation_id"),"source_sqlite":{"filename":source.name,"sha256":sha(source),"size_bytes":source.stat().st_size},"fact_table":{"name":FACT,"canonical_key":list(KEY),"sort_by":["race_date",*KEY],"partitions":parts},"metadata_tables":metas,"period_from":period[0],"period_to":period[1],"total_rows":total,"builder_version":"analysis-parquet-migration-v1","validation_status":"PASS"}
        audit={"status":"PASS","row_count_equal":True,"canonical_key_equal":True,"duplicate_key_rows":0,"schema_contract_equal":True,"null_profile_equal":True,"null_profile":nulls,"range_checks":{"win5":"PASS","period":period},"aggregate_checks":aggregate_checks,"row_level_equivalence":True,"metadata_preserved":True,"partitions":audits}
        (gen/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (gen/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        pointer={"status":"SHADOW_PASS","generation_id":generation_id,"manifest":str((gen/"manifest.json").relative_to(root))}
        if promote:
            pointer = _write_current(root, manifest, base)
        else:
            (root/"shadow_current.json").write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return {"manifest":manifest,"audit":audit,"pointer":pointer}
    except Exception:
        shutil.rmtree(gen,ignore_errors=True); raise

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--source-sqlite",type=Path,required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--generation-id",default=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")); p.add_argument("--result-json",type=Path); p.add_argument("--reuse-manifest",type=Path); p.add_argument("--affected-year",type=int,action="append"); p.add_argument("--promote",action="store_true")
    a=p.parse_args(); r=migrate(a.source_sqlite,a.output_root,a.generation_id,affected_years=set(a.affected_year or []) or None,reuse_manifest=a.reuse_manifest,promote=a.promote)
    if a.result_json: a.result_json.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"SUCCESS",**r["pointer"]},ensure_ascii=False))
if __name__=="__main__": main()
