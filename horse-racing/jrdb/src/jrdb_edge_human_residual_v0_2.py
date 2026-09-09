#!/usr/bin/env python3
"""Leakage-safe HUMAN Edge horse-quality residual support for v0.2.

Horse quality is represented by pre-race IDM rank inside each race. Expected
place probability is calibrated year-by-year using only strictly prior calendar
years, with hierarchical shrinkage by surface / field-size / quality decile.
No final odds, final popularity, target-year outcomes, or post-race features are
used to build the expectation for a target year.
"""
from __future__ import annotations

import hashlib
import math
import random
import sqlite3
from pathlib import Path
from typing import Any, Mapping

MODEL_VERSION = "HUMAN_PRE_IDM_EXPANDING_V1"
BASELINE_MODE = "human_residual_v1"
BROAD_PRIOR_STRENGTH = 40.0
GROUP_PRIOR_STRENGTH = 25.0


def _field_bucket_sql() -> str:
    return "CASE WHEN declared_field_size<=7 THEN 'LE7' WHEN declared_field_size<=11 THEN '8_11' WHEN declared_field_size<=15 THEN '12_15' ELSE '16_PLUS' END"


def calibrate_horse_quality(connection: sqlite3.Connection) -> dict[str, Any]:
    """Populate pre-race quality rank and prior-only expected place probability."""
    connection.executescript("""
      DROP TABLE IF EXISTS temp.quality_rank_tmp;
      CREATE TEMP TABLE quality_rank_tmp AS
      WITH ranked AS (
        SELECT race_key,horse_no,
          RANK() OVER(PARTITION BY race_key ORDER BY pre_idm DESC) AS qrank,
          COUNT(*) OVER(PARTITION BY race_key) AS qn
        FROM edge_runner_fact
        WHERE calculation_status='ELIGIBLE' AND pre_idm IS NOT NULL
      )
      SELECT race_key,horse_no,
        CASE WHEN qn<=1 THEN 0.0 ELSE (qrank-1.0)/(qn-1.0) END AS rank_pct,
        CASE
          WHEN qn<=1 THEN 0
          WHEN CAST(((qrank-1.0)/(qn-1.0))*10 AS INTEGER)>=10 THEN 9
          ELSE CAST(((qrank-1.0)/(qn-1.0))*10 AS INTEGER)
        END AS quality_bucket
      FROM ranked;
      CREATE INDEX temp.ix_quality_rank_tmp ON quality_rank_tmp(race_key,horse_no);
    """)
    connection.execute("""
      UPDATE edge_runner_fact
      SET horse_quality_rank_pct=(SELECT rank_pct FROM quality_rank_tmp q WHERE q.race_key=edge_runner_fact.race_key AND q.horse_no=edge_runner_fact.horse_no),
          horse_quality_bucket=(SELECT quality_bucket FROM quality_rank_tmp q WHERE q.race_key=edge_runner_fact.race_key AND q.horse_no=edge_runner_fact.horse_no)
      WHERE EXISTS(SELECT 1 FROM quality_rank_tmp q WHERE q.race_key=edge_runner_fact.race_key AND q.horse_no=edge_runner_fact.horse_no)
    """)

    years = [int(r[0]) for r in connection.execute(
        "SELECT DISTINCT substr(race_date,1,4) FROM edge_runner_fact WHERE calculation_status='ELIGIBLE' ORDER BY 1"
    ) if r[0]]
    calibrated = 0
    fs_expr = _field_bucket_sql()
    for year in years:
        prior_year = year - 1
        global_row = connection.execute(
            "SELECT COUNT(*),SUM(label_place_hit) FROM edge_runner_fact WHERE calculation_status='ELIGIBLE' AND horse_quality_bucket IS NOT NULL AND CAST(substr(race_date,1,4) AS INTEGER)<?",
            (year,),
        ).fetchone()
        prior_n = int(global_row[0] or 0)
        if prior_n == 0:
            continue
        global_rate = float(global_row[1] or 0) / prior_n
        broad: dict[int, tuple[int, int]] = {}
        for qb,n,h in connection.execute(
            "SELECT horse_quality_bucket,COUNT(*),SUM(label_place_hit) FROM edge_runner_fact WHERE calculation_status='ELIGIBLE' AND horse_quality_bucket IS NOT NULL AND CAST(substr(race_date,1,4) AS INTEGER)<? GROUP BY horse_quality_bucket",
            (year,),
        ):
            broad[int(qb)] = (int(n), int(h or 0))
        groups: dict[tuple[str,str,int], tuple[int,int]] = {}
        sql = f"SELECT surface_code,{fs_expr} AS fsb,horse_quality_bucket,COUNT(*),SUM(label_place_hit) FROM edge_runner_fact WHERE calculation_status='ELIGIBLE' AND horse_quality_bucket IS NOT NULL AND CAST(substr(race_date,1,4) AS INTEGER)<? GROUP BY surface_code,fsb,horse_quality_bucket"
        for surface,fsb,qb,n,h in connection.execute(sql,(year,)):
            groups[(str(surface),str(fsb),int(qb))] = (int(n),int(h or 0))
        target_keys = connection.execute(
            f"SELECT DISTINCT surface_code,{fs_expr} AS fsb,horse_quality_bucket FROM edge_runner_fact WHERE calculation_status='ELIGIBLE' AND horse_quality_bucket IS NOT NULL AND CAST(substr(race_date,1,4) AS INTEGER)=?",
            (year,),
        ).fetchall()
        for surface,fsb,qb in target_keys:
            qb_i=int(qb)
            bn,bh=broad.get(qb_i,(0,0))
            broad_rate=(bh + BROAD_PRIOR_STRENGTH*global_rate)/(bn+BROAD_PRIOR_STRENGTH)
            gn,gh=groups.get((str(surface),str(fsb),qb_i),(0,0))
            expected=(gh + GROUP_PRIOR_STRENGTH*broad_rate)/(gn+GROUP_PRIOR_STRENGTH)
            expected=max(0.001,min(0.999,float(expected)))
            cur=connection.execute(
                f"UPDATE edge_runner_fact SET horse_quality_expected_place=?,horse_quality_place_residual=label_place_hit-?,horse_quality_model_version=?,horse_quality_model_cutoff_year=? WHERE calculation_status='ELIGIBLE' AND horse_quality_bucket=? AND surface_code=? AND {fs_expr}=? AND CAST(substr(race_date,1,4) AS INTEGER)=?",
                (expected,expected,MODEL_VERSION,prior_year,qb_i,str(surface),str(fsb),year),
            )
            calibrated += int(cur.rowcount or 0)
    connection.commit()
    return {
        "model_version": MODEL_VERSION,
        "calibrated_rows": calibrated,
        "first_calibrated_year": min((y for y in years if y>min(years)), default=None) if years else None,
        "last_year": max(years) if years else None,
    }


