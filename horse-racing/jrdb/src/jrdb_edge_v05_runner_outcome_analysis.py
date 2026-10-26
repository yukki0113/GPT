#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jrdb_raw import Parser, canonical_members, read_fixed_records

class AnalysisError(RuntimeError):
    pass

def load_candidate_labels(path: Path) -> dict[str,str]:
    out={}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["candidate_id"]]=r["oos_label"]
    if len(out)!=1620:
        raise AnalysisError(f"expected 1620 candidate labels, got {len(out)}")
    return out

def load_sed_population(root: Path) -> tuple[dict[tuple[str,int],str], list[dict[str,Any]]]:
    parser=Parser(); names={}; population=[]
    seen=set()
    for ap in sorted(root.rglob("SED26????.zip")):
        with zipfile.ZipFile(ap) as zf:
            for member in canonical_members(zf,"SED"):
                for rec in read_fixed_records(zf,member,"SED"):
                    r=parser.sed(rec)
                    race_key=str(r["race_key_raw"]); horse_no=int(r["horse_no"])
                    key=(race_key,horse_no)
                    if key in seen:
                        raise AnalysisError(f"duplicate SED population row: {key}")
                    seen.add(key)
                    name=str(r.get("horse_name") or "").strip()
                    names[key]=name
                    abnormal=str(r.get("abnormal_code") or "")
                    eligible=r.get("finish") is not None and abnormal in {"","0"}
                    population.append({
                        "race_horse_key":race_key+f"{horse_no:02d}",
                        "race_key":race_key,"horse_no":horse_no,"horse_name":name,
                        "finish":r.get("finish"),"abnormal_code":abnormal,
                        "popularity":r.get("final_popularity"),
                        "win_payout":int(r.get("win_payout") or 0),
                        "place_payout":int(r.get("place_payout") or 0),
                        "eligible":eligible,
                        "win_hit":bool(eligible and int(r.get("finish") or 999)==1),
                        "place_hit":bool(eligible and int(r.get("place_payout") or 0)>0),
                    })
    if len(population)!=36706:
        raise AnalysisError(f"expected 36706 SED population rows, got {len(population)}")
    return names,population

def load_matches(path: Path) -> list[dict[str,Any]]:
    import pyarrow.parquet as pq
    rows=pq.read_table(path).to_pylist()
    if len(rows)!=15330:
        raise AnalysisError(f"expected 15330 signal rows, got {len(rows)}")
    return rows

def aggregate_runners(rows:list[dict[str,Any]], labels:dict[str,str], horse_names:dict[tuple[str,int],str]) -> list[dict[str,Any]]:
    groups=defaultdict(list)
    for r in rows:
        groups[r["race_horse_key"]].append(r)
    out=[]
    for key,rs in sorted(groups.items()):
        # outcome columns must be identical across duplicate signal rows
        fields=("race_date","race_key","horse_no","finish","abnormal_code","final_win_popularity",
                "final_win_odds","win_payout","place_payout","eligible_oos","win_hit","place_hit")
        for f in fields:
            vals={r.get(f) for r in rs}
            if len(vals)>1:
                raise AnalysisError(f"inconsistent outcome {f} for {key}: {vals}")
        first=rs[0]
        cids=sorted({str(r["candidate_id"]) for r in rs})
        fams=sorted({str(r["family"]) for r in rs})
        labs=[labels[c] for c in cids]
        lc=Counter(labs)
        out.append({
            "race_horse_key":key,
            "race_date":first["race_date"],
            "race_key":first["race_key"],
            "horse_no":int(first["horse_no"]),
            "horse_name":horse_names.get((str(first["race_key"]),int(first["horse_no"])),""),
            "finish":first.get("finish"),
            "abnormal_code":first.get("abnormal_code"),
            "popularity":first.get("final_win_popularity"),
            "win_odds":first.get("final_win_odds"),
            "win_payout":int(first.get("win_payout") or 0),
            "place_payout":int(first.get("place_payout") or 0),
            "eligible":bool(first.get("eligible_oos")),
            "win_hit":bool(first.get("win_hit")),
            "place_hit":bool(first.get("place_hit")),
            "signal_count":len(cids),
            "family_count":len(fams),
            "families":"+".join(fams),
            "candidate_ids":"|".join(cids),
            "labels":"+".join(sorted(set(labs))),
            "confirmed_count":lc["CONFIRMED"],
            "plausible_count":lc["STILL_PLAUSIBLE"],
            "decaying_count":lc["DECAYING"],
            "contradicted_count":lc["CONTRADICTED"],
            "insufficient_count":lc["INSUFFICIENT_OOS"],
            "has_confirmed":lc["CONFIRMED"]>0,
            "has_plausible":lc["STILL_PLAUSIBLE"]>0,
            "has_contradicted":lc["CONTRADICTED"]>0,
            "all_contradicted":lc["CONTRADICTED"]==len(cids),
        })
    if len(out)!=12633:
        raise AnalysisError(f"expected 12633 unique matched runners, got {len(out)}")
    return out

def metrics(rows:list[dict[str,Any]]) -> dict[str,Any]:
    elig=[r for r in rows if r["eligible"]]
    n=len(elig)
    wins=sum(r["win_hit"] for r in elig)
    places=sum(r["place_hit"] for r in elig)
    wr=sum(r["win_payout"] for r in elig)
    pr=sum(r["place_payout"] for r in elig)
    return {
        "matched_runners":len(rows),
        "eligible_runners":n,
        "wins":wins,
        "places":places,
        "win_rate":wins/n if n else None,
        "place_rate":places/n if n else None,
        "win_roi":wr/n if n else None,
        "place_roi":pr/n if n else None,
        "avg_popularity":sum(int(r["popularity"]) for r in elig if r.get("popularity"))/sum(1 for r in elig if r.get("popularity")) if any(r.get("popularity") for r in elig) else None,
    }

