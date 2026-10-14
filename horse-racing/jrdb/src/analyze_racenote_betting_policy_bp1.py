#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
from itertools import combinations, permutations

VENUE_CODE={"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def k(v,r): return f"{v}:{int(r)}"

def paymap(race, kind):
    out={}
    for s in race.get("payouts",{}).get(kind,[]):
        nums=tuple(map(int,s.get("numbers") or []))
        if kind in ("quinella","trio"): nums=tuple(sorted(nums))
        out[nums]=int(s.get("payout_yen") or 0)
    return out

def score_horse(h):
    a=h.get("ability") or {}; j=h.get("jrdb_ratings") or {}; t=h.get("training") or {}
    summary=t.get("summary") or {}; ana=t.get("analysis") or {}
    return float(a.get("idm") or 0)+0.45*float(a.get("total_index") or 0)+1.7*float(j.get("info_index") or 0)+0.22*float(summary.get("training_index") or 0)+0.04*float(ana.get("condition_index") or 50)

def star_from_reader(reader, control, pool):
    hs={int(h["basic"]["horse_no"]):h for h in reader.get("horses",[])}
    candidates=[int(n) for n in pool if int(n) not in control and int(n) in hs]
    if not candidates:
        candidates=[n for n in hs if n not in control]
    return max(candidates,key=lambda n:score_horse(hs[n])) if candidates else None

def qpair(a,b): return tuple(sorted((int(a),int(b))))
def trio(a,b,c): return tuple(sorted((int(a),int(b),int(c))))

def patterns(m, conf, star):
    I,O,A,D1,D2=map(int,m)
    p={}
    # quinella
    p["Q_◎-○"]=[qpair(I,O)]
    p["Q_◎-▲"]=[qpair(I,A)]
    p["Q_◎-○▲"]=[qpair(I,O),qpair(I,A)]
    p["Q_◎流し3"]=[qpair(I,x) for x in (O,A,D1)]
    p["Q_◎流し4"]=[qpair(I,x) for x in (O,A,D1,D2)]
    p["Q_◎○▲BOX"]=[qpair(x,y) for x,y in combinations((I,O,A),2)]
    p["Q_5頭BOX"]=[qpair(x,y) for x,y in combinations((I,O,A,D1,D2),2)]
    # exacta
    p["E_◎→○"]=[(I,O)]
    p["E_◎→▲"]=[(I,A)]
    p["E_◎→○▲"]=[(I,O),(I,A)]
    p["E_◎⇔○"]=[(I,O),(O,I)]
    p["E_◎⇔○▲"]=[(I,O),(O,I),(I,A),(A,I)]
    p["E_conf_policy_234"]= (
        [(I,O),(I,A)] if conf=="A" else
        [(I,O),(O,I),(I,A)] if conf=="B" else
        [(I,O),(O,I),(I,A),(A,I)]
    )
    p["E_conf_Aforward_BCreverse"]= (
        [(I,O),(I,A)] if conf=="A" else [(I,O),(O,I),(I,A),(A,I)]
    )
    # trio
    p["T_◎○▲"]=[trio(I,O,A)]
    p["T_◎1軸_相手4"]=[trio(I,x,y) for x,y in combinations((O,A,D1,D2),2)]
    p["T_◎○2軸_相手3"]=[trio(I,O,x) for x in (A,D1,D2)]
    p["T_5頭BOX"]=[trio(x,y,z) for x,y,z in combinations((I,O,A,D1,D2),3)]
    # trifecta
    p["F_◎→○▲→残り"]=[(I,s,t) for s in (O,A) for t in (O,A,D1,D2) if t!=s]
    p["F_◎1着固定_相手4"]=[(I,x,y) for x,y in permutations((O,A,D1,D2),2)]
    p["F_◎○1-2着入替_相手3"]=[x for t in (A,D1,D2) for x in ((I,O,t),(O,I,t))]
    if star is not None:
        S=int(star)
        p["T_☆追加_◎1軸相手5"]=[trio(I,x,y) for x,y in combinations((O,A,D1,D2,S),2)]
        p["T_☆追加_◎○2軸相手4"]=[trio(I,O,x) for x in (A,D1,D2,S)]
        p["T_6頭BOX"]=[trio(x,y,z) for x,y,z in combinations((I,O,A,D1,D2,S),3)]
        p["F_☆追加_◎1着固定相手5"]=[(I,x,y) for x,y in permutations((O,A,D1,D2,S),2)]
        p["F_☆追加_◎○1-2着入替相手4"]=[x for t in (A,D1,D2,S) for x in ((I,O,t),(O,I,t))]
    return p

def kind_for(name):
    return "quinella" if name.startswith("Q_") else "exacta" if name.startswith("E_") else "trio" if name.startswith("T_") else "trifecta"

def summarize(records):
    stake=sum(r["stake"] for r in records); ret=sum(r["return"] for r in records)
    hit=sum(r["return"]>0 for r in records)
    hitrets=sorted((r["return"] for r in records if r["return"]>0),reverse=True)
    day=defaultdict(lambda:[0,0])
    for r in records:
        day[r["date"]][0]+=r["stake"]; day[r["date"]][1]+=r["return"]
    balances=[]; bal=0; peak=0; maxdd=0
    for r in sorted(records,key=lambda x:(x["date"],x["venue"],x["race_no"])):
        bal+=r["return"]-r["stake"]; peak=max(peak,bal); maxdd=max(maxdd,peak-bal); balances.append(bal)
    by_day={d:{"stake_yen":st,"return_yen":rt,"profit_yen":rt-st,"roi_pct":100*rt/st if st else None} for d,(st,rt) in sorted(day.items())}
    return {
        "races":len(records),"tickets":sum(r["tickets"] for r in records),"stake_yen":stake,"return_yen":ret,
        "profit_yen":ret-stake,"roi_pct":100*ret/stake if stake else None,
        "hit_races":hit,"hit_rate_pct":100*hit/len(records) if records else None,
        "avg_hit_return_yen":sum(hitrets)/len(hitrets) if hitrets else 0,
        "max_hit_return_yen":max(hitrets) if hitrets else 0,
        "largest_hit_share_pct":100*max(hitrets)/ret if hitrets and ret else 0,
        "profitable_days":sum(ret>st for st,ret in day.values()),"days":len(day),
        "max_drawdown_yen":maxdd,"by_day":by_day,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,required=True)
    ap.add_argument("--results-dir",type=Path,required=True)
    ap.add_argument("--case",action="append",required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    rows=[]
    for spec in a.case:
        bt,date,resfile=spec.split(":",2)
        base=a.repo_root/"horse-racing/jrdb/backtests"/bt/date/"v053"
        fr=load(base/"frozen/records.json"); cf=load(base/"confidence_pre_result.json"); sh=load(base/"shadow_cf1_pre_result.json")
        rr=load(a.results_dir/resfile)
        cm={k(x["venue"],x["race_no"]):x for x in cf["assignments"]}
        sm={k(x["venue"],x["race_no"]):x for x in sh["races"]}
        rm={k(x["venue_name"],x["race_no"]):x for x in rr["races"]}
        reader_root=a.repo_root/"horse-racing/jrdb/backtests"/bt/date/"day_prep"/f"RaceNote_{date}"/"reader"
        for x in fr:
            key=k(x["venue"],x["race_no"]); d=x["decision_core"]; m=list(map(int,d["marks"]))
            c=cm[key]["confidence"]; s=sm[key]; control=list(map(int,s.get("control_final_five",s.get("control",m))))
            pool=s.get("shadow_external_pool",s.get("pool",[]))
            reader=load(reader_root/f"racenote_reader_{date}_{x['venue']}{int(x['race_no'])}R.json")
            star=star_from_reader(reader,control,pool)
            race=rm[key]
            pm={z:paymap(race,z) for z in ("quinella","exacta","trio","trifecta")}
            for name,bets in patterns(m,c,star).items():
                kind=kind_for(name); unique=[]
                for b in bets:
                    if b not in unique: unique.append(b)
                ret=sum(pm[kind].get(tuple(b),0) for b in unique)
                rows.append({"pattern":name,"kind":kind,"btday":bt,"date":x["target_date"],"venue":x["venue"],"race_no":int(x["race_no"]),"confidence":c,"star":star,"tickets":len(unique),"stake":100*len(unique),"return":ret})
    by=defaultdict(list)
    for r in rows: by[r["pattern"]].append(r)
    out={"schema_version":"racenote-betting-policy-bp1-v0.1","race_count":len(set((r["btday"],r["venue"],r["race_no"]) for r in rows)),"unit_stake_yen":100,"patterns":{}}
    for name,rs in sorted(by.items()):
        out["patterns"][name]={"overall":summarize(rs),"by_confidence":{g:summarize([r for r in rs if r["confidence"]==g]) for g in "ABC"}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()
