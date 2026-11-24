"""A3/A4 candidate scorer. Reads derived feature Freeze only, never labels/history/canonical."""
import sys,json,hashlib
from pathlib import Path
import duckdb
O=Path(__file__).parent; mode=sys.argv[1]; th=int(sys.argv[2]); c=duckdb.connect();c.execute(f'set threads={th}');c.execute("set memory_limit='1600MB'")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();config=json.loads((O/'a34_config.json').read_text());assert config['base']=='hl60';fm=json.loads((O/'feature_manifest.json').read_text());am=json.loads((O/'a34_feature_manifest.json').read_text());assert am['status']=='PASS' and am['config_sha256']==sha(O/'a34_config.json')
expr={'a0':'case when n_a0>=2 then a0 end','hl60':'case when n_hl60>=2 then hl60 end'};refs={'a0':'n_a0','hl60':'n_hl60'}
for name,f in [('opp','opp_delta'),('prize','prize_delta'),('speed','speed_score'),('gap','gap_score')]:
 for w in ([.1,.2] if name in ('opp','prize') else [.15,.30]):
  m=f'{name}{int(w*100)}';adj=f'{w}*case when n_{f}>=2 then '+(f'{f}' if name in ('opp','prize') else f'({f}-hl60)')+' else 0 end';expr[m]=f'case when n_hl60>=2 then hl60+{adj} end';refs[m]='n_hl60'
expr['one_run']='case when n_hl60>=2 then hl60 when n_hl60=1 then (hl60+1.5)/4 end';refs['one_run']='n_hl60'
if mode=='a34dev':models=list(expr)
else:
 sel=json.loads((O/'a34_shortlist.json').read_text());models=list(dict.fromkeys(['a0','hl60']+sel['models']));
 if sel.get('combined'):
  x,y=sel['combined'];expr['combined']=f'({expr[x]})+({expr[y]})-({expr["hl60"]})';refs['combined']='n_hl60'
 if mode=='a34combine': models=list(dict.fromkeys(['a0','hl60']+sel['models']+['combined']))
 if 'one_run_combined' in models:
  b=sel['one_run_parent'];expr['one_run_combined']=f'case when n_hl60=1 then (hl60+1.5)/4 else ({expr[b]}) end';refs['one_run_combined']='n_hl60'
assert c.execute('select list(horse_no order by round(score,12) desc,horse_no asc) from (values (3,0.12345678901249::double),(1,0.12345678901249::double),(2,0.12345678901251::double)) t(horse_no,score)').fetchone()[0]==[2,1,3]
for year in range(2022,2024) if mode.endswith('val') else range(2017,2022):
 p=O/f'features_{year}_t{th}.parquet';q=O/f'a34_features_{year}_t{th}.parquet';assert sha(p)==fm['files'][p.name] and sha(q)==am['files'][q.name];c.execute(f"create or replace view f as select * from read_parquet('{p}')");c.execute(f"create or replace view g as select * from read_parquet('{q}')")
 for name,man in [('f',fm),('g',am)]:assert {x[0] for x in c.execute('describe '+name).fetchall()}==set(man['columns'])
 scores=','.join(f'case when not ambiguous then ({expr[m]}) end s_{m}' for m in models);ns=','.join(f'{refs[m]} n_{m}' for m in models)
 c.execute(f'create or replace table s as select f.runner_id,f.race_id,f.race_date,venue,horse_no,field_size,ambiguous,{ns},{scores} from f join g using(runner_id)');assert c.execute('select count(*) from s').fetchone()==c.execute('select count(*) from f').fetchone()
 for m in models:assert c.execute(f'select count(*) from s where s_{m} is not null and not isfinite(s_{m})').fetchone()[0]==0
 ranks=','.join(f'case when s_{m} is not null then row_number() over(partition by race_id order by round(s_{m},12) desc nulls last,horse_no asc) end r_{m}' for m in models)
 reasons=','.join(f"case when ambiguous then 'AMBIGUOUS_IDENTITY' when s_{m} is not null then 'SCORED' when n_{m}<2 then 'INSUFFICIENT_HISTORY' else 'UNKNOWN' end reason_{m}" for m in models)
 c.execute(f"copy (select *,{ranks},{reasons} from s order by runner_id) to '{O/f'pred_{mode}_{year}_t{th}.parquet'}' (format parquet,compression zstd)");print(mode,year,th,flush=True)
