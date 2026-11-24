import duckdb,json,hashlib,sys
from pathlib import Path
O=Path(__file__).parent;mode=sys.argv[1];c=duckdb.connect(); c.execute('set threads=4');c.execute("set memory_limit='1800MB'")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if mode=='features':
 assert json.loads((O/'feature_guard.json').read_text())['status']=='PASS'; patterns=[(O/f'features_{y}_t1.parquet',O/f'features_{y}_t4.parquet') for y in range(2017,2024)]
elif mode=='a34_features':
 assert json.loads((O/'a34_guard.json').read_text())['status']=='PASS';patterns=[(O/f'a34_features_{y}_t1.parquet',O/f'a34_features_{y}_t4.parquet') for y in range(2017,2024)]
else:
 a,b=(2022,2023) if mode.endswith('val') else (2017,2021);patterns=[(O/f'pred_{mode}_{y}_t1.parquet',O/f'pred_{mode}_{y}_t4.parquet') for y in range(a,b+1)]
rows=[];files={}
for a,b in patterns:
 for n,p in [('a',a),('b',b)]:c.execute(f"create or replace view {n} as select * from read_parquet('{p}')"); files[p.name]=sha(p)
 schema=c.execute('describe a').fetchall();assert schema==c.execute('describe b').fetchall();cmp=[]
 for k,t,*_ in schema:
  if t in ('DOUBLE','FLOAT'):cmp.append(f'((a.{k} is null)<>(b.{k} is null) or abs(a.{k}-b.{k})>1e-12)')
  else:cmp.append(f'a.{k} is distinct from b.{k}')
 diff=c.execute('select count(*) from a full join b using(runner_id) where '+' or '.join(cmp)).fetchone()[0]; n=c.execute('select count(*) from a').fetchone()[0];rows.append({'file':b.name,'rows':n,'mismatch':diff}); print(rows[-1],flush=True)
 if diff:raise RuntimeError('thread parity failed')
(O/('feature_manifest.json' if mode=='features' else 'a34_feature_manifest.json' if mode=='a34_features' else f'pred_manifest_{mode}.json')).write_text(json.dumps({'status':'PASS','config_sha256':sha(O/('a34_config.json' if mode.startswith('a34') else 'run_config.json')),'files':files,'thread_parity':rows,'columns':[x[0] for x in schema]},indent=2)+'\n')
