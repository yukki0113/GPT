#!/usr/bin/env python3
"""Audit exact logical equivalence between JRDB Edge Registry SQLite and Parquet tables."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import duckdb

TABLES = (
    ("edge_registry_meta", ["registry_version"]),
    ("edge_definition", ["edge_id"]),
    ("edge_metric_snapshot", ["edge_id", "snapshot_id"]),
    ("edge_validation_event", ["validation_id"]),
    ("edge_statistical_guard", ["edge_id"]),
)


def _canon(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, float):
        if math.isnan(value): return {"__float__":"NaN"}
        if math.isinf(value): return {"__float__":"Infinity" if value>0 else "-Infinity"}
        if value == 0.0: return 0.0
    return value


def _digest_rows(rows) -> str:
    h=hashlib.sha256()
    for row in rows:
        h.update(json.dumps([_canon(v) for v in row],ensure_ascii=False,separators=(",",":"),allow_nan=False).encode())
        h.update(b"\n")
    return h.hexdigest()


def audit(sqlite_path: Path, parquet_root: Path) -> dict[str, Any]:
    sq=sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro",uri=True)
    dq=duckdb.connect()
    reports={}
    try:
        for table,keys in TABLES:
            pq=parquet_root/f"{table}.parquet"
            if not pq.is_file():
                reports[table]={"status":"FAIL","reason":"missing parquet"}
                continue
            sqlite_cols=[r[1] for r in sq.execute(f"PRAGMA table_info({table})")]
            parquet_cols=[r[0] for r in dq.execute("DESCRIBE SELECT * FROM read_parquet(?)",[str(pq)]).fetchall()]
            order=",".join(f'"{k}"' for k in keys)
            select=",".join(f'"{c}"' for c in sqlite_cols)
            srows=sq.execute(f"SELECT {select} FROM {table} ORDER BY {order}").fetchall()
            prows=dq.execute(f"SELECT {select} FROM read_parquet(?) ORDER BY {order}",[str(pq)]).fetchall()
            dups_sql=int(sq.execute(
                f"SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM {table} GROUP BY {order} HAVING COUNT(*)>1)"
            ).fetchone()[0])
            keyexpr=" || '|' || ".join([f"COALESCE(CAST({k} AS VARCHAR),'<NULL>')" for k in keys])
            dups_pq=int(dq.execute(
                f"SELECT count(*)-count(DISTINCT {keyexpr}) FROM read_parquet(?)",[str(pq)]
            ).fetchone()[0])
            row_hash_sql=_digest_rows(srows)
            row_hash_pq=_digest_rows(prows)
            null_sql={c:int(sq.execute(f'SELECT count(*) FROM {table} WHERE "{c}" IS NULL').fetchone()[0]) for c in sqlite_cols}
            null_pq={c:int(dq.execute(f'SELECT count(*) FROM read_parquet(?) WHERE "{c}" IS NULL',[str(pq)]).fetchone()[0]) for c in parquet_cols}
            ok=(sqlite_cols==parquet_cols and len(srows)==len(prows) and dups_sql==0 and dups_pq==0 and null_sql==null_pq and row_hash_sql==row_hash_pq)
            reports[table]={
                "status":"PASS" if ok else "FAIL",
                "rows_sqlite":len(srows),"rows_parquet":len(prows),
                "columns_equal":sqlite_cols==parquet_cols,
                "duplicate_key_rows_sqlite":dups_sql,"duplicate_key_rows_parquet":dups_pq,
                "null_semantics_equal":null_sql==null_pq,
                "canonical_row_hash_sqlite":row_hash_sql,
                "canonical_row_hash_parquet":row_hash_pq,
                "canonical_row_hash_equal":row_hash_sql==row_hash_pq,
            }
        passed=all(v.get("status")=="PASS" for v in reports.values())
        return {"status":"PASS" if passed else "FAIL","gate":"EDGE_REGISTRY_PARQUET_EQUIVALENCE","tables":reports}
    finally:
        sq.close(); dq.close()


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--sqlite",type=Path,required=True)
    p.add_argument("--parquet-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=audit(a.sqlite,a.parquet_root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
