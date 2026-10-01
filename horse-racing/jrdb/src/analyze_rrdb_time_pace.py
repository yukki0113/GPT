#!/usr/bin/env python3
"""Predeclared September time/pace screening; no outcome-driven threshold search.

Usage: python analyze_rrdb_time_pace.py --ledger LEDGER --output-dir OUTPUT
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from jrdb_previous_start_research_ledger import sha,write_json

QUANTILES=[0,.5,.7,.8,.9,1]
QUANTILE_LABELS=['bottom50','50-70','70-80','80-90','top10']
ODDS_LABELS=['<5','5-9.9','10-29.9','30-99.9','>=100']


def metrics(df):
    n=len(df);hits=int(df.target_place_hit.sum())
    payout=int(df.target_place_payout_yen.sum())
    finish=df.target_finish.where(df.target_finish>0)
    maximum=int(df.target_place_payout_yen.max()) if n else 0
    return dict(n=n,place_hits=hits,place_hit_rate_pct=100*hits/n if n else None,
        stake_yen=100*n,place_payout_yen=payout,place_roi_pct=payout/n if n else None,
        win_hits=int(df.target_win_hit.sum()),win_roi_pct=df.target_win_payout_yen.sum()/n if n else None,
        top3_rate_pct=100*df.target_finish.between(1,3).mean() if n else None,
        top5_rate_pct=100*df.target_finish.between(1,5).mean() if n else None,
        finish_mean=finish.mean() if finish.notna().any() else None,
        popularity_mean=df.target_popularity.mean() if n else None,popularity_median=df.target_popularity.median() if n else None,
        win_odds_mean=df.target_win_odds.mean() if n else None,win_odds_median=df.target_win_odds.median() if n else None,
        max_place_payout_yen=maximum,largest_payout_share_pct=100*maximum/payout if payout else None,
        high_payout_hits=int((df.target_place_payout_yen>=1000).sum()),
        hit_days=int(df.loc[df.target_place_hit,'target_date'].nunique()),total_days=int(df.target_date.nunique()))


def quantile_band(series,cutoffs):
    # Equal values remain together; upper-bound ties go into the higher bucket.
    idx=np.searchsorted(cutoffs[1:-1],series.fillna(-np.inf),side='right')
    result=pd.Series(np.array(QUANTILE_LABELS)[idx],index=series.index,dtype='object')
    result[series.isna()]=None
    return result


def standardize_baseline(selection,parent,fields):
    """Indirect standardization over interpretable source/market strata."""
    observed=selection.groupby(fields,dropna=False,observed=True).size().rename('selected_n')
    baseline=parent.groupby(fields,dropna=False,observed=True).agg(
        hit=('target_place_hit','mean'),payout=('target_place_payout_yen','mean'),baseline_n=('target_place_hit','size'))
    joined=observed.to_frame().join(baseline)
    count=int(joined.selected_n.sum())
    if not count:return dict(n=0,expected_hit_rate_pct=None,expected_roi_pct=None,min_cell_n=None)
    return dict(n=count,expected_hit_rate_pct=float(100*(joined.selected_n*joined.hit).sum()/count),
                expected_roi_pct=float((joined.selected_n*joined.payout).sum()/count),min_cell_n=int(joined.baseline_n.min()))


def cluster_comparison(selection,parent,rng,replicates=1000):
    """Parent includes selection: paired bootstrap by target race, fixed thresholds."""
    keys=sorted(parent.target_race_key.unique())
    def matrix(df):
        return df.groupby('target_race_key').agg(n=('target_place_hit','size'),hits=('target_place_hit','sum'),
            payout=('target_place_payout_yen','sum')).reindex(keys,fill_value=0).to_numpy(float)
    s=matrix(selection);p=matrix(parent);deltas=[]
    if not len(selection):return {'valid_replicates':0}
    for _ in range(replicates):
        draw=rng.integers(0,len(keys),size=len(keys));a=s[draw].sum(axis=0);b=p[draw].sum(axis=0)
        if not a[0] or not b[0]:continue
        deltas.append((100*(a[1]/a[0]-b[1]/b[0]),a[2]/a[0]-b[2]/b[0]))
    arr=np.array(deltas)
    return dict(valid_replicates=len(arr),hit_lift_ci95_pp=np.quantile(arr[:,0],[.025,.975]).tolist(),
                roi_lift_ci95_pp=np.quantile(arr[:,1],[.025,.975]).tolist())


def analyze(ledger,out):
    out.mkdir(parents=True,exist_ok=True)
    base=ledger[ledger.target_started & ledger.target_flat & ledger.has_previous_rrdb_start.eq(1)].copy()
    base['source_finish_band']=pd.cut(base.previous_finish,[0,3,5,9,np.inf],labels=['1-3','4-5','6-9','10+'])
    base['source_distance_band']=pd.cut(base.previous_distance_m,[0,1400,1800,2200,np.inf],labels=['<=1400','1401-1800','1801-2200','>=2201'])
    base['odds_band']=pd.cut(base.target_win_odds,[0,5,10,30,100,np.inf],right=False,labels=ODDS_LABELS)
    base['popularity_band']=pd.cut(base.target_popularity,[0,3,6,9,np.inf],labels=['1-3','4-6','7-9','10+'])
    base['frontness_band']=pd.cut(base.corner4_frontness,[-1e-12,.2,.4,.6,.8,1],right=True,
            labels=['0-.2','>.2-.4','>.4-.6','>.6-.8','>.8-1'])
    cutoffs={}
    for field in ['performance_signal','front_pace_opposition_raw','rear_pace_opposition_raw']:
        cuts=base[field].quantile(QUANTILES).to_numpy()
        cutoffs[field]={str(q):float(v) for q,v in zip(QUANTILES,cuts)}
        base[field+'_band']=quantile_band(base[field],cuts)
    q80=cutoffs['performance_signal']['0.8'];q90=cutoffs['performance_signal']['0.9']
    time_ok=base.performance_signal.notna()
    pace_ok=base.pace_balance_percentile.notna() & base.corner4_frontness.notna()
    common=time_ok & pace_ok
    closing_ok=base.last3f_speed_percentile.notna()
    masks={'ALL_USABLE':pd.Series(True,index=base.index),'TIME_COMPLETE':time_ok,'PACE_COMPLETE':pace_ok,'TIME_PACE_COMMON':common,
        'PERF_TOP20':time_ok & base.performance_signal.ge(q80),'PERF_TOP10':time_ok & base.performance_signal.ge(q90),
        'FRONT_HIGH':pace_ok & base.pace_balance_percentile.ge(70) & base.corner4_frontness.ge(.6-1e-12),
        'FRONT_VERY_HIGH':pace_ok & base.pace_balance_percentile.ge(90) & base.corner4_frontness.ge(.6-1e-12),
        'FRONT_EXTREME':pace_ok & base.pace_balance_percentile.ge(90) & base.corner4_frontness.ge(.8-1e-12),
        'REAR_HIGH':pace_ok & base.pace_balance_percentile.le(30) & base.corner4_frontness.le(.4+1e-12),
        'REAR_VERY_HIGH':pace_ok & base.pace_balance_percentile.le(10) & base.corner4_frontness.le(.4+1e-12),
        'REAR_EXTREME':pace_ok & base.pace_balance_percentile.le(10) & base.corner4_frontness.le(.2+1e-12),
        'LAST3F80':closing_ok & base.last3f_speed_percentile.ge(80),'LAST3F90':closing_ok & base.last3f_speed_percentile.ge(90),
        'POSITION_RECOVERY':base.overall_position_gain.ge(.25),
        'POSITION_RECOVERY_LAST3F80':base.overall_position_gain.ge(.25) & base.last3f_speed_percentile.ge(80),
        'CURRENT_HV07':base.match_HV07.eq(True),'CURRENT_SA':base.current_next_watch_grade.notna()}
    for finish in [4,6]:
        masks[f'FINISH_GE{finish}']=base.previous_finish.ge(finish)
        for top in [20,10]:masks[f'FINISH_GE{finish}_PERF_TOP{top}']=masks[f'FINISH_GE{finish}'] & masks[f'PERF_TOP{top}']
    for side in ['FRONT','REAR']:
        for top in [20,10]:masks[f'{side}_HIGH_PERF_TOP{top}']=masks[f'{side}_HIGH'] & masks[f'PERF_TOP{top}']
    for level in [80,90]:masks[f'REAR_HIGH_LAST3F{level}']=masks['REAR_HIGH'] & masks[f'LAST3F{level}']
    masks['REAR_HIGH_LAST3F90_CLOSING_GAIN']=masks['REAR_HIGH_LAST3F90'] & base.closing_gain_sec.gt(0)
    masks['FROZEN_PERF_Q80']=base.performance_signal.ge(-0.09305555555555287)
    masks['FROZEN_PERF_Q90']=base.performance_signal.ge(0.16777149321267684)
    masks['FROZEN_FINISH_GE6_Q80']=masks['FROZEN_PERF_Q80'] & base.previous_finish.ge(6)
    rows=[]
    def add(section,signal,frame,stratum='ALL'):
        rows.append(dict(section=section,signal=signal,stratum=stratum,**metrics(frame)))
    for field in cutoffs:
        for label in QUANTILE_LABELS:
            selected=base[base[field+'_band']==label];add('quantile',field,selected,label)
            if field=='performance_signal':
                for band,g in selected.groupby('source_finish_band',observed=True):add('finish_time',label,g,str(band))
    for (pace,frontness),g in base[pace_ok].groupby(['pace_shape','frontness_band'],observed=True):add('pace_position',str(pace),g,str(frontness))
    # Every signal has market, daily, condition and defeated-horse views.
    for name,mask in masks.items():
        selected=base[mask];add('signal',name,selected)
        for field in ['odds_band','popularity_band','target_date','source_finish_band','previous_surface_code','source_distance_band','previous_declared_class_group']:
            for band,g in selected.groupby(field,observed=True,dropna=False):add(field,name,g,str(band))
    # Quantile market stratification preserves the full five-bin time table.
    for label in QUANTILE_LABELS:
        selected=base[base.performance_signal_band==label]
        for field in ['odds_band','popularity_band']:
            for band,g in selected.groupby(field,observed=True,dropna=False):add('time_quantile_'+field,label,g,str(band))
    # Matched market baselines against all usable runners in each odds band.
    baseline=base.groupby('odds_band',observed=True).agg(hit=('target_place_hit','mean'),payout=('target_place_payout_yen','mean'))
    for row in rows:
        if row['section']=='odds_band' and row['stratum'] in baseline.index:
            reference=baseline.loc[row['stratum']]
            row['odds_baseline_hit_rate_pct']=100*reference.hit;row['odds_baseline_roi_pct']=reference.payout
            row['odds_hit_lift_pp']=row['place_hit_rate_pct']-100*reference.hit
            row['odds_roi_lift_pp']=row['place_roi_pct']-reference.payout
    result=pd.DataFrame(rows)
    result.to_csv(out/'rrdb_202609_time_pace_analysis.csv',index=False,encoding='utf-8-sig')
    result.to_parquet(out/'rrdb_202609_time_pace_analysis.parquet',index=False,compression='zstd')
    # Direct parent, common completeness, matched baseline and parent-complement.
    comparison=[];rng=np.random.default_rng(20261001)
    pairs=[('PERF_TOP20','TIME_COMPLETE'),('PERF_TOP10','TIME_COMPLETE'),
           ('FINISH_GE6_PERF_TOP20','FINISH_GE6'),('FINISH_GE6_PERF_TOP10','FINISH_GE6'),
           ('FRONT_HIGH','PACE_COMPLETE'),('REAR_HIGH','PACE_COMPLETE'),
           ('POSITION_RECOVERY','ALL_USABLE'),('POSITION_RECOVERY_LAST3F80','LAST3F80')]
    pairs += [(f'{side}_HIGH_PERF_TOP{top}',f'PERF_TOP{top}') for side in ['FRONT','REAR'] for top in [20,10]]
    pairs += [(f'REAR_HIGH_LAST3F{level}',f'LAST3F{level}') for level in [80,90]]
    pairs += [('REAR_HIGH_LAST3F90_CLOSING_GAIN','REAR_HIGH_LAST3F90')]
    source_fields=['source_finish_band','previous_surface_code','source_distance_band','previous_declared_class_group']
    for child,parent_name in pairs:
        valid=pd.Series(True,index=base.index)
        if '_PERF_TOP' in child and ('FRONT_' in child or 'REAR_' in child):valid=common
        elif child.startswith('REAR_HIGH_LAST3F'):valid=pace_ok & closing_ok
        if child.endswith('CLOSING_GAIN'):valid &= base.closing_gain_sec.notna()
        parent=base[masks[parent_name] & valid];selected=base[masks[child] & valid]
        complement=parent[~parent.index.isin(selected.index)]
        sm=metrics(selected);pm=metrics(parent)
        source_match=standardize_baseline(selected,parent,source_fields)
        market_match=standardize_baseline(selected,parent,source_fields+['odds_band'])
        comparison.append(dict(signal=child,parent=parent_name,selected=sm,parent_metrics=pm,complement=metrics(complement),
            hit_lift_pp=sm['place_hit_rate_pct']-pm['place_hit_rate_pct'] if len(selected) else None,
            roi_lift_pp=sm['place_roi_pct']-pm['place_roi_pct'] if len(selected) else None,
            source_matched=source_match,source_odds_matched=market_match,
            uncertainty=cluster_comparison(selected,parent,rng)))
    write_json(out/'rrdb_202609_matched_comparisons.json',comparison)
    high=[]
    for name,mask in masks.items():
        for _,row in base[mask & base.target_place_payout_yen.ge(1000)].sort_values('target_place_payout_yen',ascending=False).iterrows():
            high.append(dict(signal=name,**{k:row[k] for k in ['target_date','target_race_key','target_horse_no','horse_id','horse_name',
                'previous_race_date','previous_finish','performance_signal','pace_balance_percentile','corner4_frontness','target_finish',
                'target_popularity','target_win_odds','target_place_payout_yen']}))
    pd.DataFrame(high).to_csv(out/'rrdb_202609_high_payout_examples.csv',index=False,encoding='utf-8-sig')
    # Save descriptive ranks/bands separately; the original feature ledger stays immutable.
    base.to_parquet(out/'rrdb_202609_analysis_population.parquet',index=False,compression='zstd')
    write_json(out/'rrdb_202609_analysis_audit.json',dict(status='PASS',version='time-pace-screen-v0.1',
        population_n=len(base),
        time_complete_n=int(time_ok.sum()),pace_complete_n=int(pace_ok.sum()),common_complete_n=int(common.sum()),
        quantiles=cutoffs,quantile_method='linear interpolation; >= cutoffs; ties kept together',
        quantiles_use_outcomes=False,quantiles_are_month_descriptive=True,threshold_search=False,
        frozen_rule_changes=False,formal_promotion=False,signal_count=len(masks),aggregate_rows=len(result),
        primary_front_definition='pace>=70 and corner4_frontness>=0.6',primary_rear_definition='pace<=30 and corner4_frontness<=0.4',
        position_recovery_definition='overall_position_gain>=0.25; with last3f>=80 additionally reported',
        bootstrap='1000 paired target-race cluster draws, seed=20261001; exploratory, no multiplicity correction',
        matched_baseline='Indirect standardization; parent includes child; sparse cells are reported, not causal adjustment',
        outputs_sha256={p.name:sha(p) for p in out.glob('rrdb_202609*') if p.suffix in ['.csv','.parquet','.json'] and p.name!='rrdb_202609_analysis_audit.json'}))
    print(result[result.section=='signal'][['signal','n','place_hits','place_hit_rate_pct','place_roi_pct']].to_string(index=False))
    return result,comparison


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();analyze(pd.read_parquet(a.ledger),a.output_dir)
