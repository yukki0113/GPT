#!/usr/bin/env python3
"""Build compact JRDB Analysis Lite v1.2 from Core v1.2.1 (reference/regression path)."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, sqlite3
from pathlib import Path
VERSION='1.2'; SCHEMA_VERSION='v1.2'
def now(): return dt.datetime.now().isoformat(timespec='seconds')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def build(core,out,schema):
 if out.exists():raise SystemExit(f'Refusing to overwrite existing DB: {out}')
 c=sqlite3.connect(out); c.execute('pragma journal_mode=MEMORY'); c.execute('pragma synchronous=OFF'); c.executescript(schema.read_text(encoding='utf-8'))
 bid=c.execute("insert into meta_analysis_build(builder_version,schema_version,source_core_sha256,started_at,status) values(?,?,?,?,?)",(VERSION,SCHEMA_VERSION,sha(core),now(),'RUNNING')).lastrowid
 c.execute('attach database ? as core',(str(core),))
 c.execute('''INSERT INTO fact_entry_result_lite(
 race_date,year,venue_code,race_no,track_type,distance,race_condition_code,track_condition_code,grade_code,race_key,horse_no,frame_no,horse_id,horse_name,sex_code,age,sire_name,broodmare_sire_name,sire_line_code,broodmare_sire_line_code,jockey_name,running_style,distance_aptitude,uptrend,training_index,finish,abnormal_code,final_win_odds,final_win_popularity,win_payout,place_payout,prev_result_key_1,prev_race_key_1)
 SELECT r.race_date,r.year,r.venue_code,r.race_no,r.track_type,r.distance,r.condition_code,rs.track_condition_code,r.grade_code,e.race_key,e.horse_no,e.frame_no,e.horse_id,e.horse_name,hp.sex_code,
 CASE WHEN hp.birth_date GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN r.year-CAST(substr(hp.birth_date,1,4) AS INTEGER) ELSE NULL END,
 hp.sire_name,hp.broodmare_sire_name,hp.sire_line_code,hp.broodmare_sire_line_code,e.jockey_name,e.running_style,e.distance_aptitude,e.uptrend,ta.training_index,rs.finish,rs.abnormal_code,rs.final_win_odds,rs.final_win_popularity,rs.win_payout,rs.place_payout,NULLIF(trim(pr.prev_result_key),''),NULLIF(trim(pr.prev_race_key),'')
 FROM core.entry e JOIN core.race r ON r.race_key=e.race_key
 LEFT JOIN core.result rs ON rs.race_key=e.race_key AND rs.horse_no=e.horse_no
 LEFT JOIN core.training_analysis ta ON ta.race_key=e.race_key AND ta.horse_no=e.horse_no
 LEFT JOIN core.horse_profile_current hp ON hp.horse_id=e.horse_id
 LEFT JOIN core.entry_previous_result pr ON pr.race_key=e.race_key AND pr.horse_no=e.horse_no AND pr.sequence=1''')
 n=c.execute('select count(*) from fact_entry_result_lite').fetchone()[0]; c.execute("update meta_analysis_build set finished_at=?,status='SUCCESS',row_count=? where build_id=?",(now(),n,bid));c.commit();c.execute('vacuum')
 res=dict(rows=n,prev1_nonblank=c.execute("select count(*) from fact_entry_result_lite where prev_result_key_1 is not null or prev_race_key_1 is not null").fetchone()[0],integrity_check=c.execute('pragma integrity_check').fetchone()[0],size_bytes=out.stat().st_size);c.close();return res
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--core',type=Path,required=True);ap.add_argument('--db',type=Path,required=True);ap.add_argument('--schema',type=Path,default=Path(__file__).resolve().parents[1]/'schema'/'jrdb_analysis_schema_v1_2.sql');a=ap.parse_args()
 for k,v in build(a.core,a.db,a.schema).items():print(f'{k}: {v}')
if __name__=='__main__':main()
