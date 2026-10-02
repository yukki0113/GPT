#!/usr/bin/env python3
"""Prepare EdgeDB v0.4 Stage C2 shortlist and exact-metric requests.

C2A is a cheap screen over C1 metrics only. It preserves two discovery routes:
- ESTABLISHED_CURRENT: robust after top1 exclusion + positive recent 2y + n_730 >= 10
- EMERGING_HIGH_ORDER: depth 5/6, recent 2y n 5..9, recent 1y n>=3,
  strong 2y signal and positive 1y signal.

It also derives every immediate parent predicate for later incrementality evaluation.
No odds/popularity filters are used.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

def metric_id(conditions):
    payload=json.dumps(conditions,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return "v04m_"+hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

class Writer:
    def __init__(self,path,schema=None,batch=20000):
        self.path=path; self.schema=schema; self.batch=batch; self.rows=[]; self.writer=None; self.count=0
    def add(self,row):
        self.rows.append(row); self.count+=1
        if len(self.rows)>=self.batch:self.flush()
    def flush(self):
        if not self.rows:return
        t=pa.Table.from_pylist(self.rows,schema=self.schema)
        if self.writer is None:self.writer=pq.ParquetWriter(self.path,t.schema,compression="zstd")
        self.writer.write_table(t); self.rows.clear()
    def close(self):
        self.flush()
        if self.writer:self.writer.close()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--c1-parquet",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args()
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    c1=str(args.c1_parquet.resolve()).replace("'","''")
    shortlist=out/"c2_shortlist.parquet"

    con=duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{c1}')")
    con.execute("""
      COPY (
        WITH x AS (
          SELECT *,
            (
              (win_roi >= 110 and wins >= 2 and win_roi_ex_top1 >= 100 and coalesce(top1_win_contribution,1) < 0.70)
              OR
              (place_roi >= 105 and places >= 3 and place_roi_ex_top1 >= 100 and coalesce(top1_place_contribution,1) < 0.70)
            ) AS robust_top1,
            (
              (win_roi >= 110 and wins >= 2 and n_730 >= 5 and win_roi_730 >= 100)
              OR
              (place_roi >= 105 and places >= 3 and n_730 >= 5 and place_roi_730 >= 100)
            ) AS current2y_positive,
            (
              (win_roi >= 110 and wins >= 2 and win_roi_730 >= 110)
              OR
              (place_roi >= 105 and places >= 3 and place_roi_730 >= 105)
            ) AS current2y_strong,
            (
              (win_roi >= 110 and wins >= 2 and n_365 >= 3 and win_roi_365 >= 100)
              OR
              (place_roi >= 105 and places >= 3 and n_365 >= 3 and place_roi_365 >= 100)
            ) AS current1y_positive
          FROM c
        )
        SELECT *,
          CASE
            WHEN robust_top1 AND current2y_positive AND n_730 >= 10
              THEN 'ESTABLISHED_CURRENT'
            WHEN depth >= 5 AND robust_top1 AND current2y_strong AND current1y_positive
                 AND n_730 BETWEEN 5 AND 9
              THEN 'EMERGING_HIGH_ORDER'
          END AS c2_entry_route
        FROM x
        WHERE
          (robust_top1 AND current2y_positive AND n_730 >= 10)
          OR
          (depth >= 5 AND robust_top1 AND current2y_strong AND current1y_positive
           AND n_730 BETWEEN 5 AND 9)
      ) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)
    """,[str(shortlist)])

    total=con.execute(f"select count(*) from read_parquet('{str(shortlist).replace(chr(39),chr(39)*2)}')").fetchone()[0]
    route_counts={r[0]:r[1] for r in con.execute(f"select c2_entry_route,count(*) from read_parquet('{str(shortlist).replace(chr(39),chr(39)*2)}') group by 1").fetchall()}
    depth_lane=[
      {"depth":r[0],"search_lane":r[1],"c2_entry_route":r[2],"count":r[3]}
      for r in con.execute(f"select depth,search_lane,c2_entry_route,count(*) from read_parquet('{str(shortlist).replace(chr(39),chr(39)*2)}') group by 1,2,3 order by 1,2,3").fetchall()
    ]

    # Stream shortlist, add child metric ids and immediate-parent maps.
    child_writer=Writer(out/"c2_shortlist_with_metric_id.parquet")
    parent_map_writer=Writer(out/"child_parent_map_raw.parquet")
    pf=pq.ParquetFile(shortlist)
    for batch in pf.iter_batches(batch_size=10000):
        for row in batch.to_pylist():
            conds=json.loads(row["conditions_json"])
            mid=metric_id(conds)
            row["metric_request_id"]=mid
            child_writer.add(row)
            if len(conds)<=1:
                continue
            for i,cond in enumerate(conds):
                parent=conds[:i]+conds[i+1:]
                parent_map_writer.add({
                    "child_candidate_id":row["candidate_id"],
                    "child_metric_request_id":mid,
                    "parent_metric_request_id":metric_id(parent),
                    "parent_conditions_json":json.dumps(parent,ensure_ascii=False,sort_keys=True,separators=(",",":")),
                    "removed_feature":cond["feature"],
                    "parent_depth":len(parent),
                })
    child_writer.close(); parent_map_writer.close()

    childp=str((out/"c2_shortlist_with_metric_id.parquet")).replace("'","''")
    parentraw=str((out/"child_parent_map_raw.parquet")).replace("'","''")
    con.execute(f"""
      COPY (
        SELECT DISTINCT parent_metric_request_id AS metric_request_id,
               parent_conditions_json AS conditions_json,
               parent_depth AS depth
        FROM read_parquet('{parentraw}')
      ) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)
    """,[str(out/"parent_metric_requests.parquet")])

    parents=str((out/"parent_metric_requests.parquet")).replace("'","''")
    con.execute(f"""
      COPY (
        SELECT metric_request_id, conditions_json, depth, 'CHILD' AS observed_role
        FROM (
          SELECT metric_request_id, any_value(conditions_json) conditions_json,
                 min(depth) depth
          FROM read_parquet('{childp}')
          GROUP BY 1
        )
        UNION ALL
        SELECT p.metric_request_id,p.conditions_json,p.depth,'PARENT'
        FROM read_parquet('{parents}') p
        WHERE NOT EXISTS (
          SELECT 1 FROM read_parquet('{childp}') c
          WHERE c.metric_request_id=p.metric_request_id
        )
      ) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)
    """,[str(out/"metric_request_catalog.parquet")])

    parent_count=con.execute(f"select count(*) from read_parquet('{parents}')").fetchone()[0]
    request_count=con.execute(f"select count(*) from read_parquet('{str((out/'metric_request_catalog.parquet')).replace(chr(39),chr(39)*2)}')").fetchone()[0]
    map_count=con.execute(f"select count(*) from read_parquet('{parentraw}')").fetchone()[0]

    audit={
      "status":"PASS",
      "stage":"V04_STAGE_C2A_SHORTLIST_AND_PARENT_REQUESTS",
      "c1_candidate_count":con.execute("select count(*) from c").fetchone()[0],
      "c2_shortlist_count":total,
      "c2_entry_route_counts":route_counts,
      "by_depth_lane_route":depth_lane,
      "child_parent_map_count":map_count,
      "unique_parent_metric_request_count":parent_count,
      "unique_metric_request_count":request_count,
      "entry_policy":{
        "ESTABLISHED_CURRENT":"robust_top1 AND current2y_positive AND n_730>=10",
        "EMERGING_HIGH_ORDER":"depth>=5 AND robust_top1 AND current2y_strong AND current1y_positive AND 5<=n_730<=9"
      },
      "parent_definition":"all immediate predicates formed by removing exactly one child condition",
      "parent_incrementality_threshold":"NOT_APPLIED_IN_C2A",
      "market_or_popularity_used":False,
      "production_serving_changed":False,
    }
    (out/"stage_c2a_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False,sort_keys=True))
    con.close()

if __name__=="__main__":
    main()
