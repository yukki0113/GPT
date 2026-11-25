"""P9 derived-only feature generation, integer exact daily windows; no evaluator labels."""
import duckdb,sys,json,hashlib
from pathlib import Path
O=Path(__file__).parent; tag=sys.argv[1]; threads=int(sys.argv[2]); D=O/tag
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((D/'input_manifest.json').read_text()); assert all(sha(D/n)==m['stage_files'][n] for n in ('targets.parquet','history.parquet'))
c=duckdb.connect();c.execute(f"set threads={threads}; set memory_limit='1800MB'; set temp_directory='/tmp/p9spill'")
def sql(q):return c.execute(q)
def one(q):return sql(q).fetchone()[0]
T='runner_id race_id race_date venue horse_no field_size distance_m horse_key ambiguous n_hl60 s_astar r_astar reason_astar j tk p s d'.split(); H='runner_id race_date horse_key j tk p s d e'.split()
def gate(t,h):
 if [x[0] for x in sql(f'describe {t}').fetchall()]!=T or [x[0] for x in sql(f'describe {h}').fetchall()]!=H:raise ValueError('unexpected/forbidden stage column')
for v,n in [('targets','targets'),('history','history')]:sql(f"create view {v} as select * from read_parquet('{D/n}.parquet')")
gate('targets','history'); neg=[]
for col in ['popularity','payout_yen','overall_record_raw','status','track_condition','body_weight_kg','finish_position']:
 sql(f'create or replace view bad as select *,1 as {col} from targets')
 try:gate('bad','history');raise AssertionError(col)
 except ValueError:neg.append(col)
assert one('select count(*) from history where e is null or abs(e)>1000000000')==0
family={'j':[180,365],'tk':[180,365],'p':[180,365],'s':[365],'d':[365]}
# One stream per key and horse. The range end excludes every row on target day, including injected rows.
def query(f,ws,t,h):
 agg=[]; fields=[]
 for w in ws:
  for a,ex in [('g',f'partition by k order by dt range between {w} preceding and 1 preceding'),('h',f'partition by k,horse_key order by dt range between {w} preceding and 1 preceding')]:
   agg += [f'coalesce(sum(n) over({ex}),0)::bigint {a}n{w}',f'coalesce(sum(e) over({ex}),0)::bigint {a}e{w}']
  fields += [f'(gn{w}-hn{w}) {f}_n{w}',f'(ge{w}-he{w}) {f}_e{w}',f'hn{w} {f}_excluded{w}']
 return f'''with u as(select runner_id,{f} k,horse_key,cast(epoch(race_date)/86400 as bigint) dt,0::bigint n,0::bigint e,true target from {t} union all select runner_id,{f} k,horse_key,cast(epoch(race_date)/86400 as bigint) dt,1::bigint n,e,false target from {h} where {f} is not null), a as(select *,{','.join(agg)} from u where k is not null) select runner_id,{','.join(fields)} from a where target'''
if len(sys.argv)>3:
 f=sys.argv[3];ws=family[f];assert threads==1
 sql(f'create table single as '+query(f,ws,'targets','history'))
 sql(f"create view reference as select * from read_parquet('{D/'features_t4.parquet'}')")
 cmp=' or '.join(f'coalesce(a.{f}_{k}{w},0) is distinct from b.{f}_{k}{w}' for w in ws for k in ['n','e','excluded'])
 diff=one(f'select count(*) from reference b left join single a using(runner_id) where {cmp}')
 assert diff==0 and one('select count(*) from single')==one(f'select count({f}) from targets')
 (D/f'thread_parity_{f}.json').write_text(json.dumps({'family':f,'status':'PASS','mismatch':diff,'reference_sha256':sha(D/'features_t4.parquet'),'threads':[1,4],'rows':one('select count(*) from reference')})+'\n'); print(f,'t1 parity',diff,flush=True);sys.exit(0)
