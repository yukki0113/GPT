#!/usr/bin/env python3
"""Compare Raw-route and Warehouse-route downstream JRDB scientific outputs."""
from __future__ import annotations
import argparse, hashlib, json, math, sqlite3
from pathlib import Path
from typing import Any, Iterable

DB_TABLES = {
    "runperf": ("race_runperf_observation","race_expected_time","race_day_track_bias","runner_runperf_features"),
    "official": ("runperf_coefficient_snapshot","official_runperf"),
    "training": ("source_archive","training_runner"),
}
EXCLUDED_COLUMNS = {"runperf_coefficient_snapshot": {"created_at"}}
FINGERPRINT_FIELDS = (
    "core_version","training_period","training_eligible_n","training_semantic_sha256",
    "prediction_normalization_decimals","c_training_prediction_sha256","cab_training_prediction_sha256","runtime_packages",
)

def _norm(v: Any) -> Any:
    if isinstance(v, float):
        if not math.isfinite(v): raise ValueError('non-finite float')
        return {'__float__': v.hex()}
    if isinstance(v, bytes): return {'__bytes__': v.hex()}
    return v

def _table_hash(db: Path, table: str) -> dict[str, Any]:
    con=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
    try:
        info=con.execute(f'PRAGMA table_info({table})').fetchall()
        if not info: raise ValueError(f'missing table {table}: {db}')
        all_cols=[str(r[1]) for r in info]
        cols=[c for c in all_cols if c not in EXCLUDED_COLUMNS.get(table,set())]
        pk=sorted(((int(r[5]),str(r[1])) for r in info if int(r[5])>0))
        order=[name for _,name in pk] or cols
        qcols=','.join('"'+c.replace('"','""')+'"' for c in cols)
        qorder=','.join('"'+c.replace('"','""')+'"' for c in order)
        cur=con.execute(f'SELECT {qcols} FROM "{table}" ORDER BY {qorder}')
        h=hashlib.sha256(); n=0
        for row in cur:
            payload=json.dumps([_norm(v) for v in row],ensure_ascii=False,separators=(',',':'))
            h.update(payload.encode('utf-8')); h.update(b'\n'); n+=1
        return {'columns':cols,'order_by':order,'row_count':n,'sha256':h.hexdigest()}
    finally: con.close()

def _db_compare(kind: str, raw: Path, wh: Path) -> dict[str, Any]:
    tables={}
    passed=True
    for table in DB_TABLES[kind]:
        a=_table_hash(raw,table); b=_table_hash(wh,table)
        eq=a==b; passed=passed and eq
        tables[table]={'pass':eq,'raw':a,'warehouse':b}
    return {'pass':passed,'tables':tables}

def _load(path: Path) -> dict[str,Any]: return json.loads(path.read_text(encoding='utf-8'))

def _stage_compare(a: Path,b: Path)->dict[str,Any]:
    x=_load(a); y=_load(b)
    keys=('status','analysis_version','classification','population','quintiles','correlations_spearman','history_sensitivity','holdout_guard')
    diffs={k:{'raw':x.get(k),'warehouse':y.get(k)} for k in keys if x.get(k)!=y.get(k)}
    return {'pass':not diffs,'differences':diffs}

def _fingerprint_compare(a:Path,b:Path)->dict[str,Any]:
    x=_load(a); y=_load(b)
    diffs={k:{'raw':x.get(k),'warehouse':y.get(k)} for k in FINGERPRINT_FIELDS if x.get(k)!=y.get(k)}
    gx=x.get('guard') or {}; gy=y.get('guard') or {}
    if gx!=gy: diffs['guard']={'raw':gx,'warehouse':gy}
    return {'pass':not diffs,'differences':diffs,'warehouse':{k:y.get(k) for k in FINGERPRINT_FIELDS}}

def main()->int:
    p=argparse.ArgumentParser()
    for kind in ('runperf','official','training'):
        p.add_argument(f'--raw-{kind}',type=Path,required=True); p.add_argument(f'--warehouse-{kind}',type=Path,required=True)
    p.add_argument('--raw-stage1b',type=Path,required=True); p.add_argument('--warehouse-stage1b',type=Path,required=True)
    p.add_argument('--raw-fingerprint',type=Path,required=True); p.add_argument('--warehouse-fingerprint',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    report={'runperf':_db_compare('runperf',a.raw_runperf,a.warehouse_runperf),
            'official':_db_compare('official',a.raw_official,a.warehouse_official),
            'training':_db_compare('training',a.raw_training,a.warehouse_training),
            'stage1b':_stage_compare(a.raw_stage1b,a.warehouse_stage1b),
            'fingerprint':_fingerprint_compare(a.raw_fingerprint,a.warehouse_fingerprint)}
    report['status']='PASS' if all(v['pass'] for v in report.values() if isinstance(v,dict) and 'pass' in v) else 'FAIL'
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report['status']=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
