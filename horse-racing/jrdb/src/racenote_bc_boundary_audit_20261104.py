#!/usr/bin/env python3
"""Read-only, result-blind textual B/C audit of RaceNote r6 immutable Freeze files.

Input results MUST come from canonical jrdb_result_query.py, not external Web.
Output contains separate blind classifications and post-unlock outcome joins.
"""
import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

DATES = {
    122:"2025-05-24",123:"2025-11-09",124:"2025-06-28",
    125:"2025-10-26",126:"2025-10-11",127:"2025-09-06",
    128:"2025-01-25",129:"2025-10-04",130:"2025-12-20",
    131:"2025-04-12",132:"2025-02-22",133:"2025-02-15",
    134:"2025-05-04",135:"2025-10-13",138:"2025-08-02",
    139:"2025-01-26",140:"2025-04-20",141:"2025-08-23",
    142:"2025-10-19",143:"2025-08-31",144:"2025-02-23",
    145:"2025-10-05",146:"2025-07-13",147:"2025-07-27",
    148:"2025-11-29",149:"2025-01-12",150:"2025-02-01"
}
EXPECTED = {"A":205, "B":524, "C":50, "Z":121}
GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"
CONTRACT = "v055-prediction-freeze-confidence-review-r6"

# Nonexclusive, predeclared exploratory text markers. No result fields are used here.
PATTERNS = {
    "condition_gap": re.compile(
        r"未経験|初条件|初めて|未知|初距離|初出走|初舞台|条件替わり|"
        r"距離替わり|延長|短縮|適性が未|適応|実績が薄|実績がな|"
        r"同距離実績|距離適性|条件適性|初の|初めての"
    ),
    "rival_pressure": re.compile(
        r"拮抗|接戦|混戦|僅差|差が小さ|差は小さ|差を明確|"
        r"逆転|勝ち筋が複数|勝者特定|勝ち馬選定|強敵|"
        r"相手が揃|複数|競り合|比較は|上回る根拠|上回る確信"
    ),
    "win_case_gap": re.compile(
        r"勝ち切り.{0,12}(根拠|裏付け|確信|決め手|評価)|"
        r"決め手(を欠|が弱|は弱|不足)|勝利.{0,8}(根拠|実績|確信)|"
        r"押し切る.{0,10}(根拠|確信)|初勝利|"
        r"裏付け(が不足|に不足|に乏|は弱|は限定|が弱|が乏)|"
        r"確信(は弱|が低|は低|は限定|が薄|を持てない)|"
        r"勝利への確信"
    ),
    "form_or_execution": re.compile(
        r"前走.{0,8}(着|敗|不振)|近走.{0,8}(着|不振)|"
        r"出遅れ|不利|展開依存|追込|折り合い|先行争い|"
        r"逃げ粘り|経験不足|決め手不足|調教|状態"
    )
}
PRIMARY_ORDER = ["condition_gap","win_case_gap","rival_pressure","form_or_execution"]

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def key(date,venue,race):
    return (date, str(venue), int(race))

def classify(text):
    flags = {name:bool(regex.search(text)) for name,regex in PATTERNS.items()}
    primary = next((name for name in PRIMARY_ORDER if flags[name]),"uncategorized")
    return flags,primary

def wilson(k,n):
    if not n: return None
    z=1.959963984540054
    p=k/n
    q=1+z*z/n
    c=(p+z*z/(2*n))/q
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/q
    return [round(max(0,c-h),4),round(min(1,c+h),4)]

def fisher_two_sided(a,b,c,d):
    row1=a+b; row2=c+d; total=row1+row2; wins=a+c
    lo=max(0,wins-row2); hi=min(wins,row1)
    def logcomb(n,k):
        return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
    den=logcomb(total,row1)
    lp=lambda x:logcomb(wins,x)+logcomb(total-wins,row1-x)-den
    obs=lp(a)
    return round(sum(math.exp(lp(x)) for x in range(lo,hi+1) if lp(x)<=obs+1e-9),7)

