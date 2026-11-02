#!/usr/bin/env python3
"""EdgeDB v0.4 Stage C: trie-shared ROI / robustness screen.

Stage B supplies allowed dimension templates. Stage C instantiates their observed
values from the Feature Mart and evaluates Value without using odds/popularity to
define any population.

Implementation: all templates are compiled into one prefix trie. Shared prefixes
(e.g. sire -> venue -> surface) are partitioned once and reused by every descendant
template. This avoids both millions of support-only intermediate files and the
memory blow-up of large SQL GROUPING SETS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import heapq
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ALL_DIMS = [
    "venue_code","distance_m","surface_code","turn_code","inner_outer_code",
    "race_condition_code","grade_code","track_condition_bucket","frame_zone",
    "sex_code","horse_age","running_style_code","condition_class_code",
    "sire_name","sire_line_code","broodmare_sire_name","broodmare_sire_line_code",
    "prev1_venue_code","prev1_turn_code","distance_change_bucket",
    "surface_transition","frame_transition",
]
DIM_INDEX={d:i for i,d in enumerate(ALL_DIMS)}
NULL_SENTINEL="__NULL__"

@dataclass
class Node:
    children: dict[str,"Node"] = field(default_factory=dict)
    terminal: dict[str,Any] | None = None
    min_support: int = 10**9

def support_floor(depth:int,lane:str)->int:
    if lane=="TRANSITION_PRIORITY":
        return {2:12,3:10,4:8,5:7,6:6}[depth]
    if lane=="PEDIGREE_INTERACTION":
        return {2:18,3:16,4:14,5:12,6:10}[depth]
    return {2:24,3:22,4:20,5:18,6:16}[depth]

def candidate_id(template_id:str,conditions:list[dict[str,Any]])->str:
    payload=json.dumps({"template_id":template_id,"conditions":conditions},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return "v04c_"+hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

def encode(arr:pa.ChunkedArray)->tuple[np.ndarray,list[Any]]:
    a=arr.combine_chunks()
    if not (pa.types.is_string(a.type) or pa.types.is_large_string(a.type)):
        a=pc.cast(a,pa.string())
    a=pc.fill_null(a,NULL_SENTINEL)
    enc=pc.dictionary_encode(a)
    return np.asarray(enc.indices.to_numpy(zero_copy_only=False),dtype=np.int32),enc.dictionary.to_pylist()

def numeric(arr:pa.ChunkedArray,dtype)->np.ndarray:
    a=pc.fill_null(arr.combine_chunks(),0)
    return np.asarray(a.to_numpy(zero_copy_only=False),dtype=dtype)

def build_trie(templates:list[dict[str,Any]])->Node:
    root=Node()
    for t in templates:
        dims=json.loads(t["dimensions_json"])
        dims=sorted(dims,key=lambda d:DIM_INDEX[d])
        meta={
            "template_id":t["template_id"],
            "depth":int(t["depth"]),
            "lane":t["search_lane"],
            "family":t["family"],
            "dims":dims,
            "support_floor":support_floor(int(t["depth"]),t["search_lane"]),
        }
        node=root
        path=[root]
        for d in dims:
            node=node.children.setdefault(d,Node())
            path.append(node)
        if node.terminal is not None:
            raise RuntimeError(f"duplicate terminal dimensions: {dims}")
        node.terminal=meta
        for p in path:
            p.min_support=min(p.min_support,meta["support_floor"])
    return root

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--feature-parquet",type=Path,required=True)
    ap.add_argument("--template-parquet",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--min-win-roi",type=float,default=110.0)
    ap.add_argument("--min-place-roi",type=float,default=105.0)
    ap.add_argument("--max-per-template",type=int,default=100)
    args=ap.parse_args()

    feature=args.feature_parquet.resolve()
    template_path=args.template_parquet.resolve()
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    templates=pq.read_table(template_path).to_pylist()
    if not templates: raise SystemExit("empty template catalog")
    root=build_trie(templates)

    cols=[*ALL_DIMS,"race_date","label_win_hit","label_place_hit","label_win_payout","label_place_payout"]
    table=pq.read_table(feature,columns=cols)
    n_rows=table.num_rows
    codes={}; dictionaries={}
    for d in ALL_DIMS:
        codes[d],dictionaries[d]=encode(table[d])

    win_hit=numeric(table["label_win_hit"],np.int16)
    place_hit=numeric(table["label_place_hit"],np.int16)
    win_pay=numeric(table["label_win_payout"],np.float64)
    place_pay=numeric(table["label_place_payout"],np.float64)

    dates=table["race_date"].combine_chunks()
    if not (pa.types.is_string(dates.type) or pa.types.is_large_string(dates.type)):
        dates=pc.cast(dates,pa.string())
    date_np=np.asarray(pc.fill_null(dates,"0000-00-00").to_numpy(zero_copy_only=False),dtype=str)
    max_date_s=max(x for x in date_np if x!="0000-00-00")
    max_date=dt.date.fromisoformat(max_date_s)
    cut365=(max_date-dt.timedelta(days=365)).isoformat()
    cut730=(max_date-dt.timedelta(days=730)).isoformat()
    cut1095=(max_date-dt.timedelta(days=1095)).isoformat()
    recent365=date_np>=cut365
    recent730=date_np>=cut730
    recent1095=date_np>=cut1095

    # Only admitted candidates allocate heaps. Each heap is capped per template.
    heaps:dict[str,list[tuple[tuple[float,int,str],dict[str,Any]]]]={}
    terminal_groups_evaluated=0
    admitted_before_cap=0
    pruned_prefix_groups=0
    terminal_groups_by_depth={}
    admitted_by_depth={}
    admitted_by_lane={}
    jackpot_before_cap=0

    def evaluate(meta:dict[str,Any],postings:np.ndarray,conditions:list[dict[str,Any]]):
        nonlocal terminal_groups_evaluated,admitted_before_cap,jackpot_before_cap
        n=len(postings)
        if n<meta["support_floor"]: return
        terminal_groups_evaluated+=1
        terminal_groups_by_depth[str(meta["depth"])]=terminal_groups_by_depth.get(str(meta["depth"]),0)+1

        wh=win_hit[postings]; ph=place_hit[postings]
        wp=win_pay[postings]; pp=place_pay[postings]
        wins=int(wh.sum()); places=int(ph.sum())
        win_sum=float(wp.sum()); place_sum=float(pp.sum())
        win_roi=win_sum/n
        place_roi=place_sum/n
        if not ((wins>=2 and win_roi>=args.min_win_roi) or (places>=3 and place_roi>=args.min_place_roi)):
            return

        max_win=float(wp.max(initial=0.0)); max_place=float(pp.max(initial=0.0))
        top1_win=(max_win/win_sum) if win_sum>0 else None
        top1_place=(max_place/place_sum) if place_sum>0 else None
        idx365=recent365[postings]; idx730=recent730[postings]; idx1095=recent1095[postings]

        def period(mask,pays):
            nn=int(mask.sum())
            return nn,(float(pays[mask].sum())/nn if nn else None)

        n365,w365=period(idx365,wp); _,p365=period(idx365,pp)
        n730,w730=period(idx730,wp); _,p730=period(idx730,pp)
        n1095,w1095=period(idx1095,wp); _,p1095=period(idx1095,pp)

        jackpot=top1_win is not None and top1_win>=0.70
        if jackpot: jackpot_before_cap+=1
        row={
            "candidate_id":candidate_id(meta["template_id"],conditions),
            "template_id":meta["template_id"],
            "depth":meta["depth"],
            "family":meta["family"],
            "search_lane":meta["lane"],
            "conditions_json":json.dumps(conditions,ensure_ascii=False,separators=(",",":"),sort_keys=True),
            "n":n,"wins":wins,"places":places,
            "win_roi":round(win_roi,4),"place_roi":round(place_roi,4),
            "win_return_sum":win_sum,"place_return_sum":place_sum,
            "max_win_payout":max_win,"max_place_payout":max_place,
            "top1_win_contribution":round(top1_win,6) if top1_win is not None else None,
            "top1_place_contribution":round(top1_place,6) if top1_place is not None else None,
            "win_roi_ex_top1":round((win_sum-max_win)/n,4),
            "place_roi_ex_top1":round((place_sum-max_place)/n,4),
            "n_365":n365,"win_roi_365":round(w365,4) if w365 is not None else None,"place_roi_365":round(p365,4) if p365 is not None else None,
            "n_730":n730,"win_roi_730":round(w730,4) if w730 is not None else None,"place_roi_730":round(p730,4) if p730 is not None else None,
            "n_1095":n1095,"win_roi_1095":round(w1095,4) if w1095 is not None else None,"place_roi_1095":round(p1095,4) if p1095 is not None else None,
            "jackpot_dependent_top1_70pct":jackpot,
            "support_floor":meta["support_floor"],
        }
        admitted_before_cap+=1
        score=max(win_roi,place_roi)
        key=(score,n,row["candidate_id"])
        h=heaps.setdefault(meta["template_id"],[])
        item=(key,row)
        if len(h)<args.max_per_template:
            heapq.heappush(h,item)
        elif key>h[0][0]:
            heapq.heapreplace(h,item)

    all_rows=np.arange(n_rows,dtype=np.int32)

    def walk(node:Node,postings:np.ndarray,conditions:list[dict[str,Any]]):
        nonlocal pruned_prefix_groups
        if len(postings)<node.min_support:
            pruned_prefix_groups+=1; return
        if node.terminal is not None:
            evaluate(node.terminal,postings,conditions)
        for dim,child in node.children.items():
            if len(postings)<child.min_support:
                pruned_prefix_groups+=1; continue
            subcodes=codes[dim][postings]
            order=np.argsort(subcodes,kind="stable")
            sorted_codes=subcodes[order]
            if len(sorted_codes)==0: continue
            boundaries=np.flatnonzero(np.diff(sorted_codes))+1
            starts=np.concatenate(([0],boundaries)); ends=np.concatenate((boundaries,[len(sorted_codes)]))
            for start,end in zip(starts,ends):
                if int(end-start)<child.min_support:
                    pruned_prefix_groups+=1; continue
                code=int(sorted_codes[start])
                value=dictionaries[dim][code]
                if value==NULL_SENTINEL: continue
                child_postings=postings[order[start:end]]
                walk(child,child_postings,conditions+[{"feature":dim,"value":str(value)}])

    walk(root,all_rows,[])

    rows=[]
    jackpot_kept=0
    for tpl,h in heaps.items():
        selected=[item[1] for item in sorted(h,key=lambda x:x[0],reverse=True)]
        for rank,row in enumerate(selected,1):
            row["template_rank"]=rank
            rows.append(row)
            d=str(row["depth"]); lane=row["search_lane"]
            admitted_by_depth[d]=admitted_by_depth.get(d,0)+1
            admitted_by_lane[lane]=admitted_by_lane.get(lane,0)+1
            if row["jackpot_dependent_top1_70pct"]: jackpot_kept+=1

    rows.sort(key=lambda r:(r["depth"],r["template_id"],r["template_rank"]))
    if rows:
        pq.write_table(pa.Table.from_pylist(rows),out/"research_candidates.parquet",compression="zstd")
    else:
        pq.write_table(pa.table({"candidate_id":pa.array([],type=pa.string())}),out/"research_candidates.parquet",compression="zstd")

    audit={
        "status":"PASS",
        "stage":"V04_STAGE_C_ROI_ROBUSTNESS_SCREEN",
        "architecture":"PREFIX_TRIE_SHARED_VALUE_INSTANTIATION",
        "source_rows":n_rows,
        "template_count":len(templates),
        "terminal_groups_evaluated":terminal_groups_evaluated,
        "terminal_groups_evaluated_by_depth":terminal_groups_by_depth,
        "prefix_groups_pruned_by_support":pruned_prefix_groups,
        "admitted_before_template_cap":admitted_before_cap,
        "research_candidate_count":len(rows),
        "research_candidate_count_by_depth":admitted_by_depth,
        "research_candidate_count_by_lane":admitted_by_lane,
        "max_per_template":args.max_per_template,
        "admission_min_win_roi":args.min_win_roi,
        "admission_min_place_roi":args.min_place_roi,
        "support_floor_policy":{
            "TRANSITION_PRIORITY":{"2":12,"3":10,"4":8,"5":7,"6":6},
            "PEDIGREE_INTERACTION":{"2":18,"3":16,"4":14,"5":12,"6":10},
            "PEDIGREE_BASELINE":{"2":24,"3":22,"4":20,"5":18,"6":16},
        },
        "support_floor_role":"STAGE_C_RESEARCH_POOL_ADMISSION_NOT_FINAL_VALIDATION",
        "max_source_date":max_date.isoformat(),
        "recent_cutoffs":{"365d":cut365,"730d":cut730,"1095d":cut1095},
        "jackpot_flagged_before_cap":jackpot_before_cap,
        "jackpot_flagged_kept":jackpot_kept,
        "market_or_popularity_used_to_define_population":False,
        "odds_or_popularity_band_filter_used":False,
        "result_labels_used_for_evaluation_only":True,
        "parent_incrementality_status":"DEFERRED_TO_STAGE_C2_SHORTLIST_PARENT_EVAL",
        "top3_exclusion_status":"DEFERRED_TO_STAGE_C2_SHORTLIST_ROBUSTNESS",
        "production_serving_changed":False,
    }
    (out/"stage_c_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
