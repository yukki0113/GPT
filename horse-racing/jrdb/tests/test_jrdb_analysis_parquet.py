from __future__ import annotations
import sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from migrate_jrdb_analysis_parquet import migrate
from materialize_jrdb_analysis_sqlite import materialize
from rollback_jrdb_analysis_parquet_current import rollback
from build_jrdb_pwa_fact_lite_dual import build as build_dual
from audit_jrdb_pwa_fact_lite_dual import audit as audit_fact_lite

class AnalysisParquetTest(unittest.TestCase):
 def test_year_objects_metadata_and_compatibility_sqlite(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); src=root/"analysis.sqlite"; schema=ROOT/"schema/jrdb_analysis_schema_v1_3.sql"
   c=sqlite3.connect(src);c.executescript(schema.read_text(encoding="utf-8"))
   c.execute("INSERT INTO meta_analysis_build(builder_version,schema_version,status,row_count) VALUES('x','v1.3','SUCCESS',2)")
   c.execute("INSERT INTO meta_analysis_ingest_batch(target_date,builder_version,schema_version,started_at,status,row_count) VALUES('2025-01-01','x','v1.3','now','SUCCESS',2)")
   for year,no in ((2024,1),(2025,2)):
    c.execute("INSERT INTO fact_entry_result_lite(race_date,year,venue_code,race_no,track_type,distance,race_key,horse_no,horse_id,horse_name,win5_leg_no) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(f"{year}-01-01",year,"05",1,"1",1600,f"05{year}0101",no,"H","Horse",None if year==2024 else 1))
   c.commit();c.close()
   result=migrate(src,root/"store","g1")
   self.assertEqual(result["audit"]["status"],"PASS")
   self.assertEqual(len(result["manifest"]["fact_table"]["partitions"]),2)
   out=root/"compat.sqlite"; recovered=materialize(root/"store"/"generations"/"g1"/"manifest.json",out,schema)
   self.assertEqual(recovered["rows"],2)
   with sqlite3.connect(out) as db: self.assertEqual(db.execute("SELECT COUNT(*) FROM meta_analysis_ingest_batch").fetchone()[0],1)

 def test_dual_fact_lite_uses_analysis_parquet(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); src=root/"analysis.sqlite"; schema=ROOT/"schema/jrdb_analysis_schema_v1_3.sql"; c=sqlite3.connect(src);c.executescript(schema.read_text())
   c.execute("INSERT INTO meta_analysis_build(builder_version,schema_version,status,row_count) VALUES('x','v1.3','SUCCESS',1)");c.execute("INSERT INTO meta_analysis_ingest_batch(target_date,builder_version,schema_version,started_at,status,row_count) VALUES('2025-01-01','x','v1.3','now','SUCCESS',1)")
   c.execute("INSERT INTO fact_entry_result_lite(race_date,year,venue_code,race_no,track_type,distance,race_key,horse_no,horse_id,horse_name,sire_name,broodmare_sire_name,jockey_name,win5_leg_no) VALUES('2025-01-01',2025,'05',1,'1',1600,'05250101',1,'H','Horse','Sire','BMS','Jockey',1)");c.commit();c.close()
   migrate(src,root/"store","g1"); glob=root/"store"/"objects"/"fact_entry_result_lite"/"**"/"*.parquet"
   result=build_dual(glob,root/"fact.sqlite",root/"fact-parquet",ROOT/"schema/jrdb_pwa_fact_lite_schema_v0_3.sql")
   self.assertEqual(result["table_rows"]["fact_stats_entry"],1)
   self.assertTrue((root/"fact-parquet"/"fact_stats_entry.parquet").is_file())

 def test_incremental_year_reuse_idempotence_and_rollback(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); src=root/"analysis.sqlite"; schema=ROOT/"schema/jrdb_analysis_schema_v1_3.sql"; c=sqlite3.connect(src);c.executescript(schema.read_text())
   c.execute("INSERT INTO meta_analysis_build(builder_version,schema_version,status,row_count) VALUES('x','v1.3','SUCCESS',2)");c.execute("INSERT INTO meta_analysis_ingest_batch(target_date,builder_version,schema_version,started_at,status,row_count) VALUES('2025-01-01','x','v1.3','now','SUCCESS',2)")
   for year in (2024,2025): c.execute("INSERT INTO fact_entry_result_lite(race_date,year,venue_code,race_no,track_type,distance,race_key,horse_no,horse_id,horse_name) VALUES(?,?,?,?,?,?,?,?,?,?)",(f'{year}-01-01',year,'05',1,'1',1600,f'05{year}0101',1,'H','Horse'))
   c.commit();c.close()
   store=root/"store"; first=migrate(src,store,"g1",promote=True)
   second=migrate(src,store,"g2",affected_years={2025},reuse_manifest=store/"generations"/"g1"/"manifest.json",promote=True)
   first_2024=next(x for x in first["manifest"]["fact_table"]["partitions"] if x["year"]==2024)
   second_2024=next(x for x in second["manifest"]["fact_table"]["partitions"] if x["year"]==2024)
   self.assertEqual(first_2024["relative_path"],second_2024["relative_path"])
   self.assertEqual(first["manifest"]["total_rows"],second["manifest"]["total_rows"])
   restored=rollback(store);self.assertEqual(restored["generation_id"],"g1")

 def test_fact_lite_legacy_new_and_parquet_are_equivalent(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); src=root/"analysis.sqlite"; schema=ROOT/"schema/jrdb_analysis_schema_v1_3.sql"; c=sqlite3.connect(src);c.executescript(schema.read_text())
   c.execute("INSERT INTO meta_analysis_build(builder_version,schema_version,status,row_count) VALUES('x','v1.3','SUCCESS',2)");c.execute("INSERT INTO meta_analysis_ingest_batch(target_date,builder_version,schema_version,started_at,status,row_count) VALUES('2025-01-01','x','v1.3','now','SUCCESS',2)")
   rows=[('2025-01-01',2025,'05',1,'1',1600,'05250101',1,'H1','Horse1','Sire','BMS','Jockey',1),('2025-01-02',2025,'05',2,'2',1800,'05250102',1,'H2','Horse2','Sire','BMS','Jockey',None)]
   c.executemany("INSERT INTO fact_entry_result_lite(race_date,year,venue_code,race_no,track_type,distance,race_key,horse_no,horse_id,horse_name,sire_name,broodmare_sire_name,jockey_name,win5_leg_no) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",rows);c.commit();c.close()
   legacy=root/"legacy.sqlite"; subprocess.run([sys.executable,str(ROOT/"src"/"build_jrdb_pwa_fact_lite.py"),"--analysis",str(src),"--db",str(legacy)],check=True)
   migrate(src,root/"store","g1"); glob=root/"store"/"objects"/"fact_entry_result_lite"/"**"/"*.parquet"
   new=root/"new.sqlite"; pq=root/"fact-parquet"; build_dual(glob,new,pq,ROOT/"schema/jrdb_pwa_fact_lite_schema_v0_3.sql")
   self.assertTrue(audit_fact_lite(legacy,new,pq)["legacy_equals_new_sqlite"])

if __name__=="__main__":unittest.main()
