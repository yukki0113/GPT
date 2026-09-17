#!/usr/bin/env python3
"""Build Fact Lite v0.3 SQLite and Parquet from one DuckDB logical dataset.

PWA continues to consume the SQLite output.  The Parquet output is a shadow
analytical twin and never enters the browser manifest in this phase.
"""
from __future__ import annotations
import argparse, datetime as dt, json, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/"tools"/"data-storage"))
from data_storage.query import connect_parquet

VERSION="0.3.0"; TABLES=("dim_sire","dim_bms","dim_jockey","dim_race","fact_stats_entry")

def q(s:str)->str:return "'"+s.replace("'","''")+"'"
def write_sqlite(conn, out:Path, schema:Path, source:str)->dict:
 db=sqlite3.connect(out);db.executescript(schema.read_text(encoding="utf-8"))
 try:
  started=dt.datetime.now().isoformat(timespec="seconds")
  row_count=conn.execute("SELECT count(*) FROM fact_stats_entry").fetchone()[0]; period=conn.execute("SELECT min(race_date_int),max(race_date_int) FROM fact_stats_entry").fetchone()
  db.execute("INSERT INTO meta_pwa_fact_build(builder_version,schema_version,source_analysis,started_at,status,row_count,period_from,period_to) VALUES(?,?,?,?,?,?,?,?)",(VERSION,"0.3",source,started,"RUNNING",row_count,str(period[0]),str(period[1])))
  for table in TABLES:
   cols=[x[0] for x in conn.execute(f"DESCRIBE {table}").fetchall()]; rows=conn.execute(f"SELECT * FROM {table}").fetchall(); db.executemany(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',rows)
  db.execute("UPDATE meta_pwa_fact_build SET finished_at=?,status='SUCCESS'",(dt.datetime.now().isoformat(timespec="seconds"),));db.commit()
  if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise RuntimeError("SQLite integrity")
 finally:db.close()
 return {t:conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}

def load_race_names(path: Path | None) -> list[tuple[str, str]]:
 if path is None:return []
 with sqlite3.connect(f"file:{path}?mode=ro",uri=True) as db:
  table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='race_name_lookup'").fetchone()
  if table is None:raise RuntimeError("race_name_lookup was not found")
  columns={row[1] for row in db.execute("PRAGMA table_info(race_name_lookup)")}
  if {"race_key","race_name"}-columns:raise RuntimeError("invalid race_name_lookup schema")
  return [(str(row[0]),str(row[1])) for row in db.execute("SELECT race_key,race_name FROM race_name_lookup WHERE trim(coalesce(race_name,''))<>'' ORDER BY race_key")]

def build(analysis_glob:Path,sqlite_out:Path,parquet_dir:Path,schema:Path,race_names:Path|None=None)->dict:
 if sqlite_out.exists() or parquet_dir.exists():raise FileExistsError("refusing overwrite")
 c=connect_parquet(analysis_glob,"source")
 if c.execute("SELECT count(*) FROM source").fetchone()[0]==0:raise RuntimeError("empty Analysis")
 if c.execute("SELECT count(*) FROM source WHERE win5_leg_no IS NOT NULL AND win5_leg_no NOT BETWEEN 1 AND 5").fetchone()[0]:raise RuntimeError("invalid WIN5")
 c.execute("CREATE TABLE dim_sire AS SELECT row_number() over(order by sire_name)::INTEGER AS id,sire_name AS name FROM (SELECT DISTINCT sire_name FROM source WHERE trim(coalesce(sire_name,''))<>'')")
 c.execute("CREATE TABLE dim_bms AS SELECT row_number() over(order by broodmare_sire_name)::INTEGER AS id,broodmare_sire_name AS name FROM (SELECT DISTINCT broodmare_sire_name FROM source WHERE trim(coalesce(broodmare_sire_name,''))<>'')")
 c.execute("CREATE TABLE dim_jockey AS SELECT row_number() over(order by jockey_name)::INTEGER AS id,jockey_name AS name FROM (SELECT DISTINCT jockey_name FROM source WHERE trim(coalesce(jockey_name,''))<>'')")
 columns=[x[0] for x in c.execute("DESCRIBE source").fetchall()]
 lookup=load_race_names(race_names)
 c.execute("CREATE TABLE race_lookup(race_key VARCHAR, race_name VARCHAR)")
 if lookup:c.executemany("INSERT INTO race_lookup VALUES (?,?)",lookup)
 if "race_name" in columns:
  c.execute("CREATE TABLE dim_race AS SELECT row_number() over(order by s.race_key)::INTEGER id,s.race_key,coalesce(max(nullif(trim(s.race_name),'')),max(l.race_name)) race_name FROM source s LEFT JOIN race_lookup l USING(race_key) GROUP BY s.race_key")
 else:
  c.execute("CREATE TABLE dim_race AS SELECT row_number() over(order by s.race_key)::INTEGER id,s.race_key,max(l.race_name) race_name FROM (SELECT DISTINCT race_key FROM source) s LEFT JOIN race_lookup l USING(race_key) GROUP BY s.race_key")
 c.execute("""CREATE TABLE fact_stats_entry AS
 SELECT cast(replace(s.race_date,'-','') as INTEGER) AS race_date_int,s.year,cast(substr(s.race_date,6,2) as INTEGER) AS month,cast(s.venue_code as INTEGER) AS venue_code,s.race_no,r.id AS race_id,cast(s.track_type as INTEGER) AS track_type,s.distance,s.race_condition_code,nullif(s.track_condition_code,'')::INTEGER AS track_condition_code,coalesce(nullif(s.grade_code,''),'0')::INTEGER AS grade_code,s.frame_no,nullif(s.sex_code,'')::INTEGER AS sex_code,s.age,si.id AS sire_id,b.id AS bms_id,nullif(s.sire_line_code,'')::INTEGER AS sire_line_code,nullif(s.broodmare_sire_line_code,'')::INTEGER AS bms_line_code,j.id AS jockey_id,nullif(s.running_style,'')::INTEGER AS running_style,nullif(s.distance_aptitude,'')::INTEGER AS distance_aptitude,nullif(s.uptrend,'')::INTEGER AS uptrend,cast(s.training_index as INTEGER) AS training_index,s.final_win_popularity,s.finish,s.win_payout,s.place_payout,case when p.distance is null or s.distance is null then null else s.distance-p.distance end AS prev_distance_delta,
 case when p.race_key is null then null when trim(coalesce(p.grade_code,''))='1' then 11 when trim(coalesce(p.grade_code,''))='2' then 10 when trim(coalesce(p.grade_code,''))='3' then 9 when trim(coalesce(p.grade_code,''))='4' then 12 when trim(coalesce(p.grade_code,''))='6' then 8 when trim(coalesce(p.race_condition_code,''))='A1' then 1 when trim(coalesce(p.race_condition_code,''))='A2' then 2 when trim(coalesce(p.race_condition_code,''))='A3' then 3 when trim(coalesce(p.race_condition_code,'')) in ('04','05') then 4 when trim(coalesce(p.race_condition_code,'')) in ('08','09','10') then 5 when trim(coalesce(p.race_condition_code,'')) in ('15','16') then 6 when trim(coalesce(p.race_condition_code,''))='OP' then 7 else 13 end AS prev_class_code,s.win5_leg_no
 FROM source s join dim_race r using(race_key) left join dim_sire si on si.name=s.sire_name left join dim_bms b on b.name=s.broodmare_sire_name left join dim_jockey j on j.name=s.jockey_name left join (select race_key,max(distance) distance,max(race_condition_code) race_condition_code,max(grade_code) grade_code from source group by race_key) p on p.race_key=s.prev_race_key_1""")
 counts=write_sqlite(c,sqlite_out,schema,str(analysis_glob));parquet_dir.mkdir(parents=True)
 for table in (*TABLES,"meta_pwa_fact_build"):
  if table=="meta_pwa_fact_build": c.execute("CREATE OR REPLACE TABLE meta_pwa_fact_build AS SELECT 1 build_id,? builder_version,'0.3' schema_version,? source_analysis, now() started_at, now() finished_at,'SUCCESS' status, count(*)::BIGINT row_count,min(race_date_int)::VARCHAR period_from,max(race_date_int)::VARCHAR period_to FROM fact_stats_entry",[VERSION,str(analysis_glob)])
  c.execute(f"COPY {table} TO {q(str(parquet_dir/(table+'.parquet')))} (FORMAT PARQUET, COMPRESSION ZSTD)")
 audit={"status":"PASS","logical_relation":"DuckDB","table_rows":counts,"sqlite":str(sqlite_out),"parquet":str(parquet_dir)};(parquet_dir/"equivalence_audit.json").write_text(json.dumps(audit,indent=2)+"\n")
 return audit
def main():
 p=argparse.ArgumentParser();p.add_argument("--analysis-parquet",type=Path,required=True);p.add_argument("--sqlite-out",type=Path,required=True);p.add_argument("--parquet-dir",type=Path,required=True);p.add_argument("--race-names",type=Path);p.add_argument("--schema",type=Path,default=Path(__file__).resolve().parents[1]/"schema"/"jrdb_pwa_fact_lite_schema_v0_3.sql");a=p.parse_args();print(build(a.analysis_parquet,a.sqlite_out,a.parquet_dir,a.schema,a.race_names))
if __name__=="__main__":main()

