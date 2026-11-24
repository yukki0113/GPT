"""A3/A4 staged development selection and pre-frozen validation."""
import csv,json,sys,hashlib
from pathlib import Path
import numpy as np
O=Path(__file__).parent;mode=sys.argv[1]
def load(n):
 with open(O/n) as f:return [{k:(int(v) if v.lstrip('-').isdigit() else v) for k,v in r.items()} for r in csv.DictReader(f)]
def get(rows,model,year=0,ref=None):return next(x for x in rows if x['model']==model and x['yr']==year and (ref is None or x['ref']==ref))
def inspect(mode,m,b,year=0,coverage_only=False):
 ms=load(f'metrics_{mode}.csv');ps=load(f'pairs_{mode}.csv');a=get(ms,m,year);r=get(ms,b,year);p=get(ps,m,year,b)
 delta=100*(p['model_win']-p['ref_win'])/p['races'];t=100*(p['model_top3']-p['ref_top3'])/p['races'];w=100*(p['model_winner3']-p['ref_winner3'])/p['races'];rc=100*(a['scored_races']-r['scored_races'])/r['races'];hc=100*(a['scored_runners']-r['scored_runners'])/r['runners'];full=100*(a['wins']-r['wins'])/r['races'];ft=100*(a['top3']-r['top3'])/r['races'];fw=100*(a['winner3']-r['winner3'])/r['races'];valid=(delta==0 and full>0 if coverage_only else delta>0 and full>=0) and min(t,w,ft,fw)>=-.5 and rc>=-.5 and hc>=-1
 return {'model':m,'ref':b,'year':year,'common_races':p['races'],'common_runners':p['common_runners'],'delta_pp':delta,'top1_3rd_delta_pp':t,'winner_top3_delta_pp':w,'race_coverage_delta_pp':rc,'runner_coverage_delta_pp':hc,'full_win_delta_pp':full,'full_top1_3rd_delta_pp':ft,'full_winner_top3_delta_pp':fw,'qualifies':valid}
def write(name,d): (O/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(d,ensure_ascii=False,indent=2),flush=True)
if mode=='dev':
 a3=[inspect('a34dev',x,'hl60') for x in ('opp10','opp20','prize10','prize20')];a4=[inspect('a34dev',x,'hl60') for x in ('speed15','speed30','gap15','gap30')];one=inspect('a34dev','one_run','hl60',coverage_only=True)
 def best(rs):return max([x for x in rs if x['qualifies']],key=lambda x:x['delta_pp'],default=None)
 x,y=best(a3),best(a4);chosen=[z['model'] for z in (x,y) if z];order=sorted([z for z in (x,y) if z],key=lambda x:-x['delta_pp']);parent=order[0]['model'] if order else 'hl60';d={'models':chosen+(['one_run'] if one['qualifies'] else []),'A3':x,'A4':y,'development_results':a3+a4+[one],'combined':chosen if len(chosen)==2 else None,'strongest_isolated':parent,'one_run_qualified_dev':one['qualifies'],'validation_opened':False};write('a34_shortlist.json',d)
elif mode=='combine':
 d=json.loads((O/'a34_shortlist.json').read_text());r=inspect('a34combine','combined',d['strongest_isolated']);d['integration_dev']=r
 if r['qualifies']:d['models'].append('combined')
 else:d['combined']=None
 write('a34_shortlist_final.json',d); (O/'a34_shortlist.json').write_text((O/'a34_shortlist_final.json').read_text())
elif mode=='extension':
 d=json.loads((O/'a34_shortlist.json').read_text());r=inspect('a34finaldev','one_run_combined',d['one_run_parent'],coverage_only=True);d['extension_dev']=r
 if not r['qualifies']:d['models'].remove('one_run_combined')
 write('a34_shortlist_final.json',d);(O/'a34_shortlist.json').write_text((O/'a34_shortlist_final.json').read_text())
elif mode=='val':
 d=json.loads((O/'a34_shortlist.json').read_text());out=[]
 for m in d['models']:
  ref=d['one_run_parent'] if m=='one_run_combined' else d['strongest_isolated'] if m=='combined' else 'hl60';rs=[inspect('a34val',m,ref,y,coverage_only=m in ('one_run','one_run_combined')) for y in (0,2022,2023)];data=load(f'blocks_a34val_{m}_{ref}.csv');rng=np.random.default_rng(20261124);tot=np.zeros(2000);den=np.zeros(2000)
  for y in (2022,2023):
   sub=[x for x in data if x['race_date'].startswith(str(y))];n=np.array([x['n'] for x in sub]);v=np.array([x['delta'] for x in sub]);idx=rng.integers(0,len(n),size=(2000,len(n)));tot+=v[idx].sum(1);den+=n[idx].sum(1)
  ci=np.quantile(100*tot/den,[.025,.975]).tolist();out.append({'model':m,'ref':ref,'metrics':rs,'paired_ci95_pp':ci,'selected_gate':all(x['qualifies'] for x in rs)})
 accepted=[r for r in out if r['selected_gate'] and r['model'] not in ('one_run','combined','one_run_combined')];base='hl60';
 # validation selects only from frozen shortlist, prefer strongest isolated among validated; combined must improve that same isolated candidate
 if accepted:base=max(accepted,key=lambda z:z['metrics'][0]['delta_pp'])['model']
 if any(r['model']=='combined' and r['selected_gate'] and r['ref']==base for r in out):base='combined'
 # one-run extension tested only against hl60; never silently apply to integrated model
 one=next((r for r in out if r['model']=='one_run'),None);one_adopt=bool(one and one['selected_gate'] and base=='hl60'); ext=next((r for r in out if r['model']=='one_run_combined'),None);ext_adopt=bool(ext and ext['selected_gate'] and base==d['one_run_parent'])
 write('a34_decision.json',{'candidate':('one_run_combined' if ext_adopt else 'one_run' if one_adopt else base),'base':'hl60','comparisons':out,'one_run_adopted':one_adopt or ext_adopt,'one_run_note':'tested only against hl60; if an adjusted model selected, defer extension unless separately validated','confirmation_opened':False,'production_approved':False})
