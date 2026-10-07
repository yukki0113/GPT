#!/usr/bin/env python3
"""Deterministic EdgeDB v0.5 T1-T6 prototype over frozen accepted Parquet inputs.

Candidate membership uses only pre-race features in 2024-2025. Results and market
fields are joined only after the candidate table has been frozen.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, platform, tarfile, tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
SOURCE_COMMIT = "360f8756d894fa0ee137165694cd6c25c6865675"
DISCOVERY_START, DISCOVERY_END = "2024-01-01", "2025-12-31"
CONTEXT_START, CONTEXT_END = "2022-01-01", "2023-12-31"
PRE_RACE_FIELDS = ("race_date", "race_key", "horse_no", "horse_id", "venue_code", "surface_code", "distance_m", "frame_no", "sire_name", "distance_change_bucket", "surface_transition", "track_condition_bucket")
EVALUATION_FIELDS = ("label_finish", "label_win_hit", "label_place_hit", "label_win_payout", "label_place_payout", "label_final_win_odds", "label_final_win_popularity")
FORBIDDEN_MEMBERSHIP_FIELDS = frozenset({"popularity", "odds", "payout", "label_final_win_popularity", "label_final_win_odds", "label_win_payout", "label_place_payout"})
PERFORMANCE_FIELDS = frozenset({"n", "wins", "places", "misses", "win_rate", "place_rate", "unique_horses", "unique_race_days"})
RETURN_FIELDS = frozenset({"win_return_sum", "place_return_sum", "win_roi", "place_roi", "win_roi_ex_top1", "place_roi_ex_top1", "win_roi_ex_top3", "place_roi_ex_top3"})
MARKET_FIELDS = frozenset({"hit_pop_5_plus", "hit_pop_8_plus", "hit_pop_10_plus", "max_hit_popularity", "avg_popularity", "median_popularity"})
BLOCKED_FEATURES = {"first_dirt", "first_turf", "first_blinkers", "course_topology"}
VENUES = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}
SURFACES = {"1":"芝","2":"ダート","3":"障害"}
GOING = {"1":"GOOD","2":"SOFT_OR_WORSE","3":"SOFT_OR_WORSE","4":"SOFT_OR_WORSE"}
DISTANCE = {"EXTEND":"EXTEND","LARGE_EXTEND":"EXTEND","SHORTEN":"SHORTEN","LARGE_SHORTEN":"SHORTEN"}
SPECS = {
 "T1_COURSE_FRAME": {"conditions":["venue_code","surface_code","distance_m","frame_no"],"parent":["venue_code","surface_code","distance_m"],"family":"T1"},
 "T2_SIRE_COURSE": {"conditions":["sire_name","venue_code","surface_code","distance_m"],"parent":["sire_name"],"family":"T2"},
 "T3_SIRE_DISTANCE_CHANGE": {"conditions":["sire_name","distance_change"],"parent":["sire_name"],"family":"T3"},
 "T4_SIRE_SURFACE_SWITCH": {"conditions":["sire_name","surface_transition"],"parent":["sire_name"],"family":"T4"},
 "T6_SIRE_SURFACE_GOING": {"conditions":["sire_name","surface_code","going_bucket"],"parent":["sire_name","surface_code"],"family":"T6"},
}

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def candidate_id(template_id: str, conditions: dict[str, Any]) -> str:
    spec=SPECS[template_id]
    ordered={k:conditions[k] for k in spec["conditions"]}
    return "v05-"+fingerprint({"template_id":template_id,"template_version":"v0.5.1","conditions":ordered})[:24]

def shortlist_eligible(n: int) -> bool:
    return n >= 5

def support_class(n: int) -> str:
    if n < 5: return "RAW_ONLY"
    if n < 10: return "MICRO"
    if n < 20: return "SMALL"
    if n < 50: return "MEDIUM"
    return "LARGE"

def discovery_member(row: dict[str, Any]) -> bool:
    day=str(row.get("race_date") or "")[:10]
    return DISCOVERY_START <= day <= DISCOVERY_END and row.get("is_pre_race_eligible") in (1, True)

def distance_change(value: Any) -> str | None:
    return DISTANCE.get(str(value).strip()) if value is not None else None

def surface_switch(value: Any) -> bool:
    return str(value or "") in {"1->2", "2->1"}

def going_bucket(value: Any) -> str | None:
    return GOING.get(str(value).strip()) if value is not None else None

def normalize_condition_value(field: str, value: Any) -> str | None:
    if value is None: return None
    if field == "distance_change": return distance_change(value)
    if field == "going_bucket": return going_bucket(value)
    return str(value).strip() or None

def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def _metrics_query(con, template_id: str, candidates: list[dict[str,Any]], facts_path: Path) -> list[dict[str,Any]]:
    import pyarrow as pa
    spec=SPECS[template_id]
    rows=[]
    for c in candidates:
        row={"candidate_id":c["candidate_id"],"template_id":template_id,"parent_key":c["parent_key"]}
        for i in range(1,5): row[f"c{i}"]=c["condition_values"][i-1] if i<=len(c["condition_values"]) else None
        rows.append(row)
    if not rows: return []
    con.register("frozen_candidates_arrow",pa.Table.from_pylist(rows))
    con.execute("CREATE OR REPLACE TEMP TABLE frozen_candidates AS SELECT * FROM frozen_candidates_arrow")
    fields=spec["conditions"]
    expressions=[]
    for i,field in enumerate(fields,1):
        if field=="distance_change": expressions.append(f"CASE WHEN f.distance_change_bucket IN ('EXTEND','LARGE_EXTEND') THEN 'EXTEND' WHEN f.distance_change_bucket IN ('SHORTEN','LARGE_SHORTEN') THEN 'SHORTEN' END=c.c{i}")
        elif field=="going_bucket": expressions.append(f"CASE WHEN CAST(f.track_condition_bucket AS VARCHAR)='1' THEN 'GOOD' WHEN CAST(f.track_condition_bucket AS VARCHAR) IN ('2','3','4') THEN 'SOFT_OR_WORSE' END=c.c{i}")
        else: expressions.append(f"CAST(f.{field} AS VARCHAR)=c.c{i}")
    match=" AND ".join(expressions)
    query=f"""
    WITH matched AS (
      SELECT c.candidate_id,c.parent_key,f.race_date,f.race_key,f.horse_no,f.horse_id,
             f.label_win_hit,f.label_place_hit,f.label_win_payout,f.label_place_payout,
             f.label_final_win_popularity
      FROM frozen_candidates c JOIN read_parquet(?) f ON {match}
      WHERE f.race_date BETWEEN '2022-01-01' AND '2025-12-31'
        AND f.is_pre_race_eligible=1
        AND f.label_win_hit IS NOT NULL AND f.label_place_hit IS NOT NULL
    ), period_rows AS (
      SELECT *, CASE WHEN race_date BETWEEN '2022-01-01' AND '2023-12-31' THEN 'context_2022_2023'
                     WHEN substr(race_date,1,4)='2024' THEN 'year_2024'
                     WHEN substr(race_date,1,4)='2025' THEN 'year_2025' END period
      FROM matched
      UNION ALL SELECT *, 'overall_2024_2025' period FROM matched WHERE race_date BETWEEN '2024-01-01' AND '2025-12-31'
    ), ranked AS (
      SELECT *, row_number() OVER(PARTITION BY candidate_id,period ORDER BY coalesce(label_win_payout,0) DESC,race_date,race_key,horse_no) win_rank,
                row_number() OVER(PARTITION BY candidate_id,period ORDER BY coalesce(label_place_payout,0) DESC,race_date,race_key,horse_no) place_rank
      FROM period_rows WHERE period IS NOT NULL
    )
    SELECT candidate_id,parent_key,period,count(*) n,sum(label_win_hit) wins,sum(label_place_hit) places,
      count(*)-sum(label_place_hit) misses,count(DISTINCT horse_id) unique_horses,count(DISTINCT race_date) unique_race_days,
      sum(coalesce(label_win_payout,0)) win_return_sum,sum(coalesce(label_place_payout,0)) place_return_sum,
      max(coalesce(label_win_payout,0)) top1_win_return,sum(CASE WHEN win_rank<=3 THEN coalesce(label_win_payout,0) ELSE 0 END) top3_win_return,
      max(coalesce(label_place_payout,0)) top1_place_return,sum(CASE WHEN place_rank<=3 THEN coalesce(label_place_payout,0) ELSE 0 END) top3_place_return,
      sum(CASE WHEN label_place_hit=1 AND label_final_win_popularity>=5 THEN 1 ELSE 0 END) hit_pop_5_plus,
      sum(CASE WHEN label_place_hit=1 AND label_final_win_popularity>=8 THEN 1 ELSE 0 END) hit_pop_8_plus,
      sum(CASE WHEN label_place_hit=1 AND label_final_win_popularity>=10 THEN 1 ELSE 0 END) hit_pop_10_plus,
      max(CASE WHEN label_place_hit=1 THEN label_final_win_popularity END) max_hit_popularity,
      max(label_win_payout) largest_win_payout,max(label_place_payout) largest_place_payout,
      avg(label_final_win_popularity) avg_popularity,quantile_cont(label_final_win_popularity,0.5) median_popularity,
      count(*) FILTER(WHERE label_final_win_popularity BETWEEN 1 AND 4) pop_1_4_n,
      sum(label_place_hit) FILTER(WHERE label_final_win_popularity BETWEEN 1 AND 4) pop_1_4_places,
      sum(coalesce(label_place_payout,0)) FILTER(WHERE label_final_win_popularity BETWEEN 1 AND 4) pop_1_4_return,
      count(*) FILTER(WHERE label_final_win_popularity BETWEEN 5 AND 7) pop_5_7_n,
      sum(label_place_hit) FILTER(WHERE label_final_win_popularity BETWEEN 5 AND 7) pop_5_7_places,
      sum(coalesce(label_place_payout,0)) FILTER(WHERE label_final_win_popularity BETWEEN 5 AND 7) pop_5_7_return,
      count(*) FILTER(WHERE label_final_win_popularity>=8) pop_8_plus_n,
      sum(label_place_hit) FILTER(WHERE label_final_win_popularity>=8) pop_8_plus_places,
      sum(coalesce(label_place_payout,0)) FILTER(WHERE label_final_win_popularity>=8) pop_8_plus_return
    FROM ranked GROUP BY candidate_id,parent_key,period
    """
    cursor=con.execute(query,[str(facts_path)])
    names=[d[0] for d in cursor.description]
    return [dict(zip(names,r)) for r in cursor.fetchall()]

def _parent_metrics(con, template_id: str, candidates: list[dict[str,Any]], facts_path: Path) -> dict[tuple[str,str],dict[str,Any]]:
    import pyarrow as pa
    unique={}
    for c in candidates:
        key=(c["parent_key"],c["parent_template"])
        unique.setdefault(key,c["parent_values"])
    if not unique:return {}
    rows=[]
    for (pkey,ptemplate),vals in unique.items():
        row={"parent_key":pkey,"parent_template":ptemplate}
        for i in range(1,4):row[f"p{i}"]=vals[i-1] if i<=len(vals) else None
        rows.append(row)
    con.register("parents_arrow",pa.Table.from_pylist(rows));con.execute("CREATE OR REPLACE TEMP TABLE frozen_parents AS SELECT * FROM parents_arrow")
    if template_id=="T1_COURSE_FRAME": fields=["venue_code","surface_code","distance_m"]
    elif template_id=="T6_SIRE_SURFACE_GOING": fields=["sire_name","surface_code"]
    else: fields=["sire_name"]
    match=" AND ".join(f"CAST(f.{field} AS VARCHAR)=p.p{i}" for i,field in enumerate(fields,1))
    q=f"""WITH matched AS (
      SELECT p.parent_key,f.race_date,f.label_win_hit,f.label_place_hit,f.label_win_payout,f.label_place_payout
      FROM frozen_parents p JOIN read_parquet(?) f ON {match}
      WHERE f.race_date BETWEEN '2022-01-01' AND '2025-12-31' AND f.is_pre_race_eligible=1
        AND f.label_win_hit IS NOT NULL AND f.label_place_hit IS NOT NULL
      ), period_rows AS (
       SELECT *,CASE WHEN race_date BETWEEN '2022-01-01' AND '2023-12-31' THEN 'context_2022_2023' ELSE 'year_'||substr(race_date,1,4) END period FROM matched
       UNION ALL SELECT *,'overall_2024_2025' period FROM matched WHERE race_date BETWEEN '2024-01-01' AND '2025-12-31'
      ) SELECT parent_key,period,count(*) n,avg(label_win_hit) win_rate,avg(label_place_hit) place_rate,
      sum(coalesce(label_win_payout,0)) win_return_sum,sum(coalesce(label_place_payout,0)) place_return_sum
      FROM period_rows GROUP BY parent_key,period"""
    cur=con.execute(q,[str(facts_path)]);names=[d[0] for d in cur.description]
    out={}
    for row in cur.fetchall():
        d=dict(zip(names,row));n=int(d["n"]);d["win_roi"]=100*float(d["win_return_sum"] or 0)/(100*n) if n else None;d["place_roi"]=100*float(d["place_return_sum"] or 0)/(100*n) if n else None
        out[(d["parent_key"],d["period"])]=d
    return out

def _metric_obj(row: dict[str,Any] | None) -> dict[str,Any]:
    if not row:return {"n":0,"wins":0,"places":0,"misses":0,"unique_horses":0,"unique_race_days":0,"win_rate":None,"place_rate":None,"win_return_sum":0,"place_return_sum":0,"win_roi":None,"place_roi":None}
    n=int(row["n"]); wins=int(row["wins"]); places=int(row["places"]); wr=float(row["win_return_sum"] or 0);pr=float(row["place_return_sum"] or 0)
    out={k:(int(row[k]) if k in {"n","wins","places","misses","unique_horses","unique_race_days","hit_pop_5_plus","hit_pop_8_plus","hit_pop_10_plus","max_hit_popularity","largest_win_payout","largest_place_payout","pop_1_4_n","pop_1_4_places","pop_5_7_n","pop_5_7_places","pop_8_plus_n","pop_8_plus_places"} and row.get(k) is not None else row.get(k)) for k in row}
    out.update({"win_rate":wins/n if n else None,"place_rate":places/n if n else None,"win_roi":100*wr/(100*n) if n else None,"place_roi":100*pr/(100*n) if n else None,
                "win_roi_ex_top1":100*(wr-float(row.get("top1_win_return") or 0))/(100*n) if n else None,
                "place_roi_ex_top1":100*(pr-float(row.get("top1_place_return") or 0))/(100*n) if n else None,
                "win_roi_ex_top3":100*(wr-float(row.get("top3_win_return") or 0))/(100*n) if n else None,
                "place_roi_ex_top3":100*(pr-float(row.get("top3_place_return") or 0))/(100*n) if n else None,
                "top1_win_contribution":float(row.get("top1_win_return") or 0)/wr if wr else 0.0,
                "top1_place_contribution":float(row.get("top1_place_return") or 0)/pr if pr else 0.0,
                "top3_win_contribution":float(row.get("top3_win_return") or 0)/wr if wr else 0.0,
                "top3_place_contribution":float(row.get("top3_place_return") or 0)/pr if pr else 0.0})
    out["popularity_bands"]=[]
    for band in ("1_4","5_7","8_plus"):
        bn=int(row.get(f"pop_{band}_n") or 0);br=float(row.get(f"pop_{band}_return") or 0);bh=int(row.get(f"pop_{band}_places") or 0)
        out["popularity_bands"].append({"band":band,"n":bn,"place_hits":bh,"place_roi":100*br/(100*bn) if bn else None})
    return out

def _freshness(context:dict[str,Any], y24:dict[str,Any],y25:dict[str,Any],recent:dict[str,Any])->str:
    if context["n"]<5:return "INSUFFICIENT_HISTORY"
    a,b,c=context.get("place_roi"),y24.get("place_roi"),y25.get("place_roi")
    if b is not None and c is not None and abs(b-c)>=50:return "VOLATILE"
    if c is not None and c>=100 and a is not None and a<100:return "EMERGING"
    if c is not None and c<100 and a is not None and a>=100:return "DECAYING"
    if a is not None and a>=100 and recent.get("place_roi") is not None and recent["place_roi"]<100:return "OLD_ONLY"
    if recent.get("place_roi") is not None and recent["place_roi"]>=100 and c is not None and c>=100:return "CURRENT"
    if a is not None and recent.get("place_roi") is not None and recent["place_roi"]<a-20:return "DECAYING"
    return "CURRENT"

def memo(c:dict[str,Any], delta:float|None)->str:
    cond=c["conditions"]; t=c["template_id"]
    if delta is None: direction="は過去2年で要確認"
    elif delta>0: direction="は近年、親条件より複勝率が高い"
    elif delta<0: direction="は近年、親条件より複勝率が低い"
    else: direction="は近年、親条件と同程度"
    if t=="T1_COURSE_FRAME":
        base=f"{VENUES.get(cond['venue_code'],cond['venue_code'])}{SURFACES.get(cond['surface_code'],cond['surface_code'])}{cond['distance_m']}m"
        return f"{base}は{cond['frame_no']}枠{direction}"
    if t=="T2_SIRE_COURSE":return f"{cond['sire_name']}産駒は{VENUES.get(cond['venue_code'],cond['venue_code'])}{SURFACES.get(cond['surface_code'],cond['surface_code'])}{cond['distance_m']}m{direction}"
    if t=="T3_SIRE_DISTANCE_CHANGE":return f"{cond['sire_name']}産駒は距離{'延長' if cond['distance_change']=='EXTEND' else '短縮'}{direction}"
    if t=="T4_SIRE_SURFACE_SWITCH":return f"{cond['sire_name']}産駒は{'芝→ダート' if cond['surface_transition']=='1->2' else 'ダート→芝'}替わり{direction}"
    return f"{cond['sire_name']}産駒は{SURFACES.get(cond['surface_code'],cond['surface_code'])}・{'良馬場' if cond['going_bucket']=='GOOD' else '稍重以上'}{direction}"

def _distribution(values:list[float])->dict[str,Any]:
    import math
    xs=sorted(float(x) for x in values if x is not None)
    if not xs:return {"count":0,"min":None,"p10":None,"median":None,"p90":None,"max":None}
    def q(p):return xs[min(len(xs)-1,max(0,math.ceil(p*len(xs))-1))]
    return {"count":len(xs),"min":xs[0],"p10":q(.1),"median":q(.5),"p90":q(.9),"max":xs[-1]}

def _write_json(path:Path,obj:Any)->None:path.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def _write_csv(path:Path,rows:list[dict[str,Any]])->None:
    if not rows:path.write_text("\n",encoding="utf-8");return
    fields=list(rows[0]);
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader()
        for r in rows:w.writerow({k:(canonical_json(v) if isinstance(v,(dict,list)) else v) for k,v in r.items()})

def run(*,feature_input:Path,analysis_input:Path,out:Path,feature_artifact_digest:str,analysis_artifact_digest:str,feature_run:int,analysis_run:int,source_commit:str=SOURCE_COMMIT)->dict[str,Any]:
    import duckdb, pyarrow as pa, pyarrow.parquet as pq
    from jrdb_edge_feature_mart_parquet import resolve_current as resolve_feature
    from jrdb_analysis_parquet_current import resolve_current as resolve_analysis
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="edgedb-v05-") as td:
        temp=Path(td); froot=feature_input.resolve();aroot=temp/"analysis";aroot.mkdir()
        inner=analysis_input.resolve()/"analysis-parquet-candidate.tar.xz"
        with tarfile.open(inner,"r:xz") as tar:tar.extractall(aroot,filter="data")
        shadow=json.loads((aroot/"shadow_current.json").read_text(encoding="utf-8"))
        if shadow.get("status")!="SHADOW_PASS":raise ValueError("Analysis artifact shadow pointer is not SHADOW_PASS")
        (aroot/"current.json").write_text(json.dumps({**shadow,"status":"CURRENT"},sort_keys=True)+"\n",encoding="utf-8")
        areport=resolve_analysis(aroot)
        fmroot=froot/"canonical/feature_mart/v0.2"; freport=resolve_feature(fmroot)
        manifest=freport["manifest_payload"]; fpath=Path(freport["fact_path"])
        if freport["generation_id"]!="edge_feature_mart_v0_2_g20260925_pq1":raise ValueError("unexpected Feature Mart generation")
        con=duckdb.connect()
        try:
            fpath_sql=str(fpath).replace("'","''")
            con.execute(f"CREATE TEMP VIEW facts AS SELECT * FROM read_parquet('{fpath_sql}')")
            schema={r[0] for r in con.execute("DESCRIBE facts").fetchall()}
            missing=[x for x in PRE_RACE_FIELDS+EVALUATION_FIELDS if x not in schema]
            if missing:raise ValueError(f"required Feature Mart columns missing: {missing}")
            ranges=con.execute("SELECT min(race_date),max(race_date),count(*) FROM facts").fetchone()
            # Pre-race-only frozen memberships: no payout, popularity, or odds field is referenced here.
            group_sql={
             "T1_COURSE_FRAME":("venue_code,surface_code,distance_m,frame_no","venue_code IS NOT NULL AND surface_code IN ('1','2') AND distance_m IS NOT NULL AND frame_no IS NOT NULL"),
             "T2_SIRE_COURSE":("sire_name,venue_code,surface_code,distance_m","sire_name IS NOT NULL AND venue_code IS NOT NULL AND surface_code IN ('1','2') AND distance_m IS NOT NULL"),
             "T3_SIRE_DISTANCE_CHANGE":("sire_name,CASE WHEN distance_change_bucket IN ('EXTEND','LARGE_EXTEND') THEN 'EXTEND' WHEN distance_change_bucket IN ('SHORTEN','LARGE_SHORTEN') THEN 'SHORTEN' END AS distance_change","sire_name IS NOT NULL AND distance_change_bucket IN ('EXTEND','LARGE_EXTEND','SHORTEN','LARGE_SHORTEN')"),
             "T4_SIRE_SURFACE_SWITCH":("sire_name,surface_transition","sire_name IS NOT NULL AND surface_transition IN ('1->2','2->1')"),
             "T6_SIRE_SURFACE_GOING":("sire_name,surface_code,CASE WHEN CAST(track_condition_bucket AS VARCHAR)='1' THEN 'GOOD' WHEN CAST(track_condition_bucket AS VARCHAR) IN ('2','3','4') THEN 'SOFT_OR_WORSE' END AS going_bucket","sire_name IS NOT NULL AND surface_code IN ('1','2') AND track_condition_bucket IN ('1','2','3','4')")}
            candidates=[]
            for template,(group,where) in group_sql.items():
                grouped=con.execute(f"SELECT {group},count(*) n FROM facts WHERE race_date BETWEEN '{DISCOVERY_START}' AND '{DISCOVERY_END}' AND is_pre_race_eligible=1 AND {where} GROUP BY ALL ORDER BY ALL").fetchall()
                names=[d[0] for d in con.description]
                for record in grouped:
                    values=dict(zip(names,record));cond={k:normalize_condition_value(k,values[k]) for k in SPECS[template]["conditions"]}
                    if any(v is None for v in cond.values()):continue
                    cid=candidate_id(template,cond);spec=SPECS[template];parent={k:cond[k] for k in spec["parent"]}
                    ptemplate={"T1_COURSE_FRAME":"T1_COURSE","T2_SIRE_COURSE":"T2_SIRE","T3_SIRE_DISTANCE_CHANGE":"T3_SIRE","T4_SIRE_SURFACE_SWITCH":"T4_SIRE","T6_SIRE_SURFACE_GOING":"T6_SIRE_SURFACE"}[template]
                    candidates.append({"candidate_id":cid,"template_id":template,"template_version":"v0.5.1","family":spec["family"],"conditions":cond,"condition_fingerprint":fingerprint(cond),"condition_values":[cond[k] for k in spec["conditions"]],"discovery_population_n":int(values["n"]),"parent_template":ptemplate,"parent_values":[parent[k] for k in spec["parent"]],"parent_key":fingerprint({"template":ptemplate,"conditions":parent}),"depth":len(cond)})
            ids=[c["candidate_id"] for c in candidates]
            if len(ids)!=len(set(ids)):raise ValueError("duplicate deterministic candidate IDs")
            metrics=[];parents={}
            for template in SPECS:
                subset=[c for c in candidates if c["template_id"]==template]
                metrics.extend(_metrics_query(con,template,subset,fpath))
                parents.update(_parent_metrics(con,template,subset,fpath))
            # Also form an explicit recent-period aggregate from 2024 + 2025 values.
            byid=defaultdict(dict)
            for row in metrics:byid[row["candidate_id"]][row["period"]]=_metric_obj(row)
            parent_by={}
            for c in candidates:
                pset={p:parents.get((c["parent_key"],p)) for p in ("context_2022_2023","year_2024","year_2025","overall_2024_2025")}
                def parent_obj(p):
                    r=pset[p]
                    return {"n":int(r["n"]),"win_rate":r["win_rate"],"place_rate":r["place_rate"],"win_roi":r["win_roi"],"place_roi":r["place_roi"]} if r else {"n":0,"win_rate":None,"place_rate":None,"win_roi":None,"place_roi":None}
                # Membership rows are frozen; popularity diagnostics are attached only now.
                m=byid[c["candidate_id"]]; y24=m.get("year_2024",_metric_obj(None));y25=m.get("year_2025",_metric_obj(None));ctx=m.get("context_2022_2023",_metric_obj(None));recent=m.get("overall_2024_2025",_metric_obj(None))
                py24=parent_obj("year_2024");py25=parent_obj("year_2025");pctx=parent_obj("context_2022_2023");parent_recent=parent_obj("overall_2024_2025")
                c["metrics"]={"overall_2024_2025":recent,"2024":y24,"2025":y25,"context_2022_2023":ctx}
                c["parent_metrics"]={"overall_2024_2025":parent_recent,"2024":py24,"2025":py25,"context_2022_2023":pctx}
                c["parent_delta"]={"win_rate":(recent["win_rate"]-parent_recent["win_rate"]) if recent["win_rate"] is not None and parent_recent["win_rate"] is not None else None,"place_rate":(recent["place_rate"]-parent_recent["place_rate"]) if recent["place_rate"] is not None and parent_recent["place_rate"] is not None else None,"win_roi":(recent["win_roi"]-parent_recent["win_roi"]) if recent["win_roi"] is not None and parent_recent["win_roi"] is not None else None,"place_roi":(recent["place_roi"]-parent_recent["place_roi"]) if recent["place_roi"] is not None and parent_recent["place_roi"] is not None else None}
                c["support_class"]=support_class(recent["n"]);c["freshness"]=_freshness(ctx,y24,y25,recent)
                labels=[]
                d=c["parent_delta"]["place_rate"]
                if d is not None and d>0:labels.append("NICHE_VALUE_POSITIVE")
                elif d is not None and d<0:labels.append("NICHE_VALUE_NEGATIVE")
                if ctx["n"]<5:labels.append("INSUFFICIENT")
                if c["support_class"]=="MICRO" and c["freshness"] in {"CURRENT","EMERGING"}:labels.append("CURRENT_BUT_LOW_SUPPORT")
                if c["freshness"] in {"EMERGING","DECAYING"}:labels.append(c["freshness"])
                if recent.get("hit_pop_8_plus",0)>0:labels.append("LONGSHOT_EVIDENCE")
                if d is not None and d>0 and recent.get("place_roi") is not None and recent["place_roi"]<100:labels.append("SATURATED_OR_PRICED")
                if recent.get("place_roi") is not None and recent["place_roi"]<80:labels.append("WEAK")
                c["research_labels"]=sorted(set(labels));c["shortlist_eligible"]=shortlist_eligible(recent["n"])
                c["memo"]=memo(c,d)
            # Runner-set redundancy across all candidate families; evidence is only advisory.
            redundancy=[]
            import pyarrow as pa
            cand_rows=[]
            for c in candidates:
                if c["shortlist_eligible"]:
                    rr={"candidate_id":c["candidate_id"],"template_id":c["template_id"]}
                    for i in range(1,5):rr[f"c{i}"]=c["condition_values"][i-1] if i<=len(c["condition_values"]) else None
                    cand_rows.append(rr)
            if cand_rows:
                con.register("redundancy_arrow",pa.Table.from_pylist(cand_rows));con.execute("CREATE OR REPLACE TEMP TABLE redundancy_candidates AS SELECT * FROM redundancy_arrow")
                member_queries=[]
                for template,(group,where) in group_sql.items():
                    spec=SPECS[template];expr=[]
                    for i,field in enumerate(spec["conditions"],1):
                        if field=="distance_change":expr.append(f"CASE WHEN f.distance_change_bucket IN ('EXTEND','LARGE_EXTEND') THEN 'EXTEND' WHEN f.distance_change_bucket IN ('SHORTEN','LARGE_SHORTEN') THEN 'SHORTEN' END=c.c{i}")
                        elif field=="going_bucket":expr.append(f"CASE WHEN CAST(f.track_condition_bucket AS VARCHAR)='1' THEN 'GOOD' WHEN CAST(f.track_condition_bucket AS VARCHAR) IN ('2','3','4') THEN 'SOFT_OR_WORSE' END=c.c{i}")
                        else:expr.append(f"CAST(f.{field} AS VARCHAR)=c.c{i}")
                    member_queries.append(f"SELECT c.candidate_id,f.race_key||':'||CAST(f.horse_no AS VARCHAR) runner FROM redundancy_candidates c JOIN read_parquet('{str(fpath).replace(chr(39),chr(39)*2)}') f ON {' AND '.join(expr)} WHERE c.template_id='{template}' AND f.race_date BETWEEN '{DISCOVERY_START}' AND '{DISCOVERY_END}' AND f.is_pre_race_eligible=1")
                con.execute("CREATE OR REPLACE TEMP VIEW candidate_runners AS "+" UNION ALL ".join(member_queries))
                pairq="""SELECT a.candidate_id a_id,b.candidate_id b_id,count(*) overlap_count FROM candidate_runners a JOIN candidate_runners b ON a.runner=b.runner AND a.candidate_id<b.candidate_id GROUP BY 1,2"""
                candidates_by={c["candidate_id"]:c for c in candidates}
                for a,b,overlap in con.execute(pairq).fetchall():
                    ca,cb=candidates_by[a],candidates_by[b];na=ca["discovery_population_n"];nb=cb["discovery_population_n"];union=na+nb-int(overlap);jac=int(overlap)/union if union else 0
                    relation="A_SUBSET_B" if overlap==na and na<=nb else ("B_SUBSET_A" if overlap==nb and nb<=na else "OVERLAP")
                    redundancy.append({"candidate_a":a,"candidate_b":b,"overlap_count":int(overlap),"union_count":union,"jaccard":jac,"subset_relation":relation,"condition_depth_a":ca["depth"],"condition_depth_b":cb["depth"],"status":"SUGGESTED_REVIEW" if jac>=0.8 or relation!="OVERLAP" else "RAW_OVERLAP","threshold_note":"0.80 is a review suggestion only; no candidate is removed"})
            adjacency=defaultdict(set)
            for r in redundancy:
                if r["status"]=="SUGGESTED_REVIEW":adjacency[r["candidate_a"]].add(r["candidate_b"]);adjacency[r["candidate_b"]].add(r["candidate_a"])
            seen=set();clusters=[]
            for node in sorted(adjacency):
                if node in seen:continue
                stack=[node];component=[];seen.add(node)
                while stack:
                    x=stack.pop();component.append(x)
                    for y in adjacency[x]-seen:seen.add(y);stack.append(y)
                if len(component)>1:
                    members=[next(c for c in candidates if c["candidate_id"]==x) for x in component]
                    rep=sorted(members,key=lambda c:(c["depth"],-c["metrics"]["overall_2024_2025"]["n"],c["candidate_id"]))[0]
                    cid="red-"+fingerprint(sorted(component))[:16]
                    clusters.append({"redundancy_cluster_id":cid,"representative_candidate_id":rep["candidate_id"],"candidate_ids":sorted(component),"suppressed_candidate_ids":[],"reason":"suggested review cluster from Jaccard >= 0.80 or exact subset; raw candidates retained"})
                    for m in members:m["redundancy_cluster_id"]=cid;m["representative_candidate_id"]=rep["candidate_id"];m["redundancy_status"]="SUGGESTED_REDUNDANT" if m["candidate_id"]!=rep["candidate_id"] else "REPRESENTATIVE"
            for c in candidates:
                c.setdefault("redundancy_cluster_id",None);c.setdefault("representative_candidate_id",c["candidate_id"]);c.setdefault("redundancy_status","NO_SUGGESTED_CLUSTER")
            # Deterministic review examples by evidence class, not a single opaque score.
            eligible=[c for c in candidates if c["shortlist_eligible"]]
            def sort_support(c):return (-c["metrics"]["overall_2024_2025"]["n"],c["candidate_id"])
            examples=[]
            selectors=[("promising_positive",lambda c:c["parent_delta"]["place_rate"] is not None and c["parent_delta"]["place_rate"]>0),("promising_negative",lambda c:c["parent_delta"]["place_rate"] is not None and c["parent_delta"]["place_rate"]<0),("longshot_evidence",lambda c:sum((c["metrics"][p].get("hit_pop_8_plus") or 0) for p in ("2024","2025"))>0),("saturated_or_priced",lambda c:c["parent_delta"]["place_rate"] is not None and c["parent_delta"]["place_rate"]>0 and c["metrics"]["overall_2024_2025"]["place_roi"] is not None and c["metrics"]["overall_2024_2025"]["place_roi"]<100),("weak_noisy",lambda c:c["metrics"]["overall_2024_2025"]["n"]<10)]
            selected=set()
            for kind,pred in selectors:
                rows=sorted((c for c in eligible if pred(c)),key=sort_support)[:4]
                for c in rows:
                    if c["candidate_id"] in selected:continue
                    selected.add(c["candidate_id"]);examples.append({"example_type":kind,**c})
            # Include representative of a suggested redundant cluster.
            for cluster in clusters[:4]:
                c=next(x for x in candidates if x["candidate_id"]==cluster["representative_candidate_id"])
                if c["candidate_id"] not in selected:selected.add(c["candidate_id"]);examples.append({"example_type":"redundant_cluster",**c})
            # Build distributions/counts by family and support/freshness/labels.
            byfamily=defaultdict(list)
            for c in candidates:byfamily[c["family"]].append(c)
            family_summary={}
            for fam,rows in sorted(byfamily.items()):
                supported=[c for c in rows if c["shortlist_eligible"]]
                family_summary[fam]={"candidate_count_all":len(rows),"candidate_count_n_ge_5":len(supported),"candidate_count_raw_n_lt_5":len(rows)-len(supported),"support_classes":dict(Counter(c["support_class"] for c in rows)),"freshness_counts":dict(Counter(c["freshness"] for c in supported)),"label_counts":dict(Counter(label for c in supported for label in c["research_labels"])),"n_distribution":_distribution([c["metrics"]["overall_2024_2025"]["n"] for c in supported]),"win_roi_distribution":_distribution([c["metrics"]["overall_2024_2025"]["win_roi"] for c in supported]),"place_roi_distribution":_distribution([c["metrics"]["overall_2024_2025"]["place_roi"] for c in supported]),"year_2024_place_roi_distribution":_distribution([c["metrics"]["2024"]["place_roi"] for c in supported]),"year_2025_place_roi_distribution":_distribution([c["metrics"]["2025"]["place_roi"] for c in supported]),"longshot_place_hit_count_distribution":_distribution([float(c["metrics"]["2024"].get("hit_pop_8_plus",0) or 0)+float(c["metrics"]["2025"].get("hit_pop_8_plus",0) or 0) for c in supported])}
            # Feature availability with exact discovery-window coverage.
            coverage={}
            for field in PRE_RACE_FIELDS+EVALUATION_FIELDS:
                count,nonnull=con.execute(f"SELECT count(*),count({field}) FROM facts WHERE race_date BETWEEN '{DISCOVERY_START}' AND '{DISCOVERY_END}' AND is_pre_race_eligible=1").fetchone()
                coverage[field]={"available":True,"rows":int(count),"non_null":int(nonnull),"coverage_pct":round(100*int(nonnull)/int(count),4) if count else 0,"role":"PRE_RACE_CANDIDATE" if field in PRE_RACE_FIELDS else "POST_RACE_EVALUATION_ONLY"}
            unavailable={"first_dirt":"UNAVAILABLE_IN_FROZEN_FEATURE_MART; true career-first exposure cannot be asserted from immediate previous surface alone","first_turf":"UNAVAILABLE_IN_FROZEN_FEATURE_MART; true career-first exposure cannot be asserted from immediate previous surface alone","first_blinkers":"UNAVAILABLE_IN_FROZEN_FEATURE_MART; current KYI blinker code is not part of this frozen mart","course_topology":"BLOCKED; no complete venue+surface+distance(+variant) canonical topology lookup found; do not infer from distance"}
            # All full candidates n>=5; all low-support rows remain in a separate audit output.
            candidate_output=[c for c in candidates if c["shortlist_eligible"]];low_output=[c for c in candidates if not c["shortlist_eligible"]]
            pq.write_table(pa.Table.from_pylist(candidate_output),out/"t1_t6_candidates.parquet",compression="zstd")
            pq.write_table(pa.Table.from_pylist(low_output),out/"raw_candidates_n_lt_5.parquet",compression="zstd")
            _write_json(out/"redundancy_summary.json",{"pair_count":len(redundancy),"suggested_review_pair_count":sum(r["status"]=="SUGGESTED_REVIEW" for r in redundancy),"threshold":0.8,"clusters":clusters,"pairs":redundancy[:1000],"pair_list_truncated":len(redundancy)>1000})
            compact=[{k:c.get(k) for k in ("candidate_id","memo","template_id","support_class","conditions","metrics","parent_delta","freshness","research_labels","redundancy_cluster_id","redundancy_status")} for c in examples]
            _write_json(out/"shortlist_summary.json",{"count":len(compact),"examples":compact,"shortlist_is_human_review_only":True})
            _write_csv(out/"candidate_summary.csv",candidate_output)
            source_info={"instruction_source_commit":source_commit,"execution_source_commit_expected":source_commit,"feature_mart_generation_id":freport["generation_id"],"feature_mart_manifest_sha256":_sha(Path(freport["manifest"])),"feature_mart_parquet_sha256":freport["sha256"],"feature_mart_rows":freport["rows"],"feature_mart_coverage":[str(ranges[0]),str(ranges[1])],"feature_mart_artifact_run_id":feature_run,"feature_mart_artifact_digest":feature_artifact_digest,"warehouse_generation_id":manifest["source_generation_id"],"warehouse_manifest_sha256":manifest["source_manifest_sha256"],"analysis_generation_id":areport["generation_id"],"analysis_manifest_sha256":_sha(Path(areport["manifest"])),"analysis_rows":areport["rows"],"analysis_artifact_run_id":analysis_run,"analysis_artifact_digest":analysis_artifact_digest,"analysis_coverage":"validated v1.4 generation; discovery scan intentionally does not use Analysis 2026 rows"}
            summary={"schema_version":"edgedb-v05-prototype-summary/v1","status":"PASS_WITH_BLOCKED_FEATURE_FAMILIES","version":VERSION,"source_provenance":source_info,"execution":{"python":platform.python_version(),"duckdb":duckdb.__version__,"pyarrow":pa.__version__,"membership_window":{"start":DISCOVERY_START,"end":DISCOVERY_END},"context_window":{"start":CONTEXT_START,"end":CONTEXT_END},"2026_used":False,"candidate_generation_market_blind":True,"metrics_joined_after_membership_freeze":True,"discovery_rows_pre_race_eligible":int(con.execute(f"SELECT count(*) FROM facts WHERE race_date BETWEEN '{DISCOVERY_START}' AND '{DISCOVERY_END}' AND is_pre_race_eligible=1").fetchone()[0])},"feature_availability":coverage,"blocked_features":unavailable,"template_families":{"T1":"PASS","T2":"PASS; sire x course; topology semantic variant BLOCKED","T3":"PASS; canonical +/-200m semantics aggregated into EXTEND/SHORTEN","T4":"PARTIAL; cross-surface switch PASS; FIRST_DIRT/FIRST_TURF BLOCKED","T5":"BLOCKED; FIRST_BLINKERS unavailable","T6":"PASS"},"candidate_counts":{"by_family":family_summary,"n_lt_5_total":len(low_output),"n_ge_5_total":len(candidate_output),"by_support_class":dict(Counter(c["support_class"] for c in candidate_output)),"by_freshness":dict(Counter(c["freshness"] for c in candidate_output)),"by_label":dict(Counter(label for c in candidate_output for label in c["research_labels"]))},"distribution_summary_by_family":family_summary,"freshness_rule":{"version":"v0.5.1","labels":["EMERGING","CURRENT","DECAYING","OLD_ONLY","VOLATILE","INSUFFICIENT_HISTORY"],"rules":"context n<5 => INSUFFICIENT_HISTORY; 2024 vs 2025 place ROI gap >=50pp => VOLATILE; 2025 ROI >=100 with context <100 => EMERGING; 2025 ROI <100 with context >=100 => DECAYING; context >=100 and recent ROI <100 => OLD_ONLY; recent and 2025 ROI >=100 => CURRENT; otherwise relative recent decline >=20pp => DECAYING, else CURRENT. Descriptive; not optimized."},"longshot_definition":"place/top-3 hits at final popularity >=5/8/10 after candidate membership freeze; payout/odds/popularity never define membership","performance_return_separation":{"performance":"n, wins, places, misses, win_rate, place_rate, unique_horses, unique_race_days","return":"win_return_sum, place_return_sum, win_roi, place_roi; returns are per 100-yen stakes, ROI=return_sum/(n*100)*100","misses":"n minus top-3 place hits","jackpot":"top1/top3 contributions and ex-top1/ex-top3 ROI are descriptive only, never candidate gates"},"redundancy":{"candidate_runner_overlap_pairs":len(redundancy),"suggested_review_pairs":sum(r["status"]=="SUGGESTED_REVIEW" for r in redundancy),"clusters":len(clusters),"threshold":0.8,"raw_candidates_retained":True},"desired_pattern_check":{"sire_x_turf_one_turn":"BLOCKED; no canonical topology map","sire_x_distance_extension":"EXPRESSIBLE/DISCOVERED by T3 canonical distance bucket","sire_x_first_dirt":"BLOCKED; no true first-surface flag in frozen mart"},"shortlist_example_count":len(examples),"recommendation":"PARTIAL_WITH_BLOCKED_FAMILIES","generated_at":datetime.now(timezone.utc).isoformat()}
            _write_json(out/"feature_mart_manifest_audit.json",{"schema_version":"edgedb-v05-feature-mart-audit/v1","source":source_info,"status":"PASS","feature_availability":coverage,"blocked_features":unavailable})
            _write_json(out/"t1_t6_summary.json",summary)
            _write_json(out/"t1_t6_top_examples.json",compact)
            _write_csv(out/"shortlist_summary.csv",compact)
            (out/"t1_t6_report.md").write_text(render_report(summary,examples,source_info),encoding="utf-8")
            return summary
        finally:con.close()

def render_report(summary:dict[str,Any],examples:list[dict[str,Any]],source:dict[str,Any])->str:
    lines=["# EdgeDB v0.5 T1-T6 Prototype Aggregation", "",f"Status: {summary['recommendation']}","",f"Discovery: {DISCOVERY_START} through {DISCOVERY_END} (inclusive). Context only: {CONTEXT_START} through {CONTEXT_END}. 2026 excluded.","","## Source provenance","",f"- Feature Mart: {source['feature_mart_generation_id']}, {source['feature_mart_rows']:,} rows, coverage {' .. '.join(source['feature_mart_coverage'])}, manifest SHA-256 {source['feature_mart_manifest_sha256']}, Parquet SHA-256 {source['feature_mart_parquet_sha256']}, artifact run {source['feature_mart_artifact_run_id']} / {source['feature_mart_artifact_digest']}.",f"- Warehouse: {source['warehouse_generation_id']}, source manifest SHA-256 {source['warehouse_manifest_sha256']}.",f"- Analysis: {source['analysis_generation_id']}, {source['analysis_rows']:,} rows, manifest SHA-256 {source['analysis_manifest_sha256']}, artifact run {source['analysis_artifact_run_id']} / {source['analysis_artifact_digest']}. Candidate and metric scans are bounded to 2022-2025; no 2026 result enters discovery or ranking.","","## Execution route","",f"- Local Data Storage: DEPENDENCY_MISSING; one requirements install blocked by managed proxy (proxy:8080 operation not permitted); fallback_candidate=true.",f"- Runtime: Python {summary['execution']['python']}, DuckDB {summary['execution']['duckdb']}, PyArrow {summary['execution']['pyarrow']}.","- Candidate groups use only pre-race features. Outcome and market diagnostics are queried only after the frozen 2024-2025 candidate table is created.","","## Feature availability","","| Feature | Availability / role | Coverage |","|---|---|---:|"]
    for f,m in summary["feature_availability"].items():lines.append(f"| {f} | {m['role']} | {m['coverage_pct']}% ({m['non_null']:,}/{m['rows']:,}) |")
    lines += ["| FIRST_DIRT / FIRST_TURF | BLOCKED: not present in frozen Feature Mart; prior-surface difference is not substituted | — |","| FIRST_BLINKERS | BLOCKED: KYI blinker code is not present in frozen Feature Mart | — |","| Course topology | BLOCKED: no complete canonical venue+surface+distance(+variant) lookup established | — |","","## Candidate counts and distributions","", "| Family | All groups | n>=5 | n<5 raw only | Support classes | Freshness |", "|---|---:|---:|---:|---|---|"]
    for fam,v in summary["distribution_summary_by_family"].items():lines.append(f"| {fam} | {v['candidate_count_all']} | {v['candidate_count_n_ge_5']} | {v['candidate_count_raw_n_lt_5']} | {canonical_json(v['support_classes'])} | {canonical_json(v['freshness_counts'])} |")
    lines += ["","Metrics are unweighted per-runner rates. Returns are separate, with ROI based on 100-yen stakes. Longshot hits mean place/top-3 hits at popularity >=5/8/10; popularity, odds, and payouts do not define groups. Top1/top3 dependence is descriptive, not a rejection gate.","","## Human review examples","","| Type | Candidate | Memo | Template | Support | n | Wins | Places | Win ROI | Place ROI | 2024 Place ROI | 2025 Place ROI | 22-23 Context Place ROI | 5+/8+/10+ hits | Largest place payout | Parent Δ place rate | Freshness | Jackpot | Redundancy |","|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|---|"]
    for c in examples:
        m=c['metrics'];o=m['overall_2024_2025'];hits=f"{o.get('hit_pop_5_plus',0)}/{o.get('hit_pop_8_plus',0)}/{o.get('hit_pop_10_plus',0)}";jack="ONE_BIG_HIT" if max(o.get("top1_place_contribution",0) or 0,o.get("top1_win_contribution",0) or 0)>=.7 else "DESCRIPTIVE"
        f=lambda x:"—" if x is None else f"{x:.1f}"
        lines.append(f"| {c['example_type']} | {c['candidate_id']} | {c['memo']} | {c['template_id']} | {c['support_class']} | {o['n']} | {o['wins']} | {o['places']} | {f(o['win_roi'])} | {f(o['place_roi'])} | {f(m['2024'].get('place_roi'))} | {f(m['2025'].get('place_roi'))} | {f(m['context_2022_2023'].get('place_roi'))} | {hits} | {o.get('largest_place_payout') or 0} | {f(100*c['parent_delta']['place_rate']) if c['parent_delta']['place_rate'] is not None else '—'}pp | {c['freshness']} | {jack} | {c['redundancy_status']} |")
    lines += ["","## Desired-pattern check","", "- Sire × turf one-turn: BLOCKED pending canonical course-topology mapping.","- Sire × distance extension: EXPRESSIBLE; uses existing canonical >=200m EXTEND buckets (EXTEND and LARGE_EXTEND aggregated).","- Sire × first dirt: BLOCKED; no true career-first flag exists in the frozen mart, and prior surface alone is not treated as first exposure.","","## Failure modes and next research issues","","- Ordinary course and sire-course conditions may dominate output; review the n/ROI distributions and the presentation redundancy suggestions before widening templates.","- n<5 groups remain in raw audit only; all n>=5 MICRO candidates remain, including jackpot-heavy cases.","- Semantic duplicates are suggested at Jaccard >=0.80 or exact subset, but no raw candidate is removed; threshold is advisory only.","- FIRST_DIRT, FIRST_TURF, FIRST_BLINKERS and semantic topology remain blocked due to unavailable canonical features/mapping in this input generation.","- Candidate-level overlap joins are the main runtime/memory cost; timing is in fallback audit.","","## Recommendation","", "PARTIAL_WITH_BLOCKED_FAMILIES. T1, sire-course T2, T3, surface-switch T4, and T6 are executed; T2 topology, T4 first-surface, and T5 are blocked. No v0.2/v0.3/v0.4 manifest, RaceNote, Newspaper, or PWA consumer was changed.",""]
    return "\n".join(lines)

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--feature-input",type=Path,required=True);p.add_argument("--analysis-input",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);p.add_argument("--feature-run",type=int,required=True);p.add_argument("--feature-artifact-digest",required=True);p.add_argument("--analysis-run",type=int,required=True);p.add_argument("--analysis-artifact-digest",required=True);p.add_argument("--source-commit",default=SOURCE_COMMIT);a=p.parse_args()
    summary=run(feature_input=a.feature_input,analysis_input=a.analysis_input,out=a.output_dir,feature_artifact_digest=a.feature_artifact_digest,analysis_artifact_digest=a.analysis_artifact_digest,feature_run=a.feature_run,analysis_run=a.analysis_run,source_commit=a.source_commit)
    print(json.dumps({"status":summary["status"],"candidates":summary["candidate_counts"]["n_ge_5_total"],"recommendation":summary["recommendation"]},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
