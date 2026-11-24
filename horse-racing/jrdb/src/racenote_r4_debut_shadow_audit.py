#!/usr/bin/env python3
"""Attach B5 references to accepted R4 shadow, separately from general-start evidence."""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import hashlib
import json
from jsonschema import Draft202012Validator, FormatChecker
import racenote_r4_shadow_audit as common

VERSION='racenote-r4-debut-shadow-v0.1'
require=common.require
asset=common.asset
r3=common.r3
COHORTS={'A1_RACE_ACTUAL_STARTERS','FIRST_OBSERVED_JRA_START_CANDIDATE'}
LANES={'SIRE_ID','BMS_ID','PARENT_ID_PAIR','LINEAGE_CODE_PAIR'}
SCOPES={'ALL','SURFACE','SURFACE_DISTANCE','SURFACE_MONTH','SURFACE_AGE'}
CUTOFF='2026-01-01'

def key(h):return h['race_key'],h['horse_no'],h['horse_id']

def validate_horse(h,prev,target):
    require(h['paci_cancel_flag']==prev['entry_cancel_flag_raw'] and h['race_class_code']=='A1','B5 PACI identity/cancel/class drift')
    require(h['individual_eligibility']['lifetime_first_start_certified'] is False,'B5 lifetime-first promotion')
    require(h['profile_date'] is None or h['profile_date']<=target,'future target pedigree')
    cells=h['population_evidence']; rel=h['relative_evidence']; ids=[e['evidence_id'] for e in cells+rel]
    require(len(ids)==len(set(ids)) and all(i.startswith(f"{h['race_key']}:{h['horse_no']:02d}:") for i in ids),'B5 evidence identity mismatch')
    require(len(cells)==40 and {(e['cohort'],e['lane'],e['scope']) for e in cells}=={(c,l,s) for c in COHORTS for l in LANES for s in SCOPES},'B5 population coverage drift')
    for e in cells+rel:
        require(e['max_history_date'] is None or e['max_history_date']<CUTOFF,'B5 nonprior outcome')
    for e in rel:
        require(e['first_date'] is None or e['first_date']<CUTOFF,'B5 nonprior first outcome')
        require(e['first_observed_date'] is None or e['first_observed_date']<CUTOFF,'B5 nonprior first observation')
        require(e['relative_profile_date'] is None or e['relative_profile_date']<=target,'B5 future relative profile')
    return {'race_key':h['race_key'],'horse_no':h['horse_no'],'horse_id':h['horse_id'],
            'baseline_status':prev['baseline_context']['status'],'jpdb_evidence_ids':prev['jpdb_evidence_ids'],
            'general_brdb_evidence_ids':prev['brdb_evidence_ids'],
            'b5_population_refs':[e['evidence_id'] for e in cells],'b5_relative_refs':[e['evidence_id'] for e in rel],
            'b5_population_status_counts':dict(Counter(e['status'] for e in cells)),
            'b5_relative_status_counts':dict(Counter(e['sample_status'] for e in rel)),
            'b5_any_observed_population':any((e['starts'] or 0)>0 for e in cells),
            'individual_status':h['individual_eligibility']['status'],'history_gap_2026':True,
            'b5_temporal_status':'AS_OF_UNVERIFIED','numeric_exposed':False,
            'overlap_policy':'GENERAL_STARTS_DEBUT_COHORTS_LANES_SCOPES_RELATIVES_NOT_INDEPENDENT'}

