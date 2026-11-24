"""Package immutable run results, not raw inputs. All t1/t4 freeze pairs byte-identical; retain t4 plus recorded t1 hashes."""
import json,csv,hashlib,zipfile,os
from pathlib import Path
O=Path(__file__).parent;D=O.parent/'NAR_P8A_DELIVERY_20261124';D.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((O/'a34_decision.json').read_text())['candidate']=='one_run_combined'
assert (O/'a34_shortlist_frozen_before_validation.json').read_bytes()==(O/'a34_shortlist.json').read_bytes()
for f in O.glob('*_t4.parquet'):
 q=O/f.name.replace('_t4','_t1');assert q.exists() and sha(f)==sha(q),f.name
for f in ('feature_guard.json','a34_guard.json','isolation_dev.json','isolation_a34val.json','feature_manifest.json','a34_feature_manifest.json','pred_manifest_dev.json','pred_manifest_a2.json','pred_manifest_val.json','pred_manifest_a34dev.json','pred_manifest_a34combine.json','pred_manifest_a34finaldev.json','pred_manifest_a34val.json'):assert json.loads((O/f).read_text())['status']=='PASS',f
candidate={'model_id':'P8-Astar-r1','research_status':'FROZEN_FOR_P8B_NOT_PRODUCTION','source_generation':'nar_canonical_v1_201601_202512_g20260917','input_stage':'ENTRY','target_cutoff':'00:00 JST; history_date < target_date','base':{'window_days':365,'half_life_days':60,'min_runs':2,'p':'1-(finish_position-1)/(finish_count-1)','valid_history':'NORMAL/is_model_target, finish_count>1, valid rank, finish_time_seconds>0, unambiguous surrogate, prior dirt'},'opponent':{'weight':.2,'per_observation':'prior A0 of other ENTRY runners, >=3 known and >=50%; global prior 365d runner-weighted mean/std, min100; clip z [-3,3]/6','min_valid_history':2,'aggregate':'same half-life weighted mean of available deltas'},'speed':{'weight':.3,'reference':'same venue,distance,surface, historical date minus 365 days to exclusive historical date; one winner time per valid race; min100 races, robust median and 1.4826*MAD >0; clip((median-time)/scale,-3,3)/6+.5','min_valid_history':2,'aggregate':'same half-life weighted mean of available scores'},'score':'if n>=2: F + (0.2*O if n_opp>=2 else 0) + (0.3*(S-F) if n_speed>=2 else 0); if n==1: (p+1.5)/4; if n==0 or ambiguous: NULL','ranking':'round(score,12) desc, horse_no asc; store raw finite score','no_score_reason':['AMBIGUOUS_IDENTITY','INSUFFICIENT_HISTORY','UNKNOWN'],'class_direct':'HOLD_INFEASIBLE_MAPPING','prize_proxy':'NOT_SELECTED','gap_score':'NOT_SELECTED','confirmation':'LOCKED_2024_2025 until P8B config Freeze; 2026 excluded','selection_shortlist_sha256':sha(O/'a34_shortlist_frozen_before_validation.json'),'a1a2_decision_sha256':sha(O/'a1a2_decision.json'),'a34_decision_sha256':sha(O/'a34_decision.json'),'validation_prediction_manifest_sha256':sha(O/'pred_manifest_a34val.json'),'production_approved':False}
(O/'candidate_config.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n')
fd={'source_generation':candidate['source_generation'],'feature_manifest':'feature_manifest.json','a34_feature_manifest':'a34_feature_manifest.json','key':'runner_id','roster':'all ENTRY dirt flat targets, including NULL scores','dictionary':{'n_<window>':'valid historical observations in candidate window; min_<window>/max_<window> lineage dates; a0=180d mean; mean90/365; last3/5/8 <=365d; hl30/60/90 exponential date weights','med_/top_/var_/recent_/prior_':'A2 median/top2 mean/variance/recent first three/prior, counts recentn/priorn; hl uses 365d unweighted diagnostic window','cn/course/course_max':'180d same venue/distance/surface subset','jn/jp/pair_max':'180d jockey/trainer provisional pair; decimal sum stable, nonempty names','opp_delta/prize_delta/speed_score/gap_score':'A3/A4 history-level references in enriched_t4.parquet; target half-life60 aggregate with n/min/max_<family>; reference dates strictly before historical observation; gap within historical race only','ambiguous':'as-of entry identity guard, never future-derived repair','reason_<model>':'explicit scored/unknown/history insufficiency/ambiguous; r_<model> NULL if s_<model> NULL'},'lineage':'input_manifest pins 32 canonical assets; feature manifests pin per-year SHA; enriched reference stores max reference dates and support; history membership reproducible from keyed canonical rows, date/window and exact code. No source/label files available to score stage.'}
(O/'feature_dictionary.json').write_text(json.dumps(fd,ensure_ascii=False,indent=2)+'\n')
lg={'status':'PASS_SCOPED_P8A','feature_guard':json.loads((O/'feature_guard.json').read_text()),'a34_guard':json.loads((O/'a34_guard.json').read_text()),'references':json.loads((O/'reference_audit_t4.json').read_text()),'score_isolation':[json.loads((O/f).read_text()) for f in ('isolation_dev.json','isolation_a34val.json')],'all_thread_freezes_byte_identical':True,'strict_rank_parity':'PASS','notes':'Source as-of monthly final version, not exact historical snapshot. Score test no label file then poisoned label file (not an OS permission sandbox). No 2024/25 confirmation or 2026. No P8B guarantee.'};(O/'leakage_audit.json').write_text(json.dumps(lg,ensure_ascii=False,indent=2)+'\n')
# consolidate original metric/segment records while preserving original files
for prefix,out in [('metrics','metrics_by_fold.csv'),('segments','metrics_by_segment.csv')]:
 rows=[]
 for f in sorted(O.glob(prefix+'_*.csv')):
  if f.name==out:continue
  for r in csv.DictReader(open(f)):rows.append({'run':f.stem.removeprefix(prefix+'_'),**r})
 with open(O/out,'w') as h:w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
