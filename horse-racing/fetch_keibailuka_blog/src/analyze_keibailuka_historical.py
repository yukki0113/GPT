#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,io,json,re,tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
import requests

VENUE_CODES={"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def get(url,**kwargs):
    r=requests.get(url,timeout=90,**kwargs); r.raise_for_status(); return r

def download_drive(fid,path,sha=None):
    r=get("https://drive.usercontent.google.com/download",params={"id":fid,"export":"download","confirm":"t"})
    data=r.content
    if b"<html" in data[:200].lower():
        data=get("https://drive.google.com/uc",params={"export":"download","id":fid}).content
    if sha:
        got=hashlib.sha256(data).hexdigest()
        if got.lower()!=sha.lower(): raise RuntimeError(f"SHA mismatch: {got}")
    path.write_bytes(data)

def fn(v):
    if v in (None,""): return None
    try:return float(v)
    except:return None
def inn(v):
    if v in (None,""): return None
    try:return int(float(v))
    except:return None
def pct(a,b): return round(a/b*100,3) if b else None
def metric(rows):
    n=len(rows); wins=sum(inn(r.get("finish"))==1 for r in rows); places=sum((inn(r.get("finish")) or 99)<=3 for r in rows)
    wr=sum(fn(r.get("win_payout")) or 0 for r in rows); pr=sum(fn(r.get("place_payout")) or 0 for r in rows)
    return {"N":n,"wins":wins,"places":places,"win_rate_pct":pct(wins,n),"place_rate_pct":pct(places,n),
            "win_roi_pct":pct(wr,n*100),"place_roi_pct":pct(pr,n*100)}
def write_csv(path,rows):
    if not rows:return
    with open(path,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()),extrasaction="ignore"); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--request-json",required=True); ap.add_argument("--output-dir",required=True)
    a=ap.parse_args(); req=json.load(open(a.request_json,encoding="utf-8")); out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    import duckdb

    tmp=Path(tempfile.mkdtemp(prefix="keibailuka_research_"))
    p24=tmp/"sed_2024.parquet"; p25=tmp/"sed_2025.parquet"
    download_drive(req["sed_2024_id"],p24,req.get("sed_2024_sha"))
    download_drive(req["sed_2025_id"],p25,req.get("sed_2025_sha"))

    sheet=req.get("sheet_name","イルカ明細")
    url=f"https://docs.google.com/spreadsheets/d/{req['spreadsheet_id']}/gviz/tq?tqx=out:csv&sheet={quote(sheet)}"
    text=get(url).content.decode("utf-8-sig")
    picks=[]
    for d in csv.DictReader(io.StringIO(text)):
        date=(d.get("日付") or "").strip(); horse=(d.get("馬名_raw") or "").strip(); venue=(d.get("会場") or "").strip()
        if not (date.startswith("2024-") or date.startswith("2025-")) or not horse or horse=="🤡": continue
        m=re.fullmatch(r"(\d+)R",(d.get("R") or "").strip())
        if venue not in VENUE_CODES or not m: continue
        picks.append({"source_id":len(picks)+1,"key":d.get("key",""),"race_date":date,"year":int(date[:4]),"venue":venue,
                      "venue_code":VENUE_CODES[venue],"race_no":int(m.group(1)),"horse_name":horse.replace("　",""),"comment":d.get("コメント","")})

    con=duckdb.connect()
    con.execute("CREATE TABLE picks(source_id INTEGER,key VARCHAR,race_date VARCHAR,year INTEGER,venue VARCHAR,venue_code VARCHAR,race_no INTEGER,horse_name VARCHAR,comment VARCHAR)")
    con.executemany("INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?)",[(p["source_id"],p["key"],p["race_date"],p["year"],p["venue"],p["venue_code"],p["race_no"],p["horse_name"],p["comment"]) for p in picks])
    sed=f"read_parquet(['{p24.as_posix()}','{p25.as_posix()}'],union_by_name=true)"
    q=f"""SELECT p.*,COUNT(s.horse_no) OVER(PARTITION BY p.source_id) match_count,
                  s.horse_no,s.result_key,s.horse_name sed_horse_name,s.finish,s.abnormal_code,
                  s.final_win_odds,s.final_popularity,s.final_place_odds_lower,s.win_payout,s.place_payout
           FROM picks p LEFT JOIN {sed} s
             ON CAST(s.race_date AS VARCHAR)=p.race_date
            AND LPAD(CAST(s.venue_code AS VARCHAR),2,'0')=p.venue_code
            AND CAST(s.race_no AS INTEGER)=p.race_no
            AND REPLACE(TRIM(CAST(s.horse_name AS VARCHAR)),'　','')=p.horse_name"""
    cur=con.execute(q); cols=[d[0] for d in cur.description]; rows=[dict(zip(cols,r)) for r in cur.fetchall()]
    byid=defaultdict(list)
    for r in rows:byid[r["source_id"]].append(r)
    matched=[]; unmatched=[]; ambiguous=[]
    for p in picks:
        rr=byid[p["source_id"]]; mc=int(rr[0].get("match_count") or 0)
        if mc==0: unmatched.append(p)
        elif mc==1: matched.append(rr[0])
        else: ambiguous.extend(rr)
    normal=lambda r:r.get("abnormal_code") in (None,"",0,"0")
    bet=[r for r in matched if normal(r)]; abnormal=[r for r in matched if not normal(r)]

    audit=[]
    for r in [x for x in bet if inn(x.get("finish"))==1 and fn(x.get("win_payout")) and fn(x.get("final_win_odds")) is not None][:10]:
        o=fn(r["final_win_odds"]); p=fn(r["win_payout"])
        audit.append({"race_date":r["race_date"],"venue":r["venue"],"race_no":r["race_no"],"horse":r["horse_name"],
                      "final_win_odds":o,"win_payout":p,"odds_x_100":round(o*100,6),"difference":round(p-o*100,6),"place_payout":fn(r.get("place_payout"))})
    unit_ok=bool(audit) and all(abs(x["difference"])<0.01 for x in audit)

    summary={"schema_version":"keibailuka-research-v0.2",
      "source_population":{"total":len(picks),"matched":len(matched),"unmatched":len(unmatched),"ambiguous":len(set(r["source_id"] for r in ambiguous)),"match_rate_pct":pct(len(matched),len(picks))},
      "bettable_population":{"N":len(bet),"abnormal_excluded":len(abnormal)},
      "payout_unit_audit":{"unit_confirmed_100yen":unit_ok,"examples":audit},
      "overall":metric(bet),"by_year":{},"by_popularity":{},"by_win_odds":{}}
    for y in (2024,2025):summary["by_year"][str(y)]=metric([r for r in bet if r["year"]==y])
    pop=[("1人気",lambda p:p==1),("2人気",lambda p:p==2),("3人気",lambda p:p==3),("4〜5人気",lambda p:p is not None and 4<=p<=5),("6〜9人気",lambda p:p is not None and 6<=p<=9),("10人気以下",lambda p:p is not None and p>=10)]
    for n,f in pop:summary["by_popularity"][n]=metric([r for r in bet if f(inn(r.get("final_popularity")))])
    obs=[("<3",lambda o:o is not None and o<3),("3〜4.9",lambda o:o is not None and 3<=o<5),("5〜9.9",lambda o:o is not None and 5<=o<10),("10〜19.9",lambda o:o is not None and 10<=o<20),("20〜49.9",lambda o:o is not None and 20<=o<50),("50+",lambda o:o is not None and o>=50)]
    for n,f in obs:summary["by_win_odds"][n]=metric([r for r in bet if f(fn(r.get("final_win_odds")))])

    write_csv(out/"join_unmatched.csv",unmatched); write_csv(out/"join_ambiguous.csv",ambiguous); write_csv(out/"payout_unit_audit.csv",audit)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    def fm(v):return "-" if v is None else (f"{v:.2f}" if isinstance(v,float) else str(v))
    sp=summary["source_population"]; lines=["# keibailuka Historical Research 2024-2025","",
      f"- total: {sp['total']} / matched: {sp['matched']} / unmatched: {sp['unmatched']} / ambiguous: {sp['ambiguous']}",
      f"- match rate: {fm(sp['match_rate_pct'])}% / bettable N: {len(bet)} / abnormal excluded: {len(abnormal)}",
      f"- payout 100yen unit confirmed: {unit_ok}","","## Overall"]
    m=summary["overall"]; lines.append(f"N={m['N']} wins={m['wins']} places={m['places']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    lines+=["","## By year"]
    for k,m in summary["by_year"].items():lines.append(f"- {k}: N={m['N']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    lines+=["","## By popularity"]
    for k,m in summary["by_popularity"].items():lines.append(f"- {k}: N={m['N']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    lines+=["","## By win odds"]
    for k,m in summary["by_win_odds"].items():lines.append(f"- {k}: N={m['N']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    (out/"summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8"); print("\n".join(lines))

if __name__=="__main__":main()
