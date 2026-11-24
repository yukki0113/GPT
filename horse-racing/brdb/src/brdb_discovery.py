"""Deterministic, research-only discovery extraction from BRDB common analysis v0.1.

No inferred aptitude, scoring, race predictions, prose or public authorization.
"""
import argparse
import hashlib
import json
from pathlib import Path

VERSION = 'brdb-discovery-v0.1-candidate'
SIRE_SCOPES = ('VENUE_COURSE_EXACT','VENUE_DISTANCE','ALL_VENUES_DISTANCE')
TARGET_BMS = {'SHORT','MILE','MIDDLE','LONG'}


def _check(condition, reason):
    if not condition:
        raise ValueError(reason)


def discover(src):
    _check(src.get('contract_version')=='brdb-common-analysis-v0.1-candidate','invalid input contract')
    _check(src.get('release_status')=='RESEARCH_ONLY','research input required')
    policy=src.get('policy',{})
    _check(policy.get('prediction_safe') is False and policy.get('production_authorized') is False,'authorization mismatch')
    race=src['race']; field_size=race['field_size']
    _check(len(src['horses'])==field_size,'field mismatch')
    found=[];identities=set()
    for horse in src['horses']:
        ident=(horse['horse_no'],horse['horse_id'])
        _check(ident not in identities,'duplicate horse')
        _check(isinstance(ident[1],str) and len(ident[1])==8 and ident[1].isdigit(),'horse id')
        identities.add(ident)
        components=horse['components']; findings=[]
        refs=set()
        for name,comp in components.items():
            for s in comp['scopes']:
                _check(s['evidence_id'] not in refs,'duplicate evidence ID')
                refs.add(s['evidence_id'])
                n=s['counts']['starts']; w=s['counts']['wins']; t=s['counts']['top3']
                _check(0<=w<=t<=n,'invalid observed counts')
                _check(s['as_of_exclusive']==src['as_of_exclusive'],'as-of mismatch')
        sire=components['sire']
        _check(sire['availability'] in {'AVAILABLE','LOW_SAMPLE','NO_SAMPLE','SOURCE_UNAVAILABLE'},'invalid sire availability')
        for scope in SIRE_SCOPES:
            options=[s for s in sire['scopes'] if s['scope_key']==scope]
            _check(len(options)<=1,'ambiguous sire scope')
            if not options: continue
            s=options[0]; counts=s['counts']; rate=s['rates']['top3_rate']; baseline=s['baseline']
            if counts['starts']==0 or rate is None or baseline['top3_rate'] is None or baseline['starts']==0:continue
            delta=round((rate-baseline['top3_rate'])*100,2)
            findings.append({
                'finding_id':f'SIRE_BASELINE_{scope}',
                'kind':'SIRE_BASELINE_COMPARISON',
                'interpretation_status':'OBSERVATION_ONLY',
                'evidence_refs':[s['evidence_id']],
                'scope_key':scope,
                'metrics':{'starts':counts['starts'],'top3':counts['top3'],'top3_rate':rate,
                           'baseline_starts':baseline['starts'],'baseline_top3_rate':baseline['top3_rate'],
                           'delta_pp':delta},
                'signal':'ABOVE' if delta>0 else ('BELOW' if delta<0 else 'EQUAL'),
                'sample_status':s['sample_status'],
                'historical_asof_status':policy['historical_asof_status'],
                'display_eligible':False,
                'prediction_eligible':False})
        # Maternal grandsire: observed same-surface/target distance band only.
        bms=components['broodmare_sire']
        band=next((s['condition']['distance_band'] for s in sire['scopes'] if s['scope_key']=='ALL_VENUES_BAND'),None)
        surface=race['surface_code']
        if band in TARGET_BMS:
            matches=[s for s in bms['scopes'] if s['scope_key']==f'{surface}:{band}']
            _check(len(matches)<=1,'ambiguous BMS band')
            for s in matches:
                n=s['counts']['starts'];rate=s['rates']['top3_rate']
                if n==0 or rate is None:continue
                findings.append({
                    'finding_id':'BMS_TARGET_BAND', 'kind':'BMS_TARGET_BAND_OBSERVATION',
                    'interpretation_status':'OBSERVATION_ONLY','evidence_refs':[s['evidence_id']],
                    'scope_key':s['scope_key'],
                    'metrics':{'starts':n,'top3':s['counts']['top3'],'top3_rate':rate},
                    'signal':'OBSERVED','sample_status':s['sample_status'],
                    'historical_asof_status':policy['historical_asof_status'],
                    'display_eligible':False,'prediction_eligible':False})
        # Pairing and kinship are held as inputs for future validators, not promoted into findings.
        found.append({'horse_no':ident[0],'horse_id':ident[1],'findings':findings,
            'unavailable_discoveries':[
              {'kind':'GOING_COMPARISON','reason':'NO_VERIFIED_TRACK_CONDITION_SPLIT'},
              {'kind':'DISTANCE_COMPLEMENT','reason':'MATERNAL_OBSERVATION_NOT_CAUSAL_COMPLEMENT'},
              {'kind':'REGIONAL_ROOTS_APTITUDE','reason':'TAXONOMY_AND_CONDITION_VALIDATION_PENDING'},
              {'kind':'PAIRING_APTITUDE','reason':'HISTORICAL_ASOF_UNVERIFIED'},
              {'kind':'RELATIVES_APTITUDE','reason':'HISTORICAL_ASOF_UNVERIFIED'}]})
    return {'contract_version':VERSION,'release_status':'RESEARCH_ONLY',
       'race':race,'as_of_exclusive':src['as_of_exclusive'],
       'policy':{'prediction_safe':False,'production_authorized':False,
                 'display_authorized':False,'review_text_generated':False},
       'horses':found}


def run(inp,out):
    src=json.loads(Path(inp).read_text(encoding='utf-8'))
    obj=discover(src)
    Path(out).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return obj

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    r=run(args.input,args.output)
    print('PASS',len(r['horses']),'horses',sum(len(x['findings']) for x in r['horses']),'observations')
