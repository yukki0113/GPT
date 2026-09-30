#!/usr/bin/env python3
"""Merge EdgeDB v0.4 Stage C1 shard outputs deterministically."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shard-plan",type=Path,required=True)
    ap.add_argument("--shards-dir",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--max-per-template",type=int,default=100)
    args=ap.parse_args()
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    plan=json.loads(args.shard_plan.read_text())
    expected={s["shard_id"]:s for s in plan["shards"]}
    audits=[]
    tables=[]
    for sid in sorted(expected):
        aps=list(args.shards_dir.rglob(f"stage_c_shard_audit_{sid}.json"))
        pps=list(args.shards_dir.rglob(f"research_candidates_shard_{sid}.parquet"))
        if len(aps)!=1 or len(pps)!=1:
            raise SystemExit(f"missing/duplicate shard files for {sid}: audits={len(aps)} parquet={len(pps)}")
        a=json.loads(aps[0].read_text())
        if a.get("status")!="PASS" or a.get("shard_id")!=sid:raise SystemExit(f"invalid shard audit {sid}")
        if a.get("template_ids_sha256")!=expected[sid]["template_ids_sha256"]:raise SystemExit(f"template digest mismatch {sid}")
        audits.append(a); tables.append(pq.read_table(pps[0]))

    keys=["feature_parquet_sha256","template_catalog_sha256","shard_plan_sha256","policy_version","admission_min_win_roi","admission_min_place_roi"]
    for k in keys:
        vals={json.dumps(a.get(k),sort_keys=True) for a in audits}
        if len(vals)!=1:raise SystemExit(f"provenance mismatch {k}: {vals}")

    merged=pa.concat_tables(tables,promote_options="default") if tables else pa.table({"candidate_id":[]})
    raw_count=merged.num_rows
    if raw_count:
        ids=merged["candidate_id"]
        if pc.count_distinct(ids).as_py()!=raw_count:raise SystemExit("duplicate candidate_id across shards")
        # Global template cap after merge.
        rows=merged.to_pylist()
        rows.sort(key=lambda r:(r["template_id"],-max(float(r["win_roi"]),float(r["place_roi"])),-int(r["n"]),r["candidate_id"]))
        kept=[]; counts={}
        for r in rows:
            tid=r["template_id"]; n=counts.get(tid,0)
            if n>=args.max_per_template:continue
            counts[tid]=n+1; r["template_rank"]=n+1; kept.append(r)
        merged=pa.Table.from_pylist(kept)
    pq.write_table(merged,out/"research_candidates.parquet",compression="zstd")

    inventory=[{
      "shard_id":a["shard_id"],"search_lane":a["search_lane"],"depth":a["depth"],
      "template_count":a["template_count"],"research_candidate_count":a["research_candidate_count"],
      "terminal_groups_evaluated":a["terminal_groups_evaluated"]
    } for a in sorted(audits,key=lambda x:x["shard_id"])]
    (out/"shard_inventory.json").write_text(json.dumps(inventory,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    manifest={
      "status":"PASS","stage":"V04_STAGE_C1_MERGE","expected_shard_count":len(expected),
      "received_pass_shard_count":len(audits),"raw_candidate_count_before_template_cap":raw_count,
      "research_candidate_count":merged.num_rows,"max_per_template":args.max_per_template,
      "feature_parquet_sha256":audits[0]["feature_parquet_sha256"] if audits else None,
      "template_catalog_sha256":audits[0]["template_catalog_sha256"] if audits else None,
      "shard_plan_sha256":audits[0]["shard_plan_sha256"] if audits else None,
      "policy_version":audits[0]["policy_version"] if audits else None,
      "market_or_popularity_used_to_define_population":False,
      "odds_or_popularity_band_filter_used":False,"production_serving_changed":False,
    }
    (out/"stage_c_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    (out/"stage_c_audit.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print(json.dumps(manifest,ensure_ascii=False,sort_keys=True))
if __name__=="__main__":main()
