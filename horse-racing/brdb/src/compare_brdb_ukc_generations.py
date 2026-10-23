#!/usr/bin/env python3
"""Compare isolated candidate generation against pinned CURRENT without cutover."""
from __future__ import annotations
import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path

from brdb_ancestor_graph import ancestor_graph


def gather(root: Path, *, cohort_year="2025"):
    import duckdb
    con=duckdb.connect(":memory:")
    try:
        profiles=con.execute("SELECT horse_id FROM read_parquet(?) WHERE substr(profile_data_date,1,4)=? ORDER BY horse_id",[str(root/"pedigree_fact.parquet"),cohort_year]).fetchall()
        rows=con.execute("SELECT child_horse_id,role,resolved_parent_horse_id,resolution_status FROM read_parquet(?)",[str(root/"parent_relation.parquet")]).fetchall()
        n=con.execute("SELECT count(*) FROM read_parquet(?)",[str(root/"pedigree_fact.parquet")]).fetchone()[0]
    finally: con.close()
    relations={}
    status=Counter()
    for child,role,parent,st in rows:
        status[(str(role),str(st))]+=1
        if role in ("sire","dam"):
            relations.setdefault(str(child),[]).append({"role":role,"resolved_parent_horse_id":parent,"resolution_status":st})
    ids=[str(x[0]) for x in profiles]
    depth_out={}
    for depth in (2,3,4,5):
        resolved=0; full=0; cross=0; historical=Counter()
        for horse in ids:
            g=ancestor_graph(horse,lambda h:relations.get(h,[]),max_depth=depth)
            resolved+=g["resolved_paths"]
            full+=g["coverage"]=="FULL"
            counts=Counter(str(x["horse_id"]) for x in g["paths"] if x["horse_id"])
            cross+=any(v>=2 for v in counts.values())
            historical[g["resolved_paths"]]+=1
        depth_out[str(depth)]={"horses":len(ids),"fully_resolved":full,"observed_cross_horses":cross,"resolved_ancestor_paths_total":resolved,"resolved_path_histogram":dict(sorted(historical.items()))}
    return {"horse_count":n,"cohort_year":cohort_year,"cohort_horses":len(ids),"relations":{f"{r}:{status}":n for (r,status),n in sorted(status.items())},"depths":depth_out}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate-root",type=Path,required=True)
    p.add_argument("--baseline-current-zip",type=Path,required=True)
    p.add_argument("--output-json",type=Path,required=True)
    args=p.parse_args()
    roots=list(args.candidate_root.glob("brdb-pedigree-generation-*"))
    if len(roots)!=1: raise ValueError(f"expected one candidate generation, got {len(roots)}")
    candidate=roots[0]
    from brdb_current import _safe_extract
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        baseline=_safe_extract(args.baseline_current_zip,Path(t))
        old=gather(baseline);new=gather(candidate)
    result={"baseline":{"generation":"eeca93556584a5b8",**old},"candidate":{"generation":candidate.name,**new},"delta":{"master_horses":new["horse_count"]-old["horse_count"],"cohort_horses":new["cohort_horses"]-old["cohort_horses"],"depths":{d:{"fully_resolved":new["depths"][d]["fully_resolved"]-old["depths"][d]["fully_resolved"],"observed_cross_horses":new["depths"][d]["observed_cross_horses"]-old["depths"][d]["observed_cross_horses"],"resolved_paths":new["depths"][d]["resolved_ancestor_paths_total"]-old["depths"][d]["resolved_ancestor_paths_total"]} for d in ("2","3","4","5")}},"production_cutover":False}
    args.output_json.parent.mkdir(parents=True,exist_ok=True)
    args.output_json.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"baseline_horses":old["horse_count"],"candidate_horses":new["horse_count"],"depth_delta":result["delta"]["depths"]},ensure_ascii=False))


if __name__=="__main__":main()