for f,ws in family.items():
 sql(f'create table f_{f} as '+query(f,ws,'targets','history')); print('family',f,one(f'select count(*) from f_{f}'),flush=True)
cols=['t.runner_id','t.race_id','t.race_date','t.venue','t.horse_no','t.field_size','t.distance_m','t.n_hl60','t.s_astar','t.r_astar','t.reason_astar','t.ambiguous']
for f,ws in family.items():
 cols.append(f't.{f} is not null as {f}_known')
 for w in ws:
  for k in ['n','e','excluded']:cols.append(f'coalesce(f_{f}.{f}_{k}{w},0)::bigint as {f}_{k}{w}')
sql('create table features as select '+','.join(cols)+' from targets t '+ ' '.join(f'left join f_{f} using(runner_id)' for f in family))
assert one('select count(*) from features')==one('select count(*) from targets')
assert one('select count(*) from features where '+ ' or '.join(f'{f}_n{w}<0 or abs({f}_e{w})>{f}_n{w}*1000000000' for f,ws in family.items() for w in ws))==0
p=D/f'features_t{threads}.parquet';sql(f"copy (select * from features order by runner_id) to '{p}' (format parquet,compression zstd)");print('freeze',sha(p),flush=True)
if threads==4:
 # independent per-boundary strict-prefix direct join, plus real production-query negative injection on sampled targets.
 checks=[]
 for y in range(2017,m['end_year']+1):
  dt=one(f'select min(race_date) from targets where year(race_date)={y}')
  sql(f"create or replace temp table tt as select * from targets where race_date=date '{dt}' qualify row_number() over(partition by venue order by runner_id)<=5")
  sql(f"create or replace temp view hp as select * from history where race_date<date '{dt}'")
  # Inject identical keys on date and next date, incl changed horse_key to force potential contamination if date ignored.
  sql(f"create or replace temp view hx as select * from hp union all select runner_id,race_date,'INJECTED_OTHER_HORSE',j,tk,p,s,d,1000000000::bigint from tt union all select runner_id,race_date+1,'INJECTED_OTHER_HORSE',j,tk,p,s,d,-1000000000::bigint from tt")
  for f,ws in family.items():
   for w in ws:
    # reference only prior dates, same key, exclude same horse; explicit count and sum
    q=f'''select t.runner_id,count(h.runner_id)::bigint n,coalesce(sum(h.e),0)::bigint e from tt t left join hp h on t.{f}=h.{f} and h.horse_key<>t.horse_key and h.race_date>=t.race_date-interval '{w} days' group by t.runner_id'''
    diff=one(f'''select count(*) from ({q}) a join features b using(runner_id) where a.n<>b.{f}_n{w} or a.e<>b.{f}_e{w}''')
    assert diff==0,(y,f,w,diff)
   # test real window function on prefix and injection (only keys on sample, bound to max window)
   sql(f"create or replace temp view htest as select * from hx where race_date>=date '{dt}'-interval '365 days' and {f} in (select distinct {f} from tt where {f} is not null)")
   v=query(f,ws,'tt','htest'); cmp=' or '.join(f'a.{f}_{k}{w}<>b.{f}_{k}{w}' for w in ws for k in ['n','e','excluded']); diff=one(f'select count(*) from ({v}) a join features b using(runner_id) where {cmp}');assert diff==0,(y,f,diff)
   checks.append({'year':y,'date':str(dt),'family':f,'sample':one('select count(*) from tt'),'prefix_reference_diff':0,'same_future_injection_diff':0})
  print('guard',y,flush=True)
 (D/'feature_audit.json').write_text(json.dumps({'status':'PASS_SCOPED','threads':threads,'feature_sha256':sha(p),'forbidden_rejected':neg,'checks':checks,'lineage':'targets and history SHA; exact group key/date window, subtract same horse; per-target counts and excluded counts; max actual history date derivable by explicit join','quantization':'integer residual 1e9'},indent=2)+'\n')