def _where(values: Mapping[str, Any], *, start_date: str|None=None, end_date: str|None=None) -> tuple[str,list[Any]]:
    allowed={"jockey_code","trainer_code","venue_code","distance_m","surface_code"}
    parts=["calculation_status='ELIGIBLE'","horse_quality_expected_place IS NOT NULL"]
    params:list[Any]=[]
    for field,value in values.items():
        if field not in allowed:
            raise ValueError(f"unsupported HUMAN residual field: {field}")
        parts.append(f"{field}=?")
        params.append(value)
    if start_date is not None:
        parts.append("race_date>=?"); params.append(start_date)
    if end_date is not None:
        parts.append("race_date<=?"); params.append(end_date)
    return " AND ".join(parts),params


def human_metrics(connection: sqlite3.Connection, values: Mapping[str,Any], *, start_date: str|None=None, end_date: str|None=None) -> dict[str,Any]:
    where,params=_where(values,start_date=start_date,end_date=end_date)
    row=connection.execute("""SELECT COUNT(*),COUNT(DISTINCT horse_id),COUNT(DISTINCT race_key),MIN(race_date),MAX(race_date),AVG(label_win_hit),AVG(label_place_hit),AVG(horse_quality_expected_place),AVG(horse_quality_place_residual),SUM(COALESCE(label_win_payout,0))/(100.0*COUNT(*)),SUM(COALESCE(label_place_payout,0))/(100.0*COUNT(*)),SUM(COALESCE(label_win_payout,0)+COALESCE(label_place_payout,0)) FROM edge_runner_fact WHERE """+where,params).fetchone()
    n=int(row[0] or 0)
    if n==0:
        return {"sample_n":0,"unique_horses":0,"unique_races":0,"performance_lift":None,"place_roi_vs_baseline":None}
    largest_horse=connection.execute("SELECT MAX(n) FROM (SELECT COUNT(*) n FROM edge_runner_fact WHERE "+where+" GROUP BY horse_id)",params).fetchone()[0] or 0
    returns=[r[0] for r in connection.execute("SELECT COALESCE(label_win_payout,0)+COALESCE(label_place_payout,0) payout FROM edge_runner_fact WHERE "+where+" ORDER BY payout DESC LIMIT 3",params)]
    total=float(row[11] or 0)
    actual=float(row[6]) if row[6] is not None else None
    expected=float(row[7]) if row[7] is not None else None
    lift=(actual/expected) if actual is not None and expected not in (None,0) else None
    return {
        "sample_n":n,"unique_horses":int(row[1] or 0),"unique_races":int(row[2] or 0),
        "first_date":row[3],"last_date":row[4],"win_rate":row[5],"place_rate":row[6],
        "win_roi":row[9],"place_roi":row[10],"baseline_sample_n":n,
        "baseline_first_date":row[3],"baseline_last_date":row[4],"baseline_place_rate":row[7],
        "baseline_place_roi":None,"performance_lift":lift,"place_roi_vs_baseline":None,
        "horse_quality_residual_mean":row[8],
        "largest_horse_sample_share":float(largest_horse)/n,
        "largest_return_share":float(returns[0])/total if returns and total>0 else None,
        "top3_return_share":sum(float(v) for v in returns)/total if total>0 else None,
    }


