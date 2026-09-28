#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, io, json, re, sys, tempfile, zipfile
from pathlib import Path
from urllib.parse import quote
import requests

REPO=Path(__file__).resolve().parents[3]
JRDB_SRC=REPO/"horse-racing"/"jrdb"/"src"
if str(JRDB_SRC) not in sys.path: sys.path.insert(0,str(JRDB_SRC))
from jrdb_raw import ReaderAudit, canonical_members, read_fixed_records
from jrdb_warehouse_normalize import RawProvenance, normalize_record
from analyze_keibailuka_historical import VENUE_CODES, load_reason_definitions, normalize_name, tag_comment, to_int, to_float, write_csv, metric

RULE_ID="KBI_SURFACE_BASEPOP_6_9_V01"

def get(url,**kwargs):
    r=requests.get(url,timeout=120,**kwargs); r.raise_for_status(); return r

def fetch_sheet(spreadsheet_id,sheet_name):
    url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return list(csv.DictReader(io.StringIO(get(url).content.decode("utf-8-sig"))))

def download(fid,path,expected_size=None):
    data=get("https://drive.usercontent.google.com/download",params={"id":fid,"export":"download","confirm":"t"}).content
    if b"<html" in data[:200].lower():
        data=get("https://drive.google.com/uc",params={"export":"download","id":fid}).content
    path.write_bytes(data)
    if expected_size is not None and path.stat().st_size!=int(expected_size):
        raise RuntimeError(f"size mismatch {path.name}: {path.stat().st_size} != {expected_size}")

def parse_zip(path,family,date):
    out=[]
    with zipfile.ZipFile(path) as z:
        members=canonical_members(z,family)
        if not members: raise RuntimeError(f"no {family} members in {path.name}")
        for member in members:
            audit=ReaderAudit()
            records=read_fixed_records(z,member,family,audit)
            if audit.record_length_errors: raise RuntimeError(f"{family} length errors {dict(audit.record_length_errors)}")
            for i,rec in enumerate(records,1):
                row=normalize_record(family,rec,RawProvenance(source_archive_name=path.name,source_member=member,source_record_ordinal=i))
                row["_date"]=date
                out.append(row)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--request-json",required=True)
    ap.add_argument("--output-dir",required=True)
    args=ap.parse_args()
    req=json.load(open(args.request_json,encoding="utf-8"))
    outdir=Path(args.output_dir); outdir.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix="kbi_settle_"))
    reason_defs=load_reason_definitions()
    ledger=fetch_sheet(req["spreadsheet_id"],"イルカ明細")

    all_kyi=[]; all_sed=[]
    for d,spec in req["dates"].items():
        kp=temp/f"PACI{d.replace('-','')[2:]}.zip"; sp=temp/f"SED{d.replace('-','')[2:]}.zip"
        download(spec["paci_id"],kp,spec["paci_size"])
        download(spec["sed_id"],sp,spec["sed_size"])
        ky=parse_zip(kp,"KYI",d); se=parse_zip(sp,"SED",d)
        if len(ky)!=len(se): raise RuntimeError(f"daily row mismatch {d}: {len(ky)} vs {len(se)}")
        all_kyi += ky; all_sed += se

    kyi_by_name={}
    for r in all_kyi:
        k=(r["_date"],str(r.get("venue_code") or "").zfill(2),to_int(r.get("race_no")),normalize_name(r.get("horse_name")))
        kyi_by_name.setdefault(k,[]).append(r)
    sed_by_key={(r["_date"],str(r.get("race_key_raw") or ""),to_int(r.get("horse_no"))):r for r in all_sed}

    settled=[]; unmatched=[]; ambiguous=[]
    for src in ledger:
        d=(src.get("日付") or "").strip()
        if d not in req["dates"]: continue
        horse=(src.get("馬名_raw") or "").strip()
        venue=(src.get("会場") or "").strip()
        rm=re.fullmatch(r"(\d+)R",(src.get("R") or "").strip())
        if not horse or horse=="🤡" or venue not in VENUE_CODES or not rm: continue
        key=(d,VENUE_CODES[venue],int(rm.group(1)),normalize_name(horse))
        matches=kyi_by_name.get(key,[])
        if len(matches)==0:
            unmatched.append({"key":src.get("key"),"reason":"kyi_unmatched"}); continue
        if len(matches)>1:
            ambiguous.append({"key":src.get("key"),"candidate_count":len(matches)}); continue
        kyi=matches[0]
        sed=sed_by_key.get((d,str(kyi.get("race_key_raw") or ""),to_int(kyi.get("horse_no"))))
        if sed is None:
            unmatched.append({"key":src.get("key"),"reason":"sed_unmatched"}); continue
        tags=tag_comment(src.get("コメント") or "",reason_defs)
        primary=tags[0]
        base_rank=to_int(kyi.get("base_win_rank"))
        shadow=(primary=="surface" and base_rank is not None and 6<=base_rank<=9)
        finish=to_int(sed.get("finish"))
        fp=to_int(sed.get("final_popularity"))
        row={
          "key":src.get("key"),"日付":d,"会場":venue,"R":src.get("R"),"馬名":horse,
          "primary_reason":primary,"base_win_rank":base_rank,"base_win_odds":to_float(kyi.get("base_win_odds")),
          "shadow_rule_id":RULE_ID if shadow else "","shadow_selected":1 if shadow else 0,
          "着順":finish,"確定単勝人気順位":fp,"最終単勝オッズ":to_float(sed.get("final_win_odds")),
          "単勝払戻":to_float(sed.get("win_payout")) or 0,"複勝払戻":to_float(sed.get("place_payout")) or 0,
          "異常区分":sed.get("abnormal_code"),
          "単勝的中":1 if finish==1 else 0,"複勝的中":1 if finish is not None and finish<=3 else 0,
        }
        settled.append(row)

    if ambiguous: raise RuntimeError(f"ambiguous rows: {ambiguous}")
    write_csv(outdir/"settled_all.csv",settled)
    write_csv(outdir/"unmatched.csv",unmatched)
    write_csv(outdir/"shadow_selected.csv",[r for r in settled if r["shadow_selected"]==1])

    shadow_rows=[{
      "finish":r["着順"],"win_payout":r["単勝払戻"],"place_payout":r["複勝払戻"]
    } for r in settled if r["shadow_selected"]==1 and r["異常区分"] in (None,"",0,"0")]
    sm=metric(shadow_rows)
    result={
      "status":"PASS",
      "dates":list(req["dates"].keys()),
      "settled_count":len(settled),
      "unmatched_count":len(unmatched),
      "ambiguous_count":len(ambiguous),
      "shadow_rule_id":RULE_ID,
      "shadow_selected_count":len(shadow_rows),
      "shadow_metrics":sm,
      "decision_uses_result_data":False,
      "settlement_uses_sed":True
    }
    (outdir/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[
      "# keibailuka 2026-09-26/27 settlement",
      "",
      f"- settled: {len(settled)}",
      f"- unmatched: {len(unmatched)}",
      f"- ambiguous: {len(ambiguous)}",
      f"- shadow selected: {len(shadow_rows)}",
      f"- shadow wins: {sm['wins']}",
      f"- shadow places: {sm['places']}",
      f"- shadow win ROI: {sm['win_roi_pct']}%",
      f"- shadow place ROI: {sm['place_roi_pct']}%",
    ]
    (outdir/"summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("\n".join(lines))

if __name__=="__main__": main()
