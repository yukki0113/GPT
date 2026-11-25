"""P9 immutable input and historical residual staging. No candidate scores or evaluation."""
import hashlib,json,zipfile,sys,os
from pathlib import Path
import duckdb
P=Path('/mnt/data'); O=Path(__file__).parent; end=int(sys.argv[1]); tag='devval' if end==2023 else 'confirm'; D=O/tag; D.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert sha(P/'manifest.json')=='bdc6cc603f5a199fa513bffea3b0450588df828c0bdbac5c52e980f4ab6f926a'
assert sha(P/'CHECKSUMS.sha256.txt')=='40bc2c2c6e8b8a6a396411e7cb408ba997e28ed7f4d462ddbd4ca9f2f5ba8de1'
assert sha(P/'field_catalog.json')=='c08b00b2850b9b097a8f5646d4606908dbef305b1e88db6d17b802d1423ead82'
assert sha(P/'NAR_P8B_EVIDENCE_20261124.zip')=='c6a578868978c658ab0d7013fea17fdd67c42735c3bfc8dc82f07486ced22a41'
m=json.loads((P/'manifest.json').read_text()); ledger=dict((b,a) for a,b in (l.split('  ',1) for l in (P/'CHECKSUMS.sha256.txt').read_text().splitlines())); catalog=json.loads((P/'field_catalog.json').read_text()); allow={(x['canonical_table'],x['canonical_field']) for x in catalog if x['feature_policy']=='ALLOW' and x['available_stage']=='ENTRY'}
c=duckdb.connect();c.execute("set memory_limit='1800MB'; set threads=4; set temp_directory='/tmp/p9spill'")
def sql(q):return c.execute(q)
def one(q):return sql(q).fetchone()[0]
def copy(q,p):sql(f"copy ({q}) to '{p}' (format parquet,compression zstd)")
assets=[]; folders={'runner':'pre/runner','race':'pre/race','result':'post/runner_result','status':'control/race_status'}
cols={'runner':'runner_id,race_id,race_date,venue,horse_key,horse_no,jockey_name,jockey_affiliation,trainer_name,trainer_affiliation,sire_name,damsire_name','race':'race_id,surface,distance_m,field_size','result':'runner_id,finish_position,finish_time_seconds','status':'race_id,status,is_model_target,finish_count'}
for tbl,folder in folders.items():
 paths=[]
 for y in range(2016,end+1):
  rel=f'{folder}/race_year={y}/data.parquet'; a=next(x for x in m['parquet_files'] if x['relative_path']==rel)
  p=P/'p8_fetch'/f'{tbl}_{y}.bin' if y<2024 else P/'p8_fetch'/f'2024_{list(folders).index(tbl)}.bin' if y==2024 else O/'input2025'/f'{tbl}_2025.bin'
  assert p.stat().st_size==a['size_bytes'] and sha(p)==a['sha256']==ledger[rel],str(p)
  assert one(f"select count(*) from read_parquet('{p}')")==a['row_count']; assets.append(a);paths.append(str(p))
 sql(f"create view {tbl} as select {cols[tbl]} from read_parquet({paths!r})")
# source fields are allowed ENTRY; keys are canonical derived linkage.
for tbl,fields in [('pre_runner',['jockey_name','jockey_affiliation','trainer_name','trainer_affiliation','sire_name','damsire_name']),('pre_race',['surface','distance_m','field_size'])]:
 assert all((tbl,f) in allow for f in fields),[(tbl,f) for f in fields if (tbl,f) not in allow]
# Freeze archive verification against recorded P8B delivery manifest, plus internal checksum.
audit=json.loads((P/'delivery_manifest.json').read_text()); assert sha(P/'delivery_manifest.json')=='1532ffa53bae883d7970ce64ec1b0389e4fdceb344ab50185b6355f21d5a3390'
archives=[]; ps=[]
for y in range(2017,end+1):
 name=f'NAR_P8B_FREEZE_{y}.zip' if y<=2023 else f'NAR_P8B_CONFIRM_{y}.zip'; z=P/name; a=next(x for x in audit['details'] if x['name']==name); assert sha(z)==a['sha256'] and z.stat().st_size==a['bytes'];
 with zipfile.ZipFile(z) as f:
  sums=dict((b,a) for a,b in (l.split('  ',1) for l in f.read('SHA256SUMS').decode().splitlines()))
  n=f'pred_combine_dev_{y}_t4.parquet' if y<=2021 else f'pred_val_{y}_t4.parquet' if y<=2023 else f'confirm_b/pred_confirm_{y}_t4.parquet'; data=f.read(n);assert hashlib.sha256(data).hexdigest()==sums[n]; p=D/f'base_{y}.parquet';p.write_bytes(data);ps.append(str(p));archives.append(dict(year=y,archive=name,sha256=a['sha256'],member=n,member_sha256=sums[n]))
