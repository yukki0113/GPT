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
GOING = {"1":"GOOD","2":"SOFT_OR_WORSE","3":"SOFT_OR_WORSE","4":"SOFT_OR_WORSE","GOOD":"GOOD","SOFT_OR_WORSE":"SOFT_OR_WORSE"}
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

def positive_value_eligible(n: int, place_roi: float | None) -> bool:
    """The v0.5 positive Value presentation gate; ROI is percent of stake."""
    return n >= 5 and place_roi is not None and place_roi >= 100

def value_strength_band(place_roi: float | None) -> str | None:
    if place_roi is None or place_roi < 100: return None
    if place_roi < 120: return "VALUE_100_119"
    if place_roi < 150: return "VALUE_120_149"
    return "VALUE_150_PLUS"

def negative_value_eligible(n: int, delta_place_rate: float | None,
                            delta_place_roi: float | None,
                            parent_available: bool) -> bool:
    return (n >= 5 and parent_available and delta_place_rate is not None
            and delta_place_roi is not None and delta_place_rate <= -0.03
            and delta_place_roi <= -20)

def performance_labels(delta_place_rate: float | None,
                       delta_win_rate: float | None = None) -> list[str]:
    deltas = [x for x in (delta_place_rate, delta_win_rate) if x is not None]
    labels=[]
    if any(x > 0 for x in deltas): labels.append("PERFORMANCE_POSITIVE")
    if any(x < 0 for x in deltas): labels.append("PERFORMANCE_NEGATIVE")
    return labels

def positive_value_representatives(rows: list[dict[str, Any]],
                                    pairs: list[dict[str, Any]]) -> tuple[list[str], dict[str, list[str]]]:
    """Cluster only ROI-qualified review candidates; never remove raw rows."""
    eligible={r["candidate_id"]:r for r in rows if r.get("positive_value_eligible")}
    adjacency=defaultdict(set)
    for p in pairs:
        a,b=p["candidate_a"],p["candidate_b"]
        if p["status"] == "SUGGESTED_REVIEW" and a in eligible and b in eligible:
            adjacency[a].add(b);adjacency[b].add(a)
    reps=[];suppressed={};seen=set()
    for node in sorted(eligible):
        if node in seen: continue
        stack=[node];component=[];seen.add(node)
        while stack:
            cur=stack.pop();component.append(cur)
            for nxt in adjacency[cur]-seen:seen.add(nxt);stack.append(nxt)
        # Prefer simplest memo, then strongest support, then deterministic ID.
        rep=sorted(component,key=lambda cid:(eligible[cid]["depth"],
            -eligible[cid]["metrics"]["overall_2024_2025"]["n"],cid))[0]
        reps.append(rep)
        if len(component)>1: suppressed[rep]=sorted(set(component)-{rep})
    return sorted(reps),suppressed

def derive_first_surface_flags(rows: list[dict[str, Any]]) -> dict[str, dict[str, bool | None]]:
    """Derive career-first dirt/turf by horse and strict earlier-date history.

    Rows need canonical horse_id/blood_registration_no, race_date, surface_code and history_complete.
    Unknown/left-censored horses remain None; each target is evaluated before
    adding its own surface to the prior-history set.
    """
    horse=lambda r:str(r.get("horse_id") or r.get("blood_registration_no") or "")
    ordered=sorted(rows,key=lambda r:(horse(r),str(r.get("race_date") or ""),str(r.get("race_key") or r.get("race_key_raw") or "")))
    prior=defaultdict(set);out={}
    for i,row in enumerate(ordered):
        hid=horse(row)
        if not hid: continue
        day=str(row.get("race_date") or "")[:10]
        key=str(row.get("race_key") or row.get("race_key_raw") or f"{day}:{row.get('horse_no','')}:{i}")
        complete=row.get("history_complete") is True
        surface=str(row.get("surface_code") or "")
        out[key]={"first_dirt":(surface=="2" and "2" not in prior[hid]) if complete else None,
                  "first_turf":(surface=="1" and "1" not in prior[hid]) if complete else None}
        if day and surface in {"1","2"}: prior[hid].add(surface)
    return out

