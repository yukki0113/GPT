"""Predeclared development-only shortlist and held-out validation choice."""
import csv,json,sys,hashlib
from pathlib import Path
import numpy as np
O=Path(__file__).parent;mode=sys.argv[1]
def load(n):
 with open(O/n) as f:return [{k:(int(v) if v.lstrip('-').isdigit() else v) for k,v in r.items()} for r in csv.DictReader(f)]
def lookup(rows,model,year=0,ref=None):return next(x for x in rows if x['model']==model and x['yr']==year and (ref is None or x['ref']==ref))
def inspect(mode,model,ref,year=0):
 ms=load(f'metrics_{mode}.csv');ps=load(f'pairs_{mode}.csv');m=lookup(ms,model,year);b=lookup(ms,ref,year);p=lookup(ps,model,year,ref)
 delta=100*(p['model_win']-p['ref_win'])/p['races']; t=100*(p['model_top3']-p['ref_top3'])/p['races']; w=100*(p['model_winner3']-p['ref_winner3'])/p['races']; r=100*(m['scored_races']-b['scored_races'])/b['races']; h=100*(m['scored_runners']-b['scored_runners'])/b['runners']; full=100*(m['wins']-b['wins'])/b['races']; native_t=100*(m['top3']-b['top3'])/b['races']; native_w=100*(m['winner3']-b['winner3'])/b['races']
 return {'model':model,'ref':ref,'year':year,'common_races':p['races'],'common_runners':p['common_runners'],'delta_pp':delta,'top1_3rd_delta_pp':t,'winner_top3_delta_pp':w,'race_coverage_delta_pp':r,'runner_coverage_delta_pp':h,'full_win_delta_pp':full,'full_top1_3rd_delta_pp':native_t,'full_winner_top3_delta_pp':native_w,'qualifies':delta>0 and min(t,w,native_t,native_w)>=-.5 and r>=-.5 and h>=-1 and full>=0}
def save(name,d): (O/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(d,ensure_ascii=False,indent=2))
if mode=='dev':
 results=[inspect('dev',m,'a0') for m in ['last3','last5','last8','mean90','mean365','hl30','hl60','hl90']];best=max([x for x in results if x['qualifies']],key=lambda x:x['delta_pp'],default=None);save('a1_selection.json',{'a1':best['model'] if best else 'a0','results':results,'selection_data':'2017-2021 only'})
elif mode=='a2':
 a1=json.loads((O/'a1_selection.json').read_text())['a1'];results=[inspect('a2',m,a1) for m in ['median','top2']];best=max([x for x in results if x['qualifies']],key=lambda x:x['delta_pp'],default=None);save('shortlist.json',{'a1':a1,'a2':best['model'] if best else None,'models':list(dict.fromkeys(['a0','ac0','acj0',a1]+([best['model']] if best else []))),'results':results,'selection_data':'2017-2021 only','validation_opened':False})
elif mode=='val':
 s=json.loads((O/'shortlist.json').read_text());a1=s['a1']; a2=s['a2'];out=[];chosen='a0'
 for m,ref in [(a1,'a0'),(a2,a1)]:
  if not m or m==ref:continue
  results=[inspect('val',m,ref,y) for y in (0,2022,2023)]
  # stratified paired race-day bootstrap, fixed seed, before confirmation
  data=load(f'blocks_val_{m}_{ref}.csv');rng=np.random.default_rng(20261124);tot=np.zeros(2000);den=np.zeros(2000)
  for y in (2022,2023):
   subset=[x for x in data if x['race_date'].startswith(str(y))];n=np.array([x['n'] for x in subset]);d=np.array([x['delta'] for x in subset]);idx=rng.integers(0,len(n),size=(2000,len(n)));tot+=d[idx].sum(1);den+=n[idx].sum(1)
  ci=(np.quantile(100*tot/den,[.025,.975])).tolist();passed=all(x['qualifies'] for x in results) and chosen==ref
  if passed:chosen=m
  out.append({'candidate':m,'ref':ref,'metrics':results,'paired_ci95_pp':ci,'selected':passed})
 save('a1a2_decision.json',{'base_candidate':chosen,'comparisons':out,'confirmation_opened':False,'status':'RESEARCH_ONLY'})
