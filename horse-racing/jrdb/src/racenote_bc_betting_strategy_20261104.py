#!/usr/bin/env python3
"""Read-only RaceNote v055 r6 fixed-strategy historical comparison.

Uses the existing canonical jrdb_result_query library and immutable Git Freeze.
Never changes confidence, marks, or prediction assets.
"""
from __future__ import annotations
import argparse
import csv
import itertools
import json
from collections import Counter
from pathlib import Path
from jrdb_result_query import query_results
from racenote_bc_boundary_audit_20261104 import DATES, EXPECTED, GENERATION, CONTRACT, classify

STRATEGIES = (
    "win_honmei_1",
    "quinella_honmei_4",
    "quinella_box_10",
    "trio_honmei_6",
    "trio_honmei_second_3",
    "trio_box_10",
)
BET_TYPES = {"win_honmei_1":"win",
             "quinella_honmei_4":"quinella",
             "quinella_box_10":"quinella",
             "trio_honmei_6":"trio",
             "trio_honmei_second_3":"trio",
             "trio_box_10":"trio"}

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def calc_tickets(marks):
    a,b,c,d,e=tuple(map(int,marks))
    others=(b,c,d,e)
    return {
        "win_honmei_1":{(a,)},
        "quinella_honmei_4":{tuple(sorted((a,x))) for x in others},
        "quinella_box_10":{tuple(sorted(x)) for x in itertools.combinations(marks,2)},
        "trio_honmei_6":{tuple(sorted((a,x,y))) for x,y in itertools.combinations(others,2)},
        "trio_honmei_second_3":{tuple(sorted((a,b,x))) for x in (c,d,e)},
        "trio_box_10":{tuple(sorted(x)) for x in itertools.combinations(marks,3)}
    }

def score_strategy(race,strategy,tickets):
    payout_rows=race["payouts"].get(BET_TYPES[strategy])
    if not isinstance(payout_rows,list):
        raise RuntimeError("missing canonical HJC payout group "+str((race["race_key"],strategy)))
    collected=0
    hit_count=0
    for item in payout_rows:
        actual=tuple(sorted(map(int,item["numbers"])))
        if actual in tickets:
            collected+=int(item["payout_yen"])
            hit_count+=1
    stake=len(tickets)*100
    return {"hit":int(hit_count>0),"hit_ticket_count":hit_count,
            "stake_yen":stake,"return_yen":collected,"profit_yen":collected-stake,
            "tickets":len(tickets)}

def stats(records,strategy):
    n=len(records)
    stake=sum(r[strategy]["stake_yen"] for r in records)
    ret=sum(r[strategy]["return_yen"] for r in records)
    hits=sum(r[strategy]["hit"] for r in records)
    return {"races":n,"hits":hits,"hit_rate":round(hits/n,4) if n else None,
            "hit_count_ticket":sum(r[strategy]["hit_ticket_count"] for r in records),
            "stake_yen":stake,"return_yen":ret,"profit_yen":ret-stake,
            "roi_pct":round(100*ret/stake,2) if stake else None,
            "per_race_net_yen":round((ret-stake)/n,2) if n else None}