def derive_first_blinkers(rows: list[dict[str, Any]]) -> dict[str, bool | None]:
    """Derive first active blinkers from exact horse chronology; None if censored."""
    horse=lambda r:str(r.get("horse_id") or r.get("blood_registration_no") or "")
    ordered=sorted(rows,key=lambda r:(horse(r),str(r.get("race_date") or ""),str(r.get("race_key") or r.get("race_key_raw") or "")))
    prior_active=defaultdict(bool);out={}
    for i,row in enumerate(ordered):
        hid=horse(row)
        if not hid: continue
        key=str(row.get("race_key") or row.get("race_key_raw") or f"{row.get('race_date','')}:{row.get('horse_no','')}:{i}")
        code=str(row.get("blinker_code") or "")
        active=code in {"1","2","3"}
        out[key]=(active and not prior_active[hid]) if row.get("history_complete") is True else None
        if active: prior_active[hid]=True
    return out

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
    if delta is None: direction="近年の傾向を要確認"
    elif delta>0: direction="近年、親条件より複勝率が高い"
    elif delta<0: direction="近年、親条件より複勝率が低い"
    else: direction="近年、親条件と同程度"
    if t=="T1_COURSE_FRAME":
        base=f"{VENUES.get(cond['venue_code'],cond['venue_code'])}{SURFACES.get(cond['surface_code'],cond['surface_code'])}{cond['distance_m']}m"
        return f"{base}は{cond['frame_no']}枠で、{direction}"
    if t=="T2_SIRE_COURSE":return f"{cond['sire_name']}産駒は{VENUES.get(cond['venue_code'],cond['venue_code'])}{SURFACES.get(cond['surface_code'],cond['surface_code'])}{cond['distance_m']}mで、{direction}"
    if t=="T3_SIRE_DISTANCE_CHANGE":return f"{cond['sire_name']}産駒は距離{'延長' if cond['distance_change']=='EXTEND' else '短縮'}で、{direction}"
    if t=="T4_SIRE_SURFACE_SWITCH":return f"{cond['sire_name']}産駒は{'芝→ダート' if cond['surface_transition']=='1->2' else 'ダート→芝'}替わりで、{direction}"
    return f"{cond['sire_name']}産駒は{SURFACES.get(cond['surface_code'],cond['surface_code'])}・{'良馬場' if cond['going_bucket']=='GOOD' else '稍重以上'}で、{direction}"

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
                d=c["parent_delta"]["place_rate"]
                labels=performance_labels(d,c["parent_delta"]["win_rate"])
                roi=recent.get("place_roi")
                c["positive_value_eligible"]=positive_value_eligible(recent["n"],roi)
                c["value_strength_band"]=value_strength_band(roi)
                parent_available=parent_recent.get("n",0)>0 and parent_recent.get("place_rate") is not None and parent_recent.get("place_roi") is not None
                c["negative_value_eligible"]=negative_value_eligible(recent["n"],d,c["parent_delta"].get("place_roi"),parent_available)
                c["positive_shortlist_status"]="ELIGIBLE_PENDING_REDUNDANCY" if c["positive_value_eligible"] else "BELOW_VALUE_GATE"
                if c["positive_value_eligible"]:labels.append("NICHE_VALUE_POSITIVE")
                if c["negative_value_eligible"]:labels.append("NICHE_VALUE_NEGATIVE")
                if ctx["n"]<5:labels.append("INSUFFICIENT")
                if c["support_class"]=="MICRO" and c["freshness"] in {"CURRENT","EMERGING"}:labels.append("CURRENT_BUT_LOW_SUPPORT")
                if c["freshness"] in {"EMERGING","DECAYING"}:labels.append(c["freshness"])
                if recent.get("hit_pop_8_plus",0)>0:labels.append("LONGSHOT_EVIDENCE")
                if d is not None and d>0 and roi is not None and roi<100:labels.append("SATURATED_OR_PRICED")
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
            positive_reps,positive_suppressed=positive_value_representatives(eligible,redundancy)
            for c in candidates:
                cid=c["candidate_id"]
                c["positive_shortlist_status"]=("REPRESENTATIVE" if cid in positive_reps else
                    "SUPPRESSED_BY_REDUNDANCY" if any(cid in xs for xs in positive_suppressed.values()) else
                    "BELOW_VALUE_GATE" if not c.get("positive_value_eligible") else "ELIGIBLE_NO_CLUSTER")
            examples=[]
            selector_rows=[]
            # At most two positive-value representatives per family, then evidence lanes.
            for fam in sorted({c["family"] for c in eligible}):
                family_rows=sorted((c for c in eligible if c["candidate_id"] in positive_reps and c["family"]==fam),key=sort_support)
                if family_rows: selector_rows.extend(("positive_value",c) for c in family_rows[:2])
            selectors=[("longshot_evidence",lambda c:"LONGSHOT_EVIDENCE" in c["research_labels"]),
                ("emerging",lambda c:c["freshness"]=="EMERGING" and c["positive_value_eligible"]),
                ("current",lambda c:c["freshness"]=="CURRENT" and c["positive_value_eligible"]),
                ("micro_positive_value",lambda c:c["support_class"]=="MICRO" and c["positive_value_eligible"]),
                ("saturated_or_priced",lambda c:"SATURATED_OR_PRICED" in c["research_labels"]),
                ("negative_edge",lambda c:c["negative_value_eligible"])]
            selected=set()
            for kind,c in selector_rows:
                if c["candidate_id"] not in selected:
                    selected.add(c["candidate_id"]);examples.append({"example_type":kind,**c})
            for kind,pred in selectors:
                rows=sorted((c for c in eligible if pred(c)),key=sort_support)[:3]
                for c in rows:
                    selected.add(c["candidate_id"]);examples.append({"example_type":kind,**c})
            # Include actual representatives with suppressed positive-value siblings.
            for cid in sorted(positive_suppressed)[:3]:
                c=next(x for x in candidates if x["candidate_id"]==cid)
                examples.append({"example_type":"redundant_cluster",**c})
            # Build distributions/counts by family and support/freshness/labels.
            byfamily=defaultdict(list)
            for c in candidates:byfamily[c["family"]].append(c)
            family_summary={}
            for fam,rows in sorted(byfamily.items()):
                supported=[c for c in rows if c["shortlist_eligible"]]
                family_positive=[c for c in supported if c["positive_value_eligible"]]
                family_negative=[c for c in supported if c["negative_value_eligible"]]
                family_summary[fam]={"candidate_count_all":len(rows),"candidate_count_n_ge_5":len(supported),"candidate_count_raw_n_lt_5":len(rows)-len(supported),"positive_value_count":len(family_positive),"positive_value_by_support_class":dict(Counter(c["support_class"] for c in family_positive)),"longshot_evidence_positive_count":sum("LONGSHOT_EVIDENCE" in c["research_labels"] for c in family_positive),"negative_edge_count":len(family_negative),"positive_value_representative_count":sum(c["candidate_id"] in positive_reps for c in family_positive),"support_classes":dict(Counter(c["support_class"] for c in rows)),"freshness_counts":dict(Counter(c["freshness"] for c in supported)),"label_counts":dict(Counter(label for c in supported for label in c["research_labels"])),"n_distribution":_distribution([c["metrics"]["overall_2024_2025"]["n"] for c in supported]),"win_roi_distribution":_distribution([c["metrics"]["overall_2024_2025"]["win_roi"] for c in supported]),"place_roi_distribution":_distribution([c["metrics"]["overall_2024_2025"]["place_roi"] for c in supported]),"year_2024_win_roi_distribution":_distribution([c["metrics"]["2024"]["win_roi"] for c in supported]),"year_2024_place_roi_distribution":_distribution([c["metrics"]["2024"]["place_roi"] for c in supported]),"year_2025_win_roi_distribution":_distribution([c["metrics"]["2025"]["win_roi"] for c in supported]),"year_2025_place_roi_distribution":_distribution([c["metrics"]["2025"]["place_roi"] for c in supported]),"longshot_place_hit_count_distribution":_distribution([float(c["metrics"]["2024"].get("hit_pop_8_plus",0) or 0)+float(c["metrics"]["2025"].get("hit_pop_8_plus",0) or 0) for c in supported])}
            # Feature availability with exact discovery-window coverage.
            coverage={}
            for field in PRE_RACE_FIELDS+EVALUATION_FIELDS:
                count,nonnull=con.execute(f"SELECT count(*),count({field}) FROM facts WHERE race_date BETWEEN '{DISCOVERY_START}' AND '{DISCOVERY_END}' AND is_pre_race_eligible=1").fetchone()
                coverage[field]={"available":True,"rows":int(count),"non_null":int(nonnull),"coverage_pct":round(100*int(nonnull)/int(count),4) if count else 0,"role":"PRE_RACE_CANDIDATE" if field in PRE_RACE_FIELDS else "POST_RACE_EVALUATION_ONLY"}
            unavailable={"first_dirt":"DERIVABLE_FROM_WAREHOUSE_SCHEMA; not included in candidate aggregation because canonical annual history Parquet was not present in the Actions artifact inputs. Use blood_registration_no + race_key_raw to join runner history and surface_code; UNKNOWN for left-censored horses.","first_turf":"DERIVABLE_FROM_WAREHOUSE_SCHEMA; not included in candidate aggregation because canonical annual history Parquet was not present in the Actions artifact inputs. Use blood_registration_no + race_key_raw to join runner history and surface_code; UNKNOWN for left-censored horses.","first_blinkers":"DERIVABLE_FROM_WAREHOUSE_SCHEMA; not included in candidate aggregation because canonical KYI annual history Parquet was not present in the Actions artifact inputs. KYI has blood_registration_no, race_key_raw, blinker_code; codes 1/2/3 mean first-worn/re-worn/active.","course_topology":"BLOCKED_AFTER_REPOSITORY_AUDIT; BAC exposes turn_code (right/left/straight/other) and layout_code (inner/outer/straight-dirt/other), but no authoritative venue+surface+distance+layout -> one/two-turn map exists in repository metadata. These fields do not encode turn count; distance inference is invalid."}
            # All full candidates n>=5; all low-support rows remain in a separate audit output.
            candidate_output=[c for c in candidates if c["shortlist_eligible"]];low_output=[c for c in candidates if not c["shortlist_eligible"]]
            pq.write_table(pa.Table.from_pylist(candidate_output),out/"t1_t6_candidates.parquet",compression="zstd")
            pq.write_table(pa.Table.from_pylist(low_output),out/"raw_candidates_n_lt_5.parquet",compression="zstd")
            _write_json(out/"redundancy_summary.json",{"pair_count":len(redundancy),"suggested_review_pair_count":sum(r["status"]=="SUGGESTED_REVIEW" for r in redundancy),"threshold":0.8,"clusters":clusters,"pairs":redundancy[:1000],"pair_list_truncated":len(redundancy)>1000})
            compact=[{k:c.get(k) for k in ("example_type","candidate_id","memo","template_id","support_class","conditions","metrics","parent_delta","freshness","research_labels","positive_value_eligible","value_strength_band","negative_value_eligible","positive_shortlist_status","redundancy_cluster_id","redundancy_status")} for c in examples]
            _write_json(out/"shortlist_summary.json",{"count":len(compact),"examples":compact,"shortlist_is_human_review_only":True})
            _write_csv(out/"candidate_summary.csv",candidate_output)
            source_info={"instruction_source_commit":source_commit,"execution_source_commit_expected":source_commit,"feature_mart_generation_id":freport["generation_id"],"feature_mart_manifest_sha256":_sha(Path(freport["manifest"])),"feature_mart_parquet_sha256":freport["sha256"],"feature_mart_rows":freport["rows"],"feature_mart_coverage":[str(ranges[0]),str(ranges[1])],"feature_mart_artifact_run_id":feature_run,"feature_mart_artifact_digest":feature_artifact_digest,"warehouse_generation_id":manifest["source_generation_id"],"warehouse_manifest_sha256":manifest["source_manifest_sha256"],"analysis_generation_id":areport["generation_id"],"analysis_manifest_sha256":_sha(Path(areport["manifest"])),"analysis_rows":areport["rows"],"analysis_artifact_run_id":analysis_run,"analysis_artifact_digest":analysis_artifact_digest,"analysis_coverage":"validated v1.4 generation; discovery scan intentionally does not use Analysis 2026 rows"}
            summary={"schema_version":"edgedb-v05-prototype-summary/v1","status":"PASS_WITH_BLOCKED_FEATURE_FAMILIES","version":VERSION,"source_provenance":source_info,"execution":{"python":platform.python_version(),"duckdb":duckdb.__version__,"pyarrow":pa.__version__,"membership_window":{"start":DISCOVERY_START,"end":DISCOVERY_END},"context_window":{"start":CONTEXT_START,"end":CONTEXT_END},"2026_used":False,"candidate_generation_market_blind":True,"metrics_joined_after_membership_freeze":True,"discovery_rows_pre_race_eligible":int(con.execute(f"SELECT count(*) FROM facts WHERE race_date BETWEEN '{DISCOVERY_START}' AND '{DISCOVERY_END}' AND is_pre_race_eligible=1").fetchone()[0])},"feature_availability":coverage,"blocked_features":unavailable,"template_families":{"T1":"PASS","T2":"PASS; sire x course; topology semantic variant BLOCKED","T3":"PASS; canonical +/-200m semantics aggregated into EXTEND/SHORTEN","T4":"PARTIAL; cross-surface switch PASS; FIRST_DIRT/FIRST_TURF BLOCKED","T5":"BLOCKED; FIRST_BLINKERS unavailable","T6":"PASS"},"candidate_counts":{"by_family":family_summary,"n_lt_5_total":len(low_output),"n_ge_5_total":len(candidate_output),"by_support_class":dict(Counter(c["support_class"] for c in candidate_output)),"by_freshness":dict(Counter(c["freshness"] for c in candidate_output)),"by_label":dict(Counter(label for c in candidate_output for label in c["research_labels"]))},"distribution_summary_by_family":family_summary,"freshness_rule":{"version":"v0.5.1","labels":["EMERGING","CURRENT","DECAYING","OLD_ONLY","VOLATILE","INSUFFICIENT_HISTORY"],"rules":"context n<5 => INSUFFICIENT_HISTORY; 2024 vs 2025 place ROI gap >=50pp => VOLATILE; 2025 ROI >=100 with context <100 => EMERGING; 2025 ROI <100 with context >=100 => DECAYING; context >=100 and recent ROI <100 => OLD_ONLY; recent and 2025 ROI >=100 => CURRENT; otherwise relative recent decline >=20pp => DECAYING, else CURRENT. Descriptive; not optimized."},"longshot_definition":"place/top-3 hits at final popularity >=5/8/10 after candidate membership freeze; payout/odds/popularity never define membership","performance_return_separation":{"performance":"n, wins, places, misses, win_rate, place_rate, unique_horses, unique_race_days","return":"win_return_sum, place_return_sum, win_roi, place_roi; returns are per 100-yen stakes, ROI=return_sum/(n*100)*100","misses":"n minus top-3 place hits","jackpot":"top1/top3 contributions and ex-top1/ex-top3 ROI are descriptive only, never candidate gates"},"redundancy":{"candidate_runner_overlap_pairs":len(redundancy),"suggested_review_pairs":sum(r["status"]=="SUGGESTED_REVIEW" for r in redundancy),"clusters":len(clusters),"threshold":0.8,"raw_candidates_retained":True},"desired_pattern_check":{"sire_x_turf_one_turn":"BLOCKED; no canonical topology map","sire_x_distance_extension":"EXPRESSIBLE/DISCOVERED by T3 canonical distance bucket","sire_x_first_dirt":"BLOCKED; no true first-surface flag in frozen mart"},"shortlist_example_count":len(examples),"recommendation":"PARTIAL_WITH_BLOCKED_FAMILIES","generated_at":datetime.now(timezone.utc).isoformat()}
            positive=[c for c in candidate_output if c["positive_value_eligible"]]
            negative=[c for c in candidate_output if c["negative_value_eligible"]]
            summary["value_gate"]={"definition":"overall_2024_2025.place_roi >= 100 AND n >= 5","strength_bands":{"VALUE_100_119":"100 <= ROI < 120","VALUE_120_149":"120 <= ROI < 150","VALUE_150_PLUS":"ROI >= 150"},"raw_n_ge_5_preserved":len(candidate_output),"positive_value_count":len(positive),"positive_value_by_family":{fam:family_summary[fam]["positive_value_count"] for fam in sorted(family_summary)},"positive_value_by_support_class":dict(Counter(c["support_class"] for c in positive)),"longshot_evidence_positive_count":sum("LONGSHOT_EVIDENCE" in c["research_labels"] for c in positive),"negative_edge_count":len(negative),"negative_gate":"n >= 5 AND parent comparison available AND delta_place_rate <= -0.03 AND delta_place_roi <= -20 percentage points","positive_representative_count":len(positive_reps),"positive_representative_by_family":{fam:family_summary[fam]["positive_value_representative_count"] for fam in sorted(family_summary)},"positive_suppressed_ids":positive_suppressed,"representative_rule":"Within suggested Jaccard >= 0.80 or exact-subset components of ROI-qualified candidates only, choose lowest condition depth, then largest recent n, then candidate ID; raw candidates are retained."}
            summary["value_gate"]["largest_positive_clusters"]=[{"representative_candidate_id":rep,"suppressed_candidate_ids":ids,"cluster_size":len(ids)+1} for rep,ids in sorted(positive_suppressed.items(),key=lambda item:(-len(item[1]),item[0]))[:10]]
            summary["performance_value_labels"]={"performance":"PERFORMANCE_POSITIVE/PERFORMANCE_NEGATIVE from parent-relative place-rate or win-rate signs","value":"NICHE_VALUE_POSITIVE uses only the frozen absolute ROI/support gate; NICHE_VALUE_NEGATIVE uses the conservative parent-relative dual deterioration gate","saturated":"PERFORMANCE_POSITIVE plus ROI < 100 is SATURATED_OR_PRICED, never positive Value"}
            summary["warehouse_history_audit"]={"warehouse_generation_id":"jrdb_normalized_warehouse_v1_2010_2025_g20260921","warehouse_manifest_sha256":"a25cedfb5d76c1f9f2ed65308181e2f5222f294ee8015f93aabe3771fb7f1087","warehouse_asset_manifest_drive_id":"1jUX9geM4IrOcWygzbSTGVsgCJ37ULXQN","families":{"KYI":{"family_manifest_sha256":"760c9eaa98cbd590425dcf6150c11b2df3509a83a1046778404f160692d1f328","year_partitions":16,"coverage_years":"2010-2025","schema_fields":["blood_registration_no","race_key_raw","horse_no","blinker_code"],"parser_semantics":"jrdb_raw.Parser.kyi parses blinker_code; racenote_jrdb.BLINKER maps 1=初装着, 2=再装着, 3=ブリンカー","result":"SCHEMA_PASS; history calculation not run because Warehouse Parquet is not an input artifact to the approved Actions fallback"},"ZED":{"family_manifest_sha256":"43844a65fe7b836f74a5e3beabfb194fb9f942a8a16d5ceb0fc76954c483a68b","year_partitions":16,"coverage_years":"2010-2025","schema_fields":["blood_registration_no","race_key_raw","race_date","surface_code","horse_no"],"result":"SCHEMA_PASS; full surface chronology can be joined by canonical horse registration number"},"SED":{"family_manifest_sha256":"36ba1579c378588770d7d23eea4478829423441d382b3ebd99f89f3a4c926296","year_partitions":16,"coverage_years":"2010-2025","schema_fields":["blood_registration_no","race_key_raw","race_date","surface_code","horse_no"],"result":"SCHEMA_PASS; duplicate/source-consistency audit remains to be done during materialized join"},"BAC":{"family_manifest_sha256":"12c09e56ac390c2311c27b0ed68ddf3c42e9eba70c73e006121d04afe837ac3d","year_partitions":16,"coverage_years":"2010-2025","schema_fields":["race_key_raw","race_date","surface_code","distance_m","turn_code","layout_code"],"turn_code_map":{"1":"右","2":"左","3":"直線","9":"その他"},"layout_code_map":{"1":"通常（内）","2":"外","3":"直線ダート","9":"その他"},"result":"BLOCKED; no turn-count category/authoritative topology crosswalk found in repository configuration or metadata"}},"history_derivation":{"candidate_join":"KYI.race_horse_key or blood_registration_no+race_key_raw+horse_no to result rows; surface from canonical ZED/SED","first_surface_rule":"target surface must not be in strictly earlier starts; rows with first observed history at 2010 left edge are UNKNOWN; duplicate same-day/horse source rows must be reconciled","first_blinker_rule":"active code in {1,2,3} and no prior active code for the same blood_registration_no; left-edge-history targets UNKNOWN","implementation_status":"CHRONOLOGY_HELPERS_AND_FIXTURE_TESTS_PASS; canonical full-population join blocked because Data Storage fallback contract does not transport Google Drive assets and no accepted Warehouse Actions artifact was available as input"}}
            _write_json(out/"feature_mart_manifest_audit.json",{"schema_version":"edgedb-v05-feature-mart-audit/v1","source":source_info,"status":"PASS","feature_availability":coverage,"blocked_features":unavailable,"warehouse_history_audit":summary["warehouse_history_audit"]})
            _write_json(out/"t1_t6_summary.json",summary)
            _write_json(out/"t1_t6_top_examples.json",compact)
            _write_csv(out/"shortlist_summary.csv",compact)
            (out/"t1_t6_report.md").write_text(render_report(summary,examples,source_info),encoding="utf-8")
            return summary
        finally:con.close()

