"""R3 pre-D4 bridge: genuine BRDB v0.2, no fabricated v0.3/D4.
Reuse canonical PACI/BRDB/R3 logic. Private inputs and outputs only.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import racenote_r3_independent_evidence as r3
from jpdb_r1_profile_builder import read_target_paci
from jrdb_raw import Parser, iter_archive_records

BRDB = Path(__file__).resolve().parents[2] / 'brdb'
SCHEMA = Path(__file__).resolve().parents[1] / 'schema'
sys.path.insert(0, str(BRDB / 'src'))
from brdb_m7_evidence_adapter import build_v02

VERSION = 'racenote-independent-evidence-base-only-v0.1-candidate'
PREVIEW_VERSION = 'racenote-independent-evidence-base-only-preview-v0.1-candidate'
CUTOFF = '2026-11-02'
D4_STATUS = 'SOURCE_UNAVAILABLE_PRE_D3_CUTOFF'
POPULATION = 'GENERAL_STARTS_NOT_DEBUT_SPECIFIC'
ASSETS = {'prior_detail', 'paci', 'sire_bms', 'pairing', 'relatives'}


def validate(name, obj, root=SCHEMA):
    schema = json.loads((root / name).read_bytes())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(obj)


def target_race(prior, key):
    r3.require(prior['contract_version'] == r3.VERSION and prior['research_only'] is True and
               prior['prediction_safe'] is False and prior['production_authorized'] is False and
               prior['as_of_exclusive'] == prior['target_date'], 'unsafe prior')
    r3.require(prior['target_date'] < CUTOFF, 'base-only applies only before D3 cutoff')
    race = r3.keyed(prior['races'], lambda r: r['race_key_raw'])[key]
    r3.require(race['is_newcomer_race'] is True and race['race_class_code'] == 'A1' and
               race['coverage_status'] == 'JPDB_ONLY_BRDB_UNAVAILABLE', 'not an unjoined A1 race')
    return race


def context_from_paci(paci, pin, key, target, expected, raw):
    bac, rosters = read_target_paci(paci, target_date=target, expected_sha256=pin)
    b = bac[key]; roster = r3.keyed(rosters[key].values(), r3.identity)
    identities = r3.keyed(expected['horses'], r3.identity)
    r3.require(set(roster) == set(identities) and len(roster) == b['field_size'] == expected['entry_count'], 'PACI prior field mismatch')
    for ident, h in roster.items():
        r3.require(all(h[k] == identities[ident][k] for k in ('scheduled_jockey_code','entry_cancel_flag_raw')), 'PACI scheduled rider/cancel mismatch')
    r3.require(b['race_class_code'] == 'A1' and b['surface_code'] == expected['surface_code'] and
               int(b['distance_raw']) == expected['distance_m'] and b['venue_code'] == expected['venue_code'], 'PACI race mismatch')
    parser = Parser(); ids = {x[1] for x in roster}; ukc = {}
    for _, rec in iter_archive_records(paci, 'UKC'):
        row = parser.ukc(rec); hid = row['horse_id']
        if hid in ids:
            r3.require(hid not in ukc, 'duplicate UKC profile')
            stamp = row['data_date']; r3.require(date.fromisoformat(f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}').isoformat() <= target, 'future UKC')
            ukc[hid] = row
    r3.require(set(ukc) == ids, 'missing UKC profile')
    upstream = r3.keyed(raw['horses'], r3.identity)
    r3.require(set(upstream) == set(roster), 'blood source roster mismatch')
    r3.require(raw['race']['course_code'] == b['course_code'], 'course mismatch')
    entrants = []
    for no,hid in sorted(roster):
        u = ukc[hid]; h = upstream[(no,hid)]
        r3.require((h['sire'],h['bms'],h['sire_line_code'],h['bms_line_code']) ==
                   (u['sire_name'],u['broodmare_sire_name'],u['sire_line_code'],u['broodmare_sire_line_code']), 'PACI pedigree drift')
        entrants.append({'horse_no':no,'horse_id':hid,'sire_name':u['sire_name'],'broodmare_sire_name':u['broodmare_sire_name']})
    context = {'race':{'research_only':True,'target_date':target,'venue_code':b['venue_code'],
                       'track_type':b['surface_code'],'distance':int(b['distance_raw']),'field_size':len(roster)},'entrants':entrants}
    receipt = {'status':'RESEARCH_INPUT_ONLY','prediction_safe':False,'field_size':len(roster),'ukc_joined_horses':len(ukc),
               'race_key':key,'source_archive':paci.name,'source_archive_sha256':pin}
    return context, receipt


def assemble(prior, key, paci, pin, raw, pair, relatives, hashes):
    expected = target_race(prior, key); target = prior['target_date']
    r3.require(pin == prior['target_paci_sha256'] == prior['source_assets']['paci']['sha256'], 'prior PACI pin mismatch')
    ctx, receipt = context_from_paci(paci, pin, key, target, expected, raw)
    base = build_v02(ctx, receipt, raw, pairing=pair, relatives=relatives)
    validate('brdb_integrated_review_v0_2_candidate.schema.json', base, BRDB/'schema')
    bh = r3.keyed(base['horses'], r3.identity); rh = r3.keyed(relatives['horses'], r3.identity); sh = r3.keyed(raw['horses'], r3.identity)
    r3.require(set(bh)==set(rh)==set(sh)=={r3.identity(h) for h in expected['horses']}, 'base roster drift')
    r3.require(relatives['as_of_exclusive']==target and relatives['prediction_safe'] is False and relatives['research_only'] is True and
               relatives['pedigree_generation']==base['source_generations']['brdb'] and relatives['analysis_generation']==base['source_generations']['jrdb_analysis'], 'relative source drift')
    result = copy.deepcopy(prior); race = copy.deepcopy(expected); result['races'] = [race]
    result['contract_version'] = VERSION
    result['source_assets'].update({k:{'sha256':v} for k,v in hashes.items()})
    result['source_assets']['brdb_v02'] = {'sha256':hashlib.sha256(r3.encode(base)).hexdigest()}
    result['source_assets']['brdb_generations'] = base['source_generations']
    race.update(coverage_status='DUAL_SOURCE_RESEARCH', brdb_supplemental_status=D4_STATUS, brdb_population_scope=POPULATION)
    for h in race['horses']:
        ident=r3.identity(h); b=bh[ident]; rel=rh[ident]
        r3.require(not h['restricted_refs'] and all(e['family']=='JPDB' for e in h['evidence']), 'prior blood already present')
        for rr in rel['relatives']:
            for field in ('birth_date','profile_data_date'):
                s=rr[field]; dt=date.fromisoformat(f'{s[:4]}-{s[4:6]}-{s[6:]}').isoformat()
                r3.require(dt < target if field=='birth_date' else dt<=target, 'future relative')
        # The canonical projector uses an internal supplemental list; empty here
        # is only a projection argument, never a v0.3 or D4 evidence artifact.
        ev,restricted,components=r3.br_items(dict(b,supplemental_insights=[]),rel,sh[ident],key,target,race['surface_code'],raw['policy']['historical_window_start'])
        for e in ev+restricted:
            ref=e['source_ref']; ref['asset']={'brdb_v03':'brdb_v02','brdb_relatives_detail':'brdb_relatives_raw'}[ref['asset']]
        h['evidence']+=ev;h['restricted_refs']=restricted;h['brdb_components']=components;h['brdb_status']='RESEARCH_DESCRIPTIVE_PARTIAL'
    return result,base


def preview(detail,key):
    # Reuse the frozen row selection without representing the output as v0.1.
    projection=dict(detail,contract_version=r3.VERSION)
    result=r3.reader_preview(projection,key,hashlib.sha256(r3.encode(projection)).hexdigest())
    result['contract_version']=PREVIEW_VERSION;result['detail_sha256']=hashlib.sha256(r3.encode(detail)).hexdigest()
    return result


def audit(prior,detail,base,raw,relatives,pv):
    r=detail['races'][0];key=r['race_key_raw'];old=target_race(prior,key)
    r3.require(r['brdb_supplemental_status']==D4_STATUS and r['brdb_population_scope']==POPULATION, 'D4/population promotion')
    r3.require(detail['research_only'] is True and detail['prediction_safe'] is False and detail['production_authorized'] is False, 'unsafe result')
    r3.require(pv['detail_sha256']==hashlib.sha256(r3.encode(detail)).hexdigest(), 'preview binding drift')
    jo=r3.keyed(old['horses'],r3.identity); bh=r3.keyed(base['horses'],r3.identity); rr=r3.keyed(relatives['horses'],r3.identity); pp=r3.keyed(pv['horses'],r3.identity)
    r3.require(set(jo)==set(bh)==set(rr)==set(pp)=={r3.identity(h) for h in r['horses']}, 'audit roster drift')
    observed=restricted=0
    for h in r['horses']:
        ident=r3.identity(h);j=jo[ident];b=bh[ident];p=pp[ident]
        r3.require([e for e in h['evidence'] if e['family']=='JPDB']==j['evidence'], 'JPDB changed')
        es=r3.keyed([e for e in h['evidence'] if e['family']!='JPDB'],lambda e:e['source_ref']['id'])
        expected={e['evidence_id']:e for e in b['evidence'] if e['component'] in ('sire','broodmare_sire')}
        r3.require(set(es)==set(expected), 'blood evidence completeness')
        for eid,e in es.items():
            v=expected[eid];m=v['observations'];o=e['observation']
            r3.require(e['source_ref']['asset']=='brdb_v02' and e['condition']==v['condition'] and e['sample_status']==v['sample_status'] and
                       [o[k] for k in ('n','unique_horses','wins','top3','win_rate','top3_rate')]==[m[k] for k in ('starts','unique_horses','wins','top3','win_rate','top3_rate')], 'blood numeric drift')
            r3.require(e['comparison']=={'baseline_n':m['baseline_starts'],'baseline_top3_rate':m['baseline_top3_rate'],'top3_delta_pp':m['top3_delta_pp']} and e['uncertainty']['top3_wilson95']==m['top3_wilson95'], 'blood comparison drift')
        prefix=f'{key}:{h["horse_no"]:02d}:'
        expected_refs={'BRDB:'+prefix+e['evidence_id']:('brdb_v02',e['evidence_id']) for e in b['evidence'] if e['component'] in ('pairing','relatives')}
        for relative in rr[ident]['relatives']:
            eid=f'REL_{h["horse_id"]}_{relative["horse_id"]}_{relative["relationship"]}'
            for scope in relative['scope_stats']:
                expected_refs['BRDB_DETAIL:'+prefix+eid+':'+scope]=('brdb_relatives_raw',eid+':'+scope)
        refs=r3.keyed(h['restricted_refs'],lambda e:e['evidence_id'])
        r3.require(set(refs)==set(expected_refs) and all((x['source_ref']['asset'],x['source_ref']['id'])==expected_refs[eid] and x['family']!='supplemental' and x['as_of_status']=='AS_OF_UNVERIFIED' and 'observation' not in x for eid,x in refs.items()), 'restricted evidence drift')
        r3.require(all(p[k]==h[k]==j[k] for k in ('scheduled_jockey_code','entry_cancel_flag_raw')), 'preview/prior identity flags drift')
        all_e=r3.keyed(h['evidence'],lambda e:e['evidence_id']);visible=[]
        for lane in ('jockey','blood'):
            for row in p[lane]:
                x=dict(zip(pv['columns'][lane],row));v=all_e[x['evidence_id']];o=v['observation'] or {};visible.append(x['evidence_id'])
                r3.require(x['scope']==v['scope'] and x['condition']==v['condition'] and x['sample_status']==v['sample_status'] and all(x[k]==o.get(k) for k in ('n','wins','top3','top3_rate')), 'preview drift')
        r3.require(len(visible)==len(set(visible)) and p['detail_evidence_count']==len(all_e) and p['omitted_detail_count']==len(all_e)-len(visible) and p['restricted_ref_count']==len(refs),'preview count drift')
        observed+=len(es);restricted+=len(refs)
    return {'status':'PASS_BASE_ONLY_RESEARCH','field_size':len(jo),'brdb_observations':observed,'restricted_refs':restricted,'d4_status':D4_STATUS,'population_scope':POPULATION,'prediction_safe':False,'production_authorized':False}


def run(manifest,pin,output):
    m=r3.load(manifest,pin);r3.require(m['schema_version']=='racenote-r3-base-only-input-v1' and set(m['assets'])==ASSETS,'invalid input assets')
    a=m['assets'];paths={k:Path(v['path']) for k,v in a.items()};sha={k:v['sha256'] for k,v in a.items()}
    objects={k:r3.load(paths[k],sha[k]) for k in a if k!='paci'}
    validate('racenote_independent_evidence_v0_1_candidate.schema.json',objects['prior_detail'])
    hashes={'prior_r3_detail':sha['prior_detail'],'brdb_sire_bms':sha['sire_bms'],'brdb_pairing_raw':sha['pairing'],'brdb_relatives_raw':sha['relatives']}
    outputs=[]
    for _ in range(2):
        d,b=assemble(objects['prior_detail'],m['race_key'],paths['paci'],sha['paci'],objects['sire_bms'],objects['pairing'],objects['relatives'],hashes)
        p=preview(d,m['race_key']);validate('racenote_independent_evidence_base_only_v0_1_candidate.schema.json',d);validate('racenote_independent_evidence_base_only_preview_v0_1_candidate.schema.json',p)
        receipt=audit(objects['prior_detail'],d,b,objects['sire_bms'],objects['relatives'],p)
        outputs.append((r3.encode(d),r3.encode(p),r3.encode(b),r3.encode(receipt)))
    r3.require(outputs[0]==outputs[1],'base-only nondeterministic')
    output.mkdir(parents=True,exist_ok=False)
    for name,data in zip(('detail.json','preview.json','brdb_v02.json','audit.json'),outputs[0]):(output/name).write_bytes(data)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args();print(json.dumps(run(a.manifest,a.manifest_sha256,a.output_dir),sort_keys=True))