def summarize(rows):
    n=len(rows); win=sum(x["honmei_win"] for x in rows)
    second=sum(x["second_win"] for x in rows)
    top3=sum(x["honmei_top3"] for x in rows)
    return {
        "n":n,"honmei_wins":win,"honmei_win_rate":round(win/n,4) if n else None,
        "honmei_win_wilson95":wilson(win,n),
        "honmei_top3":top3,"honmei_top3_rate":round(top3/n,4) if n else None,
        "second_wins":second,
        "honmei_share_if_honmei_or_second_wins":round(win/(win+second),4) if win+second else None
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,required=True)
    ap.add_argument("--result-dir",type=Path,action="append",required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args()
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    result_map={}
    result_checks=[]
    for date in DATES.values():
        paths=[p for root in args.result_dir for p in root.glob("result_"+date+".json")]
        if len(paths)!=1:raise RuntimeError("expected one official result per date: "+date+" "+str(paths))
        p=paths[0];obj=load_json(p)
        if obj.get("status")!="success" or obj.get("provenance",{}).get("source_generation_id")!=GENERATION or obj.get("provenance",{}).get("web_used") is not False:
            raise RuntimeError("invalid source provenance: "+str(p))
        result_checks.append({"date":date,"sha256":sha256(p),"race_count":len(obj["races"]),"status":"success"})
        for race in obj["races"]:
            k=key(date,race["venue_name"],race["race_no"])
            if k in result_map:raise RuntimeError("duplicate official result "+str(k))
            if race["result_status"]!="available" or race["payouts_status"]!="available" or race["cross_validation"].get("review_required"):
                raise RuntimeError("incomplete official result "+str(k))
            result_map[k]=race
    blind=[]; rows=[];checks=[]
    all_count=Counter()
    for n,date in DATES.items():
        path=args.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{date.replace('-','')}/v055"
        pp=path/"frozen/records.json"
        cp=path/"confidence_frozen/records.json"
        preds=load_json(pp);confs=load_json(cp)
        if len(preds)!=len(confs):raise RuntimeError("Freeze count mismatch "+str(n))
        pred_map={}
        for p in preds:
            if p.get("contract_revision")!=CONTRACT or p.get("logic_version")!="RaceNote-Human-Context-Reader-0.5.5-candidate" or p.get("target_date")!=date:
                raise RuntimeError("wrong r6 identity "+str(n))
            k=key(date,p["venue"],p["race_no"])
            if k in pred_map:raise RuntimeError("duplicate Prediction "+str(k))
            pred_map[k]=p
        seen=set()
        for c in confs:
            k=key(date,c["venue"],c["race_no"])
            if k in seen or k not in pred_map or k not in result_map:
                raise RuntimeError("missing or duplicate cross-source key "+str(k))
            seen.add(k)
            p=pred_map[k]; marks=p["decision_core"]["marks"]
            if int(c["honmei"])!=int(marks[0]):raise RuntimeError("frozen ◎ mismatch "+str(k))
            grade=c["confidence"];all_count[grade]+=1
            reason=str(c.get("reason") or "")
            if not reason:raise RuntimeError("empty confidence reason "+str(k))
            flags,primary=classify(reason)
            cohort="early_0122_0135" if n<=135 else "late_0138_0150"
            b={"btday":f"BTDAY-{n:04d}","date":date,"venue":k[1],"race_no":k[2],
               "grade":grade,"honmei":int(c["honmei"]),"second":int(marks[1]),
               "reason":reason,"primary_category":primary,**{k:int(v) for k,v in flags.items()},
               "cohort":cohort,"prediction_sha256":sha256(pp),"confidence_sha256":sha256(cp)}
            blind.append(b)
        if set(pred_map)!=seen:raise RuntimeError("incomplete roster "+str(n))
        checks.append({"btday":f"BTDAY-{n:04d}","date":date,"count":len(confs),
                       "confidence_sha256":sha256(cp),"prediction_sha256":sha256(pp)})
    if dict(all_count)!=EXPECTED:raise RuntimeError("cohort cardinality failed: "+str(all_count))
    if len(blind)!=900 or len(checks)!=27:raise RuntimeError("cohort total failed")
    # Blind classes above are fully determined BEFORE this line reads any outcomes.
    for b in blind:
        race=result_map[key(b["date"],b["venue"],b["race_no"])]
        top3=race["top3"]
        winners={int(x["horse_no"]) for x in top3 if x["finish"]==1}
        top3_horses={int(x["horse_no"]) for x in top3}
        rows.append({**b,"honmei_win":int(b["honmei"] in winners),
                     "honmei_top3":int(b["honmei"] in top3_horses),
                     "second_win":int(b["second"] in winners),
                     "honmei_finish_top3":next((x["finish"] for x in top3 if int(x["horse_no"])==b["honmei"]),None),
                     "winner_numbers":sorted(winners)})
    if len(rows)!=900:raise RuntimeError("joined roster incomplete")
    grades={g:summarize([x for x in rows if x["grade"]==g]) for g in ["A","B","C","Z"]}
    for g in ["A","B","C","Z"]:
        if grades[g]["n"]!=EXPECTED[g]:raise RuntimeError("grade count mismatch")
    groups={}
    for group_name,pop in [
        ("early_0122_0135",[r for r in rows if r["cohort"]=="early_0122_0135"]),
        ("late_0138_0150",[r for r in rows if r["cohort"]=="late_0138_0150"]),
        ("late_0138_0144",[r for r in rows if 138<=int(r["btday"][-4:])<=144]),
        ("late_0145_0150",[r for r in rows if 145<=int(r["btday"][-4:])<=150])
    ]:
        groups[group_name]={g:summarize([x for x in pop if x["grade"]==g]) for g in ["A","B","C","Z"]}
    marker={}
    for cat in PATTERNS:
        marker[cat]={g:{label:summarize([r for r in rows if r["grade"]==g and bool(r[cat])==value])
                   for label,value in [("yes",True),("no",False)]} for g in ["B","C"]}
    primary={cat:{g:summarize([r for r in rows if r["grade"]==g and r["primary_category"]==cat]) for g in ["B","C"]}
             for cat in PRIMARY_ORDER+["uncategorized"]}
    day=[]
    for n,date in DATES.items():
        pop=[r for r in rows if r["date"]==date]
        day.append({"btday":f"BTDAY-{n:04d}","date":date,
                    "grades":{g:summarize([r for r in pop if r["grade"]==g]) for g in ["A","B","C","Z"]}})
    b=grades["B"];c=grades["C"]
    summary={
        "schema":"racenote-r6-bc-audit-v1",
        "status":"PASS","sample":"BTDAY-0122..0135 + 0138..0150, 900 races",
        "source":"JRDB Result Query Warehouse pinned 2025 generation",
        "results":result_checks,"freeze_checks":checks,
        "grades":grades,"cohort_groups":groups,
        "reason_flags_nonexclusive":marker,"reason_primary_exploratory":primary,"per_day":day,
        "b_vs_c_fisher_two_sided_p":fisher_two_sided(b["honmei_wins"],b["n"]-b["honmei_wins"],c["honmei_wins"],c["n"]-c["honmei_wins"]),
        "c_minus_b_winrate_points":round((c["honmei_win_rate"]-b["honmei_win_rate"])*100,2),
        "limitations":["Keyword-based blind exploratory markers are not semantic adjudications.",
                       "All historical data are in-sample; do not claim prospective uplift.",
                       "A/B/C v0.5.5 r6 are not v0.5.6 prospective outcomes.",
                       "Race-level outcomes are from official pre-existing SED/HJC canonical query."]
    }
    (out/"blind_classification.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in blind),encoding="utf-8")
    (out/"joined_b_c.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows if r["grade"] in {"B","C"}),encoding="utf-8")
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (out/"joined_b_c.csv").open("w",encoding="utf-8-sig",newline="") as fh:
        selected=[r for r in rows if r["grade"] in {"B","C"}]
        cols=["btday","date","venue","race_no","grade","honmei","second","reason","cohort",
              "primary_category",*PATTERNS.keys(),"honmei_win","second_win","honmei_top3","honmei_finish_top3","winner_numbers"]
        w=csv.DictWriter(fh,fieldnames=cols,extrasaction="ignore")
        w.writeheader()
        for row in selected:
            w.writerow({**row,"winner_numbers":"|".join(map(str,row["winner_numbers"]))})
    print(json.dumps({"status":"PASS","grades":grades,"c_minus_b_winrate_points":summary["c_minus_b_winrate_points"],
                      "fisher_p":summary["b_vs_c_fisher_two_sided_p"],"output":str(out)},ensure_ascii=False))
if __name__=="__main__":
    main()
