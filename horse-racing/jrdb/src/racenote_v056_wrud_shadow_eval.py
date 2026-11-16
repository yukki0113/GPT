#!/usr/bin/env python3
"""Read-only v0.5.6 official vs W/R/U/D Shadow evaluation against canonical 2025 JRDB Warehouse."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jrdb_result_query import query_results

TARGETS = (
    ("0186", "20250726"), ("0187", "20250803"), ("0188", "20250301"),
    ("0189", "20250119"), ("0190", "20251018"), ("0191", "20250412"),
)
GRADES = ("A", "B", "C", "Z")
BET_KINDS = ("win", "place", "quinella_axis_4", "quinella_box_10", "trio_axis_6", "trio_pair_3", "trio_box_10", "quinella_honmei_second_1", "trio_top3_1")

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def wilson(k, n):
    if not n:
        return None
    z=1.95996398454
    p=k/n
    d=1+z*z/n
    mid=(p+z*z/(2*n))/d
    hw=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round((mid-hw)*100,1),round((mid+hw)*100,1)]

def bet_calc(race, marks):
    payouts=race["payouts"]
    first, second, third, fourth, fifth=marks
    combos={
        "win":[(first,)],
        "place":[(first,)],
        "quinella_axis_4":[(first,n) for n in marks[1:]],
        "quinella_box_10":[(marks[i],marks[j]) for i in range(5) for j in range(i+1,5)],
        "trio_axis_6":[(first,marks[i],marks[j]) for i in range(1,5) for j in range(i+1,5)],
        "trio_pair_3":[(first,second,n) for n in marks[2:]],
        "trio_box_10":[(marks[i],marks[j],marks[k]) for i in range(5) for j in range(i+1,5) for k in range(j+1,5)],
        "quinella_honmei_second_1":[(first,second)],
        "trio_top3_1":[(first,second,third)],
    }
    out={}
    for bet,selected in combos.items():
        family="win" if bet=="win" else "place" if bet=="place" else "quinella" if bet.startswith("quinella") else "trio"
        wanted={tuple(sorted(row)) for row in selected}
        returned=sum(int(slot["payout_yen"] or 0) for slot in payouts[family] if tuple(sorted(slot["numbers"])) in wanted)
        out[bet]={"stake":100*len(selected),"return":returned}
    return out

def aggregate(rows):
    n=len(rows)
    bets={b:{"stake":sum(r["bets"][b]["stake"] for r in rows),"return":sum(r["bets"][b]["return"] for r in rows)} for b in BET_KINDS}
    for b,x in bets.items():
        x["net"]=x["return"]-x["stake"]
        x["roi_pct"]=round(100*x["return"]/x["stake"],1) if x["stake"] else None
        x["hits"]=sum(r["bets"][b]["return"]>0 for r in rows)
    wins=sum(r["honmei_win"] for r in rows)
    top3=sum(r["honmei_top3"] for r in rows)
    return {"races":n,"wins":wins,"win_rate_pct":round(100*wins/n,1) if n else None,
            "win_rate_ci95_wilson_pct":wilson(wins,n),"top3":top3,
            "top3_rate_pct":round(100*top3/n,1) if n else None,
            "top3_rate_ci95_wilson_pct":wilson(top3,n),"bets":bets}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--warehouse-root",type=Path,required=True)
    p.add_argument("--warehouse-manifest",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    repo=Path(__file__).resolve().parents[3]  # from horse-racing/jrdb/src -> repository root
    base=repo/"horse-racing"/"jrdb"/"backtests"
    rows=[]
    provenance=[]
    for id,date in TARGETS:
        root=base/f"BTDAY-{id}"/date/"v056"
        pred=root/"frozen"/"records.json"
        conf=root/"confidence_frozen"/"records.json"
        shadow=root/"research"/"wrud"/"frozen"/"records.json"
        seal=root/"research"/"wrud"/"frozen"/"seal.json"
        summary=read(root/"turn2_summary.json")
        s=read(seal); sh=read(shadow)
        assert summary["status"]=="TURN2_COMPLETE"
        assert s["status"]=="WRUD_SHADOW_FROZEN" and s["records_sha256"]==sha(shadow),id
        assert s["source_prediction_records_sha256"]==sha(pred) and s["source_confidence_records_sha256"]==sha(conf),id
        assert sh["prediction_records_sha256"]==sha(pred) and sh["confidence_records_sha256"]==sha(conf),id
        predictions=read(pred)
        confidences=read(conf)
        S={(r["venue"],r["race_no"]):r for r in sh["records"]}
        P={(r["venue"],r["race_no"]):r for r in predictions}
        C={(r["venue"],r["race_no"]):r for r in confidences}
        assert len(S)==len(P)==len(C)==s["records"] and S.keys()==P.keys()==C.keys()
        result=query_results(date=f"{date[:4]}-{date[4:6]}-{date[6:]}",source="warehouse",warehouse_root=args.warehouse_root,warehouse_manifest=args.warehouse_manifest,include_all_runners=True)
        if result["status"]!="success" or result["provenance"].get("web_used") is not False:
            raise RuntimeError(f"JRDB result not clean: {id} {result['status']}")
        races={(r["venue_name"],r["race_no"]):r for r in result["races"]}
        assert set(P).issubset(races),f"JRDB target race missing {id}: {set(P)-set(races)}"
        for key,pr in P.items():
            cf=C[key]; ss=S[key]; race=races[key]
            honmei=pr["decision_core"]["marks"][0]
            assert cf["honmei"]==ss["honmei"]==honmei
            assert cf["confidence"]==ss["official_confidence"]
            assert len(pr["decision_core"]["marks"])==5
            if cf["confidence"]=="Z":
                assert ss["shadow_confidence"]=="Z"
            else:
                assert ss["shadow_confidence"] in ("A","B","C")
            if race["cross_validation"]["status"]=="mismatch":
                raise RuntimeError(f"SED/HJC mismatch {id} {key}")
            runners=[z for z in race["all_runners"] if z["horse_no"]==honmei]
            assert len(runners)==1
            h=runners[0]; top3=race["top3"]; marks=pr["decision_core"]["marks"]
            bets=bet_calc(race,marks)
            rows.append({"selection_id":f"BTDAY-{id}","date":f"{date[:4]}-{date[4:6]}-{date[6:]}",
                        "venue":key[0],"race_no":key[1],"race_key":race["race_key"],
                        "honmei_no":honmei,"honmei_name":h["horse_name"],
                        "official_grade":cf["confidence"],"shadow_grade":ss["shadow_confidence"],
                        "transition":cf["confidence"]+"->"+ss["shadow_confidence"],
                        "honmei_finish":h["finish"],"honmei_abnormal":h["abnormal_code"],
                        "honmei_win":any(z["horse_no"]==honmei and z["finish"]==1 for z in top3),
                        "honmei_top3":any(z["horse_no"]==honmei for z in top3),
                        "winner_in_marks":any(z["finish"]==1 and z["horse_no"] in marks for z in top3),
                        "final_win_popularity":h["final_win_popularity"],
                        "final_win_odds":h["final_win_odds"],"bets":bets})
        provenance.append({"selection_id":f"BTDAY-{id}","date":date,"race_count":len(P),
                           "matched_results":len(P),"source_mode":result["provenance"]["source_mode"],
                           "source_generation":result["provenance"].get("source_generation_id"),
                           "shadow_records_sha256":s["records_sha256"],
                           "official_prediction_sha256":sha(pred),"official_confidence_sha256":sha(conf)})
    assert len(rows)==204
    standard=[r for r in rows if r["official_grade"]!="Z"]
    groups={"all":aggregate(rows),"standard_ABC":aggregate(standard),
            "by_official":{g:aggregate([r for r in rows if r["official_grade"]==g]) for g in GRADES},
            "by_shadow":{g:aggregate([r for r in rows if r["shadow_grade"]==g]) for g in GRADES},
            "transitions":{f"{a}->{b}":aggregate([r for r in rows if r["transition"]==f"{a}->{b}"]) for a in GRADES for b in GRADES if any(r["transition"]==f"{a}->{b}" for r in rows)},
            "retained_A":aggregate([r for r in rows if r["official_grade"]=="A" and r["shadow_grade"]=="A"]),
            "demoted_official_A":aggregate([r for r in rows if r["official_grade"]=="A" and r["shadow_grade"]!="A"]),
            "promoted_to_shadow_A":aggregate([r for r in rows if r["official_grade"]!="A" and r["shadow_grade"]=="A"]),
            "by_day":{id:{g:aggregate([r for r in rows if r["selection_id"]==f"BTDAY-{id}" and r["shadow_grade"]==g]) for g in GRADES} for id,_ in TARGETS}}
    out={"schema_version":"racenote-wrud-shadow-eval-v0.1","status":"success","records":len(rows),"provenance":provenance,"groups":groups,
         "limitations":["Historical backtest, not prospective live results","same honmei/marks under official and shadow: subset-selection effect only","100 JPY per individual ticket; no refunds handled beyond explicit HJC payouts","small Shadow A sample, confidence intervals are descriptive, not comparative test","2025 dates, neither post-hoc model adjustments nor repeated-date leakage evaluated here"]}
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (args.output_dir/"per_race.csv").open("w",encoding="utf-8-sig",newline="") as fh:
        columns=[k for k in rows[0] if k!="bets"]+[f"{b}_{t}" for b in BET_KINDS for t in ("stake","return")]
        writer=csv.DictWriter(fh,columns);writer.writeheader()
        for r in rows:
            line={k:v for k,v in r.items() if k!="bets"}
            for b in BET_KINDS:
                line[f"{b}_stake"]=r["bets"][b]["stake"]
                line[f"{b}_return"]=r["bets"][b]["return"]
            writer.writerow(line)
    print(json.dumps({"status":"success","races":len(rows),"official_A":groups["by_official"]["A"]["races"],
                      "shadow_A":groups["by_shadow"]["A"]["races"],
                      "official_A_win_rate":groups["by_official"]["A"]["win_rate_pct"],
                      "shadow_A_win_rate":groups["by_shadow"]["A"]["win_rate_pct"],
                      "official_A_win_ROI":groups["by_official"]["A"]["bets"]["win"]["roi_pct"],
                      "shadow_A_win_ROI":groups["by_shadow"]["A"]["bets"]["win"]["roi_pct"],
                      "retained_A":groups["retained_A"]["races"],
                      "demoted_A":groups["demoted_official_A"]["races"],
                      "output_files":["summary.json","per_race.csv"]},ensure_ascii=False))

if __name__=="__main__":
    main()
