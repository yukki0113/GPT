#!/usr/bin/env python3
"""Private fixed-input R1 E2E. Public output is aggregate-only; profiles remain local."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from collections import Counter
from pathlib import Path
from datetime import date
import duckdb
from jpdb_history_reader import sha256, JPDBHistoryReaderError
from jpdb_performance_reader_v11 import _windows
from jpdb_r1_profile_builder import (JPDBCourseMasterReader2026, audit_history_class, build,
                                    read_target_paci, PHYSICAL, SCOPED, VERSION)

FIXTURES={'2026-06-13':('05263305','09263306','05263312'),
          '2026-11-15':('05265404','05265405','05265412')}
# Separate SUM(CASE...) query, not the builder's filtered aggregates.
COUNT_EXPRESSIONS={
    'entries':'COUNT(*)',
    'normal_finishers':"SUM(CASE WHEN abnormal_code IN ('0','') AND field_size>=1 AND finish BETWEEN 1 AND field_size THEN 1 ELSE 0 END)",
    'cancellations':"SUM(CASE WHEN abnormal_code='1' THEN 1 ELSE 0 END)",
    'exclusions':"SUM(CASE WHEN abnormal_code='2' THEN 1 ELSE 0 END)",
    'dnf':"SUM(CASE WHEN abnormal_code='3' THEN 1 ELSE 0 END)",
    'demotion_review':"SUM(CASE WHEN abnormal_code='5' THEN 1 ELSE 0 END)",
    'unknown_codes':"SUM(CASE WHEN abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3','5') THEN 1 ELSE 0 END)",
    'invalid_normal_finish':"SUM(CASE WHEN abnormal_code IN ('0','') AND (finish IS NULL OR field_size IS NULL OR field_size<1 OR finish<1 OR finish>field_size) THEN 1 ELSE 0 END)",
}
for name,n in [('wins',1),('top2',2),('top3',3)]:
    COUNT_EXPRESSIONS[name]=f"SUM(CASE WHEN abnormal_code IN ('0','') AND field_size>=1 AND finish BETWEEN 1 AND field_size AND finish<={n} THEN 1 ELSE 0 END)"


def require(condition, label):
    if not condition:
        raise JPDBHistoryReaderError('R1 independent audit failed: '+label)


def audit_profile(reader, profile, path, expected_sha, expected_keys):
    day=profile['target_date']; db=reader.db
    bac,kyi=read_target_paci(path,target_date=day,expected_sha256=expected_sha)
    require(profile['prediction_safe'] is False and not profile['source']['strict_asof_certified'],'research boundary')
    require({r['race_key_raw'] for r in profile['races']}==set(expected_keys),'race roster')
    summary=[]; cell_checks=0; field_checks=0; ids=set(); statuses=Counter()
    for race in profile['races']:
        key=race['race_key_raw']; b=bac[key]; s=b['surface_code']; v=b['venue_code']; d=int(b['distance_raw']); c=b['race_class_code']
        require((race['surface_code'],race['venue_code'],race['distance_m'],race['race_class_code'])==(s,v,d,c),'target condition')
        require(race['is_newcomer_race']==(c=='A1'),'newcomer class')
        require(len(race['horses'])==race['entry_count']==b['field_size'],'BAC field count')
        require({h['horse_no'] for h in race['horses']}==set(kyi[key]),'KYI roster')
        expected={'ALL_FLAT':{},'SURFACE':{'surface_code':s},'VENUE':{'venue_code':v},
                  'SURFACE_DISTANCE_EXACT':{'surface_code':s,'distance_m':d},
                  'CLASS_GRADE_RAW':{'race_class_code':c,'grade_code':b['grade_code']},
                  'GOING_RAW':{'surface_code':s,'track_condition_code':None},
                  'VENUE_SURFACE':{'venue_code':v,'surface_code':s}}
        expected.update({dim:{col:race['course'][col]} for dim,col in PHYSICAL.items()})
        if c=='A1':
            expected.update({'NEWCOMER_ALL_FLAT':{'race_class_code':'A1'},
                'NEWCOMER_SURFACE':{'race_class_code':'A1','surface_code':s},
                'NEWCOMER_VENUE_SURFACE':{'race_class_code':'A1','venue_code':v,'surface_code':s},
                'NEWCOMER_SURFACE_DISTANCE_EXACT':{'race_class_code':'A1','surface_code':s,'distance_m':d}})
        else:
            expected.update({'CLASS_ONLY':{'race_class_code':c},'CLASS_SURFACE':{'race_class_code':c,'surface_code':s}})
        supports=Counter(); scopes=Counter()
        for h in race['horses']:
            no=h['horse_no']; require(all(h[k]==x for k,x in kyi[key][no].items()),'planned KYI identity')
            require(set(h['windows'])==set(_windows(date.fromisoformat(day))),'windows')
            for w,lower in _windows(date.fromisoformat(day)).items():
                data=h['windows'][w]
                require(data['period_from_inclusive']==lower and data['period_to_exclusive']==day,'time bounds')
                require(len(data['evidence'])==len(expected) and {e['dimension'] for e in data['evidence']}==set(expected),'axis coverage')
                for e in data['evidence']:
                    dim=e['dimension']; condition=expected[dim]
                    require(e['condition']==condition and e['direction']=='UNCLASSIFIED','condition and no rank label')
                    require(e['evidence_id'] not in ids,'unique evidence ID');ids.add(e['evidence_id'])
                    statuses[e['status']]+=1
                    if any(x in (None,'') for x in condition.values()):
                        require(e['metrics'] is None and e['sample_n'] is None and e['status']=='TARGET_CONDITION_UNAVAILABLE','unknown condition')
                    else:
                        require(e['metrics'] is not None,'known condition missing counts')
        codes=sorted({h['scheduled_jockey_code'] for h in race['horses']})
        for w,lower in _windows(date.fromisoformat(day)).items():
            for dim,condition in expected.items():
                if any(x in (None,'') for x in condition.values()):continue
                where=' AND '.join(k+'=?' for k in condition)
                sql='SELECT jockey_code,'+','.join(COUNT_EXPRESSIONS.values())+',MIN(race_date),MAX(race_date) FROM jpdb_course_facts WHERE race_date>=? AND race_date<? AND surface_code IN (\'1\',\'2\') AND jockey_code IN ('+','.join('?' for _ in codes)+')'+(' AND '+where if where else '')+' GROUP BY jockey_code'
                rows=db.execute(sql,[lower,day,*codes,*condition.values()]).fetchall()
                lookup={row[0]:row[1:] for row in rows}
                for h in race['horses']:
                    e=next(e for e in h['windows'][w]['evidence'] if e['dimension']==dim)
                    m=e['metrics']; row=lookup.get(h['scheduled_jockey_code'],(0,)*len(COUNT_EXPRESSIONS)+(None,None))
                    require(tuple(m[k] for k in COUNT_EXPRESSIONS)==tuple(row[:-2]),'counts')
                    require((m['first_observed'],m['last_observed'])==tuple(row[-2:]),'observed dates')
                    require(m['last_observed'] is None or m['last_observed']<day,'target date leakage')
                    require(m['actual_starts_candidate']==m['normal_finishers']+m['dnf']+m['demotion_review']==e['sample_n'],'denominator')
                    require(m['unresolved_count']==m['demotion_review']+m['invalid_normal_finish']+m['unknown_codes'],'unresolved')
                    if m['unresolved_count'] or not e['sample_n']:
                        require(m['start_basis_win_rate_candidate'] is None and m['start_basis_top3_rate_candidate'] is None,'unsafe rate withheld')
                    else:
                        require(m['start_basis_win_rate_candidate']==m['wins']/e['sample_n'] and m['start_basis_top3_rate_candidate']==m['top3']/e['sample_n'],'candidate rates')
                    if w=='ROLLING_3Y':
                        scopes[dim]+=1
                        supports[dim]+=int(e['sample_n']>=30 and m['unresolved_count']==0)
                    cell_checks+=1;field_checks+=len(COUNT_EXPRESSIONS)+2
        summary.append({'race_key_raw':key,'entries':race['entry_count'],'newcomer':race['is_newcomer_race'],
                        'surface_code':s,'rolling_3y_known_cells':dict(scopes),'rolling_3y_n_ge_30_resolved':dict(supports)})
    return {'race_summaries':summary,'independent_cells':cell_checks,'independent_count_date_fields':field_checks,
            'evidence_count':len(ids),'status_counts':dict(statuses)}


def run(args):
    with JPDBCourseMasterReader2026(input_root=args.input_root,manifest=args.manifest,daily_root=args.daily_root,
            daily_manifest=args.daily_manifest,bac_root=args.bac_root,paci_root=args.paci_root,paci_manifest=args.paci_manifest,
            course_root=args.course_root,expected_manifest_sha256=args.expected_manifest_sha256,
            expected_daily_manifest_sha256=args.expected_daily_manifest_sha256,
            expected_paci_manifest_sha256=args.expected_paci_manifest_sha256) as r:
        authority=audit_history_class(r,bac_root=args.bac_root,manifest=args.manifest,paci_root=args.paci_root,paci_manifest=args.paci_manifest)
        manifest=json.loads(args.paci_manifest.read_text())['selected']; proofs=[]
        for target,keys in FIXTURES.items():
            x=next(x for x in manifest if x['race_date']==target); path=args.paci_root/x['name']; digest=x['zip_sha256']
            kw=dict(target_date=target,paci_path=path,paci_manifest=args.paci_manifest,expected_paci_sha256=digest,race_keys=keys,class_audit=authority)
            p=build(r,**kw); audit=audit_profile(r,p,path,digest,keys)
            blob=(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
            again=(json.dumps(build(r,**kw),ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
            require(blob==again,'same input repeat byte equality')
            private=args.private_output_dir/f'jpdb_r1_{target.replace("-","")}.json';private.write_bytes(blob)
            proofs.append({'target_date':target,'profile_sha256':sha256(private),'repeat_equal':True,'target_paci_sha256':digest,**audit})
        return {'schema_version':'jpdb-r1-real-profile-e2e-v1','status':'PASS','scope':'FIXED_SOURCE_RESEARCH_ONLY',
                'runtime':{'python':platform.python_version(),'duckdb':duckdb.__version__},'class_audit':authority,
                'historical_manifest_sha256':r.manifest_sha256,'daily_sed_manifest_sha256':r.daily_manifest_sha256,
                'daily_paci_manifest_sha256':r.paci_manifest_sha256,'proofs':proofs,
                'profile_version':VERSION,'prediction_safe':False,'strict_asof_certified':False,
                'public_source_rows_exported':False,'production_changed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for label in ('input-root','manifest','daily-root','daily-manifest','bac-root','paci-root','paci-manifest','course-root','output','private-output-dir'):
        p.add_argument('--'+label,type=Path,required=True)
    for label in ('expected-manifest-sha256','expected-daily-manifest-sha256','expected-paci-manifest-sha256'):
        p.add_argument('--'+label,required=True)
    a=p.parse_args();a.private_output_dir.mkdir(parents=True,exist_ok=False)
    if a.output.exists():raise FileExistsError('refusing overwrite audit')
    result=run(a);a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'profiles':len(result['proofs']),'cells':sum(p['independent_cells'] for p in result['proofs']),
                      'fields':sum(p['independent_count_date_fields'] for p in result['proofs'])}))

if __name__=='__main__':main()
