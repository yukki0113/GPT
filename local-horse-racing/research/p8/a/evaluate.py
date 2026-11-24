"""Evaluator opens prediction Freeze, then separate labels. No feature generation or tuning on validation."""
import duckdb,json,hashlib,sys,csv
from pathlib import Path
O=Path(__file__).parent; mode=sys.argv[1]; c=duckdb.connect();c.execute('set threads=4');c.execute("set memory_limit='1800MB'")
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); mf=json.loads((O/f'pred_manifest_{mode}.json').read_text());assert mf['status']=='PASS'; assert mf['config_sha256']==sha(O/('a34_config.json' if mode.startswith('a34') else 'run_config.json'))
files=[str(O/k) for k,v in mf['files'].items() if k.endswith('_t4.parquet') and sha(O/k)==v];assert len(files)==(2 if mode.endswith('val') else 5)
c.execute(f'create view p as select * from read_parquet({files!r})'); cols=[x[0] for x in c.execute('describe p').fetchall()];models=[x[2:] for x in cols if x.startswith('s_')];assert 'a0' in models
im=json.loads((O/'input_manifest.json').read_text());assert sha(O/'labels.parquet')==im['labels_sha256'];
y0,y1=(2022,2023) if mode.endswith('val') else (2017,2021)
c.execute(f"create view label as select * from read_parquet('{O/'labels.parquet'}') where year(race_date) between {y0} and {y1}")
c.execute("create table eligible as select race_id from label where status='NORMAL' and is_model_target group by race_id having count(*) filter(where finish_position=1)>0")
c.execute('create table j as select p.*,label.finish_position from p join eligible using(race_id) left join label using(runner_id)')
assert c.execute('select count(*)=count(distinct runner_id) from j').fetchone()[0]
metrics=[];pair=[];segments=[]
for model in models:
 r='r_'+model;s='s_'+model
 # year + total, only labeled valid races; all ENTRY runners retained. Strict intent-to-predict.
 q=f'''with rr as (select race_id,year(race_date) yr,venue,count(*) runners,count({s}) scored,max(case when {r}=1 and finish_position=1 then 1 else 0 end) win,max(case when {r}=1 and finish_position between 1 and 3 then 1 else 0 end) top3,max(case when {r}<=3 and finish_position=1 then 1 else 0 end) winner3,max(case when {r}=1 and finish_position is not null then 1 else 0 end) known, count(*) filter(where finish_position=1) winners,count(*) filter(where {r}<=3 and finish_position=1) winner_found, sum(case when {r} is not null and finish_position is not null then 1 else 0 end) valid_scored from j group by all) select coalesce(yr,0) yr,count(*) races,sum(runners) runners,sum(scored) scored_runners,count(*) filter(where scored>0) scored_races,sum(win) wins,sum(top3) top3,sum(winner3) winner3,sum(known) known_top1,count(*) filter(where scored>=3) complete_top3,sum(winner3) filter(where scored>=3) winner3_complete,sum(winners) winners,sum(winner_found) winner_found,sum(valid_scored) valid_scored from rr group by grouping sets ((yr),()) order by yr'''
 cur=c.execute(q);fields=[x[0] for x in cur.description]; metrics.extend([{'model':model,**dict(zip(fields,row))} for row in cur.fetchall()]);
 q=f'''with rr as (select race_id,year(race_date) yr,venue,count(*) runners,count({s}) scored,max(case when {r}=1 and finish_position=1 then 1 else 0 end) win,max(case when {r}=1 and finish_position between 1 and 3 then 1 else 0 end) top3,max(case when {r}<=3 and finish_position=1 then 1 else 0 end) winner3 from j group by all) select yr,venue,count(*) races,sum(runners) runners,sum(scored) scored_runners,count(*) filter(where scored>0) scored_races,sum(win) wins,sum(top3) top3,sum(winner3) winner3 from rr group by all order by 1,2'''
 cur=c.execute(q);fields=[x[0] for x in cur.description];segments.extend([{'model':model,**dict(zip(fields,row))} for row in cur.fetchall()])
 # common runner cohort; rerank both from same support; report paired race wins and guards
 for ref in list(dict.fromkeys((['a0'] if mode=='dev' else ['a0']+([json.loads((O/'a1_selection.json').read_text())['a1']] if (O/'a1_selection.json').exists() else [])) + ([x for x in models if x in ('opp10','opp20','prize10','prize20','speed15','speed30','gap15','gap30','combined')] if mode in ('a34combine','a34finaldev','a34val') else []))):
  if model==ref:continue
  q=f'''with common as (select race_id,race_date,venue,runner_id,finish_position,row_number() over(partition by race_id order by round(s_{model},12) desc,horse_no) m,row_number() over(partition by race_id order by round(s_{ref},12) desc,horse_no) b from j where s_{model} is not null and s_{ref} is not null), race as (select race_id,race_date,venue,count(*) n,max(case when m=1 and finish_position=1 then 1 else 0 end) mw,max(case when b=1 and finish_position=1 then 1 else 0 end) bw,max(case when m=1 and finish_position between 1 and 3 then 1 else 0 end) mt,max(case when b=1 and finish_position between 1 and 3 then 1 else 0 end) bt,max(case when m<=3 and finish_position=1 then 1 else 0 end) m3,max(case when b<=3 and finish_position=1 then 1 else 0 end) b3 from common group by all) select coalesce(year(race_date),0) yr,count(*) races,sum(n) common_runners,sum(mw) model_win,sum(bw) ref_win,sum(mt) model_top3,sum(bt) ref_top3,sum(m3) model_winner3,sum(b3) ref_winner3 from race group by grouping sets ((year(race_date)),()) order by 1'''
  cur=c.execute(q);fields=[x[0] for x in cur.description];pair.extend([{'model':model,'ref':ref,**dict(zip(fields,row))} for row in cur.fetchall()])
  # race-day paired blocks for deterministic bootstrap; keep provenance and sufficient statistics
  q=q[:q.index('select coalesce(year(race_date)')]+"select race_date,count(*) n,sum(mw-bw) delta from race group by race_date order by race_date"
  cur=c.execute(q);rows=cur.fetchall(); (O/f'blocks_{mode}_{model}_{ref}.csv').write_text('race_date,n,delta\n'+'\n'.join(','.join(map(str,x)) for x in rows)+'\n')
for name,rows in [('metrics',metrics),('pairs',pair),('segments',segments)]:
 with open(O/f'{name}_{mode}.csv','w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(O/f'evaluation_{mode}.json').write_text(json.dumps({'mode':mode,'eligible_races':c.execute('select count(*) from eligible').fetchone()[0],'rows':c.execute('select count(*) from j').fetchone()[0],'pred_manifest_sha256':sha(O/f'pred_manifest_{mode}.json'),'label_sha256':sha(O/'labels.parquet'),'evaluation_period':[y0,y1],'labels_opened_after_freeze':True,'confirmation_opened':False},indent=2)+'\n')
for m in metrics:
 if m['yr']==0:print(m['model'],m['races'],m['scored_races'],m['wins'],round(100*m['wins']/m['scored_races'],4),m['top3'],m['winner3'],flush=True)
