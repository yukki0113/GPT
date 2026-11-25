"""Score from exact derived feature freeze only, no raw/post/labels. All runners incl unknown."""
import duckdb,sys,json,hashlib
from pathlib import Path
O=Path(__file__).parent;stage=sys.argv[1];threads=int(sys.argv[2]);tag='confirm' if stage=='confirm' else 'devval';D=O/tag;S=O/stage;S.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
family={'j':([180,365],20),'tk':([180,365],20),'p':([180,365],10),'s':([365],30),'d':([365],30)}
defs={'astar':[]}
for f,(ws,n) in family.items():
 for w in ws:
  for k in [30,100]:
   for weight in [10,20]:
    name=f'{f}{w}_k{k}_w{weight}';defs[name]=[dict(family=f,days=w,min_n=n,k=k,weight=weight/100)]
if stage=='dev': years=(2017,2021)
elif stage=='val':
 years=(2022,2023); defs=json.loads((O/'shortlist.json').read_text())['models']
else:
 years=(2024,2025); defs=json.loads((O/'candidate_config.json').read_text())['models']
feature=D/'features_t4.parquet';a=json.loads((D/'feature_audit.json').read_text()); assert sha(feature)==a['feature_sha256']
for f in family:
 x=json.loads((D/f'thread_parity_{f}.json').read_text());assert x['status']=='PASS' and x['reference_sha256']==sha(feature)
c=duckdb.connect();c.execute(f"set threads={threads}; set memory_limit='1800MB'; set temp_directory='/tmp/p9score'")
# forbid other input files; after mounting derived freeze load in memory then disable external access? COPY requires external access; no raw/post path accepted by script.
c.execute(f"create table f as select * from read_parquet('{feature}') where year(race_date) between {years[0]} and {years[1]}")
allowed={'runner_id','race_id','race_date','venue','horse_no','field_size','distance_m','n_hl60','s_astar','r_astar','reason_astar','ambiguous'}|{f'{f}_known' for f in family}|{f'{f}_{k}{w}' for f,(ws,_) in family.items() for w in ws for k in ['n','e','excluded']}
assert {r[0] for r in c.execute('describe f').fetchall()}==allowed
# DuckDB tie12 boundary regression.
assert c.execute("select list(horse_no order by round(s,12) desc,horse_no) from (values(1,0.5000000000001),(2,0.5000000000002),(3,0.5000000000006)) t(horse_no,s)").fetchone()[0]==[3,1,2]
manifest={}
for name,terms in defs.items():
 ex=[];ap=[]
 for d in terms:
  f,w,n,k,weight=d['family'],d['days'],d['min_n'],d['k'],d['weight']; cond=f'{f}_known and {f}_n{w}>={n} and not ambiguous and s_astar is not null';ex.append(f'case when {cond} then {weight}*({f}_e{w}/1000000000.0)/({f}_n{w}+{k}) else 0.0 end');ap.append(f'case when {cond} then 1 else 0 end')
 score='s_astar'+''.join(' + ('+e+')' for e in ex); applied='+'.join(ap) or '0'
 q=f'''with s as(select runner_id,race_id,race_date,venue,horse_no,distance_m,n_hl60,reason_astar, {score} score, {applied} applied,r_astar from f), r as(select *,case when score is not null then row_number() over(partition by race_id order by round(score,12) desc nulls last,horse_no) end pred_rank from s) select runner_id,race_id,race_date,venue,horse_no,distance_m,n_hl60,reason_astar,score,applied,pred_rank from r order by runner_id'''
 if threads==4:
  p=S/f'{name}.parquet';c.execute(f"copy ({q}) to '{p}' (format parquet,compression zstd)");manifest[name]=sha(p)
  assert c.execute(f"select count(*) from read_parquet('{p}') where score is not null and not isfinite(score)").fetchone()[0]==0
  if name=='astar':assert c.execute(f"select count(*) from read_parquet('{p}') p join f using(runner_id) where pred_rank is distinct from r_astar or score is distinct from s_astar").fetchone()[0]==0
 else:
  p=S/f'{name}.parquet';old=json.loads((S/'prediction_manifest.json').read_text());assert sha(p)==old['files'][name]
  n=c.execute(f'''select count(*) from ({q}) a full join read_parquet('{p}') b using(runner_id) where a.runner_id is null or b.runner_id is null or a.pred_rank is distinct from b.pred_rank or a.applied is distinct from b.applied or (a.score is null)<>(b.score is null) or abs(a.score-b.score)>1e-12 or a.reason_astar is distinct from b.reason_astar''').fetchone()[0];assert n==0,(name,n);manifest[name]=0
 print(stage,threads,name,flush=True)
if threads==4:dump(S/'prediction_manifest.json',{'stage':stage,'years':years,'feature_sha256':sha(feature),'files':manifest,'models':defs,'status':'FROZEN_T4'})
else:dump(S/'prediction_parity.json',{'status':'PASS','prediction_manifest_sha256':sha(S/'prediction_manifest.json'),'mismatch':manifest})