def discover_human(mart_path: str|Path, template: Mapping[str,Any], policy_selection: Any, template_version: str, as_of_date: str) -> list[dict[str,Any]]:
    anchor_fields=list(template["anchor_fields"]); modifier_fields=list(template["modifier_fields"])
    fields=anchor_fields+modifier_fields
    for f in fields:
        if f not in {"jockey_code","trainer_code","venue_code","distance_m","surface_code"}:
            raise ValueError(f"unsupported HUMAN template field: {f}")
    group=",".join(fields)
    nonnull=" AND ".join(f"{f} IS NOT NULL AND CAST({f} AS TEXT)<>''" for f in fields) or "1=1"
    con=sqlite3.connect(mart_path); con.row_factory=sqlite3.Row
    try:
        sql=f"""SELECT {group},COUNT(*) sample_n,COUNT(DISTINCT horse_id) unique_horses,COUNT(DISTINCT race_key) unique_races,MIN(race_date) first_date,MAX(race_date) last_date,AVG(label_win_hit) win_rate,AVG(label_place_hit) place_rate,AVG(horse_quality_expected_place) expected_place,AVG(horse_quality_place_residual) residual_mean,SUM(COALESCE(label_win_payout,0))/(100.0*COUNT(*)) win_roi,SUM(COALESCE(label_place_payout,0))/(100.0*COUNT(*)) place_roi,MAX(COALESCE(label_win_payout,0)+COALESCE(label_place_payout,0)) max_return FROM edge_runner_fact WHERE calculation_status='ELIGIBLE' AND horse_quality_expected_place IS NOT NULL AND {nonnull} GROUP BY {group}"""
        output=[]
        for row in con.execute(sql):
            identity={f:row[f] for f in fields}
            anchor={f:row[f] for f in anchor_fields}; modifiers={f:row[f] for f in modifier_fields}
            n=int(row["sample_n"]); actual=row["place_rate"]; expected=row["expected_place"]
            lift=(float(actual)/float(expected)) if actual is not None and expected not in (None,0) else None
            combined=(float(row["win_roi"] or 0)+float(row["place_roi"] or 0))*100*n
            largest=float(row["max_return"] or 0)/combined if combined>0 else None
            payload=(template["template_id"]+"|"+"|".join(f"{k}={identity[k]}" for k in sorted(identity)))
            cid="EDGE-CAND-"+hashlib.sha256(payload.encode()).hexdigest()[:20].upper()
            direction=0 if lift is None else (1 if lift>1 else (-1 if lift<1 else 0))
            output.append({
                "candidate_id":cid,"template_id":template["template_id"],"template_version":template_version,
                "family":"HUMAN","anchor_type":template["anchor_type"],"anchor":anchor,"modifiers":modifiers,
                "baseline":BASELINE_MODE,"policy_id":policy_selection.policy_id,"validation_class":policy_selection.validation_class,
                "policy_reason":policy_selection.reason,"initial_stage":"WATCH","as_of_date":as_of_date,
                "first_observed_date":row["first_date"],"last_observed_date":row["last_date"],
                "sample_n":n,"unique_horses":int(row["unique_horses"]),"unique_races":int(row["unique_races"]),
                "win_rate":row["win_rate"],"place_rate":actual,"win_roi":row["win_roi"],"place_roi":row["place_roi"],
                "baseline_sample_n":n,"baseline_place_rate":expected,"baseline_place_roi":None,
                "performance_lift":lift,"place_roi_vs_baseline":None,"raw_performance_direction":direction,
                "raw_value_direction":0,"largest_return_share_approx":largest,"promotion_status":"NOT_VALIDATED",
                "horse_quality_model_version":MODEL_VERSION,"horse_quality_residual_mean":row["residual_mean"],
            })
        return output
    finally:
        con.close()