sql(f"create table base as select runner_id,race_id,race_date,venue,horse_no,field_size,ambiguous,n_hl60,s_astar,r_astar,reason_astar from read_parquet({ps!r})")
assert one('select count(*)=count(distinct runner_id) from base');assert one('select count(*) from base where s_astar is not null and not isfinite(s_astar)')==0
assert one('''select count(*) from (select r_astar,row_number() over(partition by race_id order by round(s_astar,12) desc,horse_no) rr from base where s_astar is not null) where r_astar is distinct from rr''')==0
sql('''create table pre as select r.*,a.field_size,a.distance_m from runner r join race a using(race_id) where a.surface='ダート' and a.distance_m>0 and a.field_size>1 and year(r.race_date)>=2017''')
assert one('''select count(*) from pre p full join base b using(runner_id) where p.runner_id is null or b.runner_id is null or p.race_id is distinct from b.race_id or p.race_date is distinct from b.race_date or p.horse_no is distinct from b.horse_no or p.venue is distinct from b.venue or p.field_size is distinct from b.field_size''')==0
# Exact identity, no normalization merging. Reject missing or non-letter-only placeholder. Keep original raw strings as keys.
valid=lambda col:f"{col} is not null and regexp_matches({col}, '[\\p{{L}}\\p{{N}}]') and lower(trim({col})) not in ('unknown','不明','未定','なし','null','0')"
sql(f'''create table keyed as select p.runner_id,p.race_id,p.race_date,p.venue,p.horse_no,p.field_size,p.distance_m,p.horse_key,b.ambiguous,b.n_hl60,b.s_astar,b.r_astar,b.reason_astar,
case when {valid('jockey_name')} and {valid('jockey_affiliation')} then to_json([jockey_name,jockey_affiliation]) end j0,
case when {valid('trainer_name')} and {valid('trainer_affiliation')} then to_json([trainer_name,trainer_affiliation]) end t,
case when {valid('sire_name')} then sire_name end s,case when {valid('damsire_name')} then damsire_name end d from pre p join base b using(runner_id)''')
sql('''create table targets as select * exclude(j0,collision),case when not collision then cast(j0 as varchar) end j,cast(t as varchar) as tk,case when not collision and j0 is not null and t is not null then cast(to_json([cast(j0 as varchar),cast(t as varchar)]) as varchar) end p from (select *,j0 is not null and count(*) over(partition by race_id,j0)>1 collision from keyed)''')
# Stage: target input includes only pre and P8 frozen predictions, no labels.
copy('select runner_id,race_id,race_date,venue,horse_no,field_size,distance_m,horse_key,ambiguous,n_hl60,s_astar,r_astar,reason_astar,j,tk,p,s,d from targets order by runner_id',D/'targets.parquet')
# Historical outcome residuals: rank average by rounded score, use only valid past outcome in later feature query.
sql('''create table q as select runner_id,race_id,race_date,horse_key,j,tk,p,s,d, count(s_astar) over(partition by race_id) n, count(*) over(partition by race_id) roster, rank() over(partition by race_id order by round(s_astar,12) desc nulls last)+(count(*) over(partition by race_id,round(s_astar,12))-1)/2.0 avg_rank,s_astar,ambiguous from targets''')
copy('''select q.runner_id,q.race_date,q.horse_key,q.j,q.tk,q.p,q.s,q.d,cast(round(((1.0-(r.finish_position-1.0)/(st.finish_count-1.0))-(1.0-(q.avg_rank-1.0)/(q.n-1.0)))*1000000000,0) as bigint) e from q join result r using(runner_id) join status st using(race_id) where not q.ambiguous and q.horse_key is not null and q.s_astar is not null and q.n>=4 and q.n>=q.roster*0.5 and st.status='NORMAL' and st.is_model_target and st.finish_count>1 and r.finish_position between 1 and st.finish_count and r.finish_time_seconds>0 order by runner_id''',D/'history.parquet')
# independent evaluator labels, no scoring process reads this file.
copy('''select t.runner_id,t.race_id,t.race_date,st.status,st.is_model_target,r.finish_position from targets t join status st using(race_id) left join result r using(runner_id) order by runner_id''',D/'labels.parquet')
ident={}
for f in ['j','tk','p','s','d']:
 ident[f]=dict(zip(['known_rows','keys','missing_rows'],sql(f'select count({f}),count(distinct {f}),count(*)-count({f}) from targets').fetchone()))
ident['jockey_same_race_collision_rows']=one('select count(*) from keyed where j0 is not null and (race_id,j0) in (select race_id,j0 from keyed where j0 is not null group by all having count(*)>1)')
for n in ['jockey','trainer']:
 ident[n+'_name_multiple_affiliations']=one(f"select count(*) from (select {n}_name from pre where {valid(n+'_name')} group by 1 having count(distinct {n}_affiliation)>1)")
ident['ambiguous_rows']=one('select count(*) from targets where ambiguous');ident['target_rows']=one('select count(*) from targets');ident['residual_rows']=one(f"select count(*) from read_parquet('{D/'history.parquet'}')")
dump(D/'entity_audit.json',ident);dump(D/'input_manifest.json',{'generation':m['generation_id'],'canonical_manifest_sha256':sha(P/'manifest.json'),'canonical_assets':assets,'base_archives':archives,'stage_files':{n:sha(D/n) for n in ['targets.parquet','history.parquet','labels.parquet']},'rank_parity':True,'roster_parity':True,'end_year':end,'identity':ident});print(ident,flush=True)
