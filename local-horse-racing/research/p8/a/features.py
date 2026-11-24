"""P8A.1 feature-only stage, no labels or canonical post access."""
import json,hashlib,sys
from pathlib import Path
import duckdb
O=Path(__file__).parent; mode=sys.argv[1]; threads=int(sys.argv[2]); c=duckdb.connect(); c.execute(f'set threads={threads}');c.execute("set memory_limit='3000MB'");c.execute('set preserve_insertion_order=false')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((O/'input_manifest.json').read_text()); assert sha(O/'entry.parquet')==m['entry_sha256'] and sha(O/'history.parquet')==m['history_sha256']; assert sha(O/'run_config.json')==m['config_sha256']
T='runner_id,race_id,race_date,venue,horse_key,horse_no,surface,distance_m,field_size,jockey_name,jockey_affiliation,trainer_name,trainer_affiliation,race_type_name,conditions,race_name,prize_yen_1,ambiguous'.split(',')
H=T+'perf,finish_time_seconds,final_3f_seconds,finish_position'.split(',')
def check(table,cols):
 if [x[0] for x in c.execute('describe '+table).fetchall()]!=cols:raise ValueError('schema rejected '+table)
for name,file,cols in [('entry','entry.parquet',T),('hist','history.parquet',H)]:
 c.execute(f"create view {name} as select * from read_parquet('{O/file}')");check(name,cols)
assert c.execute('select count(*) from hist where year(race_date) not between 2016 and 2023 or perf not between 0 and 1 or not isfinite(perf)').fetchone()[0]==0
keys='jockey_name,jockey_affiliation,trainer_name,trainer_affiliation'.split(','); key=','.join(keys)
def pair_sql(t,h):
 return f'''with days as (select {key},race_date,sum(cast(perf as decimal(28,16))) ss,count(*) nn from {h} where nullif(trim(jockey_name),'') is not null and nullif(trim(trainer_name),'') is not null group by all), td as (select distinct {key},race_date from {t}), d as (select {key},race_date,sum(ss) ss,sum(nn) nn from (select * from days union all select *,0::decimal(28,16),0::bigint from td) group by all), w as (select *,sum(ss) over win ss180,sum(nn) over win nn180,max(race_date) filter(where nn>0) over win pair_max from d window win as (partition by {key} order by race_date range between interval '180 days' preceding and interval '1 day' preceding)) select t.runner_id,coalesce(w.nn180,0)::bigint jn,w.ss180::double/nullif(w.nn180,0)::double jp,w.pair_max from {t} t left join w on t.race_date=w.race_date and '''+' and '.join(f't.{k}=w.{k}' for k in keys)+" and nullif(trim(t.jockey_name),'') is not null and nullif(trim(t.trainer_name),'') is not null"
windows={'a0':'dd<=180','mean90':'dd<=90','mean365':'true','last3':'rn<=3','last5':'rn<=5','last8':'rn<=8','hl30':'true','hl60':'true','hl90':'true'}
def feature_sql(t,h):
 # One deterministic ordered history list per target; compute windows without dozens of ordered aggregate states.
 windows2={'a0':'list_filter(l,lambda x: x.dd<=180)','mean90':'list_filter(l,lambda x: x.dd<=90)','mean365':'l','last3':'list_slice(l,1,3)','last5':'list_slice(l,1,5)','last8':'list_slice(l,1,8)'}
 lists=','.join(f'{expr} as l_{name}' for name,expr in windows2.items())
 ag=[]
 for name in windows:
  w='l_mean365' if name.startswith('hl') else 'l_'+name
  vals=f'list_transform({w},lambda x: x.p)'; dates=f'list_transform({w},lambda x: x.d)'
  ag += [f'length({w})::bigint n_{name}',f'list_max({dates}) max_{name}',f'list_min({dates}) min_{name}']
  if name.startswith('hl'):
   wgt=f'exp(-ln(2.0)*x.dd/{name[2:]}.0)';ag += [f'list_sum(list_transform({w},lambda x: x.p*{wgt}))/nullif(list_sum(list_transform({w},lambda x: {wgt})),0) {name}']
  else:
   ag += [f'list_avg({vals}) {name}',f'list_median({vals}) med_{name}',f'list_avg(list_slice(list_reverse_sort({vals}),1,2)) top_{name}',f'list_var_pop({vals}) var_{name}',f'list_avg(list_transform(list_slice({w},1,3),lambda x: x.p)) recent_{name}',f'list_avg(list_transform(list_slice({w},4,999),lambda x: x.p)) prior_{name}',f'least(length({w}),3) recentn_{name}',f'greatest(length({w})-3,0) priorn_{name}']
 cl='list_filter(l_a0,lambda x: x.sc)'; ag += [f'length({cl})::bigint cn',f'list_avg(list_transform({cl},lambda x: x.p)) course',f'list_max(list_transform({cl},lambda x: x.d)) course_max','list_max(list_transform(l,lambda x: x.d)) max_hist_date','length(l)::bigint total_hist','list_min(list_transform(l,lambda x: x.dd)) days_since_last']
 return f"""with j as (select t.runner_id,coalesce(list(struct_pack(p:=h.perf,d:=h.race_date,dd:=date_diff('day',h.race_date,t.race_date),sc:=h.venue=t.venue and h.distance_m=t.distance_m and h.surface=t.surface) order by h.race_date desc,h.runner_id) filter(where h.runner_id is not null),[]) l from {t} t left join {h} h on t.horse_key=h.horse_key and not t.ambiguous and h.race_date<t.race_date and h.race_date>=t.race_date-interval '365 days' group by t.runner_id), a as (select runner_id,l,{lists} from j), b as (select runner_id,{','.join(ag)} from a), p as ({pair_sql(t,h)}) select t.runner_id,t.race_id,t.race_date,t.venue,t.horse_no,t.horse_key,t.distance_m,t.field_size,t.ambiguous,b.* exclude(runner_id),p.* exclude(runner_id) from {t} t join b using(runner_id) join p using(runner_id)"""
def difference(a,b):
 schema=c.execute('describe '+a).fetchall();comp=[]
 for name,typ,*_ in schema:
  if typ in ('DOUBLE','FLOAT'):comp.append(f'((p.{name} is null)<>(q.{name} is null) or abs(p.{name}-q.{name})>1e-12)')
  else:comp.append(f'p.{name} is distinct from q.{name}')
 return c.execute(f'select count(*) from {a} p full join {b} q using(runner_id) where '+' or '.join(comp)).fetchone()[0]
if mode=='full':
 for year in range(2017,2024):
  c.execute(f'create or replace table target as select * from entry where year(race_date)={year}')
  c.execute(f"create or replace view hyear as select * from hist where year(race_date) between {year-1} and {year}")
  c.execute('create or replace table f as '+feature_sql('target','hyear'))
  assert c.execute('select count(*)=count(distinct runner_id) from f').fetchone()[0]
  assert c.execute('select count(*) from f where max_hist_date>=race_date or pair_max>=race_date or course_max>=race_date').fetchone()[0]==0
  p=O/f'features_{year}_t{threads}.parquet';c.execute(f"copy (select * from f order by runner_id) to '{p}' (format parquet,compression zstd)");print('feature',year,threads,c.execute('select count(*) from f').fetchone(),sha(p),flush=True)
elif mode=='guard':
 rejects=[]
 for col in ['popularity','payout_yen','overall_record_raw','status','track_condition','body_weight_kg','finish_position']:
  c.execute(f'create or replace view bad as select *,1 as {col} from entry')
  try: check('bad',T);raise RuntimeError('accepted forbidden column')
  except ValueError: rejects.append(col)
 checks=[]
 for year in range(2017,2024):
  d=c.execute(f'select min(race_date) from entry where year(race_date)={year}').fetchone()[0]
  c.execute(f"create or replace table target as select * from entry where race_date=date '{d}'")
  c.execute(f"create or replace view hyear as select * from hist where year(race_date) between {year-1} and {year}")
  c.execute(f"create or replace view prefix as select * from hyear where race_date<date '{d}'")
  c.execute(f"create or replace view injected as select * from hyear union all select *,99999.0,99999.0,99999.0,1::smallint from target union all select * replace (race_date+1 as race_date),-99999.0,99999.0,99999.0,1::smallint from target")
  for f,h in [('p','prefix'),('q','hyear'),('z','injected')]:c.execute(f'create or replace table {f} as '+feature_sql('target',h))
  n1,n2=difference('p','q'),difference('p','z'); checks.append({'year':year,'date':str(d),'rows':c.execute('select count(*) from target').fetchone()[0],'prefix_full_diff':n1,'injected_diff':n2});assert n1==n2==0,checks[-1];print(checks[-1],flush=True)
 (O/'feature_guard.json').write_text(json.dumps({'status':'PASS','checks':checks,'rejected':rejects},indent=2)+'\n')