def _directional_p(z: float, direction: str) -> float:
    cdf=0.5*(1.0+math.erf(z/math.sqrt(2.0)))
    if direction=="POSITIVE": return max(0.0,min(1.0,1.0-cdf))
    if direction=="NEGATIVE": return max(0.0,min(1.0,cdf))
    return 1.0


def evaluate_human_statistical(mart_path: str|Path, candidate: Mapping[str,Any], temporal_result: Mapping[str,Any], *, bootstrap_samples: int=400) -> dict[str,Any]:
    values={**candidate["anchor"],**candidate["modifiers"]}
    where,params=_where(values)
    con=sqlite3.connect(mart_path)
    try:
        clusters=[(int(n),float(s or 0)) for n,s in con.execute("SELECT COUNT(*),SUM(horse_quality_place_residual) FROM edge_runner_fact WHERE "+where+" GROUP BY race_date ORDER BY race_date",params)]
    finally:
        con.close()
    n=sum(x[0] for x in clusters); total=sum(x[1] for x in clusters)
    mean=total/n if n else None
    direction=str(temporal_result.get("performance_signal","NEUTRAL"))
    p=None
    if mean is not None and direction!="NEUTRAL" and len(clusters)>=2:
        scores=[s-cn*mean for cn,s in clusters]
        var=(len(clusters)/(len(clusters)-1))*sum(v*v for v in scores)/(n*n)
        se=math.sqrt(max(0.0,var))
        p=_directional_p(mean/se,direction) if se>0 else 1.0
    low=high=None
    if bootstrap_samples>0 and len(clusters)>=2:
        seed=int(hashlib.sha256(str(candidate["candidate_id"]).encode()).hexdigest()[:16],16)
        rng=random.Random(seed); vals=[]; g=len(clusters)
        for _ in range(bootstrap_samples):
            sampled=[clusters[rng.randrange(g)] for _ in range(g)]
            sn=sum(x[0] for x in sampled); ss=sum(x[1] for x in sampled)
            if sn: vals.append(ss/sn)
        vals.sort()
        if vals:
            def q(pct:float)->float:
                pos=(len(vals)-1)*pct; lo_i=int(math.floor(pos)); hi_i=int(math.ceil(pos))
                if lo_i==hi_i:return vals[lo_i]
                w=pos-lo_i; return vals[lo_i]*(1-w)+vals[hi_i]*w
            low,high=q(0.025),q(0.975)
    return {
        "candidate_id":candidate["candidate_id"],"hypothesis_family":candidate["template_id"],
        "temporal_status":temporal_result["status"],"performance_signal":direction,"value_signal":"NEUTRAL",
        "candidate_n":n,"complement_n":0,"cluster_count":len(clusters),"performance_effect_abs":mean,
        "value_effect_abs":None,"performance_p_value":p,"value_p_value":None,
        "performance_ci_low":low,"performance_ci_high":high,"value_ci_low":None,"value_ci_high":None,
        "multiple_testing_version":"BH_TEMPLATE_SIGNAL_HUMAN_RESIDUAL_V1","bootstrap_samples":bootstrap_samples,
    }
