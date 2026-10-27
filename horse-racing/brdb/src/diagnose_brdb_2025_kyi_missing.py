#!/usr/bin/env python3
"""Diagnose 2025 KYI horse IDs absent from all pinned 1999–2025 UKC archives."""
from __future__ import annotations
import argparse,json,re,zipfile
from collections import Counter
from pathlib import Path

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--kyi-root",type=Path,required=True)
 ap.add_argument("--ukc-root",type=Path,required=True)
 ap.add_argument("--output-json",type=Path,required=True)
 a=ap.parse_args()
 import duckdb
 con=duckdb.connect(":memory:")
 k=list(a.kyi_root.rglob("KYI_2025.parquet"))
 if len(k)!=1:raise ValueError("expected one KYI 2025")
 rows=con.execute("SELECT CAST(blood_registration_no AS VARCHAR),CAST(horse_name AS VARCHAR),CAST(race_key_raw AS VARCHAR) FROM read_parquet(?)",[str(k[0])]).fetchall()
 con.close()
 by_horse={}
 for horse,name,key in rows:
  if horse is not None:by_horse.setdefault(horse.strip(),[]).append((name,key))
 archive_ids=set()
 archives=list(a.ukc_root.rglob("UKC_*.zip"))
 if len(archives)!=27:raise ValueError("expected 27 UKC archive files")
 for zf in archives:
  with zipfile.ZipFile(zf) as z:
   for member in z.namelist():
    if not re.search(r"(^|/)UKC[^/]*\.txt$",member,re.I):continue
    with z.open(member) as f:
     for raw in f:
      row=raw.rstrip(b"\r\n")
      if len(row)!=290:raise ValueError("unexpected UKC length")
      archive_ids.add(row[:8].decode("ascii").strip())
 missing=sorted(by_horse.keys()-archive_ids)
 records=[]
 for horse in missing:
  sample=by_horse[horse]
  records.append({"horse_id":horse,"horse_name_sample":sample[0][0],"kyi_entry_count":len(sample),"race_key_earliest":min(t[1] for t in sample),"race_key_latest":max(t[1] for t in sample)})
 result={"archive_scope":"1999-2025 UKC","kyi_year":2025,"distinct_kyi_horses":len(by_horse),"missing_in_all_ukc_years_count":len(missing),"missing_horses":records,"missing_id_prefix2":dict(sorted(Counter(x[:2] for x in missing).items())),"missing_id_prefix4":dict(sorted(Counter(x[:4] for x in missing).items())),"interpretation":"Identity-only mismatch audit; do not infer missing cause from prefix or horse name.","production_cutover":False}
 a.output_json.parent.mkdir(parents=True,exist_ok=True)
 a.output_json.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"distinct_kyi_horses":len(by_horse),"missing_in_all_ukc_years_count":len(missing),"sample":records[:5]},ensure_ascii=False))
if __name__=="__main__":main()
