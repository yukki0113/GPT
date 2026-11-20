#!/usr/bin/env python3
"""P3 strictly descriptive same-horse consecutive actual-rider switch diagnostic.

Reuses accepted P3 complete-race source/cohort and 2026 JRDB parser.
No causal, skill, or historical pre-race attribution; no individual rows exported.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import jpdb_p3_prerace_proxy_experiment as baseline

EXPECTED_2026_SELECTION='790213961912cc4bd81ac7932e17d8c54ccf20341220d1031504763cb2d635f1'
SCHEMA='jpdb-p3-same-horse-switch-matched-descriptive-v0.1'
MATCH_KEYS=['year','race_surface','distance_band','prior_top3','history_band','gap_band']

def classify(df:pd.DataFrame)->pd.DataFrame:
    """Stable coarse strata based only on source race conditions and *earlier* outcomes."""
    d=df.copy()
    d['year']=d.race_date.str[:4]
    d['distance_band']=pd.cut(pd.to_numeric(d.race_distance_m,errors="coerce"),bins=[0,1400,1800,2400,10000],labels=['SHORT','MILE','MIDDLE','LONG'],include_lowest=True).astype(str)
    d['history_band']=pd.cut(d.horse_starts_365,bins=[-1,0,2,1000],labels=['0','1-2','3+']).astype(str)
    d['gap_band']=pd.cut(d.days_since_prior,bins=[0,30,90,180],labels=['1-30','31-90','91-180'],include_lowest=True).astype(str)
    return d

def consecutive_pairs(facts:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    """Immediate observed previous start; exclude both noneligible/mixed-day starts.

    Pairs may share a horse over multiple races; this dependence is not removed
    by matching. All current and previous outcomes are post-race observations.
    """
    required={'race_date','race_key_raw','horse_no','blood_registration_no','actual_jockey_code','race_surface','race_distance_m','abnormal_code','finish','field_size'}
    if not required.issubset(facts.columns):raise ValueError(f'missing required columns: {required-set(facts)}')
    if facts.duplicated(['race_key_raw','horse_no']).any():raise ValueError('duplicate runner keys')
    if facts['blood_registration_no'].isna().any():raise ValueError('missing horse IDs')
    eligible,cohort=baseline.valid_cohort(facts)
    full=facts.copy()
    full['source_eligible']=(full.set_index(['race_key_raw','horse_no']).index.isin(eligible.set_index(['race_key_raw','horse_no']).index))
    full=full.sort_values(['blood_registration_no','race_date','race_key_raw','horse_no']).reset_index(drop=True)
    for col in ('race_date','actual_jockey_code','race_surface','race_distance_m','race_key_raw','source_eligible','finish','abnormal_code','field_size'):
        full['prev_'+col]=full.groupby('blood_registration_no',sort=False)[col].shift(1)
    full['days_since_prior']=(pd.to_datetime(full['race_date'])-pd.to_datetime(full['prev_race_date'])).dt.days
    prev_normal=full['prev_abnormal_code'].isin(['0','']) & full['prev_finish'].notna() & (full['prev_finish']>=1) & (full['prev_finish']<=full['prev_field_size'])
    full['prior_top3']=((full['prev_finish']<=3)&prev_normal).astype(int)
    # No horse-strength index, market odds, final popularity, or current result enters matching.
    valid=full.source_eligible & full.prev_source_eligible.eq(True) & prev_normal
    valid &= full.race_date.str[:4].astype(int).between(2024,2026)
    valid &= full.days_since_prior.between(1,180)
    valid &= full.race_surface.eq(full.prev_race_surface)
    valid &= (pd.to_numeric(full.race_distance_m,errors='coerce')-pd.to_numeric(full.prev_race_distance_m,errors='coerce')).abs().le(200)
    valid &= full.actual_jockey_code.notna()&full.prev_actual_jockey_code.notna()
    valid &= full.actual_jockey_code.ne('00000')&full.prev_actual_jockey_code.ne('00000')
    p=full.loc[valid].copy()
    p['switched']=p.actual_jockey_code.ne(p.prev_actual_jockey_code).astype(int)
    p['win']=(p.finish==1).astype(int)
    p['top3']=(p.finish<=3).astype(int)
    # Prior-race count computed from data strictly earlier than this day,
    # no same-day scores are allowed in matching.
    counts=eligible.sort_values(['blood_registration_no','race_date']).copy()
    counts['dt']=pd.to_datetime(counts.race_date)
    byhorse=counts.groupby('blood_registration_no',sort=False)['dt']
    counts['horse_starts_365']=byhorse.transform(lambda s: s.map(lambda dt: int(((s<dt)&(s>=dt-pd.Timedelta(days=365))).sum())))
    p=p.merge(counts[['race_key_raw','horse_no','horse_starts_365']],on=['race_key_raw','horse_no'],how='left',validate='one_to_one')
    if p.horse_starts_365.isna().any():raise ValueError('history count missing')
    p=classify(p)
    return p,cohort

def weighted_match(p:pd.DataFrame, min_per_arm:int=5)->dict:
    """Equal-weight by treated riders in each overlap stratum; not causal."""
    if min_per_arm<1:raise ValueError('min_per_arm must be positive')
    cells=p.groupby(MATCH_KEYS+['switched'],observed=True,dropna=False).agg(n=('win','size'),win=('win','mean'),top3=('top3','mean')).reset_index()
    pivot=cells.pivot(index=MATCH_KEYS,columns='switched',values=['n','win','top3'])
    if 0 not in pivot['n'].columns or 1 not in pivot['n'].columns:raise ValueError('one switch arm absent')
    n0=pivot['n'][0].fillna(0);n1=pivot['n'][1].fillna(0)
    overlap=pivot[(n0>=min_per_arm)&(n1>=min_per_arm)]
    covered1=int(overlap['n'][1].sum()); covered0=int(overlap['n'][0].sum())
    if not covered1 or not covered0:raise ValueError('no shared-strata support')
    wt=overlap['n'][1]
    return {
      'strata_with_overlap':int(len(overlap)),
      'matched_switch_rows':covered1,'matched_same_rider_rows':covered0,
      'all_switch_rows':int(p.switched.sum()),'all_same_rider_rows':int((1-p.switched).sum()),
      'switch_coverage':round(covered1/int(p.switched.sum()),6),
      'same_rider_coverage':round(covered0/int((1-p.switched).sum()),6),
      'descriptive_win_difference_pp':round(100*float(np.average(overlap['win'][1]-overlap['win'][0],weights=wt)),5),
      'descriptive_top3_difference_pp':round(100*float(np.average(overlap['top3'][1]-overlap['top3'][0],weights=wt)),5),
      'balance_not_certified':True,
      'potential_repeat_horse_clusters':True,
    }

def summarize(p:pd.DataFrame,cohort:dict)->dict:
    years=[]
    for year,sub in p.groupby('year',sort=True):
      stat={'year':int(year),'eligible_pairs':int(len(sub)),'observed_switch_pairs':int(sub.switched.sum()),
            'observed_same_rider_pairs':int((1-sub.switched).sum())}
      for arm,label in [(0,'same_rider'),(1,'switch')]:
        t=sub[sub.switched==arm]
        stat[label+'_win_rate']=round(float(t.win.mean()),6)
        stat[label+'_top3_rate']=round(float(t.top3.mean()),6)
      stat['coarsened_match']=weighted_match(sub,min_per_arm=5)
      years.append(stat)
    return {'schema':SCHEMA,'status':'DESCRIPTIVE_RESEARCH_ONLY','base_complete_race_cohort':cohort,
            'source_label':'SED_ACTUAL_JOCKEY_ONLY',
            'observed_immediate_previous_start':True,
            'historical_pre_race_version_attested':False,
            'jockey_switch_is_not_official_announcement':True,
            'model_or_jockey_ability_certified':False,
            'causal_jockey_effect_claim_allowed':False,
            'match_features':['year','surface','distance band','previous normal top3','prior 365d race count band','gap days band'],
            'selection_bias_and_confounding_remain':True,
            'licensed_individual_rows_exported':False,'years':years}

def run(root:Path,paci_root:Path,sed_root:Path)->dict:
    history,_=baseline.historical(root)
    current,source=baseline.paci(paci_root,sed_root)
    current_sha=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    if current_sha!=EXPECTED_2026_SELECTION:raise ValueError('PACI/SED selection differs from approved fixed P3 snapshot')
    facts=pd.concat([history,current],ignore_index=True)
    if len(facts)!=184922:raise ValueError('input drift')
    p,cohort=consecutive_pairs(facts)
    report=summarize(p,cohort)
    report.update({'source_rows':int(len(facts)),'source_2026_paci_sed_selection_sha256':current_sha,
                  'history_source_sha256':baseline.HIST_SHA})
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for name in ('root','paci-root','sed-root','output'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args()
    result=run(a.root,a.paci_root,a.sed_root)
    if a.output.exists():raise FileExistsError('Refusing overwrite of audit')
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':result['status'],'years':result['years']},ensure_ascii=False))