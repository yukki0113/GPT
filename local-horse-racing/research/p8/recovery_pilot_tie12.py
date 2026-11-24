"""Exploratory replacement baseline; NOT recovered NAR v0.1.0.
Run using verified shared DuckDB runtime, with 2025 four canonical tables.
Target predictions use ENTRY fields only; labels never passed to scoring.
"""
from pathlib import Path
import json, hashlib, sys, duckdb
ROOT=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/mnt/data/nar_recovery_inputs')
OUT=Path(__file__).parent
M=Path('/mnt/data/manifest.json')
m=json.loads(M.read_text())
c=duckdb.connect(); c.execute('SET threads=4')
paths={'runner':'pre/runner','race':'pre/race','result':'post/runner_result','status':'control/race_status'}
inputs=[]
for name,folder in paths.items():
    p=ROOT/folder/'race_year=2025/data.parquet'; a=next(x for x in m['parquet_files'] if x['relative_path']==f'{folder}/race_year=2025/data.parquet'); assert p.stat().st_size==a['size_bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256']; c.execute(f"create view {name} as select * from read_parquet('{p}')"); assert c.execute(f'select count(*) from {name}').fetchone()[0]==a['row_count']; inputs.append(a)
assert c.execute('select count(*)=count(distinct runner_id) from runner').fetchone()[0]
assert c.execute('select count(*)=count(distinct runner_id) from result').fetchone()[0]
assert c.execute('select count(*)=count(distinct race_id) from race').fetchone()[0]
assert c.execute('select count(*)=count(distinct race_id) from status').fetchone()[0]
# ENTRY only. Exclude missing pre race conditions, separate non-dirt events. No target result filter.
c.execute('''create temp table pre as select r.runner_id,r.race_id,r.race_date,r.venue,r.horse_key,r.horse_no,r.horse_name,r.birth_date,r.jockey_name,r.jockey_affiliation,r.trainer_name,r.trainer_affiliation,a.surface,a.distance_m,a.field_size from runner r join race a using(race_id) where a.surface='ダート' and a.distance_m>0 and a.field_size>1''')
# Independent allowlisted history builder. Never select popularity, odds, payout or snapshot.
# Race status is used only for past observations here. Target eligibility is separately applied after freeze.
c.execute('''create temp table history as select p.runner_id,p.race_id,p.race_date,p.venue,p.horse_key,p.surface,p.distance_m,p.jockey_name,p.jockey_affiliation,p.trainer_name,p.trainer_affiliation, 1.0-(o.finish_position-1.0)/(s.finish_count-1.0) as perf from pre p join result o using(runner_id) join status s on s.race_id=p.race_id where s.status='NORMAL' and s.is_model_target and s.finish_count>1 and o.finish_position between 1 and s.finish_count and o.finish_time_seconds>0''')
c.execute("create temp table targets as select * from pre where race_date >= date '2025-07-01'")
# Frozen, non-fitted baseline: mean normalized finish over preceding 180 days (>=2).
# Exact venue/distance/surface residual with k=3 shrinkage, 0.25 incremental weight.
# Jockey/trainer name+affiliation pair, k=20 shrinkage towards 0.5, 0.15 weight.
# Unknown is NULL; absent sidecars imply no adjustment, not bad performance.
def features(target, hist):
 return f'''with h as (select t.runner_id,count(p.runner_id) n,avg(p.perf) ability,max(p.race_date) max_hist_date, count(p.runner_id) filter(where p.venue=t.venue and p.distance_m=t.distance_m and p.surface=t.surface) cn,avg(p.perf) filter(where p.venue=t.venue and p.distance_m=t.distance_m and p.surface=t.surface) course from {target} t left join {hist} p on t.horse_key=p.horse_key and p.race_date<t.race_date and p.race_date>=t.race_date-interval '180 days' group by t.runner_id), j as (select t.runner_id,count(p.runner_id) jn,avg(p.perf) jp,max(p.race_date) max_pair_date from {target} t left join {hist} p on t.jockey_name=p.jockey_name and t.jockey_affiliation=p.jockey_affiliation and t.trainer_name=p.trainer_name and t.trainer_affiliation=p.trainer_affiliation and nullif(trim(t.jockey_name),'') is not null and nullif(trim(t.trainer_name),'') is not null and p.race_date<t.race_date and p.race_date>=t.race_date-interval '180 days' group by t.runner_id) select t.runner_id,t.race_id,t.race_date,t.venue,t.horse_no,h.n,h.ability,h.max_hist_date,h.cn,h.course,j.jn,j.jp,j.max_pair_date from {target} t join h using(runner_id) join j using(runner_id)'''
c.execute('create temp table f as '+features('targets','history'))
assert c.execute('select count(*) from f where max_hist_date>=race_date or max_pair_date>=race_date').fetchone()[0]==0
# Prefix regression incl. same-day exclusion: compare features for 7/15 using full data vs history truncated strictly prior.
c.execute("create temp table ttest as select * from targets where race_date=date '2025-07-15'")
c.execute("create temp table hprefix as select * from history where race_date<date '2025-07-15'")
c.execute('create temp table full_test as '+features('ttest','history'));c.execute('create temp table prefix_test as '+features('ttest','hprefix'))
# floating point reductions may differ by ~1e-15; tolerance explicit.
assert c.execute('''select count(*) from full_test a full join prefix_test b using(runner_id) where a.runner_id is null or b.runner_id is null or a.n is distinct from b.n or a.cn is distinct from b.cn or a.jn is distinct from b.jn or a.max_hist_date is distinct from b.max_hist_date or a.max_pair_date is distinct from b.max_pair_date or (a.ability is null) != (b.ability is null) or (a.course is null) != (b.course is null) or (a.jp is null) != (b.jp is null) or abs(a.ability-b.ability)>1e-12 or abs(a.course-b.course)>1e-12 or abs(a.jp-b.jp)>1e-12''').fetchone()[0]==0
# Scoring and prediction freeze before evaluation joins. Unknown horse history => no score/abstain for that runner.
c.execute('''create temp table scores as select runner_id,race_id,race_date,venue,horse_no, n,cn,jn, case when n>=2 then ability end a, case when n>=2 then ability+coalesce(0.25*(cn/(cn+3.0))*(course-ability),0) end ac, case when n>=2 then ability+coalesce(0.25*(cn/(cn+3.0))*(course-ability),0)+coalesce(0.15*(jn/(jn+20.0))*(jp-0.5),0) end acj from f''')
c.execute('''create temp table predictions as select runner_id,race_id,race_date,venue,horse_no,model,score,row_number() over(partition by race_id,model order by round(score,12) desc,horse_no asc) pred_rank from scores unpivot(score for model in (a,ac,acj)) where score is not null''')
freeze=OUT/'pilot_prediction_freeze.parquet'; c.execute(f"copy (select * from predictions order by race_id,model,pred_rank) to '{freeze}' (format parquet,compression zstd)"); freeze_sha=hashlib.sha256(freeze.read_bytes()).hexdigest()
# Evaluation only after freeze. Normal race status, valid labels; ties count as winners.
c.execute('''create temp table eligible as select distinct t.race_id from targets t join status s using(race_id) where s.status='NORMAL' and s.is_model_target''')
metrics=c.execute('''select model,count(*) filter(where pred_rank=1) predicted_races,count(*) filter(where pred_rank=1 and o.finish_position=1) win_count,count(*) filter(where pred_rank=1 and o.finish_position between 1 and 3) top3_count,count(distinct p.race_id) filter(where pred_rank<=3 and o.finish_position=1) winner_in_top3 from predictions p join eligible e using(race_id) left join result o using(runner_id) group by model order by model''').fetchall()
res={'label':'RECOVERY-PILOT-r0.1-tie12; proposed reproducibility repair, NOT promoted','generation':m['generation_id'],'manifest_sha256':hashlib.sha256(M.read_bytes()).hexdigest(),'inputs':inputs,'duckdb':duckdb.__version__,'coverage':'2025 only, dirt, H2 retrospective test, 180-day lookback','target_rows':c.execute('select count(*) from targets').fetchone()[0],'target_races':c.execute('select count(distinct race_id) from targets').fetchone()[0],'eligible_races':c.execute('select count(*) from eligible').fetchone()[0],'history_rows':c.execute('select count(*) from history').fetchone()[0],'scorable_rows':c.execute('select count(*) from scores where a is not null').fetchone()[0],'prefix_test_rows':c.execute('select count(*) from ttest').fetchone()[0],'same_future_date_check':'PASS','prefix_vs_full':'PASS','freeze_sha256':freeze_sha,'identity_conflicting_keys':c.execute('select count(*) from (select horse_key from pre group by horse_key having count(distinct horse_name)>1 or count(distinct birth_date)>1)').fetchone()[0],'metrics':[dict(zip(['model','predicted_races','win_count','top3_count','winner_in_top3'],row)) for row in metrics], 'caveats':['No prior-year input; 2025 H2 may have been used by lost research; not independent confirmation','horse_key and name+affiliation pair provisional entity resolution','No odds/payout metrics; no model adoption','Monthly data does not establish exact contemporary availability','No tuning; comparison descriptive and exploratory; missing runners may cause selection bias']}
(OUT/'pilot_metrics.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in res.items() if k!='inputs'},ensure_ascii=False,indent=2))
