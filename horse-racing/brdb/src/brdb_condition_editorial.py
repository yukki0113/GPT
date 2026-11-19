"""Optional OFFLINE descriptive wording prototype, never a PWA/forecast adapter.

Builds only literal observed facts from v0.3 structured evidence. Research output
is quarantined; these strings must not be published as blood aptitude or tips.
"""
from __future__ import annotations
import json
from pathlib import Path

VERSION='brdb-condition-editorial-v0.1-research'


def draft(data):
    if data.get('contract_version')!='brdb-condition-discovery-v0.3-candidate' or data.get('release_status')!='RESEARCH_ONLY':
        raise ValueError('research contract required')
    p=data['policy']
    if any(p[k] is not False for k in ('prediction_safe','production_authorized','display_authorized','natural_language_review_authorized')):
        raise ValueError('cannot format production/forecast authorized data')
    horses=[]
    for h in data['horses']:
        sentences=[];refs=[]
        for label in ('FULL_SIBLING','MATERNAL_HALF_SIBLING','MATERNAL_AUNT_UNCLE'):
            for x in h['relatives_condition']['grouped_scopes']:
                if x['relation']==label and x['scope_key']=='ALL_VENUES_DISTANCE' and x['counts']['starts']:
                    n=x['counts']['starts']; t=x['counts']['top3']
                    sentences.append(f'母方近親（{label}）は同芝ダート・同距離で{n}走中{t}回が3着以内。血統関係の過去時点での完全再現は未検証。')
                    refs.append(f"relatives:{label}:ALL_VENUES_DISTANCE")
        going=h['going_observations']
        if going['status']=='RESEARCH_OBSERVED':
            values=[f"{s['going_class']}{s['counts']['starts']}走" for s in going['going_scopes'] if s['counts']['starts']]
            sentences.append('父産駒の馬場状態別観測（同芝ダート・全距離）：'+'、'.join(values)+'。今回の距離適性とは区別する。')
            refs.append('going:ALL_VENUES_SAME_SURFACE_ALL_DISTANCES')
        horses.append({'horse_no':h['horse_no'],'horse_id':h['horse_id'],
            'observation_sentences':sentences,'evidence_refs':refs,
            'review_paragraph':None,'betting_tips':[],
            'display_authorized':False})
    return {'contract_version':VERSION,'release_status':'RESEARCH_ONLY','horses':horses,
            'policy':{'production_authorized':False,'display_authorized':False}}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    a=p.parse_args()
    Path(a.output).write_text(json.dumps(draft(json.loads(Path(a.input).read_text(encoding='utf-8'))),
                            ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