def run(path,pin,out):
    m=r3.load(path,pin);require(set(m)=={'schema_version','common_receipt','common_private','b5_reference_receipt','b5_schema','jobs'} and m['schema_version']=='racenote-r4-debut-input-v1','wrong debut manifest')
    c=asset(m['common_receipt']);p=asset(m['common_private']);ref=asset(m['b5_reference_receipt']);schema=asset(m['b5_schema'])
    require(c['schema_version']==common.VERSION and c['status']=='PARTIAL_R4_SHADOW_RESEARCH' and p['schema_version']==common.VERSION and c['private_shadow_sha256']==m['common_private']['sha256'],'common receipt binding')
    require(all(x['research_only'] is True and x['prediction_safe'] is False and x['production_authorized'] is False for x in (p,c)) and c['r5_authorized'] is False,'unsafe common input')
    require(m['b5_reference_receipt']['sha256']==c['b5_reference']['receipt_sha256'] and ref['status']=='PASS_RESEARCH_ONLY','B5 reference mismatch')
    require(m['b5_schema']['sha256']=='8444963bcb3634e77619876e04fb6fdbeb48ad1fdcb5fbeddaffb85234611948','unapproved B5 schema')
    Draft202012Validator.check_schema(schema);validator=Draft202012Validator(schema,format_checker=FormatChecker())
    races={r['race']['race_key_raw']:r for r in p['races'] if r['race']['cohort']=='NEWCOMER_A1'}
    prior={(k,h['horse_no'],h['horse_id']):h for k,r in races.items() for h in r['horses']};seen=set();rows=[];proofs=[]
    for j in m['jobs']:
        require(set(j)=={'review','receipt','replay_review','replay_receipt'},'unexpected B5 input')
        d=asset(j['review']);a=asset(j['receipt']);asset(j['replay_review']);asset(j['replay_receipt']);validator.validate(d)
        require(j['review']['sha256']==j['replay_review']['sha256']==a['private_output_sha256'] and j['receipt']['sha256']==j['replay_receipt']['sha256'],'B5 replay/receipt mismatch')
        require(a['status']=='PASS_RESEARCH_ONLY' and all(x['prediction_safe'] is False and x['production_authorized'] is False for x in (a,d)) and d['research_only'] is True,'unsafe B5 input')
        require(all(a[k]==d[k]==ref[k] for k in ('analysis_sha256','warehouse_sha256','pedigree_sha256','history_cutoff_exclusive')) and a['source_sha256']==ref['source_sha256'] and a['source_base_commit']==ref['source_base_commit']==d['source_commit'],'B5 frozen upstream drift')
        require(d['history_gap_2026'] is True and d['temporal_status']=='AS_OF_UNVERIFIED' and d['history_cutoff_exclusive']==CUTOFF and CUTOFF<d['target_date'],'B5 temporal policy drift')
        rr=r3.keyed(d['races'],lambda r:r['race_key']);hh=r3.keyed(d['horses'],key)
        for k,r in rr.items():
            require(k in races and races[k]['race']['target_date']==d['target_date'] and races[k]['race']['paci_sha256']==d['paci_sha256']==a['paci_sha256'],'B5 target/PACI mismatch')
            expected={i for i in prior if i[0]==k};actual={i for i in hh if i[0]==k}
            require(expected==actual and len(actual)==r['declared_count']==races[k]['race']['counts']['horses'] and r['race_class_code']=='A1','B5 full-field mismatch')
        require({i[0] for i in hh}==set(rr) and not seen&set(hh),'B5 duplicate or extra field')
        require(a['summary']['horses']==len(hh) and a['summary']['races']==len(rr),'B5 receipt count mismatch')
        for i,h in sorted(hh.items()):rows.append(validate_horse(h,prior[i],d['target_date']))
        seen.update(hh);proofs.append({'target_date':d['target_date'],'paci_sha256':d['paci_sha256'],'review_sha256':j['review']['sha256'],'receipt_sha256':j['receipt']['sha256'],'races':sorted(rr),'horses':len(hh),'replay_byte_equal':True})
    require(seen==set(prior),'incomplete B5 target cohort')
    pop=Counter();rel=Counter();per=[]
    for k in sorted(races):
        xs=[h for h in rows if h['race_key']==k];pc=Counter();rc=Counter()
        for h in xs:pc.update(h['b5_population_status_counts']);rc.update(h['b5_relative_status_counts'])
        pop.update(pc);rel.update(rc);per.append({'race_key':k,'horses':len(xs),'population_cells':sum(pc.values()),'relative_cells':sum(rc.values()),'population_status_counts':dict(pc),'relative_status_counts':dict(rc),'horses_with_observed_population':sum(h['b5_any_observed_population'] for h in xs)})
    private={'schema_version':VERSION,'research_only':True,'prediction_safe':False,'production_authorized':False,'rows':rows}
    raw=r3.encode(private);result={'schema_version':VERSION,'status':'PASS_B5_SAME_FIELD_DESCRIPTIVE_SHADOW','research_only':True,'prediction_safe':False,'production_authorized':False,'r5_authorized':False,'input_manifest_sha256':pin,'common_receipt_sha256':m['common_receipt']['sha256'],'private_sha256':hashlib.sha256(raw).hexdigest(),'races':len(races),'horses':len(rows),'population_cells':sum(pop.values()),'relative_cells':sum(rel.values()),'population_status_counts':dict(pop),'relative_status_counts':dict(rel),'horses_with_observed_population':sum(h['b5_any_observed_population'] for h in rows),'history_cutoff_exclusive':CUTOFF,'history_gap_2026':True,'temporal_status':'AS_OF_UNVERIFIED','proofs':proofs,'per_race':per}
    out=Path(out).resolve();require(not out.is_relative_to(common.REPO),'private output inside repository');out.mkdir(parents=True,exist_ok=False);(out/'PRIVATE_debut_shadow.json').write_bytes(raw);(out/'receipt.json').write_bytes(r3.encode(result));return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--manifest',type=Path,required=True);a.add_argument('--manifest-sha256',required=True);a.add_argument('--output-dir',type=Path,required=True);q=a.parse_args();print(json.dumps(run(q.manifest,q.manifest_sha256,q.output_dir),sort_keys=True))
