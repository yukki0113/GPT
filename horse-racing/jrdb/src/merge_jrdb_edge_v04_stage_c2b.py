#!/usr/bin/env python3
"""Merge v0.4 Stage C2B exact metrics and enrich C2 shortlist with parent deltas."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import duckdb

def qpath(p:Path)->str:
    return str(p.resolve()).replace("'","''")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--shards-dir",type=Path,required=True)
    ap.add_argument("--c2a-dir",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--expected-shards",type=int,default=16)
    args=ap.parse_args()
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)

    audits=sorted(args.shards_dir.rglob("stage_c2b_shard_audit_*.json"))
    pqs=sorted(args.shards_dir.rglob("metric_results_shard_*.parquet"))
    if len(audits)!=args.expected_shards or len(pqs)!=args.expected_shards:
        raise SystemExit(f"shard count mismatch audits={len(audits)} parquet={len(pqs)} expected={args.expected_shards}")
    aud=[json.loads(p.read_text()) for p in audits]
    if any(a.get("status")!="PASS" for a in aud):raise SystemExit("non-PASS shard")
    for key in ["shard_count","feature_parquet_sha256","request_parquet_sha256","policy_version","discovery_start_date","discovery_end_date"]:
        vals={json.dumps(a.get(key),sort_keys=True) for a in aud}
        if len(vals)!=1:raise SystemExit(f"provenance mismatch {key}: {vals}")
    if {a["shard_index"] for a in aud}!=set(range(args.expected_shards)):
        raise SystemExit("shard index coverage mismatch")

    shortlist=list(args.c2a_dir.rglob("c2_shortlist_with_metric_id.parquet"))
    pmap=list(args.c2a_dir.rglob("child_parent_map_raw.parquet"))
    if len(shortlist)!=1 or len(pmap)!=1:
        raise SystemExit(f"C2A shape mismatch shortlist={len(shortlist)} parentmap={len(pmap)}")

    files=",".join("'"+qpath(p)+"'" for p in pqs)
    con=duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='6GB'")
    con.execute(f"CREATE VIEW m AS SELECT * FROM read_parquet([{files}])")
    con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{qpath(shortlist[0])}')")
    con.execute(f"CREATE VIEW pm AS SELECT * FROM read_parquet('{qpath(pmap[0])}')")

    metric_count=con.execute("select count(*) from m").fetchone()[0]
    unique_metric=con.execute("select count(distinct metric_request_id) from m").fetchone()[0]
    expected_metric=sum(int(a["metric_result_count"]) for a in aud)
    if metric_count!=unique_metric or metric_count!=expected_metric:
        raise SystemExit(f"metric uniqueness/count mismatch rows={metric_count} unique={unique_metric} expected={expected_metric}")

    con.execute("""
      CREATE TEMP VIEW parent_agg AS
      SELECT
        pm.child_candidate_id,
        count(*) AS parent_count,
        max(p.n) AS parent_max_n,
        min(p.n) AS parent_min_n,
        max(p.win_roi) AS parent_best_win_roi,
        max(p.place_roi) AS parent_best_place_roi,
        median(p.win_roi) AS parent_median_win_roi,
        median(p.place_roi) AS parent_median_place_roi,
        max(p.win_roi_ex_top3) AS parent_best_win_roi_ex_top3,
        max(p.place_roi_ex_top3) AS parent_best_place_roi_ex_top3
      FROM pm
      JOIN m p ON p.metric_request_id=pm.parent_metric_request_id
      GROUP BY 1
    """)
    con.execute("""
      CREATE TEMP VIEW same_parent_pop AS
      SELECT
        pm.child_candidate_id,
        max(CASE WHEN p.match_signature=c.match_signature THEN 1 ELSE 0 END)::BOOLEAN AS has_identical_immediate_parent
      FROM pm
      JOIN s ON s.candidate_id=pm.child_candidate_id
      JOIN m c ON c.metric_request_id=s.metric_request_id
      JOIN m p ON p.metric_request_id=pm.parent_metric_request_id
      GROUP BY 1
    """)

    enriched=out/"c2_enriched_candidates.parquet"
    con.execute(f"""
      COPY (
        WITH e AS (
          SELECT
            s.*,
            c.match_signature,
            c.n AS exact_n,
            c.wins AS exact_wins,
            c.places AS exact_places,
            c.win_roi AS exact_win_roi,
            c.place_roi AS exact_place_roi,
            c.win_roi_ex_top1 AS exact_win_roi_ex_top1,
            c.place_roi_ex_top1 AS exact_place_roi_ex_top1,
            c.win_roi_ex_top3,
            c.place_roi_ex_top3,
            c.top3_win_payout_sum,
            c.top3_place_payout_sum,
            c.unique_race_days,
            c.unique_years,
            c.win_hit_years,
            c.place_hit_years,
            c.annual_win_roi_std,
            c.annual_place_roi_std,
            c.n_365 AS exact_n_365,
            c.win_roi_365 AS exact_win_roi_365,
            c.place_roi_365 AS exact_place_roi_365,
            c.n_730 AS exact_n_730,
            c.win_roi_730 AS exact_win_roi_730,
            c.place_roi_730 AS exact_place_roi_730,
            c.n_1095 AS exact_n_1095,
            c.win_roi_1095 AS exact_win_roi_1095,
            c.place_roi_1095 AS exact_place_roi_1095,
            pa.parent_count,
            pa.parent_max_n,
            pa.parent_min_n,
            pa.parent_best_win_roi,
            pa.parent_best_place_roi,
            pa.parent_median_win_roi,
            pa.parent_median_place_roi,
            pa.parent_best_win_roi_ex_top3,
            pa.parent_best_place_roi_ex_top3,
            c.win_roi-pa.parent_best_win_roi AS win_delta_vs_best_parent,
            c.place_roi-pa.parent_best_place_roi AS place_delta_vs_best_parent,
            c.win_roi-pa.parent_median_win_roi AS win_delta_vs_median_parent,
            c.place_roi-pa.parent_median_place_roi AS place_delta_vs_median_parent,
            coalesce(sp.has_identical_immediate_parent,false) AS has_identical_immediate_parent,
            count(*) OVER (PARTITION BY c.match_signature) AS population_equivalence_group_size,
            (
              (s.win_roi>=110 AND s.wins>=2 AND c.win_roi_ex_top3>=100)
              OR
              (s.place_roi>=105 AND s.places>=3 AND c.place_roi_ex_top3>=100)
            ) AS robust_top3,
            (
              (s.win_roi>=110 AND s.wins>=2 AND c.win_hit_years>=2)
              OR
              (s.place_roi>=105 AND s.places>=3 AND c.place_hit_years>=2)
            ) AS multi_year_hit_support
          FROM s
          JOIN m c ON c.metric_request_id=s.metric_request_id
          JOIN parent_agg pa ON pa.child_candidate_id=s.candidate_id
          LEFT JOIN same_parent_pop sp ON sp.child_candidate_id=s.candidate_id
        )
        SELECT * FROM e
      ) TO '{qpath(enriched)}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    con.execute(f"CREATE VIEW e AS SELECT * FROM read_parquet('{qpath(enriched)}')")
    total=con.execute("select count(*) from e").fetchone()[0]
    scenario=con.execute("""
      SELECT
        count(*) AS total,
        count(*) FILTER(WHERE robust_top3) AS robust_top3,
        count(*) FILTER(WHERE has_identical_immediate_parent) AS identical_parent_population,
        count(*) FILTER(WHERE population_equivalence_group_size>1) AS any_population_equivalence,
        count(*) FILTER(WHERE multi_year_hit_support) AS multi_year_hit_support,
        count(*) FILTER(WHERE
          (win_roi>=110 AND wins>=2 AND win_delta_vs_best_parent>=0)
          OR (place_roi>=105 AND places>=3 AND place_delta_vs_best_parent>=0)
        ) AS incremental_ge0,
        count(*) FILTER(WHERE
          (win_roi>=110 AND wins>=2 AND win_delta_vs_best_parent>=5)
          OR (place_roi>=105 AND places>=3 AND place_delta_vs_best_parent>=5)
        ) AS incremental_ge5,
        count(*) FILTER(WHERE
          (win_roi>=110 AND wins>=2 AND win_delta_vs_best_parent>=10)
          OR (place_roi>=105 AND places>=3 AND place_delta_vs_best_parent>=10)
        ) AS incremental_ge10,
        count(*) FILTER(WHERE
          (win_roi>=110 AND wins>=2 AND win_delta_vs_best_parent>=20)
          OR (place_roi>=105 AND places>=3 AND place_delta_vs_best_parent>=20)
        ) AS incremental_ge20,
        count(*) FILTER(WHERE robust_top3 AND (
          (win_roi>=110 AND wins>=2 AND win_delta_vs_best_parent>=5)
          OR (place_roi>=105 AND places>=3 AND place_delta_vs_best_parent>=5)
        )) AS robust_top3_incremental_ge5,
        count(*) FILTER(WHERE robust_top3 AND (
          (win_roi>=110 AND wins>=2 AND win_delta_vs_best_parent>=10)
          OR (place_roi>=105 AND places>=3 AND place_delta_vs_best_parent>=10)
        )) AS robust_top3_incremental_ge10
      FROM e
    """).fetchone()
    names=[d[0] for d in con.description]
    scenario=dict(zip(names,scenario))

    by_route=[
      {"c2_entry_route":r[0],"count":r[1],"robust_top3":r[2],"incremental_ge5":r[3],"incremental_ge10":r[4]}
      for r in con.execute("""
        SELECT c2_entry_route,count(*),
          count(*) filter(where robust_top3),
          count(*) filter(where (win_roi>=110 and wins>=2 and win_delta_vs_best_parent>=5)
                             or (place_roi>=105 and places>=3 and place_delta_vs_best_parent>=5)),
          count(*) filter(where (win_roi>=110 and wins>=2 and win_delta_vs_best_parent>=10)
                             or (place_roi>=105 and places>=3 and place_delta_vs_best_parent>=10))
        FROM e GROUP BY 1 ORDER BY 1
      """).fetchall()
    ]

    audit={
      "status":"PASS","stage":"V04_STAGE_C2B_EXACT_PARENT_ENRICHMENT",
      "expected_shard_count":args.expected_shards,
      "metric_result_count":metric_count,
      "c2_enriched_candidate_count":total,
      "scenario_counts":scenario,
      "by_entry_route":by_route,
      "parent_incrementality_threshold":"DIAGNOSTIC_ONLY_NOT_YET_FROZEN",
      "population_equivalence_action":"FLAG_ONLY_NOT_DROPPED",
      "feature_parquet_sha256":aud[0]["feature_parquet_sha256"],
      "request_parquet_sha256":aud[0]["request_parquet_sha256"],
      "policy_version":aud[0]["policy_version"],
      "discovery_start_date":aud[0]["discovery_start_date"],
      "discovery_end_date":aud[0]["discovery_end_date"],
      "production_serving_changed":False,
    }
    (out/"stage_c2b_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,sort_keys=True))
    con.close()

if __name__=="__main__":main()
