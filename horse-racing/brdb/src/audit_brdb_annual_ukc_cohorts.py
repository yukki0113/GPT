#!/usr/bin/env python3
"""Audit UKC annual archive cohorts against a separately built BRDB candidate.

Annual UKC membership is NOT equivalent to actual race entrants in that year.
"""
from __future__ import annotations
import argparse, json, re, zipfile
from collections import defaultdict
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive-root",type=Path,required=True)
    ap.add_argument("--generation-root",type=Path,required=True)
    ap.add_argument("--output-json",type=Path,required=True)
    args=ap.parse_args()
    roots=list(args.generation_root.glob("brdb-pedigree-generation-*"))
    if len(roots)!=1: raise ValueError("expected exactly one candidate generation")
    root=roots[0]
    import duckdb
    con=duckdb.connect(":memory:")
    try:
        cur=con.execute("SELECT horse_id,sire_name,dam_name,broodmare_sire_name,sire_line_code,broodmare_sire_line_code,profile_data_date FROM read_parquet(?)",[str(root/"pedigree_fact.parquet")])
        profiles={str(x[0]):x for x in cur.fetchall()}
        known={x[0] for x in con.execute("SELECT lineage_code FROM read_parquet(?)",[str(root/"lineage_code_master.parquet")]).fetchall()}
    finally:con.close()
    annual=[]
    for year in range(2016,2026):
        zips=list(args.archive_root.rglob(f"UKC_{year}.zip"))
        if len(zips)!=1:raise ValueError(f"expected UKC_{year}.zip exactly once")
        ids=set();rows=0;valid_dates=set()
        with zipfile.ZipFile(zips[0]) as z:
            for name in z.namelist():
                if not re.search(r"(^|/)UKC[^/]*\.txt$",name,re.I):continue
                with z.open(name) as f:
                    for line in f:
                        body=line.rstrip(b"\r\n")
                        if len(body)!=290:raise ValueError(f"invalid record length {year}/{name}")
                        horse=body[:8].decode("ascii").strip()
                        ids.add(horse);rows+=1
                        valid_dates.add(body[268:276].decode("ascii"))
        met={"archive_year":year,"cohort_type":"UKC_ANNUAL_ARCHIVE_MEMBERSHIP_NOT_RACE_ENTRANTS","observation_rows":rows,"unique_horses":len(ids)}
        predicates={
            "master_joined":lambda p:True,
            "sire_name_present":lambda p:bool(p[1]),
            "dam_name_present":lambda p:bool(p[2]),
            "bms_name_present":lambda p:bool(p[3]),
            "all_three_names":lambda p:all(bool(p[i]) for i in (1,2,3)),
            "sire_line_mapped":lambda p:bool(p[4]) and p[4] in known,
            "bms_line_mapped":lambda p:bool(p[5]) and p[5] in known,
            "both_lines_mapped":lambda p:p[4] in known and p[5] in known,
        }
        present=[profiles[x] for x in ids if x in profiles]
        for key,fn in predicates.items():
            count=sum(bool(fn(p)) for p in present)
            met[key]={"count":count,"pct_of_unique_horses":round(100*count/len(ids),4) if ids else None}
        met["missing_master_ids"]=sorted(ids-profiles.keys())[:100]
        met["profile_date_after_archive_year_end_count"]=sum(p[6]>f"{year}1231" for p in present)
        met["profile_date_after_archive_year_end_note"]="Not an as-of-safe snapshot, not a backtest-ready feature projection"
        annual.append(met)
    output={"generation_id":root.name.removeprefix("brdb-pedigree-generation-"),"population_definition":"UKC archive membership, not actual race starters","2026_status":"NOT_IN_PINNED_SOURCE","annual_archive_cohorts":annual,"production_cutover":False}
    args.output_json.parent.mkdir(parents=True,exist_ok=True)
    args.output_json.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"generation_id":output["generation_id"],"annual_summary":[{"year":x["archive_year"],"unique":x["unique_horses"],"joined":x["master_joined"]["count"],"both_lines":x["both_lines_mapped"]["count"],"future_profiles":x["profile_date_after_archive_year_end_count"]} for x in annual]},ensure_ascii=False))

if __name__=="__main__":main()
