#!/usr/bin/env python3
"""Plan deterministic Stage C1 shards from the Stage B template catalog.

No outcomes, odds, popularity, payouts, or ROI are consulted. Assignment uses only
Stage B template metadata: search_lane, depth, template_id, estimated_group_upper_bound.
Each template belongs to exactly one shard.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import pyarrow.parquet as pq

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--template-parquet",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--max-templates-per-shard",type=int,default=900)
    ap.add_argument("--target-estimated-cost",type=int,default=250_000_000)
    ap.add_argument("--max-total-shards",type=int,default=180)
    args=ap.parse_args()

    rows=pq.read_table(args.template_parquet).to_pylist()
    groups={}
    for r in rows:
        key=(str(r["search_lane"]),int(r["depth"]))
        groups.setdefault(key,[]).append(r)

    shards=[]
    assignment={}
    for (lane,depth),items in sorted(groups.items()):
        items=sorted(items,key=lambda r:str(r["template_id"]))
        total_cost=sum(int(r.get("estimated_group_upper_bound") or 0) for r in items)
        by_count=math.ceil(len(items)/args.max_templates_per_shard)
        by_cost=math.ceil(total_cost/args.target_estimated_cost) if total_cost else 1
        shard_count=max(1,by_count,by_cost)
        # weighted LPT bin packing; deterministic tie-breaking by shard index.
        bins=[{"cost":0,"items":[]} for _ in range(shard_count)]
        weighted=sorted(
            items,
            key=lambda r:(-int(r.get("estimated_group_upper_bound") or 0),str(r["template_id"]))
        )
        for r in weighted:
            idx=min(range(shard_count),key=lambda i:(bins[i]["cost"],len(bins[i]["items"]),i))
            bins[idx]["items"].append(str(r["template_id"]))
            bins[idx]["cost"]+=int(r.get("estimated_group_upper_bound") or 0)
        for idx,b in enumerate(bins):
            tids=sorted(b["items"])
            shard_id=f"{lane.lower()}-d{depth}-s{idx:03d}"
            for tid in tids:
                if tid in assignment:
                    raise SystemExit(f"duplicate template assignment: {tid}")
                assignment[tid]=shard_id
            digest=hashlib.sha256("\n".join(tids).encode()).hexdigest()
            shards.append({
                "shard_id":shard_id,
                "search_lane":lane,
                "depth":depth,
                "shard_no":idx,
                "template_count":len(tids),
                "estimated_cost":b["cost"],
                "template_ids_sha256":digest,
                "template_ids":tids,
            })

    if len(assignment)!=len(rows):
        raise SystemExit(f"assignment mismatch {len(assignment)} != {len(rows)}")
    if len(shards)>args.max_total_shards:
        raise SystemExit(f"planned {len(shards)} shards exceeds cap {args.max_total_shards}")

    plan={
        "status":"PASS",
        "stage":"V04_STAGE_C1_SHARD_PLAN",
        "template_count":len(rows),
        "shard_count":len(shards),
        "max_templates_per_shard":args.max_templates_per_shard,
        "target_estimated_cost":args.target_estimated_cost,
        "partition_inputs":["search_lane","depth","template_id","estimated_group_upper_bound"],
        "uses_results":False,
        "uses_roi":False,
        "uses_odds_or_popularity":False,
        "one_template_one_shard":True,
        "shards":shards,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(plan,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    # compact matrix for Actions output
    matrix={"include":[{"shard_id":s["shard_id"]} for s in shards]}
    args.output.with_name("matrix.json").write_text(json.dumps(matrix,separators=(",",":"))+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in plan.items() if k!="shards"},ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
