#!/usr/bin/env python3
"""Private-source real Parquet smoke for JPDB candidate Reader.

Emits only aggregate validation counts; does not export jockey IDs or source rows.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / "src"))
from jpdb_history_reader import JPDBHistoryReader, JPDBHistoryReaderError, POLICY, POPULATION


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    with JPDBHistoryReader(input_root=a.input_root,manifest=a.manifest) as reader:
        db=reader.db
        target="2025-11-15"
        # Find test subjects internally, but never disclose source jockey keys in output.
        jockeys=[r[0] for r in db.execute("""SELECT jockey_code FROM sed_all
           WHERE race_date<'2025-11-15' AND surface_code IN ('1','2')
           GROUP BY jockey_code ORDER BY COUNT(*) DESC,jockey_code LIMIT 12""").fetchall()]
        if len(jockeys)!=12:
            raise JPDBHistoryReaderError("insufficient real jockeys for focused smoke")
        inspections=[]
        for code in jockeys:
            r=reader.rider_history(target_date=target,jockey_code=code)
            exact=db.execute("""SELECT COUNT(*),
               COUNT(*) FILTER(WHERE abnormal_code IN ('0','')),
               COUNT(*) FILTER(WHERE abnormal_code IN ('0','') AND finish=1),
               COUNT(*) FILTER(WHERE abnormal_code IN ('0','') AND finish BETWEEN 1 AND 3)
               FROM sed_all WHERE jockey_code=?
               AND surface_code IN ('1','2') AND race_date<'2025-11-15'
               AND race_date>='2023-01-01'""",[code]).fetchone()
            row=r["all_flat"]
            if tuple(row[x] for x in ("entries","normal_finishes","wins","top3"))!=exact:
                raise JPDBHistoryReaderError("independent SQL disagree for historical jockey")
            if row["latest_date"] is not None and row["latest_date"]>=target:
                raise JPDBHistoryReaderError("same-day leakage")
            if r["population_filter_id"]!=POPULATION or r["asof_policy"]!=POLICY:
                raise JPDBHistoryReaderError("policy regression")
            inspections.append(row["entries"])
        empty=reader.rider_history(target_date="2023-01-01",jockey_code=jockeys[0])
        if empty["sample_status"]!="NO_HISTORY" or empty["all_flat"]["entries"]!=0:
            raise JPDBHistoryReaderError("initial boundary leaked")
        actual_year_count=db.execute("SELECT count(*) FROM sed_all").fetchone()[0]
        if actual_year_count!=142737:
            raise JPDBHistoryReaderError("source count mismatch")
        result={
          "status":"PASS",
          "kind":"JPDB_P1_CANDIDATE_READER_REAL_SMOKE",
          "source_generation":r["source_generation"],
          "source_manifest_sha256":reader.manifest_sha256,
          "source_count_sed":actual_year_count,
          "target_date":target,
          "tested_distinct_jockey_codes":len(jockeys),
          "independent_aggregate_sql_matches":len(inspections),
          "historical_entries_in_test_group":sum(inspections),
          "initial_boundary_no_history":True,
          "no_target_day_results":True,
          "asof_policy":POLICY,
          "population_filter_id":POPULATION,
          "historical_release_attested":False,
          "strict_asof_certified":False,
          "racenote_connected":False,
        }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
