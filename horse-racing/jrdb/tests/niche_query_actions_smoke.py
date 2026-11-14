#!/usr/bin/env python3
"""Canonical Data Storage / DuckDB 1.1.3 synthetic integration regression.

No proprietary JRDB input and no external Drive read. Executable as an Actions fallback step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import duckdb

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/"horse-racing/jrdb/src/niche_query"))
from run_query import run


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output-dir",type=Path,required=True);a=ap.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/"analysis"; root.mkdir()
        db=duckdb.connect(":memory:")
        db.execute("""CREATE TABLE source (
          race_date VARCHAR, year INTEGER, race_key VARCHAR, race_no INTEGER, horse_no INTEGER,
          horse_id VARCHAR, horse_name VARCHAR, age INTEGER, sire_name VARCHAR, jockey_name VARCHAR,
          track_type VARCHAR, distance INTEGER, race_condition_code VARCHAR, grade_code VARCHAR,
          track_condition_code VARCHAR, final_win_popularity INTEGER, final_win_odds DOUBLE,
          finish INTEGER, abnormal_code VARCHAR, win_payout INTEGER, place_payout INTEGER
        )""")
        rows=[
          ("2024-10-01",2024,"R1",1,1,"H1","馬A",2,"サートゥルナーリア","横山典弘","芝",1400,"OP","6","10",4,18.0,1,"0",1800,300),
          ("2024-10-01",2024,"R2",2,2,"H2","馬B",2,"サートゥルナーリア","横山典弘","芝",1600,"OP","2","20",3,4.0,2,"0",0,250),
          ("2024-10-01",2024,"R3",3,3,"H3","馬C",2,"サートゥルナーリア","横山典弘","芝",1900,"OP","3","30",2,5.0,3,"0",0,180),
          ("2024-10-01",2024,"R4",4,4,"H4","馬D",2,"サートゥルナーリア","他騎手","芝",1400,"OP","6","10",1,1.0,1,"0",120,110),
          ("2025-10-01",2025,"R5",5,5,"H5","馬E",2,"サートゥルナーリア","横山典弘","芝",2000,"OP","3","40",2,4.0,4,"0",0,0),
          ("2025-10-01",2025,"R6",6,6,"H6","馬F",2,"サートゥルナーリア","横山典弘","芝",2000,"OP","3","10",2,4.0,None,"1",None,None),
          ("2025-10-01",2025,"R7",7,7,"H7","馬G",3,"サートゥルナーリア","横山典弘","芝",2000,"OP","3","10",2,4.0,1,"0",500,150),
        ]
        db.executemany("INSERT INTO source VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",rows)
        parts=[]
        for year in (2024,2025):
            directory=root/f"objects/fact_entry_result_lite/year={year}";directory.mkdir(parents=True,exist_ok=True)
            initial=directory/"initial.parquet"
            db.execute(f"COPY (SELECT * FROM source WHERE year={year}) TO '{initial}' (FORMAT PARQUET)")
            data=initial.read_bytes();digest=hashlib.sha256(data).hexdigest();file=directory/(digest+".parquet");initial.rename(file)
            parts.append({"year":year,"sha256":digest,"rows":sum(row[1]==year for row in rows),"size_bytes":len(data),"relative_path":f"objects/fact_entry_result_lite/year={year}/{digest}.parquet"})
        # This shadow object must be ignored by the current-only resolver.
        (root/"objects/fact_entry_result_lite/year=2024/old-shadow.parquet").write_bytes(b"not a parquet")
        gen="synthetic-niche-2025"
        mf={"artifact_type":"jrdb_analysis","schema_version":"v1.4","storage_format":"parquet","generation_id":gen,
            "validation_status":"PASS","period_from":"2024-01-01","period_to":"2025-12-28","total_rows":len(rows),
            "fact_table":{"name":"fact_entry_result_lite","partitions":parts}}
        mp=root/f"generations/{gen}/manifest.json";mp.parent.mkdir(parents=True);mp.write_text(json.dumps(mf))
        (root/"current.json").write_text(json.dumps({"status":"CURRENT","generation_id":gen,"manifest":f"generations/{gen}/manifest.json"}))
        common={"dataset":"jrdb.analysis.current","as_of_generation":"CURRENT_AT_REQUEST","date_from":"2024-01-01","date_to":"2025-12-28"}
        first={**common,"filters":[{"field":"age","op":"eq","value":2},{"field":"jockey_name","op":"eq","value":"横山典弘"},{"field":"race_condition_code","op":"eq","value":"OP"}],
               "groupings":[{"field":"distance","kind":"bands","bands":[{"label":"1200-1400","min":1200,"max":1400},{"label":"1600-1800","min":1600,"max":1800},{"label":"2000+","min":2000,"max":None}],"other_bucket":"excluded_with_count"}],"detail":True}
        first_dir=a.output_dir/"yokoyama"
        audit1=run(first,root,Path(td)/"selected1",first_dir)
        result1=json.loads((first_dir/"results.json").read_text())
        assert audit1["input_parquet_rows"]==7,audit1
        assert audit1["aggregation"]["matching_entries"]==5,audit1
        assert audit1["aggregation"]["excluded_band_entries"]==1,audit1
        by_band={r["g0"]:r for r in result1["rows"]}
        assert by_band["1200-1400"]["win"]==1 and by_band["1200-1400"]["win_roi"]==1800.0,by_band
        assert by_band["1600-1800"]["second"]==1 and by_band["1600-1800"]["place_roi"]==250.0,by_band
        assert by_band["2000+"]["starts"]==1 and by_band["2000+"]["cancelled"]==1,by_band
        second={**common,"filters":[{"field":"age","op":"eq","value":2},{"field":"sire_name","op":"eq","value":"サートゥルナーリア"}],
                "groupings":[{"field":"track_type"},{"field":"track_condition"}],"detail":False}
        second_dir=a.output_dir/"saturnalia"
        audit2=run(second,root,Path(td)/"selected2",second_dir)
        result2=json.loads((second_dir/"results.json").read_text())
        by_going={r["g1"]:r for r in result2["rows"]}
        assert audit2["aggregation"]["matching_entries"]==6,audit2
        assert "良" in by_going and "稍重" in by_going and "重" in by_going and "不良" in by_going,by_going
        print(json.dumps({"status":"PASS","synthetic_entries":len(rows),"case1_matching":5,"case2_matching":6,"checks":["source_manifest","shadow_object_exclusion","roi","cancellation","distance_bands","going_codes"]}))
        (a.output_dir/"smoke_result.json").write_text(json.dumps({"status":"PASS","yokoyama":audit1["aggregation"],"saturnalia":audit2["aggregation"]},ensure_ascii=False,indent=2)+"\n")
        # Existing generic connector snapshot builder, filtered to Analysis only.
        from build_request import main as build_request_main
        dummy=Path(td)/"real-bytes.tar.xz";dummy.write_bytes(b"fixture-snapshot-not-a-real-archive")
        meta={"id":"12345678901234567890","name":"jrdb_analysis_v1_4_canonical_current.tar.xz",
              "size":str(dummy.stat().st_size),"parent_ids":["1sIja9lzuFS1U3jWMwVscZ57NrJiDZGV5"],
              "modified_time":"2025-12-28T09:00:00Z","mime_type":"application/x-tar"}
        snapshot={"sources":{"jrdb.analysis.current":{"candidates":[meta],"metadata_after":meta,"download_path":str(dummy)}}}
        sp=Path(td)/"snapshot.json";sp.write_text(json.dumps(snapshot))
        qp=Path(td)/"spec.json";qp.write_text(json.dumps(first))
        output=Path(td)/"request.json"
        from unittest.mock import patch
        with patch.object(sys,"argv",["build_request.py","--snapshot",str(sp),"--spec-file",str(qp),"--date","2025-12-28","--output",str(output)]):
            build_request_main()
        req=json.loads(output.read_text())
        assert req["dynamic_public_drive_inputs"][0]["label"]=="analysis",req
        assert len(req["dynamic_public_drive_inputs"])==1,req
        assert req["dynamic_public_drive_inputs"][0]["artifacts"][0]["sha256"]==hashlib.sha256(dummy.read_bytes()).hexdigest(),req
        assert len(req["steps"])==2 and "--spec-json" in req["steps"][1]["args"],req



if __name__=="__main__":main()