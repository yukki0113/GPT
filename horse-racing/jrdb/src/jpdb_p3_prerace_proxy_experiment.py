#!/usr/bin/env python3
"""Research-only JPDB P3 pre-entry horse-history choice baseline.

Uses 2023-25 accepted annual KYI/Sed/BAC archive and 2026 PACI KYI/BAC +
selected SED. PRE-RACE AVAILABILITY IS UNATTESTED for annual final KYI and
2026 PACI versions. History outcomes strictly prior race-day (whole-day gate).
No target result odds, jockey ID, current-race result features, or horse ID as
predictors. Never authorize predictions / jockey skill / RaceNote integration.
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path
from dateutil.relativedelta import relativedelta
import duckdb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from jrdb_raw import Parser, read_fixed_records, ymd as parse_ymd

HIST_SHA={
 'kyi_2023':'d68afa2d37e2b4308df8c1897279e6cd38f27fc83d66324b4222e4cff44ed0ce',
 'kyi_2024':'21d0d47337daa7c78f08e6e79fc41ee15eebed05630a3ff3ec6bca4d190340df',
 'kyi_2025':'55fdcc9fd03c70f284b028fa85ef3c6b2882071c685639621061ba146c0fa10b',
 'sed_2023':'3cb2cb29f509209017d2b623a9fa5bdae18d217d4bd1b9cf82cbe7ae887e28ec',
 'sed_2024':'e18da9b6147c71973d5769f5ca859bd3b1e80b53773f9ed861c7b58941464fc8',
 'sed_2025':'6a7be1dc005833c9caaa20559ac3ad40af99bdc95a342b0e57d638ca979f8974',
 'bac_2023':'c17ee5ccb8f953f090cca186ee751d12fc75b97003199dad7c14b7fee70a5daa',
 'bac_2024':'ed1b831b9236eaa85a075b1f6fce792e7292ece830688b4bd28546885761b898',
 'bac_2025':'b26a364978143fbd6e9d30289db0eb85e9b33e9fe612759b23a85ffbb78a3bb9',
}
NUM=['horse_starts_365','horse_wins_365','horse_top3_365','horse_surface_starts_365',
     'horse_surface_top3_365','horse_days_since_last','horse_starts_3y',
     'race_distance_m','race_entries','frame_no','carried_weight_tenths','rotation_interval']
CAT=['race_surface','race_venue']
FIELDS=NUM+CAT


def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()


def accepted_files(root):
 result={}
 for key,digest in HIST_SHA.items():
  paths=[p for p in root.glob(digest+'.parquet*') if p.is_file()]
  if len(paths)!=1:raise ValueError(f'Expected exactly one {key}: {paths}')
  if sha(paths[0])!=digest:raise ValueError(f'{key} SHA mismatch')
  result[key]=paths[0]
 return result


def historical(root):
 assets=accepted_files(root)
 db=duckdb.connect(':memory:')
 def read(prefix,cols):
  paths=[str(assets[f'{prefix}_{y}']) for y in (2023,2024,2025)]
  return db.execute('SELECT '+cols+' FROM read_parquet(?, union_by_name=true)',[paths]).df()
 k=read('kyi','race_key_raw,horse_no,blood_registration_no,frame_no,carried_weight_tenths,rotation_interval')
 s=read('sed','race_key_raw,horse_no,race_date,blood_registration_no,jockey_code AS actual_jockey_code,abnormal_code,finish,field_size')
 b=read('bac','race_key_raw,race_date AS bac_race_date,surface_code AS race_surface,venue_code AS race_venue,TRY_CAST(distance_raw AS BIGINT) AS race_distance_m')
 if (len(k),len(s),len(b))!=(142737,142737,10365):raise ValueError('historical input population drift')
 if k.duplicated(['race_key_raw','horse_no']).any() or s.duplicated(['race_key_raw','horse_no']).any() or b.duplicated('race_key_raw').any():raise ValueError('historical duplicate keys')
 joined=s.merge(k,on=['race_key_raw','horse_no'],how='left',suffixes=('_sed','_kyi'),validate='one_to_one',indicator=True)
 if (joined['_merge']!='both').any() or (joined['blood_registration_no_sed']!=joined['blood_registration_no_kyi']).any():raise ValueError('hist horse mismatch')
 joined=joined.merge(b,on='race_key_raw',how='left',validate='many_to_one',indicator='bac_match')
 if (joined['bac_match']!='both').any() or (joined['bac_race_date']!=joined['race_date']).any():raise ValueError('hist BAC mismatch')
 return joined.drop(columns=['_merge','bac_match','bac_race_date','blood_registration_no_kyi']).rename(columns={'blood_registration_no_sed':'blood_registration_no'}),assets


def paci(root,sed_root):
 paci_files=sorted(root.glob('PACI26????.zip'))
 sed_files=sorted(sed_root.glob('SED26????.zip'))
 if len(paci_files)!=97 or len(sed_files)!=97:raise ValueError('2026 expected 97 selected PACI/SED files')
 if [p.name[4:10] for p in paci_files]!=[p.name[3:9] for p in sed_files]:raise ValueError('PACI/SED dates diverge')
 parser=Parser()
 entries=[];bacs=[];sed=[];source=[]
 for package,sed_path in zip(paci_files,sed_files):
  ymd=package.name[4:10]; date=dt.date(2000+int(ymd[:2]),int(ymd[2:4]),int(ymd[4:]))
  date_text=date.isoformat()
  with zipfile.ZipFile(package) as arc:
   if arc.testzip():raise ValueError('PACI bad CRC')
   for kind,dest in [('KYI',entries),('BAC',bacs)]:
    name=kind+ymd+'.txt'
    rows=read_fixed_records(arc,name,kind)
    if not rows:raise ValueError(f'empty or malformed {name}')
    for row in rows:
     data=getattr(parser,kind.lower())(row)
     if kind=='KYI':
      dest.append(dict(race_key_raw=data['race_key_raw'],horse_no=data['horse_no'],
                       blood_registration_no=data['blood_registration_no'],
                       frame_no=data['frame_no'],carried_weight_tenths=data['carried_weight_tenths'],
                       rotation_interval=data['rotation_interval']))
     else:
      if parse_ymd(data['date_raw'])!=date_text:raise ValueError('2026 BAC embedded date mismatch')
      dest.append(dict(race_key_raw=data['race_key_raw'],bac_race_date=date_text,
                      race_surface=data['surface_code'],race_venue=data['race_key_raw'][:2],
                      race_distance_m=data['distance_raw']))
  with zipfile.ZipFile(sed_path) as arc:
   if arc.testzip():raise ValueError('SED bad CRC')
   rows=read_fixed_records(arc,'SED'+ymd+'.txt','SED')
   if not rows:raise ValueError('2026 SED empty')
   for row in rows:
    data=parser.sed(row)
    if parse_ymd(data['date_raw'])!=date_text:raise ValueError('2026 SED embedded date mismatch')
    sed.append(dict(race_key_raw=data['race_key_raw'],horse_no=data['horse_no'],
                    race_date=date_text,blood_registration_no=data['blood_registration_no'],
                    actual_jockey_code=data['jockey_code'],abnormal_code=data['abnormal_code'],finish=data['finish'],field_size=data['field_size']))
  source.append({'date':date_text,'paci_sha256':sha(package),'sed_sha256':sha(sed_path)})
 k,s,b=map(pd.DataFrame,(entries,sed,bacs))
 if (len(k),len(s),len(b))!=(42185,42185,3066):raise ValueError(f'2026 input drift {len(k),len(s),len(b)}')
 if any(df.duplicated(keys).any() for df,keys in ((k,['race_key_raw','horse_no']),(s,['race_key_raw','horse_no']),(b,['race_key_raw']))):raise ValueError('2026 duplicate keys')
 joined=s.merge(k,on=['race_key_raw','horse_no'],how='left',suffixes=('_sed','_kyi'),validate='one_to_one',indicator=True)
 if (joined['_merge']!='both').any() or (joined['blood_registration_no_sed']!=joined['blood_registration_no_kyi']).any():raise ValueError('2026 horse ID mismatch')
 joined=joined.merge(b,on='race_key_raw',how='left',validate='many_to_one',indicator='bac_match')
 if (joined['bac_match']!='both').any() or (joined['bac_race_date']!=joined['race_date']).any():raise ValueError('2026 BAC mismatch')
 return joined.drop(columns=['_merge','bac_match','bac_race_date','blood_registration_no_kyi']).rename(columns={'blood_registration_no_sed':'blood_registration_no'}),source


def make_features(facts,expected_rows=184922):
 """No result from race_date D can enter ANY D feature, even another race."""
 facts=facts.sort_values(['race_date','race_key_raw','horse_no']).reset_index(drop=True)
 if expected_rows is not None and len(facts)!=expected_rows:raise ValueError('combined source count drift')
 if facts.duplicated(['race_key_raw','horse_no']).any():raise ValueError('runner duplicate')
 facts['race_entries']=facts.groupby('race_key_raw')['horse_no'].transform('size')
 eligible_race_keys=set(valid_cohort(facts)[0]['race_key_raw'].unique())
 history=collections.defaultdict(collections.deque)
 long_history=collections.defaultdict(collections.deque)
 features=[]
 for day,block in facts.groupby('race_date',sort=True):
  day_date=dt.date.fromisoformat(day)
  for row in block.itertuples(index=False):
   horse=row.blood_registration_no
   if not horse or len(horse)!=8:raise ValueError('horse key invalid')
   previous=history[horse]
   longer=long_history[horse]
   long_cutoff=max(dt.date(2023,1,1),day_date-relativedelta(years=3))
   while longer and longer[0][0]<long_cutoff:longer.popleft()
   while previous and (day_date-previous[0][0]).days>365:
    previous.popleft()
   feats=[
    len(previous),sum(x[1] for x in previous),sum(x[2] for x in previous),
    sum(x[3]==row.race_surface for x in previous),
    sum(x[2] for x in previous if x[3]==row.race_surface),
    (day_date-longer[-1][0]).days if longer else np.nan,
    len(longer),row.race_distance_m,row.race_entries,row.frame_no,
    row.carried_weight_tenths,row.rotation_interval,
    row.race_surface,row.race_venue,
   ]
   features.append(feats)
  # Commit all finishes ONLY once the whole race day has been featurized.
  for row in block.itertuples(index=False):
   if row.race_key_raw not in eligible_race_keys:continue
   if row.abnormal_code not in ('0','', '3'):
    continue
   valid_normal=(row.abnormal_code in ('0','') and pd.notna(row.finish)
                 and pd.notna(row.field_size) and 1<=row.finish<=row.field_size)
   if row.abnormal_code in ('0','') and not valid_normal:continue
   horse=row.blood_registration_no
   win=int(valid_normal and row.finish==1)
   top3=int(valid_normal and row.finish<=3)
   if row.race_surface in ('1','2'):
    event=(day_date,win,top3,row.race_surface)
    history[horse].append(event)
    long_history[horse].append(event)
 x=pd.DataFrame.from_records(features,columns=FIELDS)
 joined=pd.concat([facts.drop(columns=[c for c in FIELDS if c in facts.columns]),x],axis=1)
 if (joined['horse_days_since_last'].dropna()<=0).any():raise ValueError('Same-day leakage in horse history')
 return joined


def valid_cohort(df):
 """Like P3 v0.1, exclude whole race for ambiguous outcome conditions."""
 bad=df['abnormal_code'].isna() | ~df['abnormal_code'].isin(['0','','1','2','3'])
 normal=df['abnormal_code'].isin(['0',''])
 bad |= normal & (df['finish'].isna()|df['field_size'].isna()|(df['field_size']<1)|(df['finish']<1)|(df['finish']>df['field_size']))
 starts=df['abnormal_code'].isin(['0','','3'])
 wins=normal&(df['finish']==1)
 df=df.copy()
 df['bad_row']=bad
 df['actual_start']=starts
 df['win']=wins.astype('int8')
 df=df[df.race_surface.isin(['1','2'])].copy()
 grouped=df.groupby('race_key_raw').agg(bad=('bad_row','sum'),winners=('win','sum'),starts=('actual_start','sum'),date_n=('race_date','nunique'),surface_n=('race_surface','nunique'))
 allowed=grouped[(grouped.bad==0)&(grouped.winners==1)&(grouped.starts>=2)&(grouped.date_n==1)&(grouped.surface_n==1)].index
 df=df[df.race_key_raw.isin(allowed)&df.actual_start&(df.race_surface.isin(['1','2']))].copy()
 return df,{'eligible_races':len(allowed),'eligible_runners':len(df),
            'all_races':len(grouped),'rejected_races':len(grouped)-len(allowed)}


def model():
 transform=ColumnTransformer([
  ('num',Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=False)),('scale',StandardScaler())]),NUM),
  ('cat',OneHotEncoder(handle_unknown='ignore'),CAT),
 ])
 return Pipeline([('pre',transform),('model',LogisticRegression(C=1.0,max_iter=350,random_state=0))])


def evaluate(facts):
 eligible,audit=valid_cohort(facts)
 eligible['year']=eligible['race_date'].str[:4].astype(int)
 years=[]
 rider_effects=[]
 for yr in [2024,2025,2026]:
  train=eligible[eligible.year<yr]
  test=eligible[eligible.year==yr].copy()
  if train.empty or test.empty:raise ValueError('train/eval year missing')
  if train.race_date.max()>=test.race_date.min():raise ValueError('future training leak')
  estimator=model()
  estimator.fit(train[FIELDS],train.win)
  scores=estimator.predict_proba(test[FIELDS])[:,1]
  if (not np.isfinite(scores).all()) or (scores<=0).any() or (scores>=1).any():raise ValueError('probability invalid')
  test['raw_pred']=scores
  test['pred']=test.raw_pred/test.groupby('race_key_raw')['raw_pred'].transform('sum')
  test['uniform']=1/test.groupby('race_key_raw')['win'].transform('size')
  if (test.groupby('race_key_raw')['pred'].sum().sub(1).abs()>1e-10).any():raise ValueError('race conditional probability not sum 1')
  result={
   'year':yr,'train_rows':len(train),'train_to':train.race_date.max(),'eval_from':test.race_date.min(),
   'eval_to':test.race_date.max(),'eval_rows':len(test),'eval_races':test.race_key_raw.nunique(),
   'model_brier':round(float(np.mean(np.square(test.win-test.pred))),7),
   'uniform_brier':round(float(np.mean(np.square(test.win-test.uniform))),7),
   'model_race_nll':round(float(-np.log(test.loc[test.win==1,'pred']).mean()),7),
   'uniform_race_nll':round(float(-np.log(test.loc[test.win==1,'uniform']).mean()),7),
   'year_entry_kind':'FINAL_KYI_PROXY' if yr<=2025 else 'OBSERVED_PACI_VERSION_NOT_TIME_ATTESTED',
  }
  # Race-block bootstrap, resampling complete races rather than independent runners.
  test['model_se']=np.square(test.win-test.pred)
  test['uniform_se']=np.square(test.win-test.uniform)
  race_scores=test.groupby('race_key_raw').agg(n=('win','size'),model_se=('model_se','sum'),uniform_se=('uniform_se','sum'))
  array=race_scores[['n','model_se','uniform_se']].to_numpy(dtype=float)
  rng=np.random.default_rng(20261119+yr)
  delta=[]
  for _ in range(1000):
   sample=array[rng.integers(0,len(array),len(array))]
   delta.append(float((sample[:,2].sum()-sample[:,1].sum())/sample[:,0].sum()))
  result['brier_improvement_vs_uniform']=round(float(np.mean(np.square(test.win-test.uniform))-np.mean(np.square(test.win-test.pred))),7)
  result['race_bootstrap_brier_delta_ci95']=[round(float(v),7) for v in np.quantile(delta,[.025,.975])]
  result['race_block_bootstrap_iterations']=1000
  result['observed_wins']=int(test.win.sum())
  result['expected_wins_sum']=round(float(test.pred.sum()),6)
  result['runners_with_any_3y_history']=int((test.horse_starts_3y>0).sum())
  result['runners_with_no_3y_history']=int((test.horse_starts_3y==0).sum())
  years.append(result)
  effects=test.groupby(['actual_jockey_code','race_surface']).agg(
    rides=('win','size'), observed=('win','sum'), expected=('pred','sum'))
  for (code,surface),record in effects.iterrows():
   if record['rides']>=100:
    rider_effects.append((yr,code,surface,100*(record['observed']-record['expected'])/record['rides']))
 yearly_effect={(yr,code,surface):r for yr,code,surface,r in rider_effects}
 correlation=[]
 for earlier,later in [(2024,2025),(2025,2026)]:
  pairs=[(value,yearly_effect[(later,code,surface)])
         for (year,code,surface),value in yearly_effect.items()
         if year==earlier and (later,code,surface) in yearly_effect]
  xs=np.array(pairs,dtype=float)
  correlation.append({'from_year':earlier,'to_year':later,'rider_surface_pairs':len(xs),
       'pearson':round(float(np.corrcoef(xs[:,0],xs[:,1])[0,1]),6) if len(xs)>1 else None,
       'sign_reversed':int(sum(x*y<0 for x,y in pairs))})
 return years,audit,correlation


def run(root:Path,paci_root:Path,sed_root:Path):
 hist,assets=historical(root)
 current,source=paci(paci_root,sed_root)
 facts=make_features(pd.concat([hist,current],ignore_index=True))
 years,cohort,stability=evaluate(facts)
 return {'schema':'jpdb-p3-preentry-horse-history-proxy-v0.1','status':'RESEARCH_PROXY_ONLY',
   'source_rows':len(facts),'paci_sed_date_count':len(source),
   'hist_assets_sha256':{k:sha(v) for k,v in sorted(assets.items())},
   'paci_2026_manifest_sha256':hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
   'entry_version_status':'2023_2025_FINAL_KYI_PROXY_AND_2026_PACI_UNATTESTED',
   'source_prior_history_policy':'JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1',
   'strict_asof_certified':False,'pre_race_snapshot_time_attested':False,
   'model_features':FIELDS,'jockey_or_trainer_target_id_features':False,
   'target_final_odds_popularity_used':False,'label_source':'SED_RACE_RESULT_ONLY',
   'same_date_history_included':False,'year_fold_prior_only':True,'model_hyperparameter_selection':'NONE_FIXED_C1',
   'cohort':cohort,'walk_forward_years':years,'rider_residual_year_pair_stability':stability,
   'jockey_effect_estimation_allowed':False,'prediction_safe':False,
   'production_racenote_pwa_changed':False,'licensed_rows_in_report':False}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--paci-root',type=Path,required=True);ap.add_argument('--sed-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
 args=ap.parse_args();result=run(args.root,args.paci_root,args.sed_root)
 if args.output.exists():raise FileExistsError('Refusing to overwrite audit')
 args.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'status':result['status'],'cohort':result['cohort'],'walk_forward_years':result['walk_forward_years']}))