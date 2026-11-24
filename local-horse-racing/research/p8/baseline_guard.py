"""P8.0 baseline input/lineage regression; no outcome evaluation or model selection."""
import duckdb, json, sys
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2]); c=duckdb.connect();c.execute('set threads=4')
def run(s):return c.execute(s)
def one(s):return run(s).fetchone()[0]
# Explicit input projection: no target labels/control; history input projected to P0.1 allowlisted fields.
for name,path,cols in [('r','pre/runner','runner_id,race_id,race_date,venue,horse_key,horse_no,horse_name,birth_date,sire_name,dam_name,damsire_name,sex,jockey_name,jockey_affiliation,trainer_name,trainer_affiliation'),('a','pre/race','race_id,surface,distance_m,field_size'),('o','post/runner_result','runner_id,finish_position,finish_time_seconds'),('s','control/race_status','race_id,status,is_model_target,finish_count')]:
 run(f"create view {name} as select {cols} from read_parquet('{root}/{path}/race_year=*/data.parquet')")
run("create table pre as select r.*,a.surface,a.distance_m,a.field_size from r join a using(race_id) where a.surface='ダート' and a.distance_m>0 and a.field_size>1")
run("""create table hist as select p.runner_id,p.race_id,p.race_date,p.venue,p.horse_key,p.surface,p.distance_m,p.jockey_name,p.jockey_affiliation,p.trainer_name,p.trainer_affiliation,1.0-(o.finish_position-1.0)/(s.finish_count-1.0) as perf from pre p join o using(runner_id) join s using(race_id) where s.status='NORMAL' and s.is_model_target and s.finish_count>1 and o.finish_position between 1 and s.finish_count and o.finish_time_seconds>0""")
# Reuse exact archived feature-query function, without executing the rest of the pilot.
import ast
source=(out/'reproduction/recovery_pilot.py').read_text(); tree=ast.parse(source); fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='features'); ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'archived_features','exec'),ns); features=ns['features']
# Fail closed on forbidden/extra columns at stage boundary; only exact allowlisted target/historical schema.
T=set('runner_id race_id race_date venue horse_key horse_no horse_name birth_date sire_name dam_name damsire_name sex jockey_name jockey_affiliation trainer_name trainer_affiliation surface distance_m field_size'.split());H=set('runner_id race_id race_date venue horse_key surface distance_m jockey_name jockey_affiliation trainer_name trainer_affiliation perf'.split())
def columns(table):return {r[0] for r in run('describe '+table).fetchall()}
def gate(t,h):
 if columns(t)!=T or columns(h)!=H:raise ValueError('forbidden/unexpected feature-stage column')
gate('pre','hist');negative=[]
for col in ['popularity','payout_yen','overall_record_raw','status','track_condition','body_weight_kg','finish_position']:
 run(f'create or replace temp view bad as select *,1 as {col} from pre')
 try:gate('bad','hist'); raise AssertionError(col)
 except ValueError:negative.append(col)
# Select a whole first racing day each year 2017-25, across venues; future rows added with extreme perf.
checks=[]
for year in range(2017,2026):
 d=run(f'select min(race_date) from pre where year(race_date)={year}').fetchone()[0]
 run(f"create or replace temp table t as select * from pre where race_date=date '{d}'")
 run(f"create or replace temp table hp as select * from hist where race_date<date '{d}'")
 run(f"create or replace temp view hi as select * from hist union all select * replace (date '{d}' as race_date,99999.0 as perf) from hist where race_date between date '{d}'-interval '180 days' and date '{d}'-interval '1 days' limit 2000000")
 # Injection restricted to keys represented in t; explicit same-day/target and future rows appended to full history.
 run(f"create or replace temp view hx as select * from hist union all select runner_id,race_id,race_date,venue,horse_key,surface,distance_m,jockey_name,jockey_affiliation,trainer_name,trainer_affiliation,99999.0 as perf from t union all select runner_id,race_id,race_date+1,venue,horse_key,surface,distance_m,jockey_name,jockey_affiliation,trainer_name,trainer_affiliation,-99999.0 as perf from t")
 for tab,h in [('fp','hp'),('ff','hist'),('fx','hx')]:
  gate('t',h);run(f'create or replace temp table {tab} as '+features('t',h))
  assert one(f'select count(*) from {tab} where max_hist_date>=race_date or max_pair_date>=race_date')==0
 def diff(a,b):
  checks_sql=['a.runner_id is null','b.runner_id is null']+[f'a.{k} is distinct from b.{k}' for k in ['n','cn','jn','max_hist_date','max_pair_date']]+[f'((a.{k} is null)<>(b.{k} is null) or abs(a.{k}-b.{k})>1e-12)' for k in ['ability','course','jp']]
  return one(f"select count(*) from {a} a full join {b} b using(runner_id) where "+' or '.join(checks_sql))
 row={'year':year,'date':str(d),'targets':one('select count(*) from t'),'venues':one('select count(distinct venue) from t'),'unknown_history':one('select count(*) from fp where n<2'),'cross_year_horse_history':one('select count(*) from fp where year(max_hist_date)<year(race_date)'),'prefix_full_mismatch':diff('fp','ff'),'injected_target_same_day_future_mismatch':diff('fp','fx')}
 assert row['prefix_full_mismatch']==row['injected_target_same_day_future_mismatch']==0,row
 checks.append(row);print(row,flush=True)
result={'status':'PASS_SCOPED_BASELINE_FEATURE_GUARDS','history_rows':one('select count(*) from hist'),'year_boundary_checks':checks,'forbidden_columns_rejected':negative,'note':'Audit-only test of archived feature builder. Full scoring/evaluator isolation and per-family guards still required before any P8A scoring. 2024/25 outcome metrics not evaluated. No production promotion.'};(out/'baseline_guard_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
