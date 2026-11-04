#!/usr/bin/env python3
"""P1-5: research-only outcome completeness uncertainty on a SHA-pinned 2026 cohort.

No blood-lineage prediction, bet score, model selection, or causal inference.
Resampling is one cluster dimension AT A TIME, not joint multiway inference.
Private rows are never copied to public audit outputs.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random
import re

VERSION = "brdb-m6-p1-5-dependence-diagnostics-v0.1"
EXPECTED_DATES = (
    '20260919','20260920','20260926','20260927','20261003','20261004',
    '20261010','20261011','20261012','20261017','20261018','20261024',
    '20261031','20261101',
)
SCHEMA = ('date','race_key','horse_no','horse_id','finish','abnormal_code',
          'actual_starter','normal_finisher','paci_sha256','sed_sha256')
CODES = {'0','1','2','3','4','5','6'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()

def pct_point(values, quantile):
    if not values: raise ValueError('empty quantile values')
    j=(len(values)-1)*quantile
    lower=int(j)
    frac=j-lower
    return values[lower]*(1-frac)+values[min(lower+1,len(values)-1)]*frac

def data_rows(path):
    with Path(path).open(newline='',encoding='utf-8') as f:
        rd=csv.DictReader(f)
        if tuple(rd.fieldnames or ()) != SCHEMA:
            raise ValueError('private outcome CSV schema differs')
        return list(rd)

def validate(rows, accepted):
    if not rows: raise ValueError('empty cohort')
    expected=int(accepted['race_declarations'])
    if len(rows)!=expected or accepted.get('status')!='PASS_RESEARCH_ONLY':
        raise ValueError('not the accepted P1-4d cohort')
    if accepted.get('prediction_safe') is not False:
        raise ValueError('accepted P1-4d prediction boundary missing')
    keys=set();horses=set();races=set();dates=Counter();codes=Counter()
    for r in rows:
        if r['date'] not in EXPECTED_DATES or not re.fullmatch(r'[A-Za-z0-9]{8}',r['race_key']):
            raise ValueError('invalid date/race key')
        if not re.fullmatch(r'[0-9]{8}',r['horse_id']) or not r['horse_no'].isdigit() or int(r['horse_no'])<1:
            raise ValueError('invalid horse identity')
        key=(r['date'],r['race_key'],r['horse_no'],r['horse_id'])
        if key in keys:raise ValueError('duplicate identity key')
        keys.add(key);horses.add(r['horse_id']);races.add((r['date'],r['race_key']))
        if r['abnormal_code'] not in CODES or r['actual_starter'] not in ('True','False') or r['normal_finisher'] not in ('True','False'):
            raise ValueError('bad status code or flag')
        code=r['abnormal_code']
        if (r['actual_starter']=='True') != (code not in ('1','2')) or (r['normal_finisher']=='True') != (code=='0'):
            raise ValueError('status classification inconsistent')
        if code=='0' and (not r['finish'].isdigit() or int(r['finish'])<1):
            raise ValueError('normal outcome without finish')
        if not all(re.fullmatch(r'[a-f0-9]{64}',r[col]) for col in ('paci_sha256','sed_sha256')):
            raise ValueError('missing pinned source SHA')
        dates[r['date']]+=1;codes[code]+=1
    if tuple(sorted(dates))!=EXPECTED_DATES:
        raise ValueError('incomplete date coverage')
    checks={'race_count':len(races),'unique_horses':len(horses),
            'actual_starters':sum(c for k,c in codes.items() if k not in ('1','2')),
            'normal_finishers':codes['0']}
    for key,count in checks.items():
        if accepted.get(key)!=count:raise ValueError(f'accepted audit mismatch: {key}')
    if dict(codes)!=accepted.get('abnormal_codes'):
        raise ValueError('SED status audit mismatch')
    for day in accepted.get('daily',[]):
        if dates.get(day.get('date'))!=day.get('declarations'):
            raise ValueError('accepted daily row count mismatch')
    if len(accepted.get('daily',[]))!=14:raise ValueError('accepted daily coverage mismatch')
    return codes,races,horses,dates

def bootstrap_clusters(rows, *, metric, dimension, repetitions, seed):
    """Resample independent candidate groups, one cluster dimension at a time."""
    by_cluster=defaultdict(lambda:[0,0])
    for r in rows:
        if dimension=='date': group=r['date']
        elif dimension=='race': group=(r['date'],r['race_key'])
        elif dimension=='horse': group=r['horse_id']
        else:raise ValueError('unsupported clustering dimension')
        status=r['abnormal_code']
        if metric=='starter_rate':
            denominator=1;outcome=int(status not in ('1','2'))
        elif metric=='dnf_among_starters':
            denominator=int(status not in ('1','2'));outcome=int(status=='3')
        else:raise ValueError('unsupported metric')
        by_cluster[group][0]+=outcome
        by_cluster[group][1]+=denominator
    clusters=list(by_cluster.values())
    n=len(clusters)
    observed=sum(v[0] for v in clusters)/sum(v[1] for v in clusters)
    rng=random.Random(seed)
    draws=[];invalid=0
    for _ in range(repetitions):
        numerator=denominator=0
        for _ in range(n):
            v=clusters[rng.randrange(n)]
            numerator+=v[0];denominator+=v[1]
        if denominator:draws.append(numerator/denominator)
        else:invalid+=1
    if len(draws)<0.99*repetitions:
        raise ValueError('insufficient valid bootstrap draws')
    draws.sort()
    return {'n_clusters':n,'point_estimate':observed,'bootstrap_valid':len(draws),
            'bootstrap_invalid':invalid,'ci_95_percentile':[pct_point(draws,.025),pct_point(draws,.975)],
            'groups_with_events':sum(x[0]>0 for x in clusters) if metric=='dnf_among_starters' else None}

def run(cohort, accepted_path, output, *, cohort_sha, accepted_sha, repetitions=2000, seed=260914):
    cohort,accepted_path,output=map(Path,(cohort,accepted_path,output))
    if not isinstance(seed,int) or repetitions<200 or repetitions>20000:
        raise ValueError('invalid deterministic bootstrap config')
    if digest(cohort)!=cohort_sha or digest(accepted_path)!=accepted_sha:
        raise ValueError('SHA-pinned source mismatch')
    accepted=json.loads(accepted_path.read_text(encoding='utf-8'))
    rows=data_rows(cohort)
    codes,races,horses,dates=validate(rows,accepted)
    starter_n=accepted['actual_starters']
    dnf_n=codes['3']
    rates={
      'starter_rate':{'numerator':starter_n,'denominator':len(rows)},
      'dnf_among_starters':{'numerator':dnf_n,'denominator':starter_n},
    }
    for mi, (metric,item) in enumerate(rates.items()):
        item['point_estimate']=item['numerator']/item['denominator']
        item['cluster_bootstrap']={}
        for ci,dimension in enumerate(('date','race','horse')):
            item['cluster_bootstrap'][dimension]=bootstrap_clusters(
                rows,metric=metric,dimension=dimension,repetitions=repetitions,seed=seed+100*mi+ci)
    per_date=[]
    for day in EXPECTED_DATES:
        cohort_day=[r for r in rows if r['date']==day]
        starts=sum(r['actual_starter']=='True' for r in cohort_day)
        dnfs=sum(r['abnormal_code']=='3' for r in cohort_day)
        per_date.append({'date':day,'declarations':len(cohort_day),'starters':starts,'dnfs':dnfs,
          'dnf_rate_among_starters':dnfs/starts if starts else None})
    repeated=Counter(r['horse_id'] for r in rows)
    out={'version':VERSION,'status':'PASS_DESCRIPTIVE_UNCERTAINTY_ONLY',
         'prediction_safe':False,'forecasting_promotion':'HOLD',
         'asof_release_proven':False,'historical_2016_2025_asof_proven':0,
         'source_cohort_sha256':cohort_sha,'source_aggregate_audit_sha256':accepted_sha,
         'scope':{'dates':len(dates),'races':len(races),'distinct_horses':len(horses),
                  'declarations':len(rows),'starters':starter_n,'normal_finishers':codes['0'],
                  'horses_with_repeated_declarations':sum(c>1 for c in repeated.values()),
                  'extra_repeated_declarations':sum(c-1 for c in repeated.values())},
         'bootstrap':{'replications':repetitions,'seed':seed,
           'method':'cluster pairs percentile bootstrap, one clustering dimension at a time',
           'dimensions':['date','race','horse'],
           'warning':'14 dates only; separate one-way cluster intervals do not provide simultaneous horse/race/date multiway coverage, and 13 DNF are sparse.'},
         'metrics':rates,'daily':per_date,
         'limits':['Data usability and outcome completeness only; no blood-stratum association or future predictive value tested.',
                   'Original pre-race JRDB release-time and SHA attestation unavailable.',
                   'No training/testing split or multi-year validation is possible from 14 days.',
                   'No rows, horse IDs, or race keys are written to the aggregate JSON.']}
    output.mkdir(parents=True,exist_ok=True)
    (output/'p1_5_dependence_aggregate.json').write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--cohort',type=Path,required=True);p.add_argument('--cohort-sha256',required=True)
    p.add_argument('--accepted-audit',type=Path,required=True);p.add_argument('--accepted-audit-sha256',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--repetitions',type=int,default=2000)
    p.add_argument('--seed',type=int,default=260914)
    a=p.parse_args()
    v=run(a.cohort,a.accepted_audit,a.out,cohort_sha=a.cohort_sha256,
          accepted_sha=a.accepted_audit_sha256,repetitions=a.repetitions,seed=a.seed)
    print(json.dumps({'status':v['status'],'scope':v['scope'],'metrics':{
     k: {'point_estimate':q['point_estimate'],'date_ci':q['cluster_bootstrap']['date']['ci_95_percentile']}
      for k,q in v['metrics'].items()}},ensure_ascii=False,sort_keys=True))
