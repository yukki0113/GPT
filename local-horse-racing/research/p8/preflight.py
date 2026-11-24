"""P8.0 input and identity audit. Run: python preflight.py /mnt/data /mnt/data/P8_0_20261124. No confirmation model evaluation."""
import sys, json, hashlib, shutil, zipfile
from pathlib import Path
import duckdb, pyarrow, numpy
B=Path(sys.argv[1]); O=Path(sys.argv[2]); O.mkdir(exist_ok=True)
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda n: json.loads((B/n).read_text())
def out(n,d): (O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n')
cur=read('CURRENT.json'); m=read('manifest.json'); reg=read('schema_registry.json'); pub=read('drive_publication_audit.json'); acc=read('ACCEPTED.json'); audit=read('final_audit.json'); catalog=read('field_catalog.json')
assert cur['status']==m['status']==acc['status']=='accepted' and cur['drive_publication_status']==m['drive_publication_status']=='published' and audit['status']==pub['status']=='PASS'
assert len({x['generation_id'] for x in (cur,m,reg,pub,acc,audit)})==1
assert sha(B/'manifest.json')==cur['manifest_sha256']==pub['control_files']['manifest_sha256']; assert sha(B/'final_audit.json')==cur['final_audit_sha256']==acc['basis']['final_audit_sha256']
for n,key in [('CURRENT.json','current_sha256'),('field_catalog.json','field_catalog_sha256'),('schema_registry.json','schema_registry_sha256'),('CHECKSUMS.sha256.txt','checksums_sha256'),('ACCEPTED.json','accepted_sha256')]: assert sha(B/n)==pub['control_files'][key]
ledger={p:h for h,p in (s.split('  ',1) for s in (B/'CHECKSUMS.sha256.txt').read_text().splitlines() if s.strip())}
assert cur['generation_id']=='nar_canonical_v1_201601_202512_g20260917'
assert sha(B/'manifest.json')=='bdc6cc603f5a199fa513bffea3b0450588df828c0bdbac5c52e980f4ab6f926a'
assert sha(B/'drive_publication_audit.json')=='59a328c2f68b3cbff6e55616eb55cde4decdc528eb2d2dc430fa58795afe82a9'
assert sha(B/'CHECKSUMS.sha256.txt')=='40bc2c2c6e8b8a6a396411e7cb408ba997e28ed7f4d462ddbd4ca9f2f5ba8de1'
assert ledger['ACCEPTED.json']=='cb499f51cfcfdcd5ee116ef05c656f74f31051b9bfb2b9cce61f524ff45948ec' and sha(B/'ACCEPTED.json')=='f1f946764a73b7a0c056eb4a33b43e763275fe52131e689fb6282075bfa400dd'
assert ledger['control/field_catalog.json']==sha(B/'field_catalog.json') and ledger['control/schema_registry.json']==sha(B/'schema_registry.json')
assert (duckdb.__version__,pyarrow.__version__,numpy.__version__)==('2.0.1','25.0.1','2.2.4')
assert sha(B/'jrdb-phase2-duckdb2.0.1-pyarrow25.0.1-numpy2.2.4-py313-linux-x86_64.zip')=='ceee50c7f3e7b2dc74bc8401320d1b69e96cee8d7809383b876677c74c7caa16'
c=duckdb.connect(); c.execute('set threads=4')
root=B/'nar_p8_inputs'; paths={'runner':'pre/runner','race':'pre/race','result':'post/runner_result','status':'control/race_status'}
entries=[]
for i,(short,folder) in enumerate(paths.items()):
 for y in range(2016,2026):
  rel=f'{folder}/race_year={y}/data.parquet'; a=next(z for z in m['parquet_files'] if z['relative_path']==rel); src=(B/'nar_recovery_inputs'/rel) if y==2025 else B/'p8_fetch'/(f'2024_{i}.bin' if y==2024 else f'{short}_{y}.bin')
  assert src.stat().st_size==a['size_bytes'] and sha(src)==a['sha256']==ledger[rel],rel
  p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
  if not p.exists(): shutil.copyfile(src,p)
  assert sha(p)==a['sha256']
  t=reg['tables'][a['table']]; assert t['schema_hash']==a['schema_hash']; schema=[dict(zip(('name','type','null'),z[:3])) for z in c.execute(f"describe select * from read_parquet('{p}')").fetchall()]; assert schema==t['columns'],(rel,schema[-3:],t['columns'][-3:])
  key=t['canonical_key'][0]; n,unique,null,wrongyear=c.execute(f"select count(*),count(distinct {key}),count(*) filter(where {key} is null),count(*) filter(where year(race_date) is distinct from {y}) from read_parquet('{p}')").fetchone(); assert n==unique==a['row_count'] and null==wrongyear==0,rel
  entries.append({**a,'sha_verified':True,'schema_verified':True,'unique_key':True,'year_verified':True})
 c.execute(f"create view {short} as select * from read_parquet('{root}/{folder}/race_year=*/data.parquet')")
out('input_manifest.json',{'generation':cur['generation_id'],'manifest_sha256':sha(B/'manifest.json'),'runtime':{'duckdb':duckdb.__version__,'pyarrow':pyarrow.__version__,'numpy':numpy.__version__},'correction':'P0-01-20261124','metadata_integrity':'PASS','assets':entries,'excluded':['post/payout','pre/runner_history_snapshot','post/race_result (P8B deferred)'],'full_generation_audit':False})
def q(s): return c.execute(s).fetchall()
def one(s):return c.execute(s).fetchone()[0]
def savecsv(n,s):c.execute(f"copy ({s}) to '{O/n}' (header, delimiter ',')")
joins={}
for a,b,k in [('runner','result','runner_id'),('race','status','race_id')]:
 joins[f'{a}_{b}']=q(f'select count(*) filter(where a.{k} is null), count(*) filter(where b.{k} is null), count(*) filter(where a.race_date is distinct from b.race_date or a.race_id is distinct from b.race_id) from {a} a full join {b} b using({k})')[0];assert joins[f'{a}_{b}']==(0,0,0)
joins['runner_without_race']=one('select count(*) from runner r anti join race a using(race_id)'); assert joins['runner_without_race']==0
joins['runner_result_horse_key_mismatch']=one('select count(*) from runner r join result o using(runner_id) where r.horse_key is distinct from o.horse_key'); assert joins['runner_result_horse_key_mismatch']==0
# Global counts for auditing only, NEVER create a feature quarantine based on future records.
identity={}
identity['rows'],identity['distinct_keys'],identity['missing_keys'],identity['missing_identity_components'],identity['hash_mismatch'],identity['age_mismatch']=q("""select count(*),count(distinct horse_key),count(*) filter(where horse_key is null or trim(horse_key)=''),count(*) filter(where nullif(trim(horse_name),'') is null or birth_date is null or nullif(trim(sire_name),'') is null),count(*) filter(where horse_key is distinct from 'narh:'||sha256(coalesce(horse_name,'')||chr(31)||coalesce(strftime(birth_date,'%Y%m%d'),'')||chr(31)||coalesce(sire_name,''))),count(*) filter(where birth_date is not null and age is not null and year(race_date)-year(birth_date)<>age) from runner""")[0]
identity['conflicting_identity_keys']=one('select count(*) from (select horse_key from runner group by horse_key having count(distinct horse_name)>1 or count(distinct birth_date)>1 or count(distinct sire_name)>1)')
identity['pedigree_conflict_keys']=one("select count(*) from (select horse_key from runner group by horse_key having count(distinct nullif(trim(dam_name),''))>1 or count(distinct nullif(trim(damsire_name),''))>1)")
identity['same_day_multiple_race_key_dates']=one('select count(*) from (select horse_key,race_date from runner group by 1,2 having count(distinct race_id)>1)')
identity['name_birth_split_groups']=one('select count(*) from (select horse_name,birth_date from runner where birth_date is not null group by 1,2 having count(distinct horse_key)>1)')
identity['name_normalized_birth_split_groups']=one("select count(*) from (select nfc_normalize(lower(regexp_replace(trim(horse_name),'[[:space:]　]+','','g'))) as nm,birth_date from runner where birth_date is not null group by 1,2 having count(distinct horse_key)>1)")
identity['affiliation_change_keys']=one("select count(*) from (select horse_key from runner group by 1 having count(distinct nullif(trim(trainer_affiliation),''))>1)")
identity['sex_conflict_female_vs_male_or_gelding']=one("select count(*) from (select horse_key from runner group by 1 having count(*) filter(where sex='牝')>0 and count(*) filter(where sex in ('牡','セン','騸','せん'))>0)")
identity['sex_values']=q('select sex,count(*) from runner group by 1 order by 2 desc')
identity['notes']='Global audit only. No future-derived merge or quarantine. Stable surrogate, no fuzzy merge; missing/conflicting evidence at target date flagged unknown. Same-day multiple entries audited, outcome cannot inform prediction.'
out('entity_audit.json',{'joins':joins,'identity':identity})
savecsv('entry_coverage_by_year_venue.csv',"select year(r.race_date) as yr,r.venue,a.surface,count(distinct r.race_id) races,count(*) runners,count(*) filter(where nullif(trim(r.horse_name),'') is null or r.birth_date is null or nullif(trim(r.sire_name),'') is null) incomplete_identity,count(*) filter(where a.distance_m is null or a.distance_m<=0 or a.field_size is null or a.field_size<=1) invalid_scope from runner r join race a using(race_id) group by all order by 1,2,3")
savecsv('data_coverage_by_year_venue.csv',"select year(r.race_date) as yr,r.venue,a.surface,count(*) runners,count(*) filter(where o.finish_position is not null) valid_finish,count(*) filter(where o.finish_time_seconds>0) valid_time,count(*) filter(where nullif(trim(o.margin),'') is not null) margin_present,count(*) filter(where o.final_3f_seconds>0) valid_final3f,count(*) filter(where nullif(trim(a.conditions),'') is not null) conditions_present,count(*) filter(where a.prize_yen_1>0) prize_present from runner r join race a using(race_id) join result o using(runner_id) group by all order by 1,2,3")
# Compare exact pilot scores/ranks, independent of output-byte differences.
old=B/'NAR_recovery_20261124/pilot_prediction_freeze.parquet'; new=O/'reproduction/pilot_prediction_freeze.parquet'
assert sha(B/'NAR_RECOVERY_PILOT_20261124.zip')=='3737210f679348a54d714a737ec67351540037d140d098cbdc968617685ae2e3'
join=f"from read_parquet('{old}') a full join read_parquet('{new}') b using(runner_id,model)"
missing, rank_diff, score_diff, max_delta=q(f"select count(*) filter(where a.runner_id is null or b.runner_id is null),count(*) filter(where a.pred_rank is distinct from b.pred_rank),count(*) filter(where abs(a.score-b.score)>1e-12),max(abs(a.score-b.score)) {join}")[0]
orig=json.loads((B/'NAR_recovery_20261124/pilot_metrics.json').read_text()); repro=json.loads((O/'reproduction/pilot_metrics.json').read_text()); metric_parity=orig['metrics']==repro['metrics'] and orig['eligible_races']==repro['eligible_races']
assert missing==score_diff==0 and metric_parity
# Diagnostic only. Do not replace the original ranking or change the strict gate.
rounded_rank_diff=one(f"with a as (select runner_id,model,row_number() over(partition by race_id,model order by round(score,12) desc,horse_no asc) as rk from read_parquet('{old}')),b as (select runner_id,model,row_number() over(partition by race_id,model order by round(score,12) desc,horse_no asc) as rk from read_parquet('{new}')) select count(*) from a full join b using(runner_id,model) where a.rk is distinct from b.rk")
savecsv('pilot_rank_mismatches.csv',f"select a.runner_id,a.race_id,a.race_date,a.model,a.score old_score,b.score new_score,a.pred_rank old_rank,b.pred_rank new_rank {join} where a.pred_rank is distinct from b.pred_rank order by a.race_id,a.model,a.pred_rank")
out('pilot_reproduction_audit.json',{'status':'PASS' if rank_diff==0 else 'FAIL_STRICT_RANK_PARITY','old_freeze_sha256':sha(old),'new_freeze_sha256':sha(new),'missing_rows':missing,'rank_mismatch':rank_diff,'score_tolerance_mismatch':score_diff,'max_abs_score_delta':max_delta,'rounded_rank_mismatch_diagnostic':rounded_rank_diff,'metrics_match':metric_parity,'row_count':one(f"select count(*) from read_parquet('{old}')"),'metrics':repro['metrics'],'eligible_races':repro['eligible_races'],'byte_parity':sha(old)==sha(new),'tolerance':1e-12,'note':'Rounded ranking is a diagnostic only; original strict gate remains failed. Preserve both artifacts; no downstream candidate evaluation.'})
print(json.dumps({'assets':len(entries),'joins':joins,'identity':identity,'pilot_rank_diff':rank_diff,'rounded_rank_diff_diagnostic':rounded_rank_diff,'max_delta':max_delta},ensure_ascii=False,indent=2))