rows=[]
for p,key in [('a1_selection.json','results'),('shortlist.json','results'),('a34_shortlist_frozen_before_validation.json','development_results')]:
 d=json.loads((O/p).read_text());
 for r in d[key]:rows.append({'stage':p,'candidate':r['model'],'ref':r['ref'],'delta_pp':r['delta_pp'],'qualified':r['qualifies'],'selected':'SELECTED_FOR_SHORTLIST' if r['model'] in ('hl60','opp20','speed30','one_run') and r['qualifies'] else 'NOT_SELECTED','reason':'guard and development ranking'})
for r in json.loads((O/'a34_decision.json').read_text())['comparisons']:rows.append({'stage':'validation','candidate':r['model'],'ref':r['ref'],'delta_pp':r['metrics'][0]['delta_pp'],'qualified':r['selected_gate'],'selected':'FINAL_RESEARCH_CANDIDATE' if r['model']=='one_run_combined' else 'ISOLATED_EVIDENCE','reason':'both years and guard; one-run coverage separately'})
rows.append({'stage':'class_feasibility','candidate':'direct_class','ref':'hl60','delta_pp':'','qualified':False,'selected':'HOLD','reason':'local class token coverage insufficient; no verified venue/era mapping'})
with open(O/'decision_ledger.csv','w') as h:w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# detail partitions, retain exact t4 (t1 SHA same). ZIP stored since Parquet already ZSTD.
def makezip(out,paths):
 sums=''.join(f'{sha(p)}  {p.name}\n' for p in paths)
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
  for p in paths:z.write(p,p.name)
  z.writestr('SHA256SUMS',sums)
 with zipfile.ZipFile(out) as z:
  for p in paths:assert hashlib.sha256(z.read(p.name)).hexdigest()==sha(p)
 return {'name':out.name,'bytes':out.stat().st_size,'sha256':sha(out),'files':len(paths)}
parts=[]
for y in range(2017,2024):
 fs=sorted(O.glob(f'*_{y}_t4.parquet'));assert fs;parts.append(makezip(D/f'NAR_P8A_FREEZE_{y}.zip',fs))