def breakdown(rows:list[dict[str,Any]], keyfn) -> dict[str,Any]:
    g=defaultdict(list)
    for r in rows:g[str(keyfn(r))].append(r)
    return {k:metrics(v) for k,v in sorted(g.items())}

def analyze(runners:list[dict[str,Any]], population:list[dict[str,Any]]) -> dict[str,Any]:
    sig=lambda r: "1" if r["signal_count"]==1 else "2" if r["signal_count"]==2 else "3_PLUS"
    famcnt=lambda r:"1" if r["family_count"]==1 else "2" if r["family_count"]==2 else "3_PLUS"
    def popband(r):
        p=r.get("popularity")
        if p is None:return "UNKNOWN"
        p=int(p)
        if p<=3:return "1_3"
        if p<=7:return "4_7"
        if p<=9:return "8_9"
        return "10_PLUS"
    fam={}
    for f in ("T1","T2","T3","T4","T5","T6"):
        fam[f]=metrics([r for r in runners if f in r["families"].split("+")])
    tiers={
        "HAS_CONFIRMED":metrics([r for r in runners if r["has_confirmed"]]),
        "HAS_PLAUSIBLE":metrics([r for r in runners if r["has_plausible"]]),
        "HAS_CONTRADICTED":metrics([r for r in runners if r["has_contradicted"]]),
        "ALL_CONTRADICTED":metrics([r for r in runners if r["all_contradicted"]]),
        "NO_CONFIRMED_OR_PLAUSIBLE":metrics([r for r in runners if not r["has_confirmed"] and not r["has_plausible"]]),
    }
    long8=sorted([r for r in runners if r["eligible"] and r["place_hit"] and (r.get("popularity") or 0)>=8],
                 key=lambda r:(-r["place_payout"],-int(r["popularity"]),r["race_date"]))[:30]
    long10=sorted([r for r in runners if r["eligible"] and r["place_hit"] and (r.get("popularity") or 0)>=10],
                  key=lambda r:(-r["place_payout"],-int(r["popularity"]),r["race_date"]))[:30]
    # signal count x popularity, to see whether stacking adds value within similar market rank
    cross={}
    for sb in ("1","2","3_PLUS"):
        for pb in ("1_3","4_7","8_9","10_PLUS"):
            subset=[r for r in runners if sig(r)==sb and popband(r)==pb]
            cross[f"{sb}__{pb}"]=metrics(subset)
    matched_keys={r["race_horse_key"] for r in runners}
    unmatched=[r for r in population if r["race_horse_key"] not in matched_keys]
    all_pop=breakdown(population,popband)
    unmatched_pop=breakdown(unmatched,popband)
    edge_pop=breakdown(runners,popband)
    popularity_lift={}
    for band in ("1_3","4_7","8_9","10_PLUS"):
        e=edge_pop.get(band,{}); u=unmatched_pop.get(band,{})
        popularity_lift[band]={
            "edge_place_rate":e.get("place_rate"),"nonedge_place_rate":u.get("place_rate"),
            "place_rate_delta":(e.get("place_rate")-u.get("place_rate")) if e.get("place_rate") is not None and u.get("place_rate") is not None else None,
            "edge_win_rate":e.get("win_rate"),"nonedge_win_rate":u.get("win_rate"),
            "win_rate_delta":(e.get("win_rate")-u.get("win_rate")) if e.get("win_rate") is not None and u.get("win_rate") is not None else None,
        }
    return {
        "status":"PASS",
        "overall":metrics(runners),
        "population_all":metrics(population),
        "population_nonedge":metrics(unmatched),
        "popularity_matched_vs_nonedge":popularity_lift,
        "by_signal_count":breakdown(runners,sig),
        "by_distinct_family_count":breakdown(runners,famcnt),
        "by_popularity_band":breakdown(runners,popband),
        "by_family_presence":fam,
        "by_oos_tier_presence":tiers,
        "signal_count_x_popularity":cross,
        "top_pop8_plus_place_hits":long8,
        "top_pop10_plus_place_hits":long10,
        "notes":{
            "unit":"one race runner counted once regardless of number of Edge signals",
            "roi":"100-yen hypothetical one-bet-per-matched-runner diagnostic, not a recommended betting strategy",
            "family_presence":"overlapping groups",
            "tier_presence":"overlapping except ALL_CONTRADICTED",
        }
    }

def write_csv(path:Path,rows:list[dict[str,Any]]):
    if not rows:return
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--joined-matches",type=Path,required=True)
    ap.add_argument("--candidate-eval",type=Path,required=True)
    ap.add_argument("--sed-root",type=Path,required=True)
    ap.add_argument("--output-root",type=Path,required=True)
    args=ap.parse_args()
    args.output_root.mkdir(parents=True,exist_ok=True)
    rows=load_matches(args.joined_matches)
    labels=load_candidate_labels(args.candidate_eval)
    names,population=load_sed_population(args.sed_root)
    runners=aggregate_runners(rows,labels,names)
    result=analyze(runners,population)
    write_csv(args.output_root/"v05_2026_runner_outcomes.csv",runners)
    (args.output_root/"v05_2026_runner_outcome_analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True,default=str)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,default=str))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