def strat_table(rows):
    return {s:stats(rows,s) for s in STRATEGIES}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo-root",required=True,type=Path)
    p.add_argument("--warehouse-root",required=True,type=Path)
    p.add_argument("--warehouse-manifest",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    args=p.parse_args()
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    frozen={}
    cts=Counter()
    freeze_checks=[]
    # All eligible pre-result rows fixed before reading race outcomes.
    for n,date in DATES.items():
        base=args.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{date.replace('-','')}/v055"
        preds=read(base/"frozen/records.json")
        conf=read(base/"confidence_frozen/records.json")
        if len(preds)!=len(conf):
            raise RuntimeError("Freeze cardinality mismatch "+str(n))
        pred_map={}
        for r in preds:
            if r.get("contract_revision")!=CONTRACT or r.get("target_date")!=date:
                raise RuntimeError("wrong frozen contract/date "+str(n))
            key=(date,r["venue"],int(r["race_no"]))
            if key in pred_map:
                raise RuntimeError("duplicate frozen prediction "+str(key))
            pred_map[key]=r
        for c in conf:
            key=(date,c["venue"],int(c["race_no"]))
            pr=pred_map.get(key)
            if pr is None or key in frozen:
                raise RuntimeError("missing or duplicate confidence "+str(key))
            marks=pr["decision_core"]["marks"]
            if len(marks)!=5 or len(set(marks))!=5 or int(c["honmei"])!=int(marks[0]):
                raise RuntimeError("bad five marks / confidence mismatch "+str(key))
            grade=c["confidence"]
            if grade not in EXPECTED:
                raise RuntimeError("bad grade")
            flags,primary=classify(c.get("reason") or "")
            frozen[key]={"btday":f"BTDAY-{n:04d}","date":date,"venue":c["venue"],"race_no":int(c["race_no"]),
                         "grade":grade,"marks":list(map(int,marks)), "cohort":"early" if n<=135 else "late",
                         "reason":c["reason"],"primary_reason":primary,
                         **{k:int(v) for k,v in flags.items()}}
            cts[grade]+=1
        if len(pred_map)!=len(conf):
            raise RuntimeError("incomplete frozen roster "+str(n))
        freeze_checks.append({"btday":f"BTDAY-{n:04d}","date":date,"count":len(conf)})
    if dict(cts)!=EXPECTED or len(frozen)!=900:
        raise RuntimeError("cohort mismatch "+str(cts))
    results={}
    query_checks=[]
    for date in sorted(set(DATES.values())):
        obj=query_results(date=date,source="warehouse",warehouse_root=args.warehouse_root,
                          warehouse_manifest=args.warehouse_manifest)
        if obj.get("status")!="success" or obj["provenance"].get("web_used") is not False or obj["provenance"].get("source_generation_id")!=GENERATION:
            raise RuntimeError("noncanonical or incomplete result "+date)
        query_checks.append({"date":date,"status":obj["status"],"race_count":obj["race_count"]})
        for race in obj["races"]:
            key=(date,race["venue_name"],int(race["race_no"]))
            if key in results:
                raise RuntimeError("duplicate result "+str(key))
            if race.get("result_status")!="available" or race.get("payouts_status")!="available" or race["cross_validation"].get("review_required"):
                raise RuntimeError("incomplete race "+str(key))
            for bt in ("win","quinella","trio"):
                if bt not in race["payouts"]:
                    raise RuntimeError("missing HJC bet type "+bt+str(key))
            results[key]=race
    if set(frozen)!=set(results):
        missing=set(frozen)-set(results);extra=set(results)-set(frozen)
        raise RuntimeError(f"result key mismatch missing={len(missing)} extra={len(extra)}; example={list(missing)[:3]}")
    rows=[]
    for key,fr in sorted(frozen.items()):
        race=results[key]
        top3=race["top3"]
        top3nos={int(x["horse_no"]) for x in top3}
        winners={int(x["horse_no"]) for x in top3 if x["finish"]==1}
        ticket_map=calc_tickets(fr["marks"])
        row={**fr,"honmei_win":int(fr["marks"][0] in winners),
             "honmei_top3":int(fr["marks"][0] in top3nos),
             "top3_in_five":len(set(fr["marks"])&top3nos),
             "winner_in_five":int(bool(winners&set(fr["marks"])))}
        for s in STRATEGIES:
            row[s]=score_strategy(race,s,ticket_map[s])
        rows.append(row)
    grouped={}
    for name,pop in [("all",rows),("early_0122_0135",[x for x in rows if x["cohort"]=="early"]),
                     ("late_0138_0150",[x for x in rows if x["cohort"]=="late"])]:
        grouped[name]={g:strat_table([x for x in pop if x["grade"]==g]) for g in ("A","B","C","Z")}
    group_reasons={}
    for cat in ("condition_gap","win_case_gap","rival_pressure","form_or_execution"):
        group_reasons[cat]={g:{
            "yes":strat_table([x for x in rows if x["grade"]==g and x[cat]]),
            "no":strat_table([x for x in rows if x["grade"]==g and not x[cat]])
        } for g in ("B","C")}
    box_vs_axis={}
    for group in ("B","C"):
        rr=[r for r in rows if r["grade"]==group]
        base=[r["trio_honmei_6"] for r in rr]
        box=[r["trio_box_10"] for r in rr]
        extra_hit=sum(int(b["hit"] and not a["hit"]) for a,b in zip(base,box))
        axishit=sum(a["hit"] for a in base)
        extra_return=sum(b["return_yen"]-a["return_yen"] for a,b in zip(base,box))
        extra_stake=sum(b["stake_yen"]-a["stake_yen"] for a,b in zip(base,box))
        box_vs_axis[group]={
            "base_hits":axishit,"box_hits":sum(b["hit"] for b in box),
            "extra_races_hit":extra_hit,
            "incremental_stake_yen":extra_stake,
            "incremental_return_yen":extra_return,
            "incremental_profit_yen":extra_return-extra_stake,
            "incremental_roi_pct":round(100*extra_return/extra_stake,2) if extra_stake else None
        }
    result={"schema":"racenote-r6-fixed-stakes-strategy-v1","status":"PASS",
            "research":"retrospective strategy comparison; no logic/grade changes",
            "population":900,"grade_counts":dict(cts),"freeze_checks":freeze_checks,
            "query_checks":query_checks,"strategy_names":list(STRATEGIES),
            "unit_stake_yen":100,"groups":grouped,"reason_subgroups_exploratory":group_reasons,
            "box_vs_axis_incremental":box_vs_axis,
            "interpretation_notes":[
                "100 yen per ticket per race; no odds/market filters and no allocation optimization.",
                "C SKIP = 0 yen stake, 0 yen payout; ROI undefined.",
                "A is monitoring control only, not tuned.",
                "Historical in-sample performance is not prospective validation.",
                "All payouts authoritative JRDB HJC via canonical result query; abnormal/refund handling is outside this comparison."
            ]}
    (out/"strategy_summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    fields=["btday","date","venue","race_no","grade","cohort","marks","reason",
            "primary_reason","condition_gap","rival_pressure","win_case_gap",
            "form_or_execution","honmei_win","honmei_top3","top3_in_five","winner_in_five"]
    for s in STRATEGIES:
        fields.extend((s+"_hit",s+"_stake_yen",s+"_return_yen",s+"_profit_yen"))
    with (out/"per_race_strategies.csv").open("w",encoding="utf-8-sig",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields)
        w.writeheader()
        for r in rows:
            flat={k:r.get(k) for k in fields}
            flat["marks"]="/".join(map(str,r["marks"]))
            for s in STRATEGIES:
                for k in ("hit","stake_yen","return_yen","profit_yen"):
                    flat[s+"_"+k]=r[s][k]
            w.writerow(flat)
    (out/"checks.txt").write_text("PASS: all 900 races joined; 27 canonical JRDB dates; 6 predefined strategies; no Freeze writes\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","counts":dict(cts),
                      "B":grouped["all"]["B"],"C":grouped["all"]["C"],
                      "incremental":box_vs_axis},ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