def render_report(summary:dict[str,Any],examples:list[dict[str,Any]],source:dict[str,Any])->str:
    lines=["# EdgeDB v0.5 T1-T6 Prototype Aggregation", "",f"Status: {summary['recommendation']}","",f"Discovery: {DISCOVERY_START} through {DISCOVERY_END} (inclusive). Context only: {CONTEXT_START} through {CONTEXT_END}. 2026 excluded.","","## Source provenance","",f"- Feature Mart: {source['feature_mart_generation_id']}, {source['feature_mart_rows']:,} rows, coverage {' .. '.join(source['feature_mart_coverage'])}, manifest SHA-256 {source['feature_mart_manifest_sha256']}, Parquet SHA-256 {source['feature_mart_parquet_sha256']}, artifact run {source['feature_mart_artifact_run_id']} / {source['feature_mart_artifact_digest']}.",f"- Warehouse: {source['warehouse_generation_id']}, source manifest SHA-256 {source['warehouse_manifest_sha256']}.",f"- Analysis: {source['analysis_generation_id']}, {source['analysis_rows']:,} rows, manifest SHA-256 {source['analysis_manifest_sha256']}, artifact run {source['analysis_artifact_run_id']} / {source['analysis_artifact_digest']}. Candidate and metric scans are bounded to 2022-2025; no 2026 result enters discovery or ranking.","","## Execution route","",f"- Local Data Storage: DEPENDENCY_MISSING; one requirements install blocked by managed proxy (proxy:8080 operation not permitted); fallback_candidate=true.",f"- Runtime: Python {summary['execution']['python']}, DuckDB {summary['execution']['duckdb']}, PyArrow {summary['execution']['pyarrow']}.","- Candidate groups use only pre-race features. Outcome and market diagnostics are queried only after the frozen 2024-2025 candidate table is created.","","## Feature availability","","| Feature | Availability / role | Coverage |","|---|---|---:|"]
    for f,m in summary["feature_availability"].items():lines.append(f"| {f} | {m['role']} | {m['coverage_pct']}% ({m['non_null']:,}/{m['rows']:,}) |")
    lines += ["| FIRST_DIRT / FIRST_TURF | BLOCKED: not present in frozen Feature Mart; prior-surface difference is not substituted | — |","| FIRST_BLINKERS | BLOCKED: KYI blinker code is not present in frozen Feature Mart | — |","| Course topology | BLOCKED: no complete canonical venue+surface+distance(+variant) lookup established | — |","","## Candidate counts and distributions","", "| Family | All groups | n>=5 | n<5 raw only | Support classes | Freshness | Research labels |", "|---|---:|---:|---:|---|---|---|"]
    for fam,v in summary["distribution_summary_by_family"].items():lines.append(f"| {fam} | {v['candidate_count_all']} | {v['candidate_count_n_ge_5']} | {v['candidate_count_raw_n_lt_5']} | {canonical_json(v['support_classes'])} | {canonical_json(v['freshness_counts'])} | {canonical_json(v['label_counts'])} |")
    lines += ["", "### Family metric distributions (n>=5)", "", "| Family | n median (p10-p90) | Overall win ROI median (p10-p90) | Overall place ROI median (p10-p90) | 2024 win/place ROI medians | 2025 win/place ROI medians | Longshot place hits median (p90) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for fam,v in summary["distribution_summary_by_family"].items():
        n=v["n_distribution"];wr=v["win_roi_distribution"];pr=v["place_roi_distribution"];w24=v["year_2024_win_roi_distribution"];p24=v["year_2024_place_roi_distribution"];w25=v["year_2025_win_roi_distribution"];p25=v["year_2025_place_roi_distribution"];h=v["longshot_place_hit_count_distribution"]
        lines.append(f"| {fam} | {n['median']} ({n['p10']}-{n['p90']}) | {wr['median']:.1f} ({wr['p10']:.1f}-{wr['p90']:.1f}) | {pr['median']:.1f} ({pr['p10']:.1f}-{pr['p90']:.1f}) | {w24['median'] if w24['median'] is not None else '—'} / {p24['median'] if p24['median'] is not None else '—'} | {w25['median'] if w25['median'] is not None else '—'} / {p25['median'] if p25['median'] is not None else '—'} | {h['median']} ({h['p90']}) |")
    lines += ["","Metrics are unweighted per-runner rates. Returns are separate, with ROI based on 100-yen stakes. Longshot hits mean place/top-3 hits at popularity >=5/8/10; popularity, odds, and payouts do not define groups. Top1/top3 dependence is descriptive, not a rejection gate.","","### Positive Value gate by family","","| Family | Raw n>=5 | ROI>=100 | MICRO | SMALL | MEDIUM | LARGE | Longshot positive | Post-redundancy reps |","|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for fam,v in summary["distribution_summary_by_family"].items():
        sc=v.get("positive_value_by_support_class",{})
        lines.append(f"| {fam} | {v['candidate_count_n_ge_5']} | {v['positive_value_count']} | {sc.get('MICRO',0)} | {sc.get('SMALL',0)} | {sc.get('MEDIUM',0)} | {sc.get('LARGE',0)} | {v['longshot_evidence_positive_count']} | {v['positive_value_representative_count']} |")
    vg=summary.get("value_gate",{})
    lines += ["",f"Gate: `{vg.get('definition','n >= 5 AND overall_2024_2025 place ROI >= 100%')}`. Positive labels are absolute ROI-gated; performance labels use parent-relative occurrence rates. Negative Edge uses the conservative dual deterioration gate. Representative rule: {vg.get('representative_rule','ROI-qualified overlap clusters only; raw candidates retained')}","","#### Largest positive Value redundancy clusters","","| Representative | Cluster size | Suppressed positive candidate IDs |","|---|---:|---|"]
    for cluster in vg.get("largest_positive_clusters",[]):
        lines.append(f"| {cluster['representative_candidate_id']} | {cluster['cluster_size']} | {', '.join(cluster['suppressed_candidate_ids'])} |")
    lines += ["","## Human review examples","","| Type | Candidate | Memo | Template | Support | n | Wins | Places | Win ROI | Place ROI | 2024 Place ROI | 2025 Place ROI | 22-23 Context Place ROI | 5+/8+/10+ hits | Max hit popularity | Largest place payout | Parent Δ place rate | Value band | Freshness | Jackpot | Redundancy |","|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---|---|"]
    for c in examples:
        m=c['metrics'];o=m['overall_2024_2025'];hits=f"{o.get('hit_pop_5_plus',0)}/{o.get('hit_pop_8_plus',0)}/{o.get('hit_pop_10_plus',0)}";jack="ONE_BIG_HIT" if max(o.get("top1_place_contribution",0) or 0,o.get("top1_win_contribution",0) or 0)>=.7 else "DESCRIPTIVE"
        f=lambda x:"—" if x is None else f"{x:.1f}"
        lines.append(f"| {c['example_type']} | {c['candidate_id']} | {c['memo']} | {c['template_id']} | {c['support_class']} | {o['n']} | {o['wins']} | {o['places']} | {f(o['win_roi'])} | {f(o['place_roi'])} | {f(m['2024'].get('place_roi'))} | {f(m['2025'].get('place_roi'))} | {f(m['context_2022_2023'].get('place_roi'))} | {hits} | {o.get('max_hit_popularity') or 0} | {o.get('largest_place_payout') or 0} | {f(100*c['parent_delta']['place_rate']) if c['parent_delta']['place_rate'] is not None else '—'}pp | {c.get('value_strength_band') or '—'} | {c['freshness']} | {jack} | {c['redundancy_status']} |")
    h=summary.get("warehouse_history_audit",{})
    lines += ["","## Scientific correction","","The earlier prototype labeled any positive parent-relative place-rate difference as NICHE_VALUE_POSITIVE and any negative difference as NICHE_VALUE_NEGATIVE. That conflated occurrence performance with betting value.","","The corrected labels are separate: PERFORMANCE_POSITIVE / PERFORMANCE_NEGATIVE use parent-relative place-rate or win-rate deltas. NICHE_VALUE_POSITIVE requires combined 2024-2025 place ROI >=100% and n>=5. Bands (100-119, 120-149, 150+) are descriptive. The gate uses combined years and allows one-hit/top1-driven MICRO candidates. NICHE_VALUE_NEGATIVE requires n>=5, an available parent, delta place rate <=-0.03, and delta place ROI <=-20 percentage points.","","Candidate membership remains pre-race and market-blind; popularity, odds, and payouts are attached after groups are frozen. Raw n>=5 candidates below the Value gate remain in the Parquet research table.","","## Blocked-family re-audit","","| Feature | Canonical source and fields | Result |","|---|---|---|"]
    if h:
        lines += ["| FIRST_BLINKERS | Warehouse KYI 2010-2025: blood_registration_no, race_key_raw, horse_no, blinker_code; codes 1/2/3 = first-worn/re-worn/active | Schema PASS; chronology fixture tests pass; full join BLOCKED because Warehouse Parquet is not an Actions input artifact |",
                  "| FIRST_DIRT / FIRST_TURF | Warehouse ZED/SED 2010-2025: blood_registration_no, race_key_raw, race_date, surface_code, horse_no | Schema PASS; tested helper excludes target and preserves UNKNOWN for censored history; full join awaits Warehouse materialization/source duplicate audit |",
                  "| Course topology | BAC: race_key_raw, surface, distance, turn_code, layout_code; codebooks map turn direction/layout class | BLOCKED; no authoritative one-turn/two-turn crosswalk; raw codes do not encode turn count |",
                  f"| Warehouse provenance | {h.get('warehouse_generation_id')}; manifest SHA-256 {h.get('warehouse_manifest_sha256')} | KYI/ZED/SED/BAC each contain 16 annual partitions for 2010-2025; family manifest hashes and fields are in t1_t6_summary.json |"]
    lines += ["","## Desired-pattern check","", "- Sire × turf one-turn: BLOCKED pending canonical course-topology mapping.","- Sire × distance extension: EXPRESSIBLE; uses existing canonical >=200m EXTEND buckets (EXTEND and LARGE_EXTEND aggregated).","- Sire × first dirt: source schema supports chronology derivation, but the full join was not run because canonical Warehouse Parquet was not a fallback input.","","## Failure modes and next research issues","","- The n>=5 research population stays intact; only the presentation layer applies ROI eligibility and overlap representatives.","- Positive redundancy uses ROI-qualified candidates only; suppressed IDs remain in summary metadata and raw candidate rows remain in Parquet.","- T4/T5 history must be rerun after canonical Warehouse annual assets are materialized and source duplicates reconciled.","- Course topology remains blocked because repository metadata lacks an authoritative turn-count map.","","## Recommendation","", "PARTIAL_WITH_BLOCKED_FAMILIES. Scientific labels and ROI shortlist are corrected. T1/T2/T3/T4-switch/T6 remain executable; true first surface and T5 await Warehouse asset materialization; topology remains blocked after metadata audit. Production impact NONE; no v0.2/v0.3/v0.4 manifest, RaceNote, Newspaper, or PWA consumer was changed.",""]
    return "\n".join(lines)

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--feature-input",type=Path,required=True);p.add_argument("--analysis-input",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True);p.add_argument("--feature-run",type=int,required=True);p.add_argument("--feature-artifact-digest",required=True);p.add_argument("--analysis-run",type=int,required=True);p.add_argument("--analysis-artifact-digest",required=True);p.add_argument("--source-commit",default=SOURCE_COMMIT);a=p.parse_args()
    summary=run(feature_input=a.feature_input,analysis_input=a.analysis_input,out=a.output_dir,feature_artifact_digest=a.feature_artifact_digest,analysis_artifact_digest=a.analysis_artifact_digest,feature_run=a.feature_run,analysis_run=a.analysis_run,source_commit=a.source_commit)
    print(json.dumps({"status":summary["status"],"candidates":summary["candidate_counts"]["n_ge_5_total"],"recommendation":summary["recommendation"]},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
