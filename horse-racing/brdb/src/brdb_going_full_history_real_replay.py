#!/usr/bin/env python3
"""Run validated BRDB v0.4 on public-read-only pinned Analysis + target PACI.

Private-by-design output: aggregate audit only. Never publish names, IDs, or
individual pedigree statistics in Actions logs or artifacts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

JRDB_SRC = Path(__file__).resolve().parents[2] / 'jrdb' / 'src'
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0,str(JRDB_SRC))
from jrdb_raw import Parser, iter_archive_records  # noqa: E402
from brdb_going_condition_compare import build, VERSION, SCOPE_LABELS  # noqa: E402
from brdb_going_signal_select import select as select_signals  # noqa: E402


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sha256(p):
    h=hashlib.sha256()
    with open(p,'rb') as src:
        for b in iter(lambda:src.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def paci_cohort(paci_path: Path, race_key: str, target_date: str):
    p=Parser();name='PACI'+target_date[2:4]+target_date[5:7]+target_date[8:]+'.zip'
    require(paci_path.name==name,'PACI file date mismatch')
    bac=[p.bac(x) for _,x in iter_archive_records(paci_path,'BAC') if x[:8].decode('ascii','strict')==race_key]
    require(len(bac)==1,'target BAC missing/duplicate')
    race=bac[0]
    require(race['date_raw']==target_date.replace('-',''),'target date mismatch')
    ukc={}
    for _,raw in iter_archive_records(paci_path,'UKC'):
        profile=p.ukc(raw)
        hid=profile['horse_id']
        require(hid not in ukc,'duplicate UKC identity')
        require(not profile['data_date'] or profile['data_date']<=target_date.replace('-',''),'post-target UKC profile')
        ukc[hid]=profile
    horses=[];numbers=set();ids=set()
    for _,raw in iter_archive_records(paci_path,'KYI'):
        if raw[:8].decode('ascii','strict')!=race_key:continue
        k=p.kyi(raw);number=k['horse_no'];hid=k['blood_registration_no']
        require(number not in numbers and hid not in ids,'duplicate race horse')
        require(hid in ukc,'horse pedigree missing from source PACI UKC')
        require(ukc[hid]['sire_name'],'sire missing')
        numbers.add(number);ids.add(hid)
        horses.append({'horse_id':hid,'horse_no':number,'pedigree':{'sire_name':ukc[hid]['sire_name']}})
    require(len(horses)==race['field_size'] and len(horses)>0,'target cohort incomplete')
    race_context={'race_key':race_key,'target_date':target_date,'surface_code':race['surface_code'],
                  'distance_m':int(race['distance_raw']),'venue_code':race_key[:2],
                  'course_code':race['course_code'],'field_size':int(race['field_size'])}
    common={'contract_version':'brdb-common-analysis-v0.1-candidate','release_status':'RESEARCH_ONLY',
            'race':race_context,'as_of_exclusive':target_date,
            'policy':{'prediction_safe':False,'production_authorized':False},'horses':horses}
    return common


def audit_comparison(result,paci_path:Path):
    selection=select_signals(result)
    rows=[]
    summary={}
    for scope in SCOPE_LABELS:
        obs=[]
        for h in result['horses']:
            a=next(s for s in h['scopes'] if s['scope_key']==scope)
            if a['scope_status']=='RESEARCH_OBSERVED':obs.append(a['observation'])
        observed=[o for o in obs if o['comparison_status']=='OBSERVED']
        low=sum(1 for o in observed if o['sample_status']=='LOW_SAMPLE')
        good=sum(1 for o in observed if o['difference_top3_pp']>0)
        equal=sum(1 for o in observed if o['difference_top3_pp']==0)
        worse=sum(1 for o in observed if o['difference_top3_pp']<0)
        assert len(obs)<=len(result['horses'])
        rows.append({'scope_key':scope,'horse_count':len(result['horses']),
                     'both_going_observed':len(observed),'missing_going_comparison':len(result['horses'])-len(observed),
                     'positive_delta':good,'equal_delta':equal,'negative_delta':worse,'low_sample':low,
                     'good_eligible_runs_sum_not_unique':sum(o['good']['starts'] for o in obs),
                     'non_good_eligible_runs_sum_not_unique':sum(o['non_good']['starts'] for o in obs),
                     'good_top3_sum_not_unique':sum(o['good']['top3'] for o in obs),
                     'non_good_top3_sum_not_unique':sum(o['non_good']['top3'] for o in obs)})
    require(sum(x['both_going_observed'] for x in rows)==result['total_scope_comparisons'],'comparison accounting mismatch')
    return {'audit_version':'brdb-going-full-history-real-replay-audit-v0.1',
            'status':'RESEARCH_ONLY','all_horses_matched':len(result['horses']),
            'race_key':result['race']['race_key'],'target_date':result['race']['target_date'],
            'analysis_contract':VERSION,'source':result['source'],
            'paci_sha256':sha256(paci_path),'cutoff_exclusive':result['as_of_exclusive'],
            'historical_profile_asof':result['historical_profile_asof'],
            'denominator':result['denominator'],
            'total_scope_comparisons':result['total_scope_comparisons'],
            'scope_summaries':rows,'no_horse_level_details_exported':True,
            'selection_contract':selection['contract_version'],'selection_summary':selection['summary'],
            'selection_no_horse_level_details_exported':True,
            'prediction_eligible':False,'display_eligible':False,'production_authorized':False}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True)
    ap.add_argument('--objects-root',required=True);ap.add_argument('--paci',required=True)
    ap.add_argument('--race-key',required=True);ap.add_argument('--target-date',required=True)
    ap.add_argument('--output',required=True);args=ap.parse_args()
    paci=Path(args.paci);common=paci_cohort(paci,args.race_key,args.target_date)
    result=build(common,args.manifest,args.objects_root)
    audit=audit_comparison(result,paci)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':'RESEARCH_ONLY','cohort_size':audit['all_horses_matched'],
                      'total_scope_comparisons':audit['total_scope_comparisons'],
                      'verified_partitions':audit['source']['verified_partitions']},ensure_ascii=False))

if __name__=='__main__': main()
