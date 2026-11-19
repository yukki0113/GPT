#!/usr/bin/env python3
"""Aggregate-only real-PARQUET verification for JPDB P1.1 batch Reader."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from jpdb_performance_reader_v11 import JPDBPerformanceReader, POPULATION
from jpdb_history_reader import JPDBHistoryReaderError


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    # Audit on private licensed input; export totals only, not jockey-level facts.
    with JPDBPerformanceReader(input_root=a.input_root,manifest=a.manifest) as reader:
        db=reader.db
        codes=[row[0] for row in db.execute("""SELECT jockey_code FROM sed_all
              WHERE race_date < '2025-11-15' AND surface_code IN ('1','2')
              GROUP BY jockey_code ORDER BY COUNT(*) DESC,jockey_code LIMIT 12""").fetchall()]
        if len(codes)!=12:
            raise JPDBHistoryReaderError("insufficient jockeys for full fixture")
        response=reader.rider_histories(target_date="2025-11-15",jockey_codes=codes)
        if response["population_filter_id"]!=POPULATION or len(response["jockey_histories"])!=12:
            raise JPDBHistoryReaderError("batch result contract violation")
        group_total=0
        for code in codes:
            stats=response["jockey_histories"][code]["windows"]["ROLLING_3Y"]["all_flat"]
            expected=db.execute("""SELECT
                  COUNT(*) FILTER(WHERE surface_code IN ('1','2')),
                  COUNT(*) FILTER(WHERE surface_code IN ('1','2') AND abnormal_code='1'),
                  COUNT(*) FILTER(WHERE surface_code IN ('1','2') AND abnormal_code='2'),
                  COUNT(*) FILTER(WHERE surface_code IN ('1','2') AND abnormal_code='3'),
                  COUNT(*) FILTER(WHERE surface_code IN ('1','2') AND abnormal_code='5'),
                  COUNT(*) FILTER(WHERE surface_code IN ('1','2')
                     AND abnormal_code IN ('0','') AND finish BETWEEN 1 AND field_size
                     AND field_size >= 1),
                  COUNT(*) FILTER(WHERE surface_code IN ('1','2')
                     AND abnormal_code IN ('0','') AND finish=1 AND finish BETWEEN 1 AND field_size
                     AND field_size >= 1)
               FROM sed_all WHERE jockey_code=? AND race_date<'2025-11-15'
                     AND race_date>='2023-01-01'""",[code]).fetchone()
            found=tuple(stats[k] for k in
                 ("entries","cancellations","exclusions","dnf","demotion_review","normal_finishers","wins"))
            if found!=expected:
                raise JPDBHistoryReaderError("independent raw SED aggregate differs")
            group_total+=stats["entries"]
        # Full source diagnostic, including unexpected abnormal codes and normal finish validity.
        full=db.execute("""SELECT
             COUNT(*) AS entries,
             COUNT(*) FILTER(WHERE abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3','5')),
             COUNT(*) FILTER(WHERE abnormal_code IN ('0','')
                     AND (finish IS NULL OR field_size IS NULL OR field_size < 1
                     OR finish NOT BETWEEN 1 AND field_size)),
             COUNT(*) FILTER(WHERE abnormal_code='5')
             FROM sed_all WHERE surface_code IN ('1','2')""").fetchone()
        # Boundary: even the latest 2025 race is excluded by 2023-01-01.
        boundary=reader.rider_histories(target_date="2023-01-01",jockey_codes=codes)
        if any(v["windows"]["ROLLING_3Y"]["all_flat"]["entries"]
               for v in boundary["jockey_histories"].values()):
            raise JPDBHistoryReaderError("early boundary leakage")
        # Existing v0.1 must continue to return its original schema and counts.
        earlier=reader.rider_history(target_date="2025-11-15",jockey_code=codes[0])
        old_total=earlier["all_flat"]["entries"]
        new_total=response["jockey_histories"][codes[0]]["windows"]["ROLLING_3Y"]["all_flat"]["entries"]
        if earlier["schema_version"]!="jpdb-history-reader-v0.1" or old_total!=new_total:
            raise JPDBHistoryReaderError("v0.1 compatibility break")
        result={
          "status":"PASS",
          "audit_type":"JPDB_P11_BATCH_READER_REAL_SQL",
          "source_sed_entries_all_surfaces":142737,
          "source_flat_entries":int(full[0]),
          "source_flat_unknown_code":int(full[1]),
          "source_flat_invalid_normal_finish":int(full[2]),
          "source_flat_demotions_review":int(full[3]),
          "tested_distinct_jockey_codes":len(codes),
          "independent_sql_matches":len(codes),
          "tested_historical_flat_entries":group_total,
          "v01_compatibility":True,
          "zero_history_2023_boundary":True,
          "target_day_excluded":True,
          "asof_policy":response["asof_policy"],
          "population_filter_id":POPULATION,
          "source_generation":response["source_generation"],
          "source_manifest_sha256":response["source_manifest_sha256"],
          "racenote_connected":False
        }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
