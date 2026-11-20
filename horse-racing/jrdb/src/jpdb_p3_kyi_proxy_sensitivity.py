#!/usr/bin/env python3
"""Private research diagnostic of preentry proxy v0.1 under KYI feature ablations.
No licensed row export. Do not claim historical KYI time attestation or pure jockey effect.
"""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import duckdb
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import jpdb_p3_prerace_proxy_experiment as base
from jrdb_raw import Parser,read_fixed_records

EXTRA=['idm','info_index','stable_index','training_index','base_win_odds']

def kyi_features_from_sources(root, paci_root):
    assets=base.accepted_files(root)
    db=duckdb.connect(':memory:')
    paths=[str(assets[f'kyi_{year}']) for year in (2023,2024,2025)]
    fields=','.join(EXTRA)
    historical=db.execute(f'SELECT race_key_raw,horse_no,{fields} FROM read_parquet(?,union_by_name=true)',[paths]).df()
    parser=Parser();rows=[]
    for src in sorted(paci_root.glob('PACI26????.zip')):
        with zipfile.ZipFile(src) as f:
            if f.testzip() is not None:raise ValueError('PACI zip CRC')
            for rec in read_fixed_records(f,'KYI'+src.stem[4:]+'.txt','KYI'):
                r=parser.kyi(rec)
                rows.append({k:r[k] for k in ['race_key_raw','horse_no',*EXTRA]})
    current=pd.DataFrame.from_records(rows)
    if len(historical)!=142737 or len(current)!=42185:raise ValueError('KYI source count drift')
    all_kyi=pd.concat([historical,current],ignore_index=True)
    if all_kyi.duplicated(['race_key_raw','horse_no']).any():raise ValueError('KYI duplicate')
    return all_kyi

def make_baseline(extra=[]):
    numeric=base.NUM+list(extra)
    return Pipeline([('pre',ColumnTransformer([
        ('num',Pipeline([('imputer',SimpleImputer(strategy='median')),('scale',StandardScaler())]),numeric),
        ('cat',OneHotEncoder(handle_unknown='ignore'),base.CAT),
    ])),('model',LogisticRegression(C=1.0,max_iter=350,random_state=0))])

def predict_year(df,features,yr):
    train=df[df.year<yr];test=df[df.year==yr].copy()
    clf=make_baseline(features)
    clf.fit(train[base.FIELDS+features],train.win)
    pred=clf.predict_proba(test[base.FIELDS+features])[:,1]
    test['prob_raw']=pred
    test['prob']=test.prob_raw/test.groupby('race_key_raw')['prob_raw'].transform('sum')
    if (test.groupby('race_key_raw')['prob'].sum().sub(1).abs()>1e-10).any():raise ValueError('prob not sum one')
    brier=np.mean((test.win-test.prob)**2)
    nl=-np.log(test.loc[test.win==1,'prob']).mean()
    return test, float(brier),float(nl)

