#!/usr/bin/env python3
"""R2 fixed-source research runner. Private horse contexts, public aggregate audit only."""
from __future__ import annotations
import argparse
import json
import platform
from collections import Counter,defaultdict
from pathlib import Path
import duckdb
from jpdb_history_reader import sha256
from jpdb_r1_profile_builder import JPDBCourseMasterReader2026,audit_history_class,build
from jpdb_r1_real_profile_e2e import FIXTURES,audit_profile,COUNT_EXPRESSIONS
from jpdb_r2_condition_context import (VERSION,AXES,WINDOWS,COUNTS,PERIODS,MIN_N,MARGIN,
    build_context,annual_stability,market_sensitivity,require)
from jpdb_p3_market_research_runner import convert_daily_odds,construct_view
from jpdb_p3_market_baselines import prepare,validate


def dump(data):return (json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def independent_group_check(db,context):
    # Independent direct predicates and SUM(CASE...) counts. First registered
    # horse in each race, every available dimension/window, all four cells.
    checked=0
    for race in context['races']:
        h=race['horses'][0];rider=h['scheduled_jockey_code']
        for a in h['axes']:
            parents,cols=AXES[a['dimension']];cond=a['condition']
            for w,block in a['windows'].items():
                if block['groups'] is None:continue
                known=' AND '.join(f"{k} IS NOT NULL AND TRIM(CAST({k} AS VARCHAR))<>''" for k in parents+cols) or 'TRUE'
                pf=' AND '.join(k+'=?' for k in parents) or 'TRUE';cf=' AND '.join(k+'=?' for k in cols) or 'TRUE'
                for label,own,matched in [('own_match',True,True),('own_other',True,False),('peer_match',False,True),('peer_other',False,False)]:
                    sql=f"SELECT {','.join(COUNT_EXPRESSIONS[k] for k in COUNTS)} FROM jpdb_course_facts WHERE race_date>=? AND race_date<? AND surface_code IN ('1','2') AND regexp_full_match(jockey_code,'[0-9]{{5}}') AND jockey_code<>'00000' AND ({known}) AND ({pf}) AND jockey_code {'=' if own else '<>'} ? AND {'(' if matched else 'NOT ('}{cf})"
                    row=db.execute(sql,[block['period_from_inclusive'],block['period_to_exclusive'],*[cond[k] for k in parents],rider,*[cond[k] for k in cols]]).fetchone()
                    require(tuple(x or 0 for x in row)==tuple(block['groups'][label][k] for k in COUNTS),'independent direct group mismatch')
                    checked+=1
    return checked


def summarize(context):
    out=defaultdict(lambda:defaultdict(Counter)); counts=Counter();n=0
    for race in context['races']:
        cohort='newcomer' if race['is_newcomer_race'] else 'non_newcomer'
        for h in race['horses']:
            n+=1;counts[cohort]+=1
            for a in h['axes']:
                for comp,s in a['window_summary'].items():
                    out[cohort][a['dimension']][f'{comp}:{s["status"]}:{s["direction"]}']+=1
                if not a['window_summary']:out[cohort][a['dimension']]['UNAVAILABLE']+=1
    return {'entries':n,'cohorts':dict(counts),'summary':{k:{a:dict(c) for a,c in v.items()} for k,v in out.items()}}


def run(a):
    require(sha256(a.protocol)==a.expected_protocol_sha256,'protocol SHA mismatch')
    require(not a.output.exists() and not a.private_output_dir.exists(),'refuse overwrite')
    a.private_output_dir.mkdir(parents=True)
    with JPDBCourseMasterReader2026(input_root=a.input_root,manifest=a.manifest,daily_root=a.daily_root,
            daily_manifest=a.daily_manifest,bac_root=a.input_root,paci_root=a.paci_root,paci_manifest=a.paci_manifest,
            course_root=a.course_root,expected_manifest_sha256=a.expected_manifest_sha256,
            expected_daily_manifest_sha256=a.expected_daily_manifest_sha256,expected_paci_manifest_sha256=a.expected_paci_manifest_sha256) as r:
        db=r.db;db.execute('SET threads=1')
        authority=audit_history_class(r,bac_root=a.input_root,manifest=a.manifest,paci_root=a.paci_root,paci_manifest=a.paci_manifest)
        manifest=json.loads(a.paci_manifest.read_text())['selected'];proofs=[]
        receipt=json.loads(a.r1_audit.read_text());require(sha256(a.r1_audit)==a.expected_r1_audit_sha256,'R1 audit SHA mismatch')
        for target,keys in FIXTURES.items():
            old=a.r1_profile_dir/f'jpdb_r1_{target.replace("-","")}.json';pinned=next(x for x in receipt['proofs'] if x['target_date']==target)
            require(sha256(old)==pinned['profile_sha256'],'R1 profile receipt drift')
            x=next(x for x in manifest if x['race_date']==target);path=a.paci_root/x['name'];digest=x['zip_sha256']
            p=build(r,target_date=target,paci_path=path,paci_manifest=a.paci_manifest,expected_paci_sha256=digest,race_keys=keys,class_audit=authority)
            require(dump(p)==old.read_bytes(),'reconstructed R1 bytes differ')
            audit_profile(r,p,path,digest,keys)
            out=build_context(db,p);raw=dump(out);require(raw==dump(build_context(db,p)),'R2 repeat bytes differ')
            checks=independent_group_check(db,out)
            dest=a.private_output_dir/f'jpdb_r2_{target.replace("-","")}.json';dest.write_bytes(raw)
            proofs.append({'date':target,'r1_profile_sha256':sha256(old),'r2_context_sha256':sha256(dest),
                           'r1_matched_count_cells':out['r1_matched_count_cells'],'independent_four_group_checks':checks,
                           'repeat_equal':True,**summarize(out)})
            print('profile checked',target,flush=True)
        annual=annual_stability(db);print('annual stability complete',flush=True)
        # Separate retrospective lane. Target contexts already sealed.
        convert_daily_odds(r,a.daily_root);construct_view(r,a.input_root,a.manifest)
        prepare(db,'2026-11-16');market_audit=validate(db,'2026-11-16')
        db.execute('''CREATE TEMP TABLE r2_market_race_conditions AS SELECT DISTINCT race_key_raw,
            race_class_code,distance_m FROM jpdb_course_facts WHERE surface_code IN ('1','2')''')
        require(db.execute('SELECT COUNT(*)=COUNT(DISTINCT race_key_raw) FROM r2_market_race_conditions').fetchone()[0],'market race condition ambiguity')
        db.execute('''CREATE TEMP TABLE r2_market_facts AS SELECT e.*, c.race_class_code,c.distance_m
            FROM p3_eligible e JOIN r2_market_race_conditions c USING(race_key_raw)''')
        n=db.execute('SELECT COUNT(*) FROM p3_eligible').fetchone()[0]
        require(db.execute('SELECT COUNT(*) FROM r2_market_facts').fetchone()[0]==n,'market join count')
        market=market_sensitivity(db);print('market sensitivity complete',flush=True)
        return {'schema_version':'jpdb-r2-fixed-source-research-v1','status':'PASS_RESEARCH_CONTEXT_ONLY','prediction_safe':False,
            'strict_asof_certified':False,'production_changed':False,'protocol_sha256':sha256(a.protocol),
            'runtime':{'python':platform.python_version(),'duckdb':duckdb.__version__,'threads':1},
            'input_manifest_sha256':{'historical':r.manifest_sha256,'daily_sed':r.daily_manifest_sha256,'daily_paci':r.paci_manifest_sha256},
            'class_audit':authority,'profile_proofs':proofs,'periods':PERIODS,'min_n':MIN_N,'display_margin_pp':100*MARGIN,
            'annual_reproduction':annual,'retrospective_market_sensitivity':market,'market_cohort_rows':n,
            'market_cohort_audit':market_audit,'policy':{'suggestive_certified':False,'individual_inference':False,
            'market_in_profile':False,'overlapping_evidence_independent':False,'r3_r6_approved':False}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for label in ('input-root','manifest','daily-root','daily-manifest','paci-root','paci-manifest','course-root','output','private-output-dir','protocol','r1-audit','r1-profile-dir'):
        p.add_argument('--'+label,required=True,type=Path)
    for label in ('expected-manifest-sha256','expected-daily-manifest-sha256','expected-paci-manifest-sha256','expected-protocol-sha256','expected-r1-audit-sha256'):
        p.add_argument('--'+label,required=True)
    a=p.parse_args();result=run(a);a.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n');print(result['status'])

if __name__=='__main__':main()
