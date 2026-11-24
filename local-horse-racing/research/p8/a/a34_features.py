"""A3/A4 aggregation, strictly earlier historical observations; no evaluation labels."""
import duckdb,json,hashlib,sys
from pathlib import Path
O=Path(__file__).parent; mode=sys.argv[1];th=int(sys.argv[2]);c=duckdb.connect();c.execute(f'set threads={th}');c.execute("set memory_limit='2200MB'")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); im=json.loads((O/'input_manifest.json').read_text()); fm=json.loads((O/'feature_manifest.json').read_text()); assert sha(O/'entry.parquet')==im['entry_sha256'];a=json.loads((O/f'reference_audit_t{th}.json').read_text());p=O/f'enriched_t{th}.parquet';assert sha(p)==a['enriched_sha256'];assert sha(O/'enriched_t1.parquet')==sha(O/'enriched_t4.parquet'); assert a['strict_reference_dates']=='PASS'
c.execute(f"create view entry as select runner_id,race_id,race_date,horse_key,ambiguous from read_parquet('{O/'entry.parquet'}')");c.execute(f"create view hist as select * from read_parquet('{p}')")
H='runner_id race_id race_date horse_key perf opp_delta opp_ref_max prize_delta prize_ref_n prize_ref_max speed_score speed_ref_n speed_ref_max gap_score'.split();T='runner_id race_id race_date horse_key ambiguous'.split()
def validate(n,cols):
 if [x[0] for x in c.execute('describe '+n).fetchall()]!=cols:raise ValueError('unexpected stage columns')
validate('entry',T);validate('hist',H)
family=['opp_delta','prize_delta','speed_score','gap_score']
def sql(t,h):
 ag=[]
 for f in family:
  cond=f'filter(where {f} is not null)';w='exp(-ln(2.0)*date_diff(\'day\',h.race_date,t.race_date)/60.0)'
  # sorted ordered aggregate (deterministic). Relative reference support already audited in enriched history.
  ag.extend([f'count({f}) n_{f}',f'max(h.race_date) {cond} max_{f}',f'min(h.race_date) {cond} min_{f}',f'fsum({f}*{w} order by h.race_date,h.runner_id) {cond}/nullif(fsum({w} order by h.race_date,h.runner_id) {cond},0) {f}'])
 return f'''select t.runner_id,t.race_id,t.race_date,{','.join(ag)} from {t} t left join {h} h on h.horse_key=t.horse_key and not t.ambiguous and h.race_date<t.race_date and h.race_date>=t.race_date-interval '365 days' group by t.runner_id,t.race_id,t.race_date'''
def diff(a,b):
 cmp=[]
 for k,t,*_ in c.execute('describe '+a).fetchall():
  cmp.append(f'((a.{k} is null)<>(b.{k} is null) or abs(a.{k}-b.{k})>1e-12)' if t=='DOUBLE' else f'a.{k} is distinct from b.{k}')
 return c.execute(f'select count(*) from {a} a full join {b} b using(runner_id) where '+' or '.join(cmp)).fetchone()[0]
checks=[]
for y in range(2017,2024):
 c.execute(f'create or replace table target as select * from entry where year(race_date)={y}')
 c.execute(f'create or replace view hy as select * from hist where year(race_date) between {y-1} and {y}')
 if mode=='full':
  c.execute('create or replace table f as '+sql('target','hy'));assert c.execute('select count(*) from f where '+' or '.join(f'max_{k}>=race_date' for k in family)).fetchone()[0]==0
  c.execute(f"copy (select * from f order by runner_id) to '{O/f'a34_features_{y}_t{th}.parquet'}' (format parquet,compression zstd)");print('A34 feature',y,th,flush=True)
 else:
  d=c.execute('select min(race_date) from target').fetchone()[0];c.execute(f"create or replace table t as select * from target where race_date=date '{d}'");c.execute(f"create or replace view hp as select * from hy where race_date<date '{d}'");c.execute(f"create or replace view hx as select * from hy union all select runner_id,race_id,race_date,horse_key,9999.,9999.,race_date-1,9999.,100,race_date-1,9999.,100,race_date-1,9999. from t union all select runner_id,race_id,race_date+1,horse_key,-9999.,-9999.,race_date, -9999.,100,race_date,-9999.,100,race_date,-9999. from t")
  for name,src in [('p','hp'),('q','hy'),('z','hx')]:c.execute(f'create or replace table {name} as '+sql('t',src))
  n1=diff('p','q');n2=diff('p','z');checks.append({'year':y,'rows':c.execute('select count(*) from t').fetchone()[0],'prefix_diff':n1,'injected_diff':n2});assert n1==n2==0,checks[-1];print(checks[-1],flush=True)
if mode=='guard':
 for col in ['finish_position','popularity','status','body_weight_kg','payout_yen','overall_record_raw','track_condition']:
  c.execute(f'create or replace view bad as select *,0 as {col} from entry')
  try:validate('bad',T);raise RuntimeError('bad column accepted')
  except ValueError:pass
 (O/'a34_guard.json').write_text(json.dumps({'status':'PASS','checks':checks,'forbidden_columns_rejected':7},indent=2)+'\n')