def summarize_effect(predicts):
    eff={}
    for yr,df in predicts.items():
        gb=df.groupby(['actual_jockey_code','race_surface']).agg(n=('win','size'),o=('win','sum'),e=('prob','sum'))
        for (code,surf),row in gb.iterrows():
            if row['n']>=100:eff[(yr,code,surf)]=100*(row.o-row.e)/row.n
    pairs=[]
    for a,b in [(2024,2025),(2025,2026)]:
        xs=[(x,eff[(b,c,s)]) for (y,c,s),x in eff.items() if y==a and (b,c,s) in eff]
        x=np.array(xs,dtype=float)
        pairs.append({'years':f'{a}-{b}','n':len(xs),'corr':round(float(np.corrcoef(x[:,0],x[:,1])[0,1]),6) if len(xs)>1 and np.std(x[:,0])>0 and np.std(x[:,1])>0 else None,
            'sign_reversed':int((np.prod(x,axis=1)<0).sum())})
    return pairs

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--historical-root',type=Path,required=True)
    ap.add_argument('--paci-root',type=Path,required=True)
    ap.add_argument('--sed-root',type=Path,required=True)
    ap.add_argument('--expected-paci-manifest-sha256',required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists():raise FileExistsError('Refusing to overwrite prior audit')
    root=args.historical_root;paci=args.paci_root;sed=args.sed_root
    h,assets=base.historical(root)
    daily,src=base.paci(paci,sed)
    manifest=hashlib.sha256(json.dumps(src,sort_keys=True).encode()).hexdigest()
    if manifest!=args.expected_paci_manifest_sha256:raise ValueError('2026 selected asset bytes differ from accepted P3 manifest')
    full=pd.concat([h,daily],ignore_index=True)
    f=base.make_features(full)
    eligible,summary=base.valid_cohort(f)
    if summary!={'eligible_races':12934,'eligible_runners':178515,'all_races':12951,'rejected_races':17}:raise ValueError('P3 eligible cohort differs')
    extra=kyi_features_from_sources(root,paci)
    eligible=eligible.merge(extra,on=['race_key_raw','horse_no'],how='left',validate='one_to_one',indicator=True)
    if not (eligible['_merge']=='both').all():raise ValueError('missing KYI')
    eligible=eligible.drop(columns=['_merge'])
    eligible['year']=eligible.race_date.str[:4].astype(int)
    print('READY',len(eligible),manifest,flush=True)
    missing={}
    zeros={}
    for year,block in eligible.groupby('year'):
        missing[str(year)]={col:round(float(block[col].isna().mean()),6) for col in EXTRA}
        zeros[str(year)]={col:round(float((block[col]==0).mean()),6) for col in EXTRA}

    models={'history_only':[], 'history_plus_kyi_horse_assessment':['idm','info_index','training_index','stable_index'],
        'history_plus_kyi_base_odds':['base_win_odds'],
        'history_plus_kyi_assessment_and_base_odds':EXTRA}
    out={'schema':'jpdb-p3-kyi-proxy-sensitivity-v0.1','source_manifest_sha256':manifest,
        'status':'RESEARCH_SENSITIVITY_ONLY','eligible_rows':len(eligible),'eligible_races':summary['eligible_races'],
        'model_variants':{},'missingness_by_year':missing,'zero_or_sentinel_rate_by_year':zeros,'safe_to_use_as_prediction':False,'ability_certified':False}
    all_predictions={}
    for name,features in models.items():
        prints={};year_results=[]
        for year in (2024,2025,2026):
            test,brier,nll=predict_year(eligible,features,year)
            prints[year]=test
            year_results.append({'year':year,'races':int(test.race_key_raw.nunique()),'runners':len(test),
                'brier':round(brier,7),'race_nll':round(nll,7)})
            print(name,year,'brier',round(brier,7),flush=True)
        out['model_variants'][name]={'features':features,'years':year_results,'rider_surface_stability':summarize_effect(prints)}
        all_predictions[name]=prints
    out['paired_race_bootstrap_1000_vs_history_only']={}
    base_predictions=all_predictions['history_only']
    for name in models:
        if name=='history_only':continue
        comparisons=[]
        for year in (2024,2025,2026):
            original=base_predictions[year]
            candidate=all_predictions[name][year]
            if not np.array_equal(original[['race_key_raw','horse_no']].to_numpy(), candidate[['race_key_raw','horse_no']].to_numpy()):
                raise ValueError('Model prediction cohort not identically ordered')
            diff=(original.win-original.prob)**2-(candidate.win-candidate.prob)**2
            tmp=original[['race_key_raw']].copy();tmp['diff']=diff.to_numpy()
            grp=tmp.groupby('race_key_raw').agg(n=('diff','size'),d=('diff','sum'))
            vals=grp[['n','d']].to_numpy(dtype=float)
            random=np.random.default_rng(20261120+year)
            boots=[]
            for _ in range(1000):
                index=random.integers(0,len(vals),len(vals))
                draw=vals[index]
                boots.append(float(draw[:,1].sum()/draw[:,0].sum()))
            comparisons.append({'year':year,'mean_brier_improvement_vs_history_only':round(float(diff.mean()),7),
                'paired_race_bootstrap_95ci':[round(float(v),7) for v in np.quantile(boots,[0.025,0.975])],
                'races':len(grp),'bootstrap_iterations':1000})
        out['paired_race_bootstrap_1000_vs_history_only'][name]=comparisons
    out['historical_KYI_2023_2025_entry_version']='FINAL_KYI_PROXY'
    out['daily_PACI_2026_entry_version']='OBSERVED_PACI_VERSION_NOT_TIME_ATTESTED'
    out['KYI_indicators_may_encode_jockey_and_market_assessments']=True
    out['rider_residual_reduction_is_not_causal_identification']=True
    outfile=args.output
    outfile.parent.mkdir(parents=True,exist_ok=True)
    outfile.write_text(json.dumps(out,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
    print('RESULT',outfile,hashlib.sha256(outfile.read_bytes()).hexdigest(),flush=True)

if __name__=='__main__':main()