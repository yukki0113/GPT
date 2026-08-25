#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, sqlite3
from pathlib import Path
from typing import Any

JRA_VENUES={"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}
VENUE_TO_CODE={v:k for k,v in JRA_VENUES.items()}
TRACK_CONDITION={"1":"良","2":"稍重","3":"重","4":"不良","10":"良","11":"速良","12":"遅良","20":"稍重","21":"速稍重","22":"遅稍重","30":"重","31":"速重","32":"遅重","40":"不良","41":"速不良","42":"遅不良"}
GRADE={"1":"G1","2":"G2","3":"G3","4":"重賞","5":"特別","6":"L"}
T="fact_entry_result_lite"

def dec(m,v):
    if v is None:return None
    s=str(v).strip(); return m.get(s,v)
def rate(n,d): return round(n*100/d,1) if d else None
def sm(starts,wins,top3): return {"starts":int(starts),"wins":int(wins),"top3":int(top3),"win_rate":rate(int(wins),int(starts)),"top3_rate":rate(int(top3),int(starts))}

def qsum(c,where,p):
    r=c.execute(f"SELECT COUNT(*),SUM(CASE WHEN finish=1 THEN 1 ELSE 0 END),SUM(CASE WHEN finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END) FROM {T} WHERE {where}",p).fetchone()
    return sm(r[0] or 0,r[1] or 0,r[2] or 0)

def target_entry(c,d,v,rn,hn):
    return c.execute(f"SELECT * FROM {T} WHERE race_date=? AND venue_code=? AND race_no=? AND horse_no=?",(d,v,rn,hn)).fetchone()

def profile(c,hid,d,v,track,dist,window_start):
    b="horse_id=? AND race_date<?"; p=[hid,d]
    return {"source":"JRDB Analysis Lite","source_window_start":window_start,"as_of_exclusive":d,"career":qsum(c,b,p),"same_surface":qsum(c,b+" AND track_type=?",p+[track]),"same_distance":qsum(c,b+" AND distance=?",p+[dist]),"same_venue":qsum(c,b+" AND venue_code=?",p+[v])}

def older(c,hid,d,recent,limit):
    ds=[x.get("race",{}).get("date") for x in recent if x.get("race",{}).get("date")]
    cutoff=min(ds) if ds else d
    rows=c.execute(f"SELECT race_date,venue_code,race_no,track_type,distance,track_condition_code,grade_code,running_style,training_index,finish,abnormal_code,final_win_odds,final_win_popularity FROM {T} WHERE horse_id=? AND race_date<? ORDER BY race_date DESC,race_no DESC LIMIT ?",(hid,cutoff,limit)).fetchall()
    return [{"date":x["race_date"],"venue":JRA_VENUES.get(str(x["venue_code"]),x["venue_code"]),"race_no":x["race_no"],"surface":x["track_type"],"distance_m":x["distance"],"track_condition":dec(TRACK_CONDITION,x["track_condition_code"]),"grade":dec(GRADE,x["grade_code"]),"running_style":x["running_style"],"training_index":x["training_index"],"finish":x["finish"],"abnormal_code":x["abnormal_code"],"final_win_odds":x["final_win_odds"],"final_popularity":x["final_win_popularity"]} for x in rows]

def mart_prior(c,table,col,val,ys,ye,v,track,dist):
    if ye<ys:return 0,0,0
    r=c.execute(f"SELECT COALESCE(SUM(starts),0),COALESCE(SUM(wins),0),COALESCE(SUM(top3),0) FROM {table} WHERE year BETWEEN ? AND ? AND venue_code=? AND track_type=? AND distance=? AND {col}=?",(ys,ye,v,track,dist,val)).fetchone(); return tuple(int(z or 0) for z in r)

def current_year(c,col,val,y,d,v,track,dist):
    r=c.execute(f"SELECT COUNT(*),SUM(CASE WHEN finish=1 THEN 1 ELSE 0 END),SUM(CASE WHEN finish BETWEEN 1 AND 3 THEN 1 ELSE 0 END) FROM {T} WHERE year=? AND race_date<? AND venue_code=? AND track_type=? AND distance=? AND {col}=?",(y,d,v,track,dist,val)).fetchone(); return tuple(int(z or 0) for z in r)

def asof(a,m,table,mcol,acol,val,d,v,track,dist,years):
    y=int(d[:4]); ys=y-years+1
    p=mart_prior(m,table,mcol,val,ys,y-1,v,track,dist); q=current_year(a,acol,val,y,d,v,track,dist)
    out=sm(*(p[i]+q[i] for i in range(3)))
    out.update({"period":f"{ys}-{y}YTD","as_of_exclusive":d,"track_condition_scope":"all_conditions","source":"Stats Mart prior years + Analysis Lite target-year YTD"}); return out

def enrich(base,a,m,older_limit,years):
    d=base["race"]["date"]; vn=base["race"]["venue"]; v=VENUE_TO_CODE[vn]; rn=int(base["race"]["race_no"]); track=base["race"]["surface"]; dist=int(base["race"]["distance_m"])
    w=a.execute(f"SELECT MIN(race_date) FROM {T}").fetchone()[0]
    out=copy.deepcopy(base); warnings=[]
    out.setdefault("metadata",{})["history_enrichment_poc"]={"version":"0.1","older_runs_per_horse":older_limit,"stats_window_years":years,"as_of_exclusive":d,"future_leakage_policy":"prior completed years from Stats Mart; target year from Analysis Lite with race_date < target_date"}
    for h in out.get("horses",[]):
        hn=int(h["basic"]["horse_no"]); te=target_entry(a,d,v,rn,hn)
        if te is None:
            warnings.append(f"target_entry_not_found:horse_no={hn}"); h["older_runs"]=[]; h["historical_profile"]=None; h["stats"]={"sire":None,"jockey":None}; continue
        hid=te["horse_id"]
        h["older_runs"]=older(a,hid,d,h.get("recent_runs",[]),older_limit) if hid else []
        h["historical_profile"]=profile(a,hid,d,v,track,dist,w) if hid else None
        sire=te["sire_name"]; jockey=te["jockey_name"] or h["basic"].get("jockey")
        h["stats"]={"sire":asof(a,m,"mart_sire_yearly","sire_name","sire_name",sire,d,v,track,dist,years) if sire else None,"jockey":asof(a,m,"mart_jockey_yearly","jockey_name","jockey_name",jockey,d,v,track,dist,years) if jockey else None}
    frames={}
    for f in range(1,9):
        s=asof(a,m,"mart_frame_yearly","frame_no","frame_no",f,d,v,track,dist,years)
        if s["starts"]: frames[str(f)]=s
    out["race"]["race_trends"]={"frame":frames}
    return out,warnings

def metrics(x):
    s=json.dumps(x,ensure_ascii=False,indent=2); return {"chars":len(s),"utf8_bytes":len(s.encode())}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--bundle",required=True); p.add_argument("--analysis",required=True); p.add_argument("--mart",required=True); p.add_argument("--output-dir",default="./racenote_history_poc"); p.add_argument("--stats-window-years",type=int,default=5); args=p.parse_args()
    bp=Path(args.bundle); od=Path(args.output_dir); od.mkdir(parents=True,exist_ok=True); base=json.loads(bp.read_text(encoding="utf-8")); bm=metrics(base)
    a=sqlite3.connect(args.analysis); m=sqlite3.connect(args.mart); a.row_factory=m.row_factory=sqlite3.Row
    variants={}
    try:
        for total,lim in ((8,3),(10,5)):
            x,w=enrich(base,a,m,lim,args.stats_window_years); txt=json.dumps(x,ensure_ascii=False,indent=2); op=od/f"{bp.stem}_enriched_{total}runs_poc.json"; op.write_text(txt+"\n",encoding="utf-8"); mm=metrics(x)
            variants[str(total)]={"path":str(op),**mm,"incremental_utf8_bytes":mm["utf8_bytes"]-bm["utf8_bytes"],"warning_count":len(w),"warnings":w,"older_runs_counts":[len(h.get("older_runs",[])) for h in x.get("horses",[])]}
    finally: a.close(); m.close()
    comp={"poc_version":"0.1","target":{"date":base["race"]["date"],"venue":base["race"]["venue"],"race_no":base["race"]["race_no"],"race_name":base["race"].get("race_name"),"horses":len(base.get("horses",[]))},"base":bm,"variants":variants,"notes":["8runs = PACI recent_runs (up to 5) + Analysis older_runs (up to 3).","10runs = PACI recent_runs (up to 5) + Analysis older_runs (up to 5).","Stats use all track conditions; target-year rows are recalculated from Analysis before target date to prevent future leakage."]}
    cp=od/f"{bp.stem}_enrichment_comparison_poc.json"; cp.write_text(json.dumps(comp,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(comp,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
