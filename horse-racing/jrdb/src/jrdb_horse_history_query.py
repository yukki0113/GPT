#!/usr/bin/env python3
"""Exact horse-centric history query over canonical Analysis Parquet."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION="jrdb-horse-history/v1"

class HorseHistoryError(RuntimeError): pass

def _date(value):
    if value is None:return None
    return str(value)[:10]

def _normalize(row:dict[str,Any])->dict[str,Any]:
    out={k:row.get(k) for k in ("horse_id","race_date","race_key","race_horse_key","venue_code","race_no","horse_no","track_type","surface_code","distance","distance_m","frame_no","finish","finish_position","odds","popularity","win_payout","place_payout")}
    if out.get("race_horse_key") is None and out.get("race_key") is not None and out.get("horse_no") is not None:
        out["race_horse_key"]=f"{out['race_key']}{int(out['horse_no']):02d}"
    return out

def _guard(rows):
    seen=set()
    for r in rows:
        key=(r.get("race_key"),r.get("horse_no"))
        if None not in key and key in seen: raise HorseHistoryError(f"duplicate Analysis start: {key}")
        seen.add(key)

def query(*,horse_id:str,analysis_root:str|Path|None=None,analysis_db:str|Path|None=None,from_date:str|None=None,to_date:str|None=None,limit:int|None=None,order="asc"):
    if not horse_id: raise ValueError("horse_id is required")
    for label, value in (("from_date",from_date),("to_date",to_date)):
        if value is not None:
            try:
                from datetime import date
                if date.fromisoformat(value).isoformat()!=value: raise ValueError
            except ValueError as e: raise ValueError(f"{label} must be YYYY-MM-DD") from e
    if from_date and to_date and from_date>to_date: raise ValueError("from_date must not exceed to_date")
    if (analysis_root is None)==(analysis_db is None): raise ValueError("provide exactly one of analysis_root or analysis_db")
    if order not in {"asc","desc"}: raise ValueError("order must be asc or desc")
    if limit is not None and limit<=0: raise ValueError("limit must be positive")
    if analysis_db is not None:
        db=Path(analysis_db)
        con=sqlite3.connect(f"file:{db.resolve()}?mode=ro",uri=True); con.row_factory=sqlite3.Row
        try:
            cols={r[1] for r in con.execute("PRAGMA table_info(fact_entry_result_lite)")}
            if "horse_id" not in cols: raise HorseHistoryError("Analysis fact table lacks horse_id")
            sql="SELECT * FROM fact_entry_result_lite WHERE horse_id=?"; params=[horse_id]
            if from_date: sql+=" AND CAST(race_date AS TEXT)>=?"; params.append(from_date)
            if to_date: sql+=" AND CAST(race_date AS TEXT)<=?"; params.append(to_date)
            sql+=" ORDER BY race_date "+order.upper()+", race_key "+order.upper()+", horse_no "+order.upper()
            if limit: sql+=" LIMIT ?"; params.append(limit)
            rows=[dict(r) for r in con.execute(sql,params)]
        finally: con.close()
        provenance={"backend":"sqlite_compatibility","source":str(db)}
    else:
        try: import duckdb
        except ImportError as e: raise HorseHistoryError("DuckDB is required. Follow tools/data-storage/README.md and docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md; run .venv-data-storage check-deps, one normal dependency repair, then the documented GitHub Actions fallback if the managed proxy blocks it.") from e
        try: from jrdb_analysis_parquet_current import resolve_current
        except ImportError as e: raise HorseHistoryError("Unable to import canonical Analysis resolver jrdb_analysis_parquet_current") from e
        root=Path(analysis_root); report=resolve_current(root)
        generation_manifest=json.loads(Path(report["manifest"]).read_text(encoding="utf-8"))
        fact_count=len(generation_manifest["fact_table"]["partitions"])
        files=[str(a["path"]) for a in report["assets"][:fact_count]]
        con=duckdb.connect()
        try:
            # One parameterized DuckDB query across the validated generation partitions.
            sql="SELECT * FROM read_parquet(?, union_by_name=true) WHERE CAST(horse_id AS VARCHAR)=?"; params=[files,str(horse_id)]
            if from_date: sql+=" AND CAST(race_date AS VARCHAR)>=?"; params.append(from_date)
            if to_date: sql+=" AND CAST(race_date AS VARCHAR)<=?"; params.append(to_date)
            sql+=" ORDER BY CAST(race_date AS VARCHAR) "+order.upper()+", CAST(race_key AS VARCHAR) "+order.upper()+", CAST(horse_no AS BIGINT) "+order.upper()
            if limit: sql+=" LIMIT ?"; params.append(limit)
            cur=con.execute(sql,params); columns=[d[0] for d in cur.description]; rows=[dict(zip(columns,row)) for row in cur.fetchall()]
        finally: con.close()
        provenance={"backend":"duckdb_parquet","generation_id":report["generation_id"],"manifest":str(report["manifest"]),"source":"fact_entry_result_lite"}
    rows=[_normalize(r) for r in rows]; _guard(rows)
    return {"schema_version":SCHEMA_VERSION,"horse_id":str(horse_id),"order":order,"source_provenance":provenance,"starts":rows}

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--horse-id",required=True); g=p.add_mutually_exclusive_group(required=True); g.add_argument("--analysis-root"); g.add_argument("--analysis-db"); p.add_argument("--from-date"); p.add_argument("--to-date"); p.add_argument("--limit",type=int); p.add_argument("--order",choices=("asc","desc"),default="asc"); p.add_argument("--output",required=True); p.add_argument("--pretty",action="store_true"); a=p.parse_args()
    result=query(horse_id=a.horse_id,analysis_root=a.analysis_root,analysis_db=a.analysis_db,from_date=a.from_date,to_date=a.to_date,limit=a.limit,order=a.order)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2 if a.pretty else None,separators=None if a.pretty else (",",":"))+"\n",encoding="utf-8"); return 0
if __name__=="__main__":raise SystemExit(main())
