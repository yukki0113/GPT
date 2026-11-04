#!/usr/bin/env python3
"""Pinned annual UKC ZIP metadata inventory. ZIP mtimes NEVER prove release times."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

VERSION = "brdb-p1-4b-ukc-zip-timestamp-inventory-v0.1"
MEMBER = re.compile(r"^UKC(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})\.txt$",re.I)

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1048576),b""):h.update(chunk)
    return h.hexdigest()

def nominal_day(name,year):
    m=MEMBER.fullmatch(name)
    if m is None:raise ValueError("invalid UKC member filename")
    yy,mm,dd=map(int,(m["yy"],m["mm"],m["dd"]))
    if 2000+yy!=year:raise ValueError("archive/member year mismatch")
    return date(2000+yy,mm,dd)

def audit(root,manifest):
    root=Path(root).resolve()
    entries=manifest.get("archives")
    if not isinstance(entries,list) or [r.get("year") for r in entries]!=list(range(2016,2026)):
        raise ValueError("require exactly 2016-2025 annual UKC archives")
    annual=[]
    for entry in entries:
        year=entry["year"]
        path=root/("UKC_"+str(year)+".zip")
        if not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError("archive unavailable")
        if path.stat().st_size!=entry["size_bytes"] or digest(path)!=entry["sha256"]:
            raise ValueError("ZIP SHA/size mismatch")
        created=entry.get("drive_created_time")
        if not isinstance(created,str) or not created.startswith("2026-09-16T"):
            raise ValueError("missing expected Drive upload-time provenance")
        buckets=Counter();names=set()
        try:
            with ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.is_dir():raise ValueError("directory not allowed")
                    name=member.filename.lower()
                    if name in names:raise ValueError("duplicate member")
                    names.add(name)
                    day=nominal_day(member.filename,year)
                    try:stamp=datetime(*member.date_time).date()
                    except (ValueError,TypeError) as exc:raise ValueError("invalid ZIP mtime") from exc
                    lag=(day-stamp).days
                    if lag>=2:bucket="member_mtime_2plus_days_before"
                    elif lag==1:bucket="member_mtime_previous_day"
                    elif lag==0:bucket="member_mtime_same_day"
                    else:bucket="member_mtime_after_day"
                    buckets[bucket]+=1
                if archive.testzip() is not None:raise ValueError("ZIP CRC mismatch")
        except BadZipFile as exc:raise ValueError("invalid ZIP") from exc
        keys=("member_mtime_2plus_days_before","member_mtime_previous_day","member_mtime_same_day","member_mtime_after_day")
        annual.append({"year":year,"members":len(names),"archive_bytes":entry["size_bytes"],
                       "archive_sha256":entry["sha256"],"drive_created_time":created,
                       **{k:buckets[k] for k in keys}})
    totals={key:sum(row[key] for row in annual) for key in ("members",)+keys}
    if sum(totals[k] for k in keys)!=totals["members"]:raise AssertionError("classification gap")
    return {"version":VERSION,"status":"PASS_ARCHIVE_INVENTORY_ONLY",
      "years":"2016-2025","files_verified":len(annual),"totals":totals,"annual":annual,
      "archive_metadata_is_independent_release_proof":False,
      "asof_attested_entries":0,"prediction_safe":False,
      "decision":"HOLD_FOR_INDEPENDENT_PRE_RACE_DISTRIBUTION_EVIDENCE",
      "notes":[
       "ZIP member mtime is editable and does not independently attest JRDB distribution.",
       "Nominal member filename dates do not independently attest actual release or race start.",
       "Drive created_time in September 2026 is a later upload, not historical release.",
       "No horse-level as-of feature admission or prediction backtest is performed."]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=audit(args.archive_root,json.loads(args.manifest.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"ukc_zip_timestamps_audit.json").write_text(
        json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"totals":result["totals"]}))
if __name__=="__main__":main()
