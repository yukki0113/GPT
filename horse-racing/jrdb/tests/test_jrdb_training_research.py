#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from analyze_jrdb_training_stage1b import analyze
from audit_jrdb_training_research import audit
from build_jrdb_training_research import build


class TrainingResearchTest(unittest.TestCase):
    def _sources(self, root: Path) -> tuple[Path,Path]:
        index=root/"index.sqlite"
        official=root/"official.sqlite"
        db=sqlite3.connect(index)
        db.executescript((ROOT/"schema/jrdb_index_base_schema_v0_1.sql").read_text(encoding="utf-8"))
        db.execute("""INSERT INTO meta_index_base_build(
          builder_version,schema_version,started_at,status,years_json)
          VALUES('test','v0.1','now','SUCCESS','[]')""")
        for year in range(2010,2026):
            race_key=f"05{year%100:02d}0101"
            date=f"{year}-01-01"
            db.execute("""INSERT INTO race_context(
              race_key,race_date,year,venue_code,race_no,source_kind,availability_class,record_hash)
              VALUES(?,?,?,?,?,'BAC','PRE_RACE',?)""",(race_key,date,year,"05",1,f"r{year}"))
            db.execute("""INSERT INTO runner_pre(
              race_key,horse_no,horse_id,horse_name,trainer_code,trainer_name,jockey_code,jockey_name,
              rotation_interval,training_score,training_arrow_code,source_member,record_hash)
              VALUES(?,1,'HORSE001','Horse','TR001','Trainer','JK001','Jockey',4,50,'1',?,?)""",
              (race_key,f"KYI{year}.txt",f"k{year}"))
            db.execute("""INSERT INTO runner_result(
              race_key,horse_no,horse_id,horse_name,finish,body_weight_kg,source_member,record_hash)
              VALUES(?,1,'HORSE001','Horse',1,480,?,?)""",(race_key,f"SED{year}.txt",f"s{year}"))
            db.execute("""INSERT INTO workout_main(
              race_key,horse_no,training_date,workout_count,course_code,furlong_count,final_segment_sec,
              source_member,record_hash) VALUES(?,1,?,1,'CW',5,?,?,?)""",
              (race_key,f"{year-1}-12-29",15.0-(year-2010)*0.1,f"CHA{year}.txt",f"w{year}"))
            db.execute("""INSERT INTO training_analysis(
              race_key,horse_no,training_type_code,training_course_type_code,used_wood,
              source_member,record_hash) VALUES(?,1,'01','W',1,?,?)""",
              (race_key,f"CYB{year}.txt",f"y{year}"))
            for kind in ("BAC","KYI","CHA","CYB","SED","UKC"):
                db.execute("""INSERT INTO meta_index_base_source(
                  build_id,source_kind,year,archive_path,archive_sha256,archive_size_bytes,member_count,imported_at)
                  VALUES(1,?,?,?,?,1,1,'now')""",(kind,year,f"/{kind}_{year}.zip","0"*64))
        db.commit(); db.close()

        off=sqlite3.connect(official)
        off.executescript((ROOT/"schema/jrdb_official_runperf_schema_v0_1.sql").read_text(encoding="utf-8"))
        for year in range(2010,2026):
            race_key=f"05{year%100:02d}0101"
            off.execute("""INSERT INTO official_runperf(
              race_key,race_date,year,horse_no,horse_id,source_calculation_status,score_status,
              runperf_raw,score_provenance) VALUES(?,?,?,?,?,'OK','OK',?,'official-test')""",
              (race_key,f"{year}-01-01",year,1,"HORSE001",float(year-2010)))
        off.commit(); off.close()
        return index,official

    def test_build_audit_and_holdout_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            index,official=self._sources(root)
            output=root/"training.sqlite"
            result=build(index,official,output,ROOT/"schema/jrdb_training_research_schema_v0_1.sql","a"*40)
            self.assertEqual(result["runner_count"],16)
            db=sqlite3.connect(output)
            columns={row[1] for row in db.execute("PRAGMA table_info(training_runner)")}
            db.close()
            self.assertFalse(any(token in name.lower() for name in columns for token in ("odds","popularity","payout")))
            report=audit(output)
            self.assertEqual(report["status"],"PASS")
            evidence=analyze(output)
            self.assertEqual(evidence["holdout_guard"]["max_selected_year"],2023)
            self.assertFalse(evidence["holdout_guard"]["opened"])
            self.assertEqual(evidence["population"]["source_rows_2010_2023"],14)
            self.assertGreater(evidence["population"]["primary_min3"],0)


if __name__=="__main__":
    unittest.main()
