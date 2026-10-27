#!/usr/bin/env python3
"""Build read-only provisional pedigree overlay from PACI-contained UKC records.

No name-based identity fallback, no CURRENT writes, no retrospective as-of claims.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def field(raw,start,end):
    return raw[start:end].decode("cp932","strict").strip()

def parse(raw):
    if len(raw)!=290:
        raise ValueError(f"unexpected UKC record length: {len(raw)}")
    positions={"horse_id":(0,8),"horse_name":(8,44),"sire_name":(49,85),
      "dam_name":(85,121),"broodmare_sire_name":(121,157),
      "birth_date":(157,165),"sire_birth_year":(165,169),
      "dam_birth_year":(169,173),"broodmare_sire_birth_year":(173,177),
      "profile_data_date":(268,276),"sire_line_code":(276,280),
      "broodmare_sire_line_code":(280,284)}
    return {k:field(raw,*v) for k,v in positions.items()}

def recover(paci_dir,missing_json,output_json):
    source=json.loads(missing_json.read_text(encoding="utf-8"))
    if source.get("kyi_year")!=2025:
        raise ValueError("unexpected cohort year")
    missing={str(x["horse_id"]):x for x in source["missing_horses"]}
    if len(missing)!=source["missing_in_all_ukc_years_count"]:
        raise ValueError("missing list count/identity collision")
    archives=sorted(paci_dir.glob("PACI26????.zip"))
    if not archives:
        raise ValueError("2026 PACI source missing")
    matches=defaultdict(list)
    receipts=[]
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:
                raise ValueError("corrupt PACI ZIP: "+archive.name)
            names=[n for n in z.namelist() if re.fullmatch(r"UKC26\d{4}\.txt",Path(n).name,re.I)]
            if len(names)!=1:
                raise ValueError("PACI expected one UKC member: "+archive.name)
            count=0
            for raw in z.read(names[0]).splitlines():
                row=parse(raw);count+=1
                horse_id=row["horse_id"]
                if horse_id in missing:
                    date=row["profile_data_date"]
                    try: datetime.strptime(date,"%Y%m%d")
                    except ValueError as exc: raise ValueError(f"invalid UKC date {horse_id} {date}") from exc
                    matches[horse_id].append((date,row,archive.name,names[0]))
            receipts.append({"archive":archive.name,"sha256":sha256(archive),"ukc_rows":count})
    horses=[]; name_differences=[]
    for horse_id,kyi in sorted(missing.items()):
        candidates=matches.get(horse_id,[])
        if not candidates:
            horses.append({"horse_id":horse_id,"horse_name":kyi.get("horse_name_sample"),
               "registration_state":"PROVISIONAL_ID_ONLY","identity_source":"KYI_2025",
               "sire_name":None,"dam_name":None,"broodmare_sire_name":None,
               "sire_line_code":None,"broodmare_sire_line_code":None,
               "ancestor_resolution":"UNKNOWN","historical_asof_verified":False})
            continue
        date=max(t[0] for t in candidates)
        latest=[t for t in candidates if t[0]==date]
        if len({json.dumps(t[1],ensure_ascii=False,sort_keys=True) for t in latest})!=1:
            raise ValueError("same-date profile conflict: "+horse_id)
        _,p,archive,member=latest[0]
        if p["horse_name"]!=kyi.get("horse_name_sample"):
            name_differences.append({"horse_id":horse_id,"kyi":kyi.get("horse_name_sample"),"ukc":p["horse_name"]})
        horses.append({**p,"registration_state":"SOURCE_VERIFIED_2026_UKC",
           "source_archive":archive,"source_member":member,
           "observations_count":len(candidates),"horse_name_kyi":kyi.get("horse_name_sample"),
           "identity_source":"KYI_2025+UKC_2026","historical_asof_verified":False})
    report={"schema_version":1,"cohort":"KYI_2025_missing_108",
        "paci_archive_count":len(archives),"paci_ukc_record_count":sum(r["ukc_rows"] for r in receipts),
        "target_horse_count":len(horses),
        "source_verified_count":sum(h["registration_state"]=="SOURCE_VERIFIED_2026_UKC" for h in horses),
        "provisional_id_only_count":sum(h["registration_state"]=="PROVISIONAL_ID_ONLY" for h in horses),
        "horse_name_discrepancies":name_differences,
        "receipts":receipts,"horses":horses,
        "historical_asof_verified":False,"production_current_modified":False}
    output_json.parent.mkdir(parents=True,exist_ok=True)
    if output_json.exists(): raise FileExistsError(output_json)
    output_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--paci-dir",required=True,type=Path)
    p.add_argument("--missing-json",required=True,type=Path)
    p.add_argument("--output-json",required=True,type=Path)
    a=p.parse_args()
    report=recover(a.paci_dir,a.missing_json,a.output_json)
    print(json.dumps({k:report[k] for k in ("paci_archive_count","source_verified_count","provisional_id_only_count")},ensure_ascii=False))
