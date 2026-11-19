"""Research-only M7 v0.3 -> common analysis candidate. No prediction / publishing.
Inputs are explicit local immutable files; do not commit horse-level output to public Git.
"""
import argparse
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

CONTRACT = 'brdb-common-analysis-v0.1-candidate'

def read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()

def require(ok, message):
    if not ok:
        raise ValueError(message)

def build(integrated, detail, preview, newspaper, shas):
    require(integrated['contract_version']=='brdb-integrated-blood-review-v0.3-candidate','integrated contract')
    require(detail['contract_version']=='brdb-m7-relatives-detail-v0.1-candidate','detail contract')
    require(preview['contract_version']=='brdb-m7-research-consumer-preview-v0.1','preview contract')
    require(newspaper['bundle_kind']=='jrdb_pwa_newspaper_race','newspaper contract')
    require(integrated['release_status']=='RESEARCH_CANDIDATE','release status')
    require(detail['research_only'] is True and detail['prediction_safe'] is False,'detail safety')
    require(preview['research_only'] is True and preview['production_authorized'] is False and preview['prediction_safe'] is False,'preview safety')
    require(preview['source_sha256']['integrated_v03']==detail['integrated_v03_canonical_sha256'],'preview integrated semantic SHA linkage')
    # Preview's detail digest is a canonical/semantic digest, not the raw-file digest.
    # Exact canonicalization verification must use the existing M7 hash routine, not a guessed algorithm.
    race=integrated['race'];nr=newspaper['race']
    for src in [preview['race']]:
        require(src==race,'race mismatch with preview')
    for a,b in [('race_key','race_key'),('target_date','date'),('venue_code','venue_code'),('distance_m','distance_m'),('field_size','field_size')]:
        require(race[a]==nr[b],f'newspaper race mismatch: {a}')
    require(nr['surface']=={'1':'芝','2':'ダート'}[race['surface_code']],'surface mismatch')
    require(integrated['as_of_exclusive']==race['target_date'],'as-of mismatch')
    require(detail['source_metadata']['as_of_exclusive']==race['target_date'],'detail as-of mismatch')
    require(detail['aggregate_coverage']['field_size']==race['field_size'],'detail field size')
    require(preview['as_of_status']=='AS_OF_UNVERIFIED' and detail['historical_asof_status']=='AS_OF_UNVERIFIED','temporal claims')
    def index(rows,id_get):
        ids=[id_get(x) for x in rows]
        require(len(ids)==len(set(ids)),'duplicate horse identity')
        require(len(rows)==race['field_size'],'field size mismatch')
        for no,hid in ids:
            require(type(no)==int and no>=1 and isinstance(hid,str) and len(hid)==8 and hid.isdigit(),'canonical horse identity')
        return dict(zip(ids,rows))
    h1=index(integrated['horses'],lambda x:(x['horse_no'],x['horse_id']))
    h2=index(detail['horses'],lambda x:(x['horse_no'],x['horse_id']))
    h3=index(preview['horses'],lambda x:(x['horse_no'],x['horse_id']))
    h4=index(newspaper['horses'],lambda x:(x['key']['horse_no'],x['key']['horse_id']))
    require(h1.keys()==h2.keys()==h3.keys()==h4.keys(),'full cohort mismatch')
    result=[]
    for key in sorted(h1):
        h=h1[key];d=h2[key];n=h4[key]
        require(h['horse_name']==n['basic']['horse_name'],'name mismatch')
        require(h['pedigree_facts']['sire_name']==n['basic']['sire_name'],'sire mismatch')
        require(h['pedigree_facts']['broodmare_sire_name']==n['basic']['broodmare_sire_name'],'bms mismatch')
        # Newspaper canonical basic is preferred to M7 incomplete dam_name.
        pedigree=dict(h['pedigree_facts']);pedigree['dam_name']=n['basic'].get('dam_name')
        evidence_ids=[e['evidence_id'] for e in h['evidence']]
        require(len(evidence_ids)==len(set(evidence_ids)),'duplicate evidence_id')
        evidence_index={e['evidence_id']:e for e in h['evidence']}
        comps={}
        for name,c in h['components'].items():
            require(set(c['evidence_ids']).issubset(evidence_index),'dangling evidence ref')
            scopes=[]
            for eid in c['evidence_ids']:
                e=evidence_index[eid]
                require(e['component']==name,'evidence component mismatch')
                o=e['observations']
                if o is None:continue
                starts=o['starts'];wins=o['wins'];top3=o['top3']
                require(0<=wins<=top3<=starts,'invalid counts')
                require(e['as_of_exclusive']==race['target_date'],'evidence asof mismatch')
                scopes.append({'evidence_id':eid,'overlap_group':e['overlap_group'],'source_name':e['source_name'],'scope_key':e['scope_key'],'condition':e['condition'],
                  'sample_status':e['sample_status'],'data_status':'NO_SAMPLE' if starts==0 else 'OBSERVED',
                  'source_generation':e['source_generation'],'as_of_exclusive':e['as_of_exclusive'],
                  'counts':{'starts':starts,'wins':wins,'seconds':None,'thirds':None,'out_of_top3':None,'top3':top3,'unique_horses':o['unique_horses']},
                  'rates':{'win_rate':o['win_rate'],'top3_rate':o['top3_rate'],'win_return_rate':None,'place_return_rate':None},
                  'baseline':{'starts':o['baseline_starts'],'top3_rate':o['baseline_top3_rate'],'top3_delta_pp':o['top3_delta_pp']}})
            comps[name]={'availability':c['availability'],'scopes':scopes}
        zero=sum(1 for rel in d['relatives'] for stat in rel['scope_stats'].values() if stat['starts']==0)
        require((d['status']=='DESCRIPTIVE_RELATION' and h['components']['relatives']['availability']=='AS_OF_UNVERIFIED') or d['status']==h['components']['relatives']['availability'],'relative status mapping mismatch')
        # No new validated discoveries synthesized from descriptive statistics.
        result.append({'horse_id':key[1],'horse_no':key[0],'horse_name':h['horse_name'],
         'status':h['status'],'pedigree':pedigree,'components':comps,
         'relatives':{'status':d['status'],'relative_count':len(d['relatives']),'zero_start_cells':zero},'findings':[]})
    require(sum(h['relatives']['relative_count'] for h in result)==detail['aggregate_coverage']['relative_records'],'rel count mismatch')
    require(sum(h['relatives']['zero_start_cells'] for h in result)==detail['aggregate_coverage']['zero_start_cells'],'zero cells mismatch')
    return {'contract_version':CONTRACT,'release_status':'RESEARCH_ONLY','race':race,
      'as_of_exclusive':integrated['as_of_exclusive'], 'sources':{'source_generations':integrated['source_generations'],**shas},
      'policy':{'prediction_safe':False,'production_authorized':False,'historical_asof_status':'AS_OF_UNVERIFIED','score_included':False},
      'horses':result}

def run(paths, schema):
    docs={};shas={}
    mapping={'integrated':'integrated_v03_raw_sha256','detail':'relatives_detail_raw_sha256','preview':'preview_raw_sha256','newspaper':'newspaper_raw_sha256'}
    for key,path in paths.items():
        docs[key],shas[mapping[key]]=read(path)
    output=build(docs['integrated'],docs['detail'],docs['preview'],docs['newspaper'],shas)
    s=json.loads(Path(schema).read_text())
    Draft202012Validator(s, format_checker=FormatChecker()).validate(output)
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('integrated','detail','preview','newspaper','schema','output'):p.add_argument('--'+n,required=True)
    a=vars(p.parse_args());schema=a.pop('schema');out=a.pop('output')
    obj=run(a,schema)
    Path(out).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print('PASS',len(obj['horses']),'horses',obj['race']['race_key'])
