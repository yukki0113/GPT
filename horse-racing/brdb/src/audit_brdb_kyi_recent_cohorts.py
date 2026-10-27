#!/usr/bin/env python3
"""Audit recent KYI race-entry identity against isolated BRDB candidate (research only)."""
from __future__ import annotations
import argparse,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--kyi-root",type=Path,required=True)
 p.add_argument("--generation-root",type=Path,required=True)
 p.add_argument("--output-json",type=Path,required=True)
 a=p.parse_args()
 import duckdb
 con=duckdb.connect(":memory:")
 roots=list(a.generation_root.glob("brdb-pedigree-generation-*"))
 if len(roots)!=1:raise ValueError("single candidate generation required")
 root=roots[0]
 prof={str(r[0]):r for r in con.execute("SELECT horse_id,sire_name,dam_name,broodmare_sire_name,sire_line_code,broodmare_sire_line_code,profile_data_date FROM read_parquet(?)",[str(root/"pedigree_fact.parquet")]).fetchall()}
 codes={r[0] for r in con.execute("SELECT lineage_code FROM read_parquet(?)",[str(root/"lineage_code_master.parquet")]).fetchall()}
 out=[]
 for year in (2023,2024,2025):
  files=list(a.kyi_root.rglob(f"KYI_{year}.parquet"))
  if len(files)!=1: raise ValueError(f"missing KYI_{year}")
  f=str(files[0])
  columns=[str(x[0]) for x in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[f]).fetchall()]
  candidates=("blood_registration_no","horse_id","blood_registration_number","ketto_toroku_bango")
  key=next((x for x in candidates if x in columns),None)
  if not key:raise ValueError(f"KYI_{year} missing approved identity key: {columns}")
  ids=[str(x[0]).strip() for x in con.execute(f'SELECT CAST("{key}" AS VARCHAR) FROM read_parquet(?)',[f]).fetchall()]
  unique=set(x for x in ids if x and x.lower()!="none")
  selected=[prof[x] for x in unique if x in prof]
  stats={"year":year,"source_family":"JRDB_KYI","source_columns":columns,"identity_field":key,"entry_rows":len(ids),"unique_horse_ids":len(unique),
   "matched_horse_ids":len(selected),"missing_master_horse_ids":sorted(unique-prof.keys())[:100],
   "sire_name_present":sum(bool(r[1]) for r in selected),"dam_name_present":sum(bool(r[2]) for r in selected),
   "bms_name_present":sum(bool(r[3]) for r in selected),
   "all_three_names":sum(all(bool(r[i]) for i in (1,2,3)) for r in selected),
   "sire_line_mapped":sum(r[4] in codes for r in selected),
   "bms_line_mapped":sum(r[5] in codes for r in selected),
   "both_lines_mapped":sum(r[4] in codes and r[5] in codes for r in selected),
   "profile_later_than_year_end":sum(str(r[6])>f"{year}1231" for r in selected),
   "asof_safe_backtest_ready":False}
  for metric in ("matched_horse_ids","sire_name_present","dam_name_present","bms_name_present","all_three_names","sire_line_mapped","bms_line_mapped","both_lines_mapped"):
   stats[metric+"_pct"]=round(100*stats[metric]/len(unique),4) if unique else None
  out.append(stats)
 con.close()
 report={"generation_id":root.name.removeprefix("brdb-pedigree-generation-"),"cohort_type":"KYI race entries by warehouse year; confirm race date semantics before retrospective features","by_year":out,"2026_status":"NOT_PRESENT_IN_2010_2025_WAREHOUSE","historical_feature_asof_cleared":False,"production_cutover":False}
 a.output_json.parent.mkdir(parents=True,exist_ok=True)
 a.output_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"generation_id":report["generation_id"],"years":[{k:v for k,v in row.items() if k in ("year","entry_rows","unique_horse_ids","matched_horse_ids","both_lines_mapped","profile_later_than_year_end")} for row in out]},ensure_ascii=False))
if __name__=="__main__":main()
