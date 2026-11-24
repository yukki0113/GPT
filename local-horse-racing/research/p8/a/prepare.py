import json,hashlib,zipfile,sys
from pathlib import Path
import duckdb,pyarrow,numpy
B=Path('/mnt/data'); O=Path(__file__).parent; root=B/'nar_p8_inputs'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(B/'manifest.json')=='bdc6cc603f5a199fa513bffea3b0450588df828c0bdbac5c52e980f4ab6f926a'
assert sha(B/'experiment_registry.json')=='cc59b7dede36f8fbbaf9d88b084cdd999d8a34b0b31d00ce23cc70a8d8cc2691'
assert sha(B/'NAR_PREDICTION_RESEARCH_CURRENT.md')=='930b70fa90445612c55dd1729be7c34be72d9fcc59692f066f176b1b7a51a0eb'
assert sha(B/'NAR_P8_0_EVIDENCE_20261124.zip')=='6c48f8c33cf6f5aa65703f7a876223404820111971692a08a4c1687eef5eae6b'
assert sha(B/'P8_0_20261124/input_manifest.json')=='5efafa73f8c6d5ac68d2e77df5001650815bc5a56112003d0618f70c1e51013c'
assert (duckdb.__version__,pyarrow.__version__,numpy.__version__)==('2.0.1','25.0.1','2.2.4')
prev=json.loads((B/'P8_0_20261124/input_manifest.json').read_text()); m=json.loads((B/'manifest.json').read_text()); catalog=json.loads((B/'field_catalog.json').read_text()); reg=json.loads((B/'schema_registry.json').read_text())
assert sha(B/'field_catalog.json')==m['field_catalog_sha256']; assert sha(B/'schema_registry.json')=='373b1ac1bc3ada2b375eb0e566825fe308cb618cbe77108548116b3fee56670d'
assert sha(B/'jrdb-phase2-duckdb2.0.1-pyarrow25.0.1-numpy2.2.4-py313-linux-x86_64.zip')=='ceee50c7f3e7b2dc74bc8401320d1b69e96cee8d7809383b876677c74c7caa16'
paths={'r':'pre/runner','a':'pre/race','o':'post/runner_result','s':'control/race_status'}
cols={'r':'runner_id,race_id,race_date,venue,horse_key,horse_no,horse_name,birth_date,sire_name,dam_name,damsire_name,sex,age,jockey_name,jockey_affiliation,trainer_name,trainer_affiliation','a':'race_id,surface,distance_m,field_size,race_type_name,conditions,race_name,prize_yen_1','o':'runner_id,finish_position,finish_time_seconds,final_3f_seconds','s':'race_id,status,is_model_target,finish_count'}
c=duckdb.connect();c.execute('set threads=4'); assets=[]
for k,folder in paths.items():
 files=[]
 for y in range(2016,2024):
  rel=f'{folder}/race_year={y}/data.parquet'; p=root/rel; a=next(x for x in prev['assets'] if x['relative_path']==rel); assert a['sha_verified'] and a['schema_verified'] and a['unique_key']; assert p.stat().st_size==a['size_bytes'] and sha(p)==a['sha256'],rel; files.append(str(p)); assets.append(a)
 c.execute(f'create view {k} as select {cols[k]} from read_parquet({files!r})')
# source field stage enforcement; derived keys are canonical keys, not source fields
for k,table in [('r','pre_runner'),('a','pre_race')]:
 for name in cols[k].split(','):
  entries=[x for x in catalog if x['canonical_table']==table and x['canonical_field']==name]
  if entries: assert all(x['available_stage']=='ENTRY' and x['feature_policy']=='ALLOW' for x in entries),(name,entries)
  else: assert name in ('runner_id','race_id','horse_key','race_date','venue','horse_no'),(name,table)
# target identity checks from currently visible entry only; no future-derived quarantine
c.execute('''create table entry as select r.*,a.surface,a.distance_m,a.field_size,a.race_type_name,a.conditions,a.race_name,a.prize_yen_1 from r join a using(race_id) where a.surface='ダート' and a.distance_m>0 and a.field_size>1''')
# identity at date: previous entries and same-day pre identity facts only (no outcomes)
c.execute('''create table ident as select runner_id, (horse_key is null or nullif(trim(horse_name),'') is null or birth_date is null or nullif(trim(sire_name),'') is null or horse_key is distinct from 'narh:'||sha256(horse_name||chr(31)||strftime(birth_date,'%Y%m%d')||chr(31)||sire_name) or (age is not null and year(race_date)-year(birth_date)<>age) or count(distinct race_id) over(partition by horse_key,race_date)>1 or count(distinct nullif(trim(dam_name),'')) over w>1 or count(distinct nullif(trim(damsire_name),'')) over w>1) as ambiguous from entry window w as (partition by horse_key order by race_date range between unbounded preceding and current row)''')
c.execute('''create table targets as select e.runner_id,e.race_id,e.race_date,e.venue,e.horse_key,e.horse_no,e.surface,e.distance_m,e.field_size,e.jockey_name,e.jockey_affiliation,e.trainer_name,e.trainer_affiliation,e.race_type_name,e.conditions,e.race_name,e.prize_yen_1, i.ambiguous from entry e join ident i using(runner_id)''')
c.execute('''create table hist as select t.*,1.0-(o.finish_position-1.0)/(s.finish_count-1.0) perf,o.finish_time_seconds,o.final_3f_seconds,o.finish_position from targets t join o using(runner_id) join s using(race_id) where not ambiguous and s.status='NORMAL' and s.is_model_target and s.finish_count>1 and o.finish_position between 1 and s.finish_count and o.finish_time_seconds>0''')
# store separate inputs to builder and evaluator; only evaluation years labels, never 2024-25
c.execute(f"copy (select * from targets order by runner_id) to '{O/'entry.parquet'}' (format parquet,compression zstd)")
c.execute(f"copy (select * from hist order by runner_id) to '{O/'history.parquet'}' (format parquet,compression zstd)")
c.execute(f"copy (select t.runner_id,t.race_id,t.race_date,t.venue,o.finish_position,s.status,s.is_model_target from targets t join o using(runner_id) join s using(race_id) where year(t.race_date)>=2017 order by runner_id) to '{O/'labels.parquet'}' (format parquet,compression zstd)")
(O/'input_manifest.json').write_text(json.dumps({'status':'PASS_SAME_BYTES_AS_P8_0','generation':m['generation_id'],'assets':assets,'input_years':list(range(2016,2024)),'runtime':{'duckdb':duckdb.__version__,'pyarrow':pyarrow.__version__,'numpy':numpy.__version__},'config_sha256':sha(O/'run_config.json'),'entry_sha256':sha(O/'entry.parquet'),'history_sha256':sha(O/'history.parquet'),'labels_sha256':sha(O/'labels.parquet'),'notes':'32 previously audited assets byte verified; P8.0 full metadata/row/schema/key evidence reused. Only 2016-23 loaded.'},ensure_ascii=False,indent=2)+'\n')
print(c.execute('select count(*),count(distinct race_id),count(*) filter(where ambiguous) from targets').fetchall(),c.execute('select count(*) from hist').fetchall())
