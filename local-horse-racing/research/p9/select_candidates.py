"""Preregistered P9 candidate selection; never reads confirmation outcomes."""
import csv,json,hashlib,sys
from pathlib import Path
O=Path(__file__).parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def rows(stage):return {(x['model'],int(x['yr'])):{k:(v if k=='model' else int(v)) for k,v in x.items()} for x in csv.DictReader((O/stage/'metrics.csv').open())}
def qualify(x,b):
 return x['wins']>b['wins'] and all((x[k]-b[k])/b['scored_races']*100>=-.5 for k in ['top3','winner3']) and x['scored_races']==b['scored_races'] and x['scored_runners']==b['scored_runners']
if sys.argv[1]=='dev':
 assert not (O/'shortlist.json').exists();r=rows('dev');b=r['astar',0];defs=json.loads((O/'dev/prediction_manifest.json').read_text())['models']; winners=[]; decisions=[]
 for family in ['j','tk','p','s','d']:
  names=[n for n,v in defs.items() if v and v[0]['family']==family];valid=[n for n in names if qualify(r[n,0],b)];valid.sort(key=lambda n:(-r[n,0]['wins'],defs[n][0]['weight'],-defs[n][0]['k'],-defs[n][0]['days'],n))
  for n in names:decisions.append({'model':n,'family':family,'dev_delta_wins':r[n,0]['wins']-b['wins'],'dev_qualifies':n in valid,'shortlisted':bool(valid and n==valid[0])})
  if valid:winners.append(valid[0])
 winners.sort(key=lambda n:(-r[n,0]['wins'],n)); models={'astar':[],**{n:defs[n] for n in winners}}
 for i in range(2,len(winners)+1):models['prefix'+str(i)]=[defs[n][0] for n in winners[:i]]
 dump(O/'shortlist.json',{'status':'FROZEN_BEFORE_VALIDATION','dev_metrics_sha256':sha(O/'dev/metrics.csv'),'ordered_winners':winners,'models':models,'decisions':decisions,'validation_opened':False});print(winners,flush=True)
else:
 assert not (O/'candidate_config.json').exists();r=rows('val');a=json.loads((O/'shortlist.json').read_text());wins=a['ordered_winners'];models=a['models']; passed={};decisions=[]
 for n in models:
  if n=='astar':continue
  good=all(qualify(r[n,y],r['astar',y]) for y in [2022,2023]);prev=None
  if n.startswith('prefix'):
   i=int(n[6:]);prev=wins[0] if i==2 else 'prefix'+str(i-1);good=good and all(passed.get(x,False) for x in wins[:i]) and all(r[n,y]['wins']>r[prev,y]['wins'] for y in [2022,2023])
  passed[n]=good;decisions.append({'model':n,'wins':r[n,0]['wins'],'delta_wins':r[n,0]['wins']-r['astar',0]['wins'],'annual_delta_wins':[r[n,y]['wins']-r['astar',y]['wins'] for y in [2022,2023]],'qualified':good,'incremental_ref':prev})
 cand=sorted([n for n,ok in passed.items() if ok],key=lambda n:(-r[n,0]['wins'],len(models[n]),n));sel=cand[0] if cand else 'astar';dump(O/'candidate_config.json',{'status':'FROZEN_BEFORE_RETROSPECTIVE','model_id':'P9-Cstar-r1' if sel!='astar' else 'P8-Astar-r1','selected':sel,'models':{'astar':[],**({sel:models[sel]} if sel!='astar' else {})},'base_config_sha256':'bea7046ab28aa1f18c11e387634f18d70e8687f38dd22cea54c5213b9f622bc2','shortlist_sha256':sha(O/'shortlist.json'),'validation_metrics_sha256':sha(O/'val/metrics.csv'),'decisions':decisions,'confirmation_opened':False,'production_approved':False});print(sel,decisions,flush=True)
