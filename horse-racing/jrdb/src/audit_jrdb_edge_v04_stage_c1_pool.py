#!/usr/bin/env python3
"""Audit the v0.4 Stage C1 research pool before parent-incrementality C2.

This is diagnostic only. It does not promote/reject candidates and does not change
production. It measures how much of the C1 pool survives cheap robustness/currentness
screens that are already present in the C1 artifact.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import duckdb

def rows(con, sql):
    cur=con.execute(sql)
    cols=[d[0] for d in cur.description]
    return [dict(zip(cols,r)) for r in cur.fetchall()]

def scalar(con, sql):
    return con.execute(sql).fetchone()[0]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--c1-parquet",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    p=str(args.c1_parquet.resolve()).replace("'","''")
    con=duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{p}')")

    total=scalar(con,"select count(*) from c")
    templates=scalar(con,"select count(distinct template_id) from c")
    sat=scalar(con,"select count(*) from (select template_id,count(*) n from c group by 1 having count(*)>=100)")
    exactly100=scalar(con,"select count(*) from (select template_id,count(*) n from c group by 1 having count(*)=100)")
    avg_per=scalar(con,"select avg(n) from (select template_id,count(*) n from c group by 1)")

    quant=rows(con,"""
      select
        quantile_cont(n,0.10) q10,
        quantile_cont(n,0.25) q25,
        quantile_cont(n,0.50) q50,
        quantile_cont(n,0.75) q75,
        quantile_cont(n,0.90) q90,
        quantile_cont(n,0.99) q99
      from c
    """)[0]

    template_quant=rows(con,"""
      select
        quantile_cont(n,0.10) q10,
        quantile_cont(n,0.25) q25,
        quantile_cont(n,0.50) q50,
        quantile_cont(n,0.75) q75,
        quantile_cont(n,0.90) q90,
        quantile_cont(n,0.99) q99
      from (select template_id,count(*) n from c group by 1)
    """)[0]

    by_depth_lane=rows(con,"""
      select depth,search_lane,count(*) candidates,count(distinct template_id) templates,
             avg(n) avg_support
      from c group by 1,2 order by 1,2
    """)

    scenario=rows(con,"""
      with x as (
        select *,
          (win_roi >= 110 and wins >= 2) as win_signal,
          (place_roi >= 105 and places >= 3) as place_signal,
          (
            (win_roi >= 110 and wins >= 2 and win_roi_ex_top1 >= 100 and coalesce(top1_win_contribution,1) < 0.70)
            or
            (place_roi >= 105 and places >= 3 and place_roi_ex_top1 >= 100 and coalesce(top1_place_contribution,1) < 0.70)
          ) as robust_top1,
          (
            (win_roi >= 110 and wins >= 2 and n_730 >= 5 and win_roi_730 >= 100)
            or
            (place_roi >= 105 and places >= 3 and n_730 >= 5 and place_roi_730 >= 100)
          ) as current2y_positive,
          (
            (win_roi >= 110 and wins >= 2 and n_730 >= 5 and win_roi_730 >= 110)
            or
            (place_roi >= 105 and places >= 3 and n_730 >= 5 and place_roi_730 >= 105)
          ) as current2y_strong,
          (
            (win_roi >= 110 and wins >= 2 and n_1095 >= 8 and win_roi_1095 >= 100)
            or
            (place_roi >= 105 and places >= 3 and n_1095 >= 8 and place_roi_1095 >= 100)
          ) as current3y_positive,
          (
            (win_roi >= 110 and wins >= 2 and n_365 >= 3 and win_roi_365 >= 100)
            or
            (place_roi >= 105 and places >= 3 and n_365 >= 3 and place_roi_365 >= 100)
          ) as current1y_positive
        from c
      )
      select
        count(*) total,
        count(*) filter(where robust_top1) robust_top1,
        count(*) filter(where current2y_positive) current2y_positive,
        count(*) filter(where current2y_strong) current2y_strong,
        count(*) filter(where current3y_positive) current3y_positive,
        count(*) filter(where current1y_positive) current1y_positive,
        count(*) filter(where robust_top1 and current2y_positive) robust_and_2y_positive,
        count(*) filter(where robust_top1 and current2y_strong) robust_and_2y_strong,
        count(*) filter(where robust_top1 and current2y_positive and current3y_positive) robust_2y_3y_positive,
        count(*) filter(where robust_top1 and current2y_positive and current1y_positive) robust_1y_2y_positive,
        count(*) filter(where robust_top1 and current2y_positive and current3y_positive and current1y_positive) robust_1y_2y_3y_positive,
        count(*) filter(where robust_top1 and n_730 >= 10 and current2y_positive) robust_2y_positive_n10,
        count(*) filter(where robust_top1 and n_730 >= 20 and current2y_positive) robust_2y_positive_n20
      from x
    """)[0]

    jackpot=rows(con,"""
      select
        count(*) filter(where coalesce(top1_win_contribution,0) >= .70) win_top1_70,
        count(*) filter(where coalesce(top1_place_contribution,0) >= .70) place_top1_70,
        count(*) filter(where coalesce(top1_win_contribution,0) >= .50) win_top1_50,
        count(*) filter(where coalesce(top1_place_contribution,0) >= .50) place_top1_50,
        count(*) filter(where win_roi_ex_top1 >= 100) win_ex_top1_ge100,
        count(*) filter(where place_roi_ex_top1 >= 100) place_ex_top1_ge100
      from c
    """)[0]

    recent_support=rows(con,"""
      select
        count(*) filter(where n_365>=1) n365_ge1,
        count(*) filter(where n_365>=3) n365_ge3,
        count(*) filter(where n_365>=5) n365_ge5,
        count(*) filter(where n_730>=5) n730_ge5,
        count(*) filter(where n_730>=10) n730_ge10,
        count(*) filter(where n_730>=20) n730_ge20,
        count(*) filter(where n_1095>=8) n1095_ge8,
        count(*) filter(where n_1095>=15) n1095_ge15,
        count(*) filter(where n_1095>=30) n1095_ge30
      from c
    """)[0]

    out={
      "status":"PASS",
      "stage":"V04_STAGE_C1_POOL_DIAGNOSTIC",
      "candidate_count":total,
      "distinct_template_count":templates,
      "avg_candidates_per_template":avg_per,
      "templates_at_or_above_100":sat,
      "templates_exactly_100":exactly100,
      "template_saturation_pct":round(100.0*exactly100/templates,4) if templates else 0,
      "support_n_quantiles":quant,
      "candidates_per_template_quantiles":template_quant,
      "by_depth_lane":by_depth_lane,
      "scenario_counts":scenario,
      "jackpot_and_ex_top1_counts":jackpot,
      "recent_support_counts":recent_support,
      "diagnostic_only":True,
      "production_serving_changed":False,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,sort_keys=True))
    con.close()

if __name__=="__main__":
    main()