parts.append(makezip(D/'NAR_P8A_REFERENCE.zip',[O/'enriched_t4.parquet']))
(O/'delivery_manifest.json').write_text(json.dumps({'status':'LOCAL_VERIFIED','details':parts,'note':'t1/t4 all same bytes; t1 duplicate not included. Drive private detailed archives; compact portable Library bundle.'},indent=2)+'\n')
# concise technical report with actual denominators and limitations
r='''# NAR P8A 実行・研究報告 — 2026-11-24

Status: RESEARCH_CANDIDATE_FROZEN / P8A.3 evaluation complete; persistence/readback required before CURRENT advances. Production not approved. 2024–25 locked, 2026 excluded.

## Input and execution
- 32 same-byte canonical assets (2016–23), P8.0 verified schema/key/row evidence reused; 2016 warm-up only. 1,067,484 ENTRY rows / 105,532 races total incl warm-up; 939,724 target rows 2017–23. 0 as-of ambiguous identity. Approved runtime DuckDB 2.0.1 / PyArrow 25.0.1 / NumPy 2.2.4; common check-deps success. No target post/control in roster or score. First ordered-aggregate attempt exceeded memory; rewritten ordered history list without changing candidate grid. All t1/t4 freezes byte-identical; all 7 boundaries prefix/injected tests zero; forbidden 7/7; A3/A4 reference prefix tests speed 1098/prize 728/opponent 14; score isolated no labels then poisoned labels unchanged. Monthly retrospective limitations remain.

## A1/A2
2017–21: 64,876 eligible races. A0 17,066/63,694; AC0 17,155; ACJ0 17,350; hl60 18,419/63,713. Mean90, last3 weaker; hl60 best qualifying development candidate. Median/top2 rejected (common delta -2.144/-14.207pp vs hl60). 2022–23 26,919 eligible: A0 6776/26314, hl60 7390/26319. Common 26314 races and 242439 runners: delta +1.4213pp CI [1.0579,1.7621], years +1.6678/+1.1780; coverage improved.

## A3/A4/A5
Class token feasibility: 56,156/77,697 historical normal valid races (2016–21); prize present all. Direct national class mapping HOLD. Prize and within-race gap positive in development but not shortlisted. Opp20 and speed30 selected on development, then combination +0.7393pp vs speed30 in same cohort. One-run shrink tested alone and with combination before A3/A4 validation shortlist freeze. Validation top1 wins / scored: hl60 7390/26319; opp20 7583/26319; speed30 7710/26319; combined 7911/26319; one_run_combined 8329/26391. Each incremental opponent/speed/combine improvement in both validation years; one-run extension common-runner ranking unchanged, full win delta +1.5528pp vs combined, positive both years. a34_decision.json legacy explanatory one_run_note is stale: actual comparisons include separately validated one_run_combined vs combined; see comparison records.

## Frozen P8-Astar-r1
Formula in candidate_config.json. n>=2: F=365d HL60 weighted normalized finish; add .2*O if >=2 valid opponent features; add .3*(S-F) if >=2 valid speed features. Missing correction=0. n=1: (p+1.5)/4. n=0/ambiguous unknown. No odds, target timing/going or PENDING features. Rank tie12. Same formula frozen for P8B, NOT final P9/P10 adoption.
- 2022–23 full eligible 26919; 26391 scored races, 261049/272409 scored runners. 8329 wins, 16808 top1 3rd-or-better, 16310 winner in top3. A0 26314 scored races, 242439 scored runners, 6776 wins, 15062 top1 top3, 13498 winner in top3. Common runner cohort 26314 races: final 7669 vs 6776 wins, +3.3936pp; paired race-day bootstrap 2000 reps seed20261124 CI [3.0093,3.7691]. Common years +476/13071 and +417/13243. Native full intent-to-predict +1553 wins/26919. Coverage expansion not same-cohort improvement; compare separately. Rank concordance native finishers (different support) A0 65.52%/65.82%, final 68.22%/68.63% by year. Segments descriptive only, no routing/tuning.
- No confirmation period opened. No ROI or production. Class direct mapping remains unresolved (P8B transition feasibility). P8B must add 10 post/race_result assets and parse audit, perform per-family gates; no automatic P9 promotion. Final confirmation after A/B candidate freeze only.

## Reproduction / delivery
Run scripts in this run directory using /tmp/narvenv/bin/python or approved matching venv. prepare.py uses /mnt/data cache from prior run; verify source hashes or reconstruct exact paths using input_manifest. features.py full 4/1, guard 4; freeze_guard features; score dev/a2/val 4/1; freeze_guard each; evaluate and select staged; reference.py 4/1; a34_features full 4/1, guard 4; a34_score/evaluate/freeze_guard/a34_select staged dev/combine/finaldev/val, frozen shortlist before val; isolation guards and final_diagnostics. See exact run configs and all decision/metric evidence. `delivery_manifest.json` references annual detailed archives and historical reference archive; compact evidence contains code, hashes and metrics. Raw/post source inputs are not committed or included in portable bundle. Save, read back and compare SHA prior to phase advancement.
'''
(O/'NAR_P8A_REPORT_20261124.md').write_text(r)
# compact evidence incl all non-parquet text/code, no raw/labels or logs duplicated unnecessarily
small=sorted(p for p in O.iterdir() if p.is_file() and p.suffix in ('.py','.json','.csv','.md','.sha256','.log'))
compact=makezip(D/'NAR_P8A_EVIDENCE_20261124.zip',small)
(D/'NAR_P8A_REPORT_20261124.md').write_bytes((O/'NAR_P8A_REPORT_20261124.md').read_bytes());(D/'candidate_config.json').write_bytes((O/'candidate_config.json').read_bytes());(D/'delivery_manifest.json').write_bytes((O/'delivery_manifest.json').read_bytes());
allfiles=sorted(p for p in D.iterdir() if p.name!='SHA256SUMS');(D/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in allfiles))
print(json.dumps({'parts':parts,'compact':compact,'report_sha256':sha(D/'NAR_P8A_REPORT_20261124.md'),'candidate_sha256':sha(D/'candidate_config.json')},indent=2))
