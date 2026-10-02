#!/usr/bin/env python3
"""EdgeDB v0.4 Stage C2B exact metric evaluator for one request shard."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

NULL="__NULL__"
POLICY_VERSION="v04-stage-c2b-exact-r1"

@dataclass
class Node:
    children: dict[tuple[str,str],"Node"] = field(default_factory=dict)
    terminals: list[str] = field(default_factory=list)

class Sink:
    def __init__(self,path:Path,batch=10000):
        self.path=path; self.batch=batch; self.rows=[]; self.writer=None; self.count=0
    def add(self,row):
        self.rows.append(row); self.count+=1
        if len(self.rows)>=self.batch:self.flush()
    def flush(self):
        if not self.rows:return
        t=pa.Table.from_pylist(self.rows)
        if self.writer is None:self.writer=pq.ParquetWriter(self.path,t.schema,compression="zstd")
        self.writer.write_table(t); self.rows.clear()
    def close(self):
        self.flush()
        if self.writer:self.writer.close()

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def selected(mid:str,index:int,count:int)->bool:
    return int(mid[5:7],16)%count==index

def encode(arr):
    a=arr.combine_chunks()
    if not (pa.types.is_string(a.type) or pa.types.is_large_string(a.type)):
        a=pc.cast(a,pa.string())
    a=pc.fill_null(a,NULL)
    e=pc.dictionary_encode(a)
    vals=e.dictionary.to_pylist()
    return np.asarray(e.indices.to_numpy(zero_copy_only=False),dtype=np.int32),vals,{str(v):i for i,v in enumerate(vals)}

def numeric(arr,dtype):
    return np.asarray(pc.fill_null(arr.combine_chunks(),0).to_numpy(zero_copy_only=False),dtype=dtype)

def topk_sum(a,k):
    if len(a)==0:return 0.0
    if len(a)<=k:return float(a.sum())
    return float(np.partition(a,len(a)-k)[-k:].sum())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--feature-parquet",type=Path,required=True)
    ap.add_argument("--request-parquet",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--shard-index",type=int,required=True)
    ap.add_argument("--shard-count",type=int,required=True)
    ap.add_argument("--discovery-years",type=int,default=5)
    args=ap.parse_args()
    if not 0<=args.shard_index<args.shard_count:raise SystemExit("invalid shard")
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)

    requests=[]
    dims=set()
    pf=pq.ParquetFile(args.request_parquet)
    for batch in pf.iter_batches(batch_size=20000,columns=["metric_request_id","conditions_json","depth"]):
        for r in batch.to_pylist():
            if not selected(r["metric_request_id"],args.shard_index,args.shard_count):continue
            conds=json.loads(r["conditions_json"])
            requests.append((r["metric_request_id"],conds,int(r["depth"])))
            dims.update(c["feature"] for c in conds)
    if not requests:raise SystemExit("empty request shard")

    root=Node()
    for mid,conds,_ in requests:
        node=root
        for c in conds:
            key=(str(c["feature"]),str(c["value"]))
            node=node.children.setdefault(key,Node())
        node.terminals.append(mid)

    cols=sorted(dims)+["race_date","label_win_hit","label_place_hit","label_win_payout","label_place_payout"]
    alltab=pq.read_table(args.feature_parquet,columns=cols)
    dates_all=alltab["race_date"].combine_chunks()
    if not (pa.types.is_string(dates_all.type) or pa.types.is_large_string(dates_all.type)):
        dates_all=pc.cast(dates_all,pa.string())
    ds=np.asarray(pc.fill_null(dates_all,"0000-00-00").to_numpy(zero_copy_only=False),dtype=str)
    max_date=dt.date.fromisoformat(max(x for x in ds if x!="0000-00-00"))
    try:start=max_date.replace(year=max_date.year-args.discovery_years)
    except ValueError:start=max_date.replace(year=max_date.year-args.discovery_years,day=28)
    mask=pc.greater_equal(dates_all,pa.scalar(start.isoformat(),type=pa.string()))
    tab=alltab.filter(mask); n_rows=tab.num_rows

    codes={}; value_to_code={}
    for d in sorted(dims):
        codes[d],_,value_to_code[d]=encode(tab[d])
    wh=numeric(tab["label_win_hit"],np.int16); ph=numeric(tab["label_place_hit"],np.int16)
    wp=numeric(tab["label_win_payout"],np.float64); pp=numeric(tab["label_place_payout"],np.float64)
    dates=tab["race_date"].combine_chunks()
    if not (pa.types.is_string(dates.type) or pa.types.is_large_string(dates.type)):dates=pc.cast(dates,pa.string())
    date_np=np.asarray(pc.fill_null(dates,"0000-00-00").to_numpy(zero_copy_only=False),dtype=str)
    years=np.asarray([int(x[:4]) for x in date_np],dtype=np.int16)
    cuts={365:(max_date-dt.timedelta(days=365)).isoformat(),730:(max_date-dt.timedelta(days=730)).isoformat(),1095:(max_date-dt.timedelta(days=1095)).isoformat()}
    recent={k:date_np>=v for k,v in cuts.items()}

    sink=Sink(out/f"metric_results_shard_{args.shard_index:02d}.parquet")
    missing_value_branches=0

    def emit(mid,postings):
        n=len(postings)
        w=wp[postings]; p=pp[postings]
        wins=int(wh[postings].sum()); places=int(ph[postings].sum())
        wsum=float(w.sum()); psum=float(p.sum())
        top1w=float(w.max(initial=0)); top1p=float(p.max(initial=0))
        top3w=topk_sum(w,3); top3p=topk_sum(p,3)
        ys=years[postings]; uniq=np.unique(ys)
        wy=[]; py=[]
        for y in uniq:
            ym=ys==y; nn=int(ym.sum())
            wy.append(float(w[ym].sum())/nn if nn else 0.0)
            py.append(float(p[ym].sum())/nn if nn else 0.0)
        signature=hashlib.sha256(np.asarray(postings,dtype=np.int32).tobytes()).hexdigest()[:24]
        row={
          "metric_request_id":mid,"match_signature":signature,"n":n,"wins":wins,"places":places,
          "win_roi":wsum/n if n else None,"place_roi":psum/n if n else None,
          "win_return_sum":wsum,"place_return_sum":psum,
          "top1_win_payout":top1w,"top1_place_payout":top1p,
          "top3_win_payout_sum":top3w,"top3_place_payout_sum":top3p,
          "win_roi_ex_top1":(wsum-top1w)/n if n else None,
          "place_roi_ex_top1":(psum-top1p)/n if n else None,
          "win_roi_ex_top3":(wsum-top3w)/n if n else None,
          "place_roi_ex_top3":(psum-top3p)/n if n else None,
          "unique_race_days":len(np.unique(date_np[postings])),
          "unique_years":len(uniq),
          "win_hit_years":len(np.unique(years[postings][wh[postings]>0])) if wins else 0,
          "place_hit_years":len(np.unique(years[postings][ph[postings]>0])) if places else 0,
          "annual_win_roi_std":float(np.std(wy)) if wy else None,
          "annual_place_roi_std":float(np.std(py)) if py else None,
        }
        for days in (365,730,1095):
            m=recent[days][postings]; nn=int(m.sum())
            row[f"n_{days}"]=nn
            row[f"win_roi_{days}"]=float(w[m].sum())/nn if nn else None
            row[f"place_roi_{days}"]=float(p[m].sum())/nn if nn else None
        sink.add(row)

    allrows=np.arange(n_rows,dtype=np.int32)
    def walk(node,postings):
        nonlocal missing_value_branches
        for mid in node.terminals:emit(mid,postings)
        by_dim={}
        for (dim,val),child in node.children.items():
            by_dim.setdefault(dim,[]).append((val,child))
        for dim,items in by_dim.items():
            requested={}
            for val,child in items:
                code=value_to_code[dim].get(val)
                if code is None:
                    missing_value_branches+=1; continue
                requested[code]=child
            if not requested:continue
            sub=codes[dim][postings]
            order=np.argsort(sub,kind="stable"); ss=sub[order]
            if len(ss)==0:continue
            b=np.flatnonzero(np.diff(ss))+1
            starts=np.concatenate(([0],b)); ends=np.concatenate((b,[len(ss)]))
            for s,e in zip(starts,ends):
                code=int(ss[s])
                child=requested.get(code)
                if child is not None:
                    walk(child,postings[order[s:e]])
    walk(root,allrows); sink.close()

    if sink.count!=len(requests):
        raise SystemExit(f"metric result mismatch {sink.count} != {len(requests)}")
    audit={
      "status":"PASS","stage":"V04_STAGE_C2B_EXACT_SHARD","policy_version":POLICY_VERSION,
      "shard_index":args.shard_index,"shard_count":args.shard_count,
      "request_count":len(requests),"metric_result_count":sink.count,
      "feature_rows_all_history":alltab.num_rows,"feature_rows_discovery":n_rows,
      "discovery_start_date":start.isoformat(),"discovery_end_date":max_date.isoformat(),
      "missing_value_branches":missing_value_branches,
      "feature_parquet_sha256":sha256_file(args.feature_parquet),
      "request_parquet_sha256":sha256_file(args.request_parquet),
      "production_serving_changed":False,
    }
    (out/f"stage_c2b_shard_audit_{args.shard_index:02d}.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
