#!/usr/bin/env python3
"""EdgeDB v0.4 Stage C1 shard evaluator.

Evaluates exactly one deterministic template shard. Candidate populations are
defined only by Stage B pre-race dimensions/values. Outcomes/payouts are used
only after population definition for ROI screening. Odds/popularity are unused.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, heapq, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from jrdb_edge_v04_preflight import resolve_date_window

ALL_DIMS=[
"venue_code","distance_m","surface_code","turn_code","inner_outer_code",
"race_condition_code","grade_code","track_condition_bucket","frame_zone",
"sex_code","horse_age","running_style_code","condition_class_code",
"sire_name","sire_line_code","broodmare_sire_name","broodmare_sire_line_code",
"prev1_venue_code","prev1_turn_code","distance_change_bucket",
"surface_transition","frame_transition",
]
DIM_INDEX={d:i for i,d in enumerate(ALL_DIMS)}
NULL_SENTINEL="__NULL__"
POLICY_VERSION="v04-stage-c1-sharded-r1"

@dataclass
class Node:
    children:dict[str,"Node"]=field(default_factory=dict)
    terminal:dict[str,Any]|None=None
    min_support:int=10**9

class Sink:
    def __init__(self,path:Path,batch_size:int=10000):
        self.path=path; self.batch_size=batch_size; self.rows=[]; self.writer=None; self.count=0
    def add(self,row):
        self.rows.append(row); self.count+=1
        if len(self.rows)>=self.batch_size:self.flush()
    def flush(self):
        if not self.rows:return
        t=pa.Table.from_pylist(self.rows)
        if self.writer is None:self.writer=pq.ParquetWriter(self.path,t.schema,compression="zstd")
        self.writer.write_table(t); self.rows.clear()
    def close(self):
        self.flush()
        if self.writer:self.writer.close()
        if self.writer is None:
            pq.write_table(pa.table({"candidate_id":pa.array([],type=pa.string())}),self.path,compression="zstd")

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def support_floor(depth:int,lane:str)->int:
    if lane=="TRANSITION_PRIORITY":return {2:12,3:10,4:8,5:7,6:6}[depth]
    if lane=="PEDIGREE_INTERACTION":return {2:18,3:16,4:14,5:12,6:10}[depth]
    return {2:24,3:22,4:20,5:18,6:16}[depth]

def candidate_id(template_id:str,conditions:list[dict[str,Any]])->str:
    payload=json.dumps({"template_id":template_id,"conditions":conditions},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return "v04c_"+hashlib.sha256(payload.encode()).hexdigest()[:24]

def encode(arr):
    a=arr.combine_chunks()
    if not (pa.types.is_string(a.type) or pa.types.is_large_string(a.type)):a=pc.cast(a,pa.string())
    a=pc.fill_null(a,NULL_SENTINEL); enc=pc.dictionary_encode(a)
    return np.asarray(enc.indices.to_numpy(zero_copy_only=False),dtype=np.int32),enc.dictionary.to_pylist()

def numeric(arr,dtype):
    return np.asarray(pc.fill_null(arr.combine_chunks(),0).to_numpy(zero_copy_only=False),dtype=dtype)

def build_trie(templates):
    root=Node()
    for t in templates:
        dims=sorted(json.loads(t["dimensions_json"]),key=lambda d:DIM_INDEX[d])
        meta={"template_id":t["template_id"],"depth":int(t["depth"]),"lane":t["search_lane"],"family":t["family"],"dims":dims,"support_floor":support_floor(int(t["depth"]),t["search_lane"])}
        node=root; path=[root]
        for d in dims:
            node=node.children.setdefault(d,Node()); path.append(node)
        if node.terminal is not None:raise RuntimeError(f"duplicate template dims {dims}")
        node.terminal=meta
        for p in path:p.min_support=min(p.min_support,meta["support_floor"])
    return root

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--feature-parquet",type=Path,required=True)
    ap.add_argument("--template-parquet",type=Path,required=True)
    ap.add_argument("--shard-plan",type=Path,required=True)
    ap.add_argument("--shard-id",required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--min-win-roi",type=float,default=110.0)
    ap.add_argument("--min-place-roi",type=float,default=105.0)
    ap.add_argument("--max-per-template",type=int,default=100)
    ap.add_argument("--discovery-years",type=int,default=5)
    ap.add_argument("--as-of-date",help="inclusive YYYY-MM-DD research endpoint; defaults to max source race_date")
    args=ap.parse_args()
    if args.discovery_years<=0:raise SystemExit("discovery-years must be a positive integer")
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    plan=json.loads(args.shard_plan.read_text())
    shard=next((s for s in plan["shards"] if s["shard_id"]==args.shard_id),None)
    if not shard:raise SystemExit(f"unknown shard_id {args.shard_id}")
    tids=set(shard["template_ids"])
    all_templates=pq.read_table(args.template_parquet).to_pylist()
    templates=[t for t in all_templates if t["template_id"] in tids]
    if len(templates)!=len(tids):raise SystemExit(f"template shard mismatch {len(templates)} != {len(tids)}")
    if any(t["search_lane"]!=shard["search_lane"] or int(t["depth"])!=int(shard["depth"]) for t in templates):
        raise SystemExit("shard lane/depth mismatch")
    root=build_trie(templates)

    cols=[*ALL_DIMS,"race_date","label_win_hit","label_place_hit","label_win_payout","label_place_payout"]
    table_all=pq.read_table(args.feature_parquet,columns=cols)
    source_rows_all=table_all.num_rows
    dates_all=table_all["race_date"].combine_chunks()
    if not (pa.types.is_string(dates_all.type) or pa.types.is_large_string(dates_all.type)):
        dates_all=pc.cast(dates_all,pa.string())
    try:
        as_of_date,discovery_start,max_source_date=resolve_date_window(
            pc.unique(dates_all).to_pylist(),args.discovery_years,args.as_of_date
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    discovery_start_s=discovery_start.isoformat()
    lower=pc.greater_equal(dates_all,pa.scalar(discovery_start_s,type=pa.string()))
    upper=pc.less_equal(dates_all,pa.scalar(as_of_date.isoformat(),type=pa.string()))
    keep_mask=pc.fill_null(pc.and_(lower,upper),False)
    table=table_all.filter(keep_mask)
    n_rows=table.num_rows
    codes={}; dictionaries={}
    for d in ALL_DIMS:codes[d],dictionaries[d]=encode(table[d])
    win_hit=numeric(table["label_win_hit"],np.int16); place_hit=numeric(table["label_place_hit"],np.int16)
    win_pay=numeric(table["label_win_payout"],np.float64); place_pay=numeric(table["label_place_payout"],np.float64)
    dates=table["race_date"].combine_chunks()
    if not (pa.types.is_string(dates.type) or pa.types.is_large_string(dates.type)):dates=pc.cast(dates,pa.string())
    date_np=np.asarray(pc.fill_null(dates,"0000-00-00").to_numpy(zero_copy_only=False),dtype=str)
    cuts={365:(as_of_date-dt.timedelta(days=365)).isoformat(),730:(as_of_date-dt.timedelta(days=730)).isoformat(),1095:(as_of_date-dt.timedelta(days=1095)).isoformat()}
    recent={k:date_np>=v for k,v in cuts.items()}

    heaps={}
    terminal_groups=0; pruned=0; jackpot=0; admitted_before_cap=0
    def evaluate(meta,postings,conditions):
        nonlocal terminal_groups,jackpot,admitted_before_cap
        n=len(postings)
        if n<meta["support_floor"]:return
        terminal_groups+=1
        wh=win_hit[postings]; ph=place_hit[postings]; wp=win_pay[postings]; pp=place_pay[postings]
        wins=int(wh.sum()); places=int(ph.sum()); wsum=float(wp.sum()); psum=float(pp.sum())
        wroi=wsum/n; proi=psum/n
        if not ((wins>=2 and wroi>=args.min_win_roi) or (places>=3 and proi>=args.min_place_roi)):return
        maxw=float(wp.max(initial=0)); maxp=float(pp.max(initial=0))
        topw=maxw/wsum if wsum>0 else None; topp=maxp/psum if psum>0 else None
        if topw is not None and topw>=.70:jackpot+=1
        row={
            "candidate_id":candidate_id(meta["template_id"],conditions),"template_id":meta["template_id"],
            "depth":meta["depth"],"family":meta["family"],"search_lane":meta["lane"],
            "conditions_json":json.dumps(conditions,ensure_ascii=False,separators=(",",":"),sort_keys=True),
            "n":n,"wins":wins,"places":places,"win_roi":round(wroi,4),"place_roi":round(proi,4),
            "win_return_sum":wsum,"place_return_sum":psum,"max_win_payout":maxw,"max_place_payout":maxp,
            "top1_win_contribution":round(topw,6) if topw is not None else None,
            "top1_place_contribution":round(topp,6) if topp is not None else None,
            "win_roi_ex_top1":round((wsum-maxw)/n,4),"place_roi_ex_top1":round((psum-maxp)/n,4),
            "jackpot_dependent_top1_70pct":bool(topw is not None and topw>=.70),"support_floor":meta["support_floor"],
            "shard_id":args.shard_id,
        }
        for days in (365,730,1095):
            m=recent[days][postings]; nn=int(m.sum())
            row[f"n_{days}"]=nn
            row[f"win_roi_{days}"]=round(float(wp[m].sum())/nn,4) if nn else None
            row[f"place_roi_{days}"]=round(float(pp[m].sum())/nn,4) if nn else None
        admitted_before_cap+=1
        score=max(float(row["win_roi"]),float(row["place_roi"]))
        key=(score,int(row["n"]),row["candidate_id"])
        h=heaps.setdefault(meta["template_id"],[])
        item=(key,row)
        if len(h)<args.max_per_template:
            heapq.heappush(h,item)
        elif key>h[0][0]:
            heapq.heapreplace(h,item)

    all_rows=np.arange(n_rows,dtype=np.int32)
    def walk(node,postings,conditions):
        nonlocal pruned
        if len(postings)<node.min_support:pruned+=1; return
        if node.terminal:evaluate(node.terminal,postings,conditions)
        for dim,child in node.children.items():
            if len(postings)<child.min_support:pruned+=1; continue
            vals=codes[dim][postings]; order=np.argsort(vals,kind="stable"); sv=vals[order]
            if len(sv)==0:continue
            b=np.flatnonzero(np.diff(sv))+1; starts=np.concatenate(([0],b)); ends=np.concatenate((b,[len(sv)]))
            for s,e in zip(starts,ends):
                if e-s<child.min_support:pruned+=1; continue
                code=int(sv[s]); value=dictionaries[dim][code]
                if value==NULL_SENTINEL:continue
                walk(child,postings[order[s:e]],conditions+[{"feature":dim,"value":str(value)}])
    walk(root,all_rows,[])
    sink=Sink(out/f"research_candidates_shard_{args.shard_id}.parquet")
    for tid,h in heaps.items():
        selected=[x[1] for x in sorted(h,key=lambda x:x[0],reverse=True)]
        for rank,row in enumerate(selected,1):
            row["template_rank"]=rank
            sink.add(row)
    sink.close()

    audit={
      "status":"PASS","stage":"V04_STAGE_C1_SHARD","policy_version":POLICY_VERSION,
      "shard_id":args.shard_id,"search_lane":shard["search_lane"],"depth":int(shard["depth"]),
      "template_count":len(templates),"source_rows_all_history":source_rows_all,"source_rows":n_rows,
      "discovery_years":args.discovery_years,"requested_as_of_date":args.as_of_date,
      "resolved_as_of_date":as_of_date.isoformat(),"discovery_start_date":discovery_start_s,"discovery_end_date":as_of_date.isoformat(),
      "terminal_groups_evaluated":terminal_groups,
      "prefix_groups_pruned_by_support":pruned,"admitted_before_template_cap":admitted_before_cap,
      "research_candidate_count":sink.count,"max_per_template":args.max_per_template,
      "jackpot_flagged_top1_70pct_count":jackpot,"admission_min_win_roi":args.min_win_roi,
      "admission_min_place_roi":args.min_place_roi,"max_source_date":max_source_date.isoformat(),
      "recent_cutoffs":{f"{k}d":v for k,v in cuts.items()},
      "feature_parquet_sha256":sha256_file(args.feature_parquet),
      "template_catalog_sha256":sha256_file(args.template_parquet),
      "shard_plan_sha256":sha256_file(args.shard_plan),
      "template_ids_sha256":shard["template_ids_sha256"],
      "market_or_popularity_used_to_define_population":False,"odds_or_popularity_band_filter_used":False,
      "result_labels_used_for_evaluation_only":True,"template_cap_applied":True,
      "template_cap_is_globally_equivalent":True,
      "production_serving_changed":False,
    }
    (out/f"stage_c_shard_audit_{args.shard_id}.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":main()
