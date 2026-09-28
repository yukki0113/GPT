#!/usr/bin/env python3
"""EdgeDB v0.4 Stage C: grouped ROI / robustness evaluator.

Consumes:
- accepted Feature Mart Parquet
- canonical Stage B search-template catalog

Stage C is the first layer allowed to use payout/hit labels. Popularity and odds are
still NOT used to define candidate populations. Candidate populations are defined
only by Stage B pre-race template dimensions and their observed values.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

ALL_DIMS = [
    "venue_code","distance_m","surface_code","turn_code","inner_outer_code",
    "race_condition_code","grade_code","track_condition_bucket","frame_zone",
    "sex_code","horse_age","running_style_code","condition_class_code",
    "sire_name","sire_line_code","broodmare_sire_name","broodmare_sire_line_code",
    "prev1_venue_code","prev1_turn_code","distance_change_bucket",
    "surface_transition","frame_transition",
]

LABEL_FIELDS = [
    "label_win_hit","label_place_hit","label_win_payout","label_place_payout",
]

def q(s: str) -> str:
    return '"' + s.replace('"','""') + '"'

def gid_for(dims: list[str]) -> int:
    selected=set(dims)
    n=len(ALL_DIMS)
    gid=0
    for i,d in enumerate(ALL_DIMS):
        if d not in selected:
            gid |= 1 << (n-1-i)
    return gid

def instantiated_id(template_id: str, conditions: list[dict[str, Any]]) -> str:
    payload=json.dumps(
        {"template_id":template_id,"conditions":conditions},
        ensure_ascii=False,sort_keys=True,separators=(",",":")
    )
    return "v04c_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

def support_floor(depth: int, lane: str) -> int:
    # Stage C research-pool floor. This is deliberately permissive for transition
    # and pedigree-interaction lanes; Stage D owns chronological validation.
    if lane == "TRANSITION_PRIORITY":
        return {2:12,3:10,4:8,5:7,6:6}[depth]
    if lane == "PEDIGREE_INTERACTION":
        return {2:18,3:16,4:14,5:12,6:10}[depth]
    return {2:24,3:22,4:20,5:18,6:16}[depth]

def min_win_hits(depth: int) -> int:
    return 2 if depth <= 4 else 2

def min_place_hits(depth: int) -> int:
    return 4 if depth <= 4 else 3

class Sink:
    def __init__(self,path:Path,batch_size:int=10000):
        self.path=path
        self.batch_size=batch_size
        self.rows=[]
        self.writer=None
        self.count=0
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

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--feature-parquet",type=Path,required=True)
    ap.add_argument("--template-parquet",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    ap.add_argument("--template-batch-size",type=int,default=250)
    ap.add_argument("--min-win-roi",type=float,default=110.0)
    ap.add_argument("--min-place-roi",type=float,default=105.0)
    ap.add_argument("--max-per-template",type=int,default=100)
    args=ap.parse_args()

    feature=args.feature_parquet.resolve()
    templates_path=args.template_parquet.resolve()
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    if not feature.is_file() or not templates_path.is_file():
        raise SystemExit("missing Stage C input")

    ts=pq.read_table(templates_path).to_pylist()
    if not ts: raise SystemExit("empty Stage B template catalog")
    schema=set(pq.read_schema(feature).names)
    missing=[x for x in [*ALL_DIMS,"race_date",*LABEL_FIELDS] if x not in schema]
    if missing: raise SystemExit(f"feature mart missing Stage C fields: {missing}")

    con=duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='6GB'")
    source_sql=f"read_parquet('{str(feature).replace(chr(39),chr(39)*2)}')"
    max_date=con.execute(f"select max(cast(race_date as date)) from {source_sql}").fetchone()[0]
    if max_date is None: raise SystemExit("race_date max missing")
    cut365=max_date-dt.timedelta(days=365)
    cut730=max_date-dt.timedelta(days=730)
    cut1095=max_date-dt.timedelta(days=1095)

    sink=Sink(out/"research_candidates.parquet")
    template_summary=[]
    total_group_rows=0
    kept_by_depth={}
    kept_by_lane={}
    jackpot_flagged=0
    batches=0

    dim_select=",\n".join(q(d) for d in ALL_DIMS)
    grouping_args=",".join(q(d) for d in ALL_DIMS)

    for batch_start in range(0,len(ts),args.template_batch_size):
        batch=ts[batch_start:batch_start+args.template_batch_size]
        batches+=1
        gid_meta={}
        grouping_sets=[]
        case_support=[]
        case_lane=[]
        case_tpl=[]
        case_depth=[]
        for t in batch:
            dims=json.loads(t["dimensions_json"])
            gid=gid_for(dims)
            if gid in gid_meta:
                raise SystemExit(f"duplicate grouping id in batch: {gid}")
            meta={
                "template_id":t["template_id"],
                "dims":dims,
                "depth":int(t["depth"]),
                "lane":t["search_lane"],
                "family":t["family"],
                "support_floor":support_floor(int(t["depth"]),t["search_lane"]),
            }
            gid_meta[gid]=meta
            grouping_sets.append("(" + ",".join(q(d) for d in dims) + ")")
            case_support.append(f"WHEN {gid} THEN {meta['support_floor']}")
            case_lane.append(f"WHEN {gid} THEN '{meta['lane']}'")
            case_tpl.append(f"WHEN {gid} THEN '{meta['template_id']}'")
            case_depth.append(f"WHEN {gid} THEN {meta['depth']}")

        sql=f"""
        WITH g AS (
          SELECT
            {dim_select},
            grouping_id({grouping_args}) AS gid,
            count(*)::BIGINT AS n,
            sum(coalesce(label_win_hit,0))::BIGINT AS wins,
            sum(coalesce(label_place_hit,0))::BIGINT AS places,
            sum(coalesce(label_win_payout,0))::DOUBLE AS win_return_sum,
            sum(coalesce(label_place_payout,0))::DOUBLE AS place_return_sum,
            max(coalesce(label_win_payout,0))::DOUBLE AS max_win_payout,
            max(coalesce(label_place_payout,0))::DOUBLE AS max_place_payout,
            count(DISTINCT race_date)::BIGINT AS unique_race_days,
            count(DISTINCT substr(race_date,1,4))::BIGINT AS unique_years,
            count(DISTINCT CASE WHEN coalesce(label_win_hit,0)>0 THEN substr(race_date,1,4) END)::BIGINT AS win_hit_years,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut365.isoformat()}' THEN 1 ELSE 0 END)::BIGINT AS n_365,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut365.isoformat()}' THEN coalesce(label_win_payout,0) ELSE 0 END)::DOUBLE AS win_return_365,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut365.isoformat()}' THEN coalesce(label_place_payout,0) ELSE 0 END)::DOUBLE AS place_return_365,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut730.isoformat()}' THEN 1 ELSE 0 END)::BIGINT AS n_730,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut730.isoformat()}' THEN coalesce(label_win_payout,0) ELSE 0 END)::DOUBLE AS win_return_730,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut730.isoformat()}' THEN coalesce(label_place_payout,0) ELSE 0 END)::DOUBLE AS place_return_730,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut1095.isoformat()}' THEN 1 ELSE 0 END)::BIGINT AS n_1095,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut1095.isoformat()}' THEN coalesce(label_win_payout,0) ELSE 0 END)::DOUBLE AS win_return_1095,
            sum(CASE WHEN cast(race_date as date) >= DATE '{cut1095.isoformat()}' THEN coalesce(label_place_payout,0) ELSE 0 END)::DOUBLE AS place_return_1095
          FROM {source_sql}
          GROUP BY GROUPING SETS ({",".join(grouping_sets)})
        ),
        scored AS (
          SELECT *,
            CASE gid {" ".join(case_support)} ELSE 999999999 END AS support_floor,
            CASE gid {" ".join(case_lane)} ELSE 'UNKNOWN' END AS search_lane,
            CASE gid {" ".join(case_tpl)} ELSE 'UNKNOWN' END AS template_id,
            CASE gid {" ".join(case_depth)} ELSE 0 END AS depth,
            100.0*win_return_sum/nullif(100.0*n,0) AS win_roi,
            100.0*place_return_sum/nullif(100.0*n,0) AS place_roi,
            CASE WHEN win_return_sum>0 THEN max_win_payout/win_return_sum ELSE NULL END AS top1_win_contribution,
            CASE WHEN place_return_sum>0 THEN max_place_payout/place_return_sum ELSE NULL END AS top1_place_contribution,
            100.0*(win_return_sum-max_win_payout)/nullif(100.0*n,0) AS win_roi_ex_top1,
            100.0*(place_return_sum-max_place_payout)/nullif(100.0*n,0) AS place_roi_ex_top1,
            CASE WHEN n_365>0 THEN 100.0*win_return_365/(100.0*n_365) END AS win_roi_365,
            CASE WHEN n_365>0 THEN 100.0*place_return_365/(100.0*n_365) END AS place_roi_365,
            CASE WHEN n_730>0 THEN 100.0*win_return_730/(100.0*n_730) END AS win_roi_730,
            CASE WHEN n_730>0 THEN 100.0*place_return_730/(100.0*n_730) END AS place_roi_730,
            CASE WHEN n_1095>0 THEN 100.0*win_return_1095/(100.0*n_1095) END AS win_roi_1095,
            CASE WHEN n_1095>0 THEN 100.0*place_return_1095/(100.0*n_1095) END AS place_roi_1095
          FROM g
        ),
        admitted AS (
          SELECT *,
            row_number() OVER (
              PARTITION BY template_id
              ORDER BY greatest(coalesce(win_roi,0),coalesce(place_roi,0)) DESC, n DESC
            ) AS template_rank
          FROM scored
          WHERE n >= support_floor
            AND (
              (wins >= 2 AND win_roi >= {args.min_win_roi})
              OR
              (places >= 3 AND place_roi >= {args.min_place_roi})
            )
        )
        SELECT * FROM admitted WHERE template_rank <= {args.max_per_template}
        """
        batch_table=con.execute(sql).fetch_arrow_table()
        total_group_rows+=batch_table.num_rows
        if batch_table.num_rows==0:
            continue
        for row in batch_table.to_pylist():
            gid=int(row["gid"])
            meta=gid_meta[gid]
            conditions=[]
            invalid=False
            for d in meta["dims"]:
                v=row[d]
                if v is None:
                    invalid=True; break
                conditions.append({"feature":d,"value":str(v)})
            if invalid:
                continue
            top1=float(row["top1_win_contribution"]) if row["top1_win_contribution"] is not None else None
            jackpot = top1 is not None and top1 >= 0.70
            if jackpot: jackpot_flagged+=1
            outrow={
                "candidate_id":instantiated_id(meta["template_id"],conditions),
                "template_id":meta["template_id"],
                "depth":meta["depth"],
                "family":meta["family"],
                "search_lane":meta["lane"],
                "conditions_json":json.dumps(conditions,ensure_ascii=False,separators=(",",":"),sort_keys=True),
                "n":int(row["n"]),
                "wins":int(row["wins"]),
                "places":int(row["places"]),
                "win_roi":round(float(row["win_roi"]),4) if row["win_roi"] is not None else None,
                "place_roi":round(float(row["place_roi"]),4) if row["place_roi"] is not None else None,
                "win_return_sum":float(row["win_return_sum"]),
                "place_return_sum":float(row["place_return_sum"]),
                "max_win_payout":float(row["max_win_payout"]),
                "max_place_payout":float(row["max_place_payout"]),
                "top1_win_contribution":round(top1,6) if top1 is not None else None,
                "top1_place_contribution":round(float(row["top1_place_contribution"]),6) if row["top1_place_contribution"] is not None else None,
                "win_roi_ex_top1":round(float(row["win_roi_ex_top1"]),4) if row["win_roi_ex_top1"] is not None else None,
                "place_roi_ex_top1":round(float(row["place_roi_ex_top1"]),4) if row["place_roi_ex_top1"] is not None else None,
                "unique_race_days":int(row["unique_race_days"]),
                "unique_years":int(row["unique_years"]),
                "win_hit_years":int(row["win_hit_years"]),
                "n_365":int(row["n_365"]),
                "win_roi_365":round(float(row["win_roi_365"]),4) if row["win_roi_365"] is not None else None,
                "place_roi_365":round(float(row["place_roi_365"]),4) if row["place_roi_365"] is not None else None,
                "n_730":int(row["n_730"]),
                "win_roi_730":round(float(row["win_roi_730"]),4) if row["win_roi_730"] is not None else None,
                "place_roi_730":round(float(row["place_roi_730"]),4) if row["place_roi_730"] is not None else None,
                "n_1095":int(row["n_1095"]),
                "win_roi_1095":round(float(row["win_roi_1095"]),4) if row["win_roi_1095"] is not None else None,
                "place_roi_1095":round(float(row["place_roi_1095"]),4) if row["place_roi_1095"] is not None else None,
                "jackpot_dependent_top1_70pct":jackpot,
                "template_rank":int(row["template_rank"]),
                "support_floor":int(row["support_floor"]),
            }
            sink.add(outrow)
            kept_by_depth[str(meta["depth"])]=kept_by_depth.get(str(meta["depth"]),0)+1
            kept_by_lane[meta["lane"]]=kept_by_lane.get(meta["lane"],0)+1

    sink.close(); con.close()

    audit={
        "status":"PASS",
        "stage":"V04_STAGE_C_ROI_ROBUSTNESS_SCREEN",
        "architecture":"GROUPING_SETS_BATCHED_TEMPLATE_EVALUATION",
        "source_rows":pq.read_metadata(feature).num_rows,
        "template_count":len(ts),
        "template_batch_size":args.template_batch_size,
        "template_batches":batches,
        "research_candidate_count":sink.count,
        "research_candidate_count_by_depth":kept_by_depth,
        "research_candidate_count_by_lane":kept_by_lane,
        "admission_min_win_roi":args.min_win_roi,
        "admission_min_place_roi":args.min_place_roi,
        "max_per_template":args.max_per_template,
        "support_floor_policy":{
            "TRANSITION_PRIORITY":{"2":12,"3":10,"4":8,"5":7,"6":6},
            "PEDIGREE_INTERACTION":{"2":18,"3":16,"4":14,"5":12,"6":10},
            "PEDIGREE_BASELINE":{"2":24,"3":22,"4":20,"5":18,"6":16},
        },
        "support_floor_role":"STAGE_C_RESEARCH_POOL_ADMISSION_NOT_FINAL_VALIDATION",
        "max_source_date":max_date.isoformat(),
        "recent_cutoffs":{"365d":cut365.isoformat(),"730d":cut730.isoformat(),"1095d":cut1095.isoformat()},
        "jackpot_flagged_top1_70pct_count":jackpot_flagged,
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
