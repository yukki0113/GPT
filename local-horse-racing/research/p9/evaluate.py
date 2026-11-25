"""Independent outcome evaluator, only after prediction manifest + rank parity."""
import duckdb,json,sys,hashlib,csv
from pathlib import Path
O=Path(__file__).parent; stage=sys.argv[1]; S=O/stage;D=O/('confirm' if stage=='confirm' else 'devval');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (S/'evaluation.json').exists(),'already evaluated; immutable run'
m=json.loads((S/'prediction_manifest.json').read_text());a=json.loads((S/'prediction_parity.json').read_text());assert a['status']=='PASS' and a['prediction_manifest_sha256']==sha(S/'prediction_manifest.json') and set(a['mismatch'])==set(m['files']) and all(x==0 for x in a['mismatch'].values());im=json.loads((D/'input_manifest.json').read_text());assert sha(D/'labels.parquet')==im['stage_files']['labels.parquet']
c=duckdb.connect();c.execute("set threads=4;set memory_limit='1800MB'");q=c.execute
q(f"create table labels as select * from read_parquet('{D/'labels.parquet'}') where year(race_date) between {m['years'][0]} and {m['years'][1]}")
q("create table eligible as select race_id from labels where status='NORMAL' and is_model_target group by race_id having count(*) filter(where finish_position=1)>0")
rows=[];segments=[];blocks=[];allrace={};coverage=[];diagnostics=[]
def collect(query,model,ls):
 res=q(query); names=[x[0] for x in res.description];ls.extend([dict(model=model,**dict(zip(names,x))) for x in res.fetchall()])
for n,h in m['files'].items():
 p=S/f'{n}.parquet';assert sha(p)==h
 q(f"create or replace view pp as select * from read_parquet('{p}')")
 if n=='astar':q('create table support as select runner_id,score is not null scored from pp')
 else:assert q('select count(*) from pp p full join support s using(runner_id) where p.runner_id is null or s.runner_id is null or (p.score is not null)<>s.scored').fetchone()[0]==0
 q('''create or replace table j as select p.*,l.finish_position from pp p join eligible using(race_id) left join labels l using(runner_id)''')
 q('''create or replace table rr as select race_id,race_date,venue,any_value(distance_m) distance_m,count(*) runners,count(score) scored_runners,max(case when pred_rank=1 and finish_position=1 then 1 else 0 end) win,max(case when pred_rank=1 and finish_position between 1 and 3 then 1 else 0 end) top3,max(case when pred_rank<=3 and finish_position=1 then 1 else 0 end) winner3,max(case when pred_rank=1 and finish_position is not null then 1 else 0 end) known_top1,sum(case when finish_position=1 then 1 else 0 end) winners,sum(case when finish_position=1 and pred_rank<=3 then 1 else 0 end) winners_found,count(*) filter(where applied>0) applied from j group by race_id,race_date,venue''')
 if n=='astar':q('create table base_rr as select * from rr')
 summary='count(*) eligible,sum(runners) runners,sum(scored_runners) scored_runners,count(*) filter(where scored_runners>0) scored_races,sum(win) wins,sum(top3) top3,sum(winner3) winner3,sum(known_top1) known_top1,count(*) filter(where scored_runners>=3) complete_top3,sum(winner3) filter(where scored_runners>=3) winner3_complete,sum(winners) winners,sum(winners_found) winners_found,sum(applied) applied'
 collect(f'select coalesce(year(race_date),0) yr,{summary} from rr group by grouping sets ((year(race_date)),()) order by 1',n,rows)
 collect(f'select year(race_date) yr,venue,{summary} from rr group by all order by 1,2',n,segments)
 collect(f'select year(race_date) yr,distance_m,{summary} from rr group by all order by 1,2',n,diagnostics)
 collect('''select year(race_date) yr,n_hl60,count(*) runners,count(score) scored,count(*) filter(where applied>0) applied,count(*) filter(where pred_rank=1) top1_count,count(*) filter(where pred_rank=1 and finish_position=1) wins from j group by all order by 1,2''',n,coverage)
 collect('''select r.race_date,r.venue,count(*) filter(where r.scored_runners>0) den,sum(r.win-b.win) delta from rr r join base_rr b using(race_id) group by r.race_date,r.venue order by 1,2''',n,blocks)
 if stage!='dev':
  # paired rank agreement with actual finish positions; tied finish pairs not counted; tie12 scoring ties give half credit
  z=q('''select year(a.race_date),count(*),sum(case when round(a.score,12)=round(b.score,12) then .5 when (a.score>b.score)=(a.finish_position<b.finish_position) then 1.0 else 0.0 end) from j a join j b on a.race_id=b.race_id and a.horse_no<b.horse_no where a.score is not null and b.score is not null and a.finish_position is not null and b.finish_position is not null and a.finish_position<>b.finish_position group by 1 order by 1''').fetchall()
  allrace[n]=z
 print(n,next(x for x in rows if x['model']==n and x['yr']==0)['wins'],flush=True)
for name,data in [('metrics',rows),('segments',segments),('distance_segments',diagnostics),('history_segments',coverage),('blocks',blocks)]:
 with (S/f'{name}.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
dump(S/'evaluation.json',{'status':'PASS','prediction_manifest_sha256':sha(S/'prediction_manifest.json'),'label_sha256':im['stage_files']['labels.parquet'],'stage':stage,'rank_concordance':allrace,'support_identical':True})
