#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, os, re, tempfile
from collections import defaultdict
from pathlib import Path

VENUE_CODES={"札幌":"01","函館":"02","福島":"03","新潟":"04","東京":"05","中山":"06","中京":"07","京都":"08","阪神":"09","小倉":"10"}

def fnum(v):
    if v in (None,""): return None
    try: return float(v)
    except Exception: return None

def inum(v):
    if v in (None,""): return None
    try: return int(float(v))
    except Exception: return None

def pct(a,b):
    return round(a/b*100,3) if b else None

def metric(rows):
    n=len(rows)
    wins=sum(1 for r in rows if inum(r.get("finish"))==1)
    places=sum(1 for r in rows if (inum(r.get("finish")) or 99)<=3)
    wr=sum(fnum(r.get("win_payout")) or 0 for r in rows)
    pr=sum(fnum(r.get("place_payout")) or 0 for r in rows)
    return {
      "N":n,"wins":wins,"places":places,
      "win_rate_pct":pct(wins,n),"place_rate_pct":pct(places,n),
      "win_roi_pct":pct(wr,n*100),"place_roi_pct":pct(pr,n*100),
      "win_return_yen":wr,"place_return_yen":pr,
    }

def write_csv(path, rows):
    if not rows: return
    fields=list(rows[0].keys())
    with open(path,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--request-json",required=True)
    ap.add_argument("--output-dir",required=True)
    a=ap.parse_args()
    req=json.load(open(a.request_json,encoding="utf-8"))
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import duckdb

    info=json.loads(os.environ["GPT_GDRIVE_SERVICE_ACCOUNT_JSON"])
    creds=service_account.Credentials.from_service_account_info(
      info, scopes=["https://www.googleapis.com/auth/drive","https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    drive=build("drive","v3",credentials=creds,cache_discovery=False)
    sheets=build("sheets","v4",credentials=creds,cache_discovery=False)

    def download(fid,path):
        reqd=drive.files().get_media(fileId=fid,supportsAllDrives=True)
        with open(path,"wb") as fh:
            dl=MediaIoBaseDownload(fh,reqd,chunksize=1024*1024)
            done=False
            while not done: _,done=dl.next_chunk()

    tmp=Path(tempfile.mkdtemp(prefix="keibailuka_research_"))
    p24=tmp/"sed_2024.parquet"; p25=tmp/"sed_2025.parquet"
    download(req["sed_2024_id"],p24); download(req["sed_2025_id"],p25)

    vals=sheets.spreadsheets().values().get(
      spreadsheetId=req["spreadsheet_id"],range="'イルカ明細'!A1:M6000"
    ).execute().get("values",[])
    hdr=vals[0]
    picks=[]
    for row in vals[1:]:
        d={hdr[i]:(row[i] if i<len(row) else "") for i in range(len(hdr))}
        date=str(d.get("日付","")).strip()
        if not (date.startswith("2024-") or date.startswith("2025-")): continue
        horse=str(d.get("馬名_raw","")).strip()
        if not horse or horse=="🤡": continue
        venue=str(d.get("会場","")).strip()
        m=re.fullmatch(r"(\d+)R",str(d.get("R","")).strip())
        if venue not in VENUE_CODES or not m: continue
        picks.append({
          "source_id":len(picks)+1,"key":d.get("key",""),"race_date":date,
          "year":int(date[:4]),"venue":venue,"venue_code":VENUE_CODES[venue],
          "race_no":int(m.group(1)),"horse_name":horse.replace("　",""),"comment":d.get("コメント","")
        })

    con=duckdb.connect()
    con.execute("""CREATE TABLE picks(
      source_id INTEGER,key VARCHAR,race_date VARCHAR,year INTEGER,venue VARCHAR,
      venue_code VARCHAR,race_no INTEGER,horse_name VARCHAR,comment VARCHAR
    )""")
    con.executemany("INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?)",[
      (p["source_id"],p["key"],p["race_date"],p["year"],p["venue"],p["venue_code"],p["race_no"],p["horse_name"],p["comment"])
      for p in picks
    ])
    sed=f"read_parquet(['{p24.as_posix()}','{p25.as_posix()}'], union_by_name=true)"
    q=f"""
    SELECT p.source_id,p.key,p.race_date,p.year,p.venue,p.venue_code,p.race_no,
           p.horse_name AS source_horse_name,p.comment,
           COUNT(s.horse_no) OVER (PARTITION BY p.source_id) AS match_count,
           s.horse_no,s.result_key,s.horse_name AS sed_horse_name,s.finish,s.abnormal_code,
           s.final_win_odds,s.final_popularity,s.final_place_odds_lower,s.win_payout,s.place_payout
    FROM picks p
    LEFT JOIN {sed} s
      ON CAST(s.race_date AS VARCHAR)=p.race_date
     AND LPAD(CAST(s.venue_code AS VARCHAR),2,'0')=p.venue_code
     AND CAST(s.race_no AS INTEGER)=p.race_no
     AND REPLACE(TRIM(CAST(s.horse_name AS VARCHAR)),'　','')=p.horse_name
    """
    cur=con.execute(q); cols=[d[0] for d in cur.description]
    rows=[dict(zip(cols,r)) for r in cur.fetchall()]
    byid=defaultdict(list)
    for r in rows: byid[r["source_id"]].append(r)

    matched=[]; unmatched=[]; ambiguous=[]
    for p in picks:
        rr=byid[p["source_id"]]
        mc=int(rr[0].get("match_count") or 0)
        if mc==0: unmatched.append(p)
        elif mc==1: matched.append(rr[0])
        else: ambiguous.extend(rr)

    def normal(r):
        v=r.get("abnormal_code")
        return v in (None,"",0,"0")
    bettable=[r for r in matched if normal(r)]
    abnormal=[r for r in matched if not normal(r)]

    winners=[r for r in bettable if inum(r.get("finish"))==1 and fnum(r.get("win_payout")) and fnum(r.get("final_win_odds")) is not None][:10]
    payout_audit=[]
    for r in winners:
        odds=fnum(r["final_win_odds"]); pay=fnum(r["win_payout"])
        payout_audit.append({
          "race_date":r["race_date"],"venue":r["venue"],"race_no":r["race_no"],
          "horse":r["source_horse_name"],"final_win_odds":odds,"win_payout":pay,
          "odds_x_100":round(odds*100,6),"difference":round(pay-odds*100,6),
          "place_payout":fnum(r.get("place_payout"))
        })
    unit_ok=bool(payout_audit) and all(abs(x["difference"])<0.01 for x in payout_audit)

    summary={
      "schema_version":"keibailuka-research-v0.2",
      "source_population":{"total":len(picks),"matched":len(matched),"unmatched":len(unmatched),
        "ambiguous":len({r["source_id"] for r in ambiguous}),"match_rate_pct":pct(len(matched),len(picks))},
      "bettable_population":{"N":len(bettable),"abnormal_excluded":len(abnormal)},
      "payout_unit_audit":{"unit_confirmed_100yen":unit_ok,"examples":payout_audit},
      "overall":metric(bettable),"by_year":{},"by_popularity":{},"by_win_odds":{}
    }
    for y in (2024,2025):
        summary["by_year"][str(y)]=metric([r for r in bettable if r["year"]==y])

    pop_bins=[
      ("1人気",lambda p:p==1),("2人気",lambda p:p==2),("3人気",lambda p:p==3),
      ("4〜5人気",lambda p:p is not None and 4<=p<=5),
      ("6〜9人気",lambda p:p is not None and 6<=p<=9),
      ("10人気以下",lambda p:p is not None and p>=10),
    ]
    for name,fn in pop_bins:
        summary["by_popularity"][name]=metric([r for r in bettable if fn(inum(r.get("final_popularity")))])

    odds_bins=[
      ("<3",lambda o:o is not None and o<3),
      ("3〜4.9",lambda o:o is not None and 3<=o<5),
      ("5〜9.9",lambda o:o is not None and 5<=o<10),
      ("10〜19.9",lambda o:o is not None and 10<=o<20),
      ("20〜49.9",lambda o:o is not None and 20<=o<50),
      ("50+",lambda o:o is not None and o>=50),
    ]
    for name,fn in odds_bins:
        summary["by_win_odds"][name]=metric([r for r in bettable if fn(fnum(r.get("final_win_odds")))])

    write_csv(out/"join_unmatched.csv",unmatched)
    write_csv(out/"join_ambiguous.csv",ambiguous)
    write_csv(out/"payout_unit_audit.csv",payout_audit)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")

    def fm(v):
        if v is None:return "-"
        if isinstance(v,float): return f"{v:.2f}"
        return str(v)
    lines=["# keibailuka Historical Research 2024-2025",""]
    sp=summary["source_population"]
    lines += [
      f"- total: {sp['total']} / matched: {sp['matched']} / unmatched: {sp['unmatched']} / ambiguous: {sp['ambiguous']}",
      f"- match rate: {fm(sp['match_rate_pct'])}%",
      f"- bettable N: {len(bettable)} / abnormal excluded: {len(abnormal)}",
      f"- payout 100yen unit confirmed: {unit_ok}","",
      "## Overall"
    ]
    m=summary["overall"]
    lines.append(f"N={m['N']} wins={m['wins']} places={m['places']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    lines += ["","## By year"]
    for k,m in summary["by_year"].items():
        lines.append(f"- {k}: N={m['N']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    lines += ["","## By popularity"]
    for k,m in summary["by_popularity"].items():
        lines.append(f"- {k}: N={m['N']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    lines += ["","## By win odds"]
    for k,m in summary["by_win_odds"].items():
        lines.append(f"- {k}: N={m['N']} win%={fm(m['win_rate_pct'])} place%={fm(m['place_rate_pct'])} winROI={fm(m['win_roi_pct'])}% placeROI={fm(m['place_roi_pct'])}%")
    (out/"summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("\n".join(lines))

if __name__=="__main__":
    main()
