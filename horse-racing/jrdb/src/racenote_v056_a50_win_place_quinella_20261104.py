#!/usr/bin/env python3
"""Read-only A-grade win/place/quinella 10-BTDAY check; canonical 2025 JRDB warehouse."""
from __future__ import annotations
import argparse, json, csv, hashlib
from pathlib import Path
from jrdb_result_query import query_results
DAYS={152:"20250907",153:"20251025",154:"20250809",155:"20250816",156:"20251227",157:"20251213",158:"20250113",159:"20250419",160:"20250817",161:"20250323"}
GEN="jrdb_normalized_warehouse_v1_2010_2025_g20260921"
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def score(race,kind,tickets):
    pay=race["payouts"].get(kind)
    if not isinstance(pay,list):raise RuntimeError(f"payout group {kind} missing: {race['race_key']}")
    return sum(int(p["payout_yen"]) for p in pay if tuple(sorted(map(int,p["numbers"]))) in tickets)
def main():
    p=argparse.ArgumentParser()
    for key in ("repo-root","warehouse-root","warehouse-manifest","output-dir"):p.add_argument("--"+key,required=True,type=Path)
    args=p.parse_args();out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    selected={};audit=[]
    for n,d in DAYS.items():
        root=args.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{d}/v056"
        predpath=root/"frozen/records.json";confpath=root/"confidence_frozen/records.json"
        pred=load(predpath);conf=load(confpath)
        ph=load(root/"frozen/day_handoff.json");ch=load(root/"confidence_frozen/day_handoff.json")
        if (ph.get("records_sha256")!=sha(predpath) or
            ch.get("confidence_records_sha256")!=sha(confpath) or
            ch.get("prediction_records_sha256")!=sha(predpath)):
            raise RuntimeError(f"Freeze integrity failed {n}")
        pi={(x["venue"],x["race_no"]):x for x in pred}
        if len(pi)!=len(pred) or len(conf)!=len(pred):raise RuntimeError("Freeze roster mismatch "+str(n))
        a=0
        for c in conf:
            if c["confidence"]!="A":continue
            a+=1;k=(f"{d[:4]}-{d[4:6]}-{d[6:]}",c["venue"],int(c["race_no"]))
            if k in selected:raise RuntimeError(f"duplicate {k}")
            fr=pi.get((c["venue"],c["race_no"]))
            if fr is None:raise RuntimeError(f"prediction mismatch {k}")
            marks=list(map(int,fr["decision_core"]["marks"]))
            if len(marks)!=5 or len(set(marks))!=5 or marks[0]!=int(c["honmei"]):raise RuntimeError(f"bad marks {k}")
            selected[k]={"btday":f"BTDAY-{n:04d}","date":k[0],"venue":k[1],"race_no":k[2],"honmei":marks[0],"marks":marks}
        audit.append({"btday":n,"A_count":a,"prediction_sha256":sha(predpath),"confidence_sha256":sha(confpath)})
    if len(selected)!=50:raise RuntimeError(f"Expected A50 got {len(selected)}")
    dates=sorted(set(k[0] for k in selected));race_results={}
    for date in dates:
        d=query_results(date=date,source="warehouse",warehouse_root=args.warehouse_root,warehouse_manifest=args.warehouse_manifest)
        if d.get("status")!="success" or d["provenance"].get("source_generation_id")!=GEN or d["provenance"].get("web_used") is not False:raise RuntimeError("Noncanonical results "+date)
        for r in d["races"]:
            key=(date,r["venue_name"],int(r["race_no"]))
            if key in race_results:raise RuntimeError("duplicate result "+str(key))
            if r.get("result_status")!="available" or r.get("payouts_status")!="available" or r["cross_validation"].get("review_required"):raise RuntimeError("nonaccepted result "+str(key))
            race_results[key]=r
    if not set(selected).issubset(race_results):raise RuntimeError(f"Missing races {set(selected)-set(race_results)}")
    rows=[]
    for key,fr in sorted(selected.items()):
        r=race_results[key];h=fr["honmei"]; marks=fr["marks"]
        top3={int(x["horse_no"]) for x in r["top3"]}
        wins={int(x["horse_no"]) for x in r["top3"] if x["finish"]==1}
        q={tuple(sorted((h,x))) for x in marks[1:]}
        vals={"win":score(r,"win",{(h,)}),"place":score(r,"place",{(h,)}),"quinella":score(r,"quinella",q)}
        rows.append({**fr,"honmei_win":int(h in wins),"honmei_top3":int(h in top3),
                     "win_return":vals["win"],"place_return":vals["place"],"quinella_return":vals["quinella"],
                     "win_stake":100,"place_stake":100,"quinella_stake":400,
                     "win_hit":int(vals["win"]>0),"place_hit":int(vals["place"]>0),"quinella_hit":int(vals["quinella"]>0)})
    result={"status":"PASS","source_generation":GEN,"population":len(rows),
            "honmei_wins":sum(x["honmei_win"] for x in rows),"honmei_top3":sum(x["honmei_top3"] for x in rows),
            "audit":audit,"strategies":{}}
    for kind in ("win","place","quinella"):
        invested=sum(r[kind+"_stake"] for r in rows);returned=sum(r[kind+"_return"] for r in rows);hits=sum(r[kind+"_hit"] for r in rows)
        result["strategies"][kind]={"tickets_per_race":1 if kind!="quinella" else 4,"hits":hits,
                                  "hit_rate_pct":round(hits*100/len(rows),2),"stake_yen":invested,"return_yen":returned,
                                  "net_yen":returned-invested,"roi_pct":round(returned*100/invested,2)}
    (out/"A50_summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    fields=["btday","date","venue","race_no","honmei","marks","honmei_win","honmei_top3","win_hit","win_return","place_hit","place_return","quinella_hit","quinella_return","win_stake","place_stake","quinella_stake"]
    with (out/"A50_per_race.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fields);w.writeheader()
        for row in rows:
            row={**row,"marks":"/".join(map(str,row["marks"]))}
            w.writerow({k:row.get(k) for k in fields})
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
