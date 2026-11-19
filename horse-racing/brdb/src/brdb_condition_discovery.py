"""Research-only M7 relatives/going condition observations and deterministic wording.

A v0.3 sidecar: no mutation of v0.1 common contract or v0.2 cross contract.
Going rows MUST be a separately audited SED-derived, race-date-scoped source;
no unprovided going is interpreted as 良. Output is never consumer authorized.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

VERSION = 'brdb-condition-discovery-v0.3-candidate'
SCOPES = ('VENUE_COURSE_EXACT','VENUE_DISTANCE','VENUE_BAND',
          'ALL_VENUES_DISTANCE','ALL_VENUES_BAND')
GOING = ('良','稍重','重','不良')
RELATIONS = ('FULL_SIBLING','MATERNAL_HALF_SIBLING','MATERNAL_AUNT_UNCLE',
             'SAME_DAM_SAME_SIRE_NAME_UNVERIFIED')


def require(ok,why):
    if not ok: raise ValueError(why)


def _index(rows):
    result={}; horses=set(); numbers=set()
    for h in rows:
        key=(h['horse_no'],h['horse_id'])
        require(isinstance(key[0],int) and key[0]>0 and
                isinstance(key[1],str) and len(key[1])==8 and key[1].isdigit(), 'invalid horse identity')
        require(key not in result and key[1] not in horses and key[0] not in numbers,'duplicate horse identity')
        result[key]=h;horses.add(key[1]);numbers.add(key[0])
    return result


def _stat(s):
    n,w,t = s['starts'],s['wins'],s['top3']
    require(all(type(z) is int for z in (n,w,t)) and 0<=w<=t<=n,'invalid relative/going counts')
    require((s['top3_rate'] is None if n==0 else
             s['top3_rate'] is not None and abs(s['top3_rate']-t/n)<0.00011), 'relative/going rate mismatch')
    return dict(starts=n,wins=w,top3=t,top3_rate=s['top3_rate'])


def _relatives(h, race):
    rels=h['relatives']; seen=set(); by_scope=defaultdict(list); individual=[]
    for r in rels:
        rid=r['horse_id']; relationship=r['relationship']
        require(isinstance(rid,str) and len(rid)==8 and rid.isdigit(),'relative id invalid')
        require(rid not in seen,'duplicate relative id')
        seen.add(rid)
        require(relationship in RELATIONS,'unknown kinship')
        require(set(r['scope_stats'])==set(SCOPES),'relative scope set mismatch')
        for scope in SCOPES:
            s=_stat(r['scope_stats'][scope]); by_scope[(scope,relationship)].append((rid,s))
        individual.append({'relative_horse_id':rid,'relative_name':r.get('horse_name'),
            'relation':relationship,
            'scope_observations':[
                {'scope_key':scope,'counts':_stat(r['scope_stats'][scope])}
                for scope in SCOPES],
            'historical_asof_status':'AS_OF_UNVERIFIED'})
    summaries=[]
    for scope in SCOPES:
        for relationship in RELATIONS:
            sample=by_scope[(scope,relationship)]
            if not sample: continue
            n=sum(s['starts'] for _,s in sample)
            w=sum(s['wins'] for _,s in sample)
            t=sum(s['top3'] for _,s in sample)
            summaries.append({'scope_key':scope,'relation':relationship,
                'relative_count':len(sample),
                'relatives_with_starts':sum(s['starts']>0 for _,s in sample),
                'counts':{'starts':n,'wins':w,'top3':t,'top3_rate':t/n if n else None},
                'source':'M7_RELATIVES_DETAIL',
                'interpretation_status':'OBSERVATION_ONLY',
                'historical_asof_status':'AS_OF_UNVERIFIED',
                'prediction_eligible':False,'display_eligible':False})
    # Scoped results are overlapping views of history, and cannot be added across scopes.
    pending=[] if rels else [{'kind':'RELATIVES_CONDITION','reason':'NO_CONFIRMED_RELATIVES'}]
    return {'status':h['status'],'individual':individual,'grouped_scopes':summaries,
        'pending':pending,'overlapping_scopes':True,'historical_asof_status':'AS_OF_UNVERIFIED'}


def _check_going(raw, race, asof):
    require(raw['contract_version']=='brdb-going-observation-input-v0.1-candidate','going contract')
    require(raw['research_only'] is True and raw['prediction_safe'] is False, 'going authorization')
    require(raw['source']['reader']=='JRDB_SED_COMMON_READER' and
            raw['source']['historical_parent_mapping_status'] in ('AS_OF_UNVERIFIED','VERIFIED'), 'going provenance')
    require(raw['race']==race and raw['as_of_exclusive']==asof,'going context mismatch')
    require(raw['source']['source_sha256'] and len(raw['source']['source_sha256'])==64 and
            all(c in '0123456789abcdef' for c in raw['source']['source_sha256']),'going source digest')
    unique=set(); by_sire=defaultdict(lambda:defaultdict(lambda:[0,0,0]))
    for row in raw['records']:
        require(row['race_date']<asof,'post-target leakage')
        require(row['surface_code']==race['surface_code'],'going surface mismatch')
        require(row['going_class'] in GOING,'unknown going class')
        require(isinstance(row['sire_name'],str) and row['sire_name'].strip(),'sire name unavailable')
        k=(row['race_key'],row['horse_no'],row['horse_id'])
        require(k not in unique,'duplicate historical start')
        unique.add(k)
        require(isinstance(row['horse_id'],str) and len(row['horse_id'])==8 and row['horse_id'].isdigit(),'historical horse id')
        require(type(row['horse_no']) is int and row['horse_no']>0,'historical horse no')
        require(row['outcome'] in ('FINISHED','EXCLUDED'),'invalid result status')
        finish=row['finish_position']
        if row['outcome']=='FINISHED':
            require(type(finish) is int and finish>=1,'missing finish')
            stats=by_sire[row['sire_name']][row['going_class']]
            stats[0]+=1;stats[1]+=int(finish==1);stats[2]+=int(finish<=3)
        else:
            require(finish is None,'excluded result with finish')
    return by_sire


def _going(h,going_index, context):
    if going_index is None:
        return {'status':'SOURCE_UNAVAILABLE','going_scopes':[],
                'pending':[{'kind':'GOING_COMPARISON','reason':'NO_CANONICAL_SED_GOING_HISTORY_INPUT'}]}
    name=h['pedigree']['sire_name']
    counts=going_index.get(name,{})
    scopes=[]
    for going in GOING:
        n,w,t=counts.get(going,[0,0,0]); scopes.append({
            'going_class':going, 'scope':'ALL_VENUES_SAME_SURFACE_ALL_DISTANCES',
            'counts':{'starts':n,'wins':w,'top3':t,'top3_rate':t/n if n else None},
            'historical_parent_mapping_status':context,
            'interpretation_status':'OBSERVATION_ONLY',
            'display_eligible':False,'prediction_eligible':False})
    return {'status':'RESEARCH_OBSERVED' if sum(s['counts']['starts'] for s in scopes) else 'NO_SAMPLE',
            'going_scopes':scopes,
            'pending':[{'kind':'GOING_TARGET_DISTANCE','reason':'HISTORY_NOT_DISTANCE_STRATIFIED'},
                       {'kind':'GOING_APTITUDE','reason':'UNCONTROLLED_DESCRIPTIVE_COMPARISON'}]}



def build(common,detail,cross,going_input=None,detail_raw_sha256=None,target_going=None):
    require(common['contract_version']=='brdb-common-analysis-v0.1-candidate','common contract')
    require(cross['contract_version']=='brdb-cross-discovery-v0.2-candidate','cross contract')
    require(detail['contract_version']=='brdb-m7-relatives-detail-v0.1-candidate','detail contract')
    require(common['release_status']==cross['release_status']=='RESEARCH_ONLY','research-only inputs')
    require(detail['research_only'] is True and detail['prediction_safe'] is False and
            detail['historical_asof_status']=='AS_OF_UNVERIFIED','detail historical policy')
    require(common['policy']['production_authorized'] is False and
            common['policy']['prediction_safe'] is False and
            cross['policy']['display_authorized'] is False and
            cross['policy']['prediction_safe'] is False,'authorization mismatch')
    race=common['race'];asof=common['as_of_exclusive']
    require(target_going is None or target_going in GOING,'invalid target assumed going')
    require(asof==race['target_date']==cross['as_of_exclusive']==
            detail['source_metadata']['as_of_exclusive'],'target date mismatch')
    require(race==cross['race'],'race mismatch')
    require(race['field_size']==len(common['horses'])==len(cross['horses'])==
            len(detail['horses'])==detail['aggregate_coverage']['field_size'],'cohort size mismatch')
    if detail_raw_sha256 is not None:
        require(detail_raw_sha256==common['sources']['relatives_detail_raw_sha256'],'detail raw SHA mismatch')
    require(len(detail['integrated_v03_canonical_sha256'])==64,'integrated canonical reference missing')
    indexed=[_index(v['horses']) for v in (common,detail,cross)]
    require(indexed[0].keys()==indexed[1].keys()==indexed[2].keys(),'horse cohort mismatch')
    going_index=None;mapping=None
    if going_input is not None:
        going_index=_check_going(going_input,race,asof)
        mapping=going_input['source']['historical_parent_mapping_status']
    output=[]
    for key in sorted(indexed[0]):
        h,d,c=(x[key] for x in indexed)
        require(d['horse_name']==h['horse_name'],'relative horse name mismatch')
        require(len(d['relatives'])==h['relatives']['relative_count'],'relative count mismatch')
        for f in c['cross_observations']:
            require(f['prediction_eligible'] is False and f['display_eligible'] is False
                    and f['causal_claim'] is False and f['suitability_claim'] is False,'cross safety')
        rel=_relatives(d,race);go=_going(h,going_index,mapping)
        require(h['relatives']['zero_start_cells']==sum(
                1 for r in d['relatives'] for s in r['scope_stats'].values() if s['starts']==0),
                'relative zero coverage mismatch')
        output.append({'horse_no':key[0],'horse_id':key[1],
            'relatives_condition':rel,'going_observations':go,
            'pending':[{'kind':'DISTANCE_COMPLEMENT','reason':'CAUSAL_OR_MATCHED_COMPARISON_NOT_VALIDATED'},
                       {'kind':'PEDIGREE_ROOTS','reason':'REGIONAL_TAXONOMY_NOT_VALIDATED'}]})
    require(sum(len(h['relatives_condition']['individual']) for h in output)==
            detail['aggregate_coverage']['relative_records'],'total relatives mismatch')
    return {'contract_version':VERSION,'release_status':'RESEARCH_ONLY',
            'race':race,'as_of_exclusive':asof,
            'policy':{'prediction_safe':False,'production_authorized':False,
                      'display_authorized':False,'natural_language_review_authorized':False},
            'target_assumption':{'going_class':target_going,
                'source':'NOT_SPECIFIED' if target_going is None else 'USER_ASSUMPTION',
                'observation_not_aptitude':True},
            'sources':{'detail_raw_sha256':detail_raw_sha256,
                       'going_input_sha256':None if going_input is None else going_input['source']['source_sha256']},
            'horses':output}


def run(common_path,detail_path,cross_path,output_path,going_path=None,target_going=None):
    def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
    common=read(common_path);detail=read(detail_path);cross=read(cross_path)
    rawsha=hashlib.sha256(Path(detail_path).read_bytes()).hexdigest()
    going=read(going_path) if going_path else None
    result=build(common,detail,cross,going,rawsha,target_going)
    Path(output_path).write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for x in ('common','detail','cross','output'):p.add_argument('--'+x,required=True)
    p.add_argument('--going');p.add_argument('--target-going',choices=GOING)
    a=p.parse_args();r=run(a.common,a.detail,a.cross,a.output,a.going,a.target_going)
    print('PASS',len(r['horses']),'horses',sum(len(h['relatives_condition']['individual']) for h in r['horses']),'relatives')
