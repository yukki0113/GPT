#!/usr/bin/env python3
"""R4: independent research-only shadow audit of accepted R3 + sealed v056 Reader.

No marks, confidence, prediction scoring, target results, or production writes.
A missing baseline or debut-specific contract stays missing. Private rows are
written only to caller-supplied local output; only aggregate receipt is public.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator, FormatChecker
import racenote_r3_independent_evidence as r3
import racenote_r3_brdb_base_only as base
from jpdb_r1_profile_builder import read_target_paci

VERSION = 'racenote-r4-shadow-audit-v0.1'
NORMAL = r3.VERSION
BASE = base.VERSION
SHARED = 'SHARED_JRDB_HISTORY_NOT_INDEPENDENT'
SCHEMAS = Path(__file__).resolve().parents[1] / 'schema'
REPO = Path(__file__).resolve().parents[3]
ASSET_FIELDS = {'path', 'sha256'}
BASELINE_FIELDS = {'operation', 'session', 'reader_manifest', 'reader', 'prediction_handoff', 'confidence_handoff'}
SIDE_SCHEMAS = {
    NORMAL: ('racenote_independent_evidence_v0_1_candidate.schema.json', 'racenote_independent_evidence_preview_v0_1_candidate.schema.json'),
    BASE: ('racenote_independent_evidence_base_only_v0_1_candidate.schema.json', 'racenote_independent_evidence_base_only_preview_v0_1_candidate.schema.json'),
}
VENUE = {'01':'札幌','02':'函館','03':'福島','04':'新潟','05':'東京','06':'中山','07':'中京','08':'京都','09':'阪神','10':'小倉'}
TARGET_MARKET_KEYS = {'odds','final_odds','final_popularity','popularity','payout','payouts','target_result','target_results','target_odds','target_popularity','actual_finish','win_probability','prediction_score'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return r3.digest(path)


def asset(ref, *, json_file=True):
    require(set(ref)==ASSET_FIELDS, 'invalid asset reference')
    p = Path(ref['path'])
    if json_file:
        return r3.load(p, ref['sha256'])
    require(re.fullmatch(r'[0-9a-f]{64}', ref['sha256']) and sha(p)==ref['sha256'], 'input SHA mismatch')
    return p


def validate(name, obj):
    s = json.loads((SCHEMAS/name).read_bytes())
    Draft202012Validator.check_schema(s)
    Draft202012Validator(s, format_checker=FormatChecker()).validate(obj)


def safe_sidecar(d):
    require(d['contract_version'] in SIDE_SCHEMAS and d['research_only'] is True and d['prediction_safe'] is False and
            d['production_authorized'] is False and d['as_of_exclusive']==d['target_date'] and
            d['policy']=='NO_ADDITIVE_VOTES_NO_FIT_VERDICT_NO_TARGET_RESULTS', 'unsafe R3 source')
    date.fromisoformat(d['target_date'])


def expected_targets(accepted, original):
    require(accepted['status']=='PASS_R3_TECHNICAL_COMMON_EVIDENCE_RESEARCH' and accepted['prediction_safe'] is False and
            accepted['production_authorized'] is False and accepted['research_only'] is True, 'R3 newcomer receipt not accepted')
    require(original['status']=='PASS_FIXED_SOURCE_RESEARCH_CONTRACT' and original['prediction_safe'] is False and original['production_authorized'] is False, 'R3 original receipt not accepted')
    news = r3.keyed(accepted['races'], lambda r:r['race_key_raw'])
    require(len(news)==accepted['accepted_races'] and sum(x['field_size'] for x in news.values())==accepted['accepted_horses'], 'newcomer receipt cardinality')
    # Older receipt identifies ordinary races by day, preview hash, and cohort;
    # no invented race key mapping is accepted. The exact detail+preview binds it.
    others = {}
    for p in original['proofs']:
        require(p['status']=='PASS_FIXED_SOURCE_PROJECTION_ONLY' and p['detail_schema_pass'], 'original proof not accepted')
        for r in p['races']:
            if r['cohort']!='NEWCOMER':
                k=r['preview_sha256']; require(k not in others, 'duplicate original preview')
                others[k]={'detail_sha256':p['detail_sha256'],'paci_sha256':p['source_asset_sha256']['paci'],
                           'target_date':p['target_date'],'field_size':r['field_size'],'coverage_status':r['coverage_status'],
                           'contract_version':NORMAL,'jpdb_evidence':r['counts']['jpdb_evidence'],
                           'brdb_observations':r['counts'].get('brdb_observations',0),
                           'population_scope':'GENERAL_STARTS_NOT_DEBUT_SPECIFIC' if r['coverage_status']=='DUAL_SOURCE_RESEARCH' else 'SOURCE_UNAVAILABLE'}
    return news,others


def target_from_detail(job, d, p, accept, paci):
    safe_sidecar(d)
    require(d['target_date']==accept['target_date'] and d['contract_version']==accept['contract_version'] and
            d['target_paci_sha256']==accept['paci_sha256']==job['paci']['sha256'], 'R3 target/date/source mismatch')
    require(job['detail']['sha256']==accept['detail_sha256'], 'R3 detail receipt mismatch')
    key=job['race_key']; rr=r3.keyed(d['races'],lambda x:x['race_key_raw']);require(key in rr,'R3 target race missing');r=rr[key]
    require(r['entry_count']==accept['field_size'] and r['coverage_status']==accept['coverage_status'], 'R3 coverage receipt mismatch')
    s,ps=SIDE_SCHEMAS[d['contract_version']];validate(s,d);validate(ps,p)
    expected=base.preview(d,key) if d['contract_version']==BASE else r3.reader_preview(d,key,job['detail']['sha256'])
    require(r3.encode(expected)==r3.encode(p)==Path(job['preview']['path']).read_bytes(), 'R3 preview projection drift')
    require(p['detail_sha256']==job['detail']['sha256'], 'R3 preview detail binding')
    bac,rosters=read_target_paci(paci,target_date=d['target_date'],expected_sha256=job['paci']['sha256'])
    b=bac[key]; raw=r3.keyed(rosters[key].values(),r3.identity); horses=r3.keyed(r['horses'],r3.identity)
    require(set(raw)==set(horses) and len(raw)==r['entry_count']==b['field_size'] and len({x[0] for x in raw})==len(raw) and len({x[1] for x in raw})==len(raw),'PACI all-registered identity mismatch')
    require(r['race_class_code']==b['race_class_code'] and r['surface_code']==b['surface_code'] and r['venue_code']==b['venue_code'] and r['distance_m']==int(b['distance_raw']) and r['is_newcomer_race']==(b['race_class_code']=='A1'),'PACI condition/cohort mismatch')
    for ident,h in horses.items():
        require(all(h[k]==raw[ident][k] for k in ('scheduled_jockey_code','entry_cancel_flag_raw')),'PACI scheduled jockey/cancel mismatch')
    return r,horses


def clean_blind(meta):
    return meta.get('market_blind') is True and meta.get('result_opened') is False and meta.get('target_market_opened') is False


def baseline_for(job, detail, race, horses):
    refs=job.get('baseline')
    if refs is None:
        return None, {'status':'BASELINE_READER_NOT_AVAILABLE'}
    require(set(refs)==BASELINE_FIELDS,'missing baseline seal inputs')
    x={k:asset(v) for k,v in refs.items()};op=x['operation'];s=x['session'];m=x['reader_manifest'];pr=x['prediction_handoff'];cf=x['confidence_handoff'];rd=x['reader']
    sid=s['session_id'];target=detail['target_date'];msha=refs['reader_manifest']['sha256']
    require(all(z['session_id']==sid and z['target_date']==target for z in (op,s,m,pr,cf)), 'baseline session/date mismatch')
    require(all(clean_blind(z) for z in (op,s,pr,cf)), 'baseline not clean blind')
    require(op['execution_mode']=='FORWARD' and op['status']=='READY_FOR_V056_AUTHORING' and s['status']=='SESSION_SEALED' and
            pr['status']=='PREDICTION_FROZEN_CLEAN_BLIND' and cf['status']=='CONFIDENCE_FROZEN_CLEAN_BLIND', 'baseline not sealed')
    require(all(z['reader_manifest_sha256']==msha for z in (op,s,pr)) and cf['prediction_records_sha256']==pr['records_sha256'], 'baseline freeze binding drift')
    require(op['paci']['sha256']==detail['target_paci_sha256'], 'baseline PACI mismatch')
    require(all(z['logic_version']=='RaceNote-Human-Context-Reader-0.5.6-candidate' for z in (op,s,m,pr,cf)), 'baseline logic version mismatch')
    v=rd['race'];num=int(race['race_key_raw'][-2:]);venue=VENUE[race['venue_code']]
    require(v['date']==target and v['venue']==venue and v['race_no']==num and v['distance_m']==race['distance_m'] and
            v['surface']=={'1':'芝','2':'ダート'}[race['surface_code']] and v['field_size']==race['entry_count'] and (v['class']=='新馬')==race['is_newcomer_race'], 'baseline race condition mismatch')
    ent=[e for e in m['entries'] if e['venue']==venue and e['race_no']==num]
    require(len(ent)==1 and ent[0]['derived_normal_sha256']==refs['reader']['sha256'] and
            ent[0]['derived_normal_filename']==Path(refs['reader']['path']).name and sorted(ent[0]['horse_nos'])==sorted(x[0] for x in horses), 'baseline reader manifest mismatch')
    rh=r3.keyed(rd['horses'],lambda h:r3.identity(h['identity']));require(set(rh)==set(horses),'baseline full-field identity mismatch')
    require(len({h[0] for h in rh})==len(rh),'baseline duplicate horse no')
    # Sealed Reader can contain prior race outcomes, not target outcomes. Audit explicit
    # source-run dates and any history refs; the accepted T1 seal remains authoritative.
    for h in rh.values():
        check_reader_history(h,target)
    return rh,{'status':'PASS_SEALED_V056_READER_MATCH','session_id':sid,'reader_manifest_sha256':msha,
               'reader_sha256':refs['reader']['sha256'],'prediction_records_sha256':pr['records_sha256'],
               'confidence_records_sha256':cf['confidence_records_sha256'], 'target_paci_sha256':op['paci']['sha256'],
               'baseline_logic':s['logic_version'],'reader_jockey_code':'NOT_EXPOSED_IN_READER; PACI_SCHEDULED_CODE_VERIFIED_SEPARATELY',
               'freeze_records_opened':False}


def check_reader_history(h,target):
    # Traverse known historical dates/references, including RaceReview source refs.
    # Past results remain legal. Reject explicit current/final market or target result keys.
    def walk(value,path=()):
        if isinstance(value,dict):
            for k,v in value.items():
                require(k.lower() not in TARGET_MARKET_KEYS,'forbidden market/target field in sealed Reader')
                if k in ('race_date','result_date') or (k=='date' and any(y in path for y in ('recent_runs','older_runs','source_run'))):
                    if v is not None:
                        require(isinstance(v,str) and date.fromisoformat(v).isoformat()<target,'nonprior historical Reader date')
                if k=='source_run_refs':
                    for ref in v:
                        require(isinstance(ref,str) and re.fullmatch(r'[0-9A-Za-z]{8}@\d{4}-\d{2}-\d{2}',ref) and date.fromisoformat(ref[-10:]).isoformat()<target,'nonprior history reference')
                walk(v,path+(k,))
        elif isinstance(value,list):
            for v in value:walk(v,path)
    walk(h)


def compare_windows(entries):
    """Comparison conflict by axis/comparator, not votes. Preserve references."""
    cells=defaultdict(list)
    for e in entries:
        if e['family']!='JPDB':continue
        for name,c in (e['comparison'] or {}).items():
            cells[(e['scope'],name)].append((e['evidence_id'],e['uncertainty']['window'],c))
    result=[]
    for (scope,name),rows in sorted(cells.items()):
        require(len({w for _,w,_ in rows})==len(rows),'duplicate comparison window')
        reported={c['across_windows_status'] for _,_,c in rows}; require(len(reported)==1,'inconsistent R2 cross-window status')
        directions={c['direction'] for _,_,c in rows if c['status']=='CONTEXTUAL' and c['direction'] in ('POSITIVE','NEGATIVE')}
        explicit='CONFLICTED' in reported
        if explicit or directions=={'POSITIVE','NEGATIVE'}:
            result.append({'scope':scope,'comparator':name,'r2_status':next(iter(reported)),
                           'contextual_opposite_directions':directions=={'POSITIVE','NEGATIVE'},
                           'evidence_ids':[i for i,_,_ in rows], 'interpretation':'DESCRIPTIVE_WINDOW_DISAGREEMENT_NOT_RIDER_ABILITY'})
    return result


def blood_contrast(entries):
    # Only compare sign descriptions for the same target surface/band and time.
    # A shared comparison baseline is required. This is not a contradiction in ability.
    a=[e for e in entries if e['family']=='BRDB:sire' and e['scope']=='ALL_VENUES_BAND']
    b=[e for e in entries if e['family']=='BRDB:broodmare_sire' and e['condition_relation']=='TARGET_CONDITION_OR_BROAD_CONTEXT' and e['condition'].get('distance_band') is not None]
    if len(a)!=1 or len(b)!=1:return {'status':'UNAVAILABLE_OR_NONUNIQUE'}
    s,t=a[0],b[0];ids=[s['evidence_id'],t['evidence_id']];c,d=s['condition'],t['condition'];u,v=s['comparison'],t['comparison']
    if not all(x['sample_status']=='DESCRIPTIVE' and x['observation'] and x['observation']['n']>0 for x in (s,t)):
        return {'status':'LOW_OR_NO_SAMPLE','evidence_ids':ids}
    if any(c.get(k)!=d.get(k) for k in ('surface_code','distance_band','venue_code','course_code','distance_m')) or any(s[k]!=t[k] for k in ('period_from_inclusive','period_to_exclusive')) or any(u[k]!=v[k] for k in ('baseline_n','baseline_top3_rate')):
        return {'status':'DIFFERENT_CONDITION_OR_BASELINE','evidence_ids':ids}
    x,y=u['top3_delta_pp'],v['top3_delta_pp']
    if x is None or y is None:return {'status':'UNAVAILABLE_DELTA','evidence_ids':ids}
    return {'status':'OPPOSING_DESCRIPTIVE_DELTAS' if x*y<0 else 'NO_OPPOSITE_SIGN_OBSERVED', 'evidence_ids':ids,
            'interpretation':'PARENT_LANES_OVERLAP_NOT_INDEPENDENT; NOT_A_FIT_VERDICT'}


def baseline_context(h):
    if h is None:return {'status':'BASELINE_UNAVAILABLE'}
    e=h.get('evidence',{});conn=e.get('CONNECTIONS',{});ctx=h.get('other_context',{});rr=ctx.get('racereview',{});p=ctx.get('pedigree',{});pc=ctx.get('pedigree_context',{});hist=ctx.get('history_coverage',{})
    conn_keys={k for z in conn.values() if isinstance(z,dict) for k,v in z.items() if v is not None}
    # Do not compare the heterogeneous index numerically with historical rates.
    return {'status':'BASELINE_MATCHED','existing_jockey_index':'jockey_index' in conn_keys,
            'existing_stable_index':'stable_index' in conn_keys,
            'jpdb_overlap':'POTENTIAL_CONNECTIONS_OVERLAP_NOT_QUANTIFIED' if 'jockey_index' in conn_keys else 'NO_JOCKEY_INDEX_OBSERVED',
            'existing_pedigree_status':p.get('coverage_status','MISSING'),
            'existing_pedigree_context_status':pc.get('coverage_status','MISSING'),
            'prior_recent_count':hist.get('recent_runs',{}).get('observed_count'),
            'prior_older_count':hist.get('older_runs',{}).get('observed_count'),
            'rrdb_history_status':rr.get('history_status','MISSING'),
            'rrdb_contradiction_status':rr.get('history_profile',{}).get('contradiction',{}).get('status') if isinstance(rr.get('history_profile'),dict) else None,
            'training_context_present':bool(ctx.get('training')),
            'cross_source_interpretation':'DIFFERENT_DENOMINATORS_OR_CONSTRUCTS_NOT_NUMERICALLY_COMPARABLE'}


def horse_audit(h,baseline_horse, target, newcomer):
    ev=h['evidence'];rs=h['restricted_refs'];items=r3.keyed(ev,lambda e:e['evidence_id']);refs=r3.keyed(rs,lambda e:e['evidence_id'])
    require(not set(items)&set(refs),'restricted/numeric overlap')
    counts=defaultdict(Counter);groups=Counter();denoms=Counter();new_n=0
    for e in ev:
        require(e['period_to_exclusive']==target and e['period_from_inclusive']<target and e['redundancy_group_id']==SHARED,'R3 cutoff/redundancy drift')
        require(e['uncertainty']['interpretation']=='DESCRIPTIVE_ONLY_NOT_CAUSAL','causal promotion')
        counts[e['family']][e['sample_status']]+=1;groups[e['native_overlap_group']]+=1
        o=e['observation'];last=e['uncertainty'].get('last_observed')
        require(last is None or last<target,'nonprior JPDB observation')
        if o is not None:
            denoms[o['denominator']]+=1
            require(0<=o['wins']<=o['top3']<=o['n'],'invalid observed counts')
            require(o['n']!=0 or (o['top3_rate'] is None and o['win_rate'] is None),'zero denominator numeric rate')
        if e['family']=='JPDB' and e['scope'].startswith('NEWCOMER_') and e['uncertainty']['window']=='ROLLING_3Y' and o is not None and o['n']>=30:
            new_n+=1
    require(all(e['as_of_status']=='AS_OF_UNVERIFIED' and 'observation' not in e and 'comparison' not in e for e in rs),'restricted numeric/as-of leak')
    require((newcomer and any(e['family']=='JPDB' and e['scope'].startswith('NEWCOMER_') for e in ev)) or (not newcomer and not any(e['scope'].startswith('NEWCOMER_') for e in ev)),'newcomer scope mismatch')
    j=[e for e in ev if e['family']=='JPDB'];b=[e for e in ev if e['family']!='JPDB']; bc=baseline_context(baseline_horse)
    return {'horse_no':h['horse_no'],'horse_id':h['horse_id'],'scheduled_jockey_code':h['scheduled_jockey_code'],
            'entry_cancel_flag_raw':h['entry_cancel_flag_raw'],'baseline_context':bc,
            'sample_counts':{k:dict(v) for k,v in sorted(counts.items())},'denominator_counts':dict(denoms),
            'native_overlap_groups':dict(groups),'cross_db_overlap_group':SHARED,
            'jpdb_evidence_ids':[e['evidence_id'] for e in j],'brdb_evidence_ids':[e['evidence_id'] for e in b],
            'restricted_ref_ids':[e['evidence_id'] for e in rs], 'restricted_numeric_exposed':False,
            'jpdb_cross_window_conflicts':compare_windows(j),'brdb_target_band_contrast':blood_contrast(b),
            'jpdb_newcomer_3y_cells_n_ge_30':new_n if newcomer else None,
            'brdb_debut_specific_status':'B5_TARGET_NOT_ACCEPTED' if newcomer else 'NOT_APPLICABLE',
            'evidence_use':'DESCRIPTIVE_REVIEW_ONLY_NO_ADDITIVE_VOTES_NO_FIT_VERDICT'}


def aggregate(r, rows, baseline_receipt, population):
    count=Counter();jp=Counter();br=Counter();contrast=Counter();rr=Counter()
    for h in rows:
        c=h['baseline_context'];count['horses']+=1;count['jpdb_horses']+=bool(h['jpdb_evidence_ids']);count['brdb_horses']+=bool(h['brdb_evidence_ids']);count['jpdb_evidence']+=len(h['jpdb_evidence_ids']);count['brdb_observations']+=len(h['brdb_evidence_ids']);count['restricted_refs']+=len(h['restricted_ref_ids'])
        jp.update(h['sample_counts'].get('JPDB',{}));br.update(h['sample_counts'].get('BRDB:sire',{}));br.update(h['sample_counts'].get('BRDB:broodmare_sire',{}));contrast[h['brdb_target_band_contrast']['status']]+=1
        count['horses_with_r2_conflicts']+=bool(h['jpdb_cross_window_conflicts']);count['r2_conflict_axes_comparators']+=len(h['jpdb_cross_window_conflicts'])
        if h['jpdb_newcomer_3y_cells_n_ge_30'] is not None:
            count['jpdb_newcomer_n_ge_30_horses']+=h['jpdb_newcomer_3y_cells_n_ge_30']>0
        if c['status']=='BASELINE_MATCHED':
            count['baseline_matched_horses']+=1;count['existing_jockey_index']+=c['existing_jockey_index'];count['existing_stable_index']+=c['existing_stable_index'];count['existing_training_context']+=c['training_context_present'];count['pedigree_context_none']+=c['existing_pedigree_context_status']=='NONE';count['baseline_no_recent_or_older_runs']+=(c['prior_recent_count']==0 and c['prior_older_count']==0);rr[c['rrdb_history_status']]+=1
    return {'race_key_raw':r['race_key_raw'],'cohort':'NEWCOMER_A1' if r['is_newcomer_race'] else 'OTHER_NON_A1',
            'coverage_status':r['coverage_status'],'brdb_population_scope':population,'counts':dict(count),
            'jpdb_sample_status_counts':dict(jp),'brdb_sample_status_counts':dict(br), 'blood_band_contrast_status_counts':dict(contrast),
            'baseline_rrdb_history_status_counts':dict(rr),'baseline':baseline_receipt,
            'shadow_status':'PASS_SEALED_READER_DESCRIPTIVE_SHADOW' if baseline_receipt['status']=='PASS_SEALED_V056_READER_MATCH' else 'R3_EVIDENCE_ONLY_BASELINE_PENDING',
            'debut_specific_status':'B5_TARGET_NOT_ACCEPTED' if r['is_newcomer_race'] else 'NOT_APPLICABLE'}


def run(manifest_path,pin,output):
    m=r3.load(manifest_path,pin);require(m['schema_version']=='racenote-r4-shadow-input-v1' and set(m)=={'schema_version','source_commit','r3_newcomer_receipt','r3_original_receipt','b5_reference_receipt','jobs'},'wrong R4 manifest')
    require(re.fullmatch(r'[0-9a-f]{40}',m['source_commit']),'invalid source commit')
    new=asset(m['r3_newcomer_receipt']);old=asset(m['r3_original_receipt']);b5=asset(m['b5_reference_receipt']);news,others=expected_targets(new,old)
    require(m['b5_reference_receipt']['sha256']==new['b5_reference_receipt_sha256'] and b5['status']=='PASS_RESEARCH_ONLY' and b5['prediction_safe'] is False and b5['production_authorized'] is False,'B5 reference receipt mismatch')
    b5keys={r['race_key'] for r in b5['summary']['races_coverage']};require(not set(news)&b5keys,'B5 targets overlap: use dedicated same-field acceptance before R4')
    jobs=r3.keyed(m['jobs'],lambda j:j['race_key']);done_news=set();done_others=set();private=[];public=[]
    for k,j in sorted(jobs.items()):
        require(set(j)=={'race_key','paci','detail','preview','baseline'},'unexpected job fields')
        d=asset(j['detail']);p=asset(j['preview']);paci=asset(j['paci'],json_file=False);isnew=k in news
        if isnew:
            a=news[k];require(j['preview']['sha256']==a['preview_sha256'],'newcomer preview receipt mismatch');done_news.add(k)
        else:
            pv=j['preview']['sha256'];require(pv in others and pv not in done_others,'ordinary receipt mismatch');a=others[pv];done_others.add(pv)
        r,hs=target_from_detail(j,d,p,a,paci);require(r['is_newcomer_race']==isnew,'receipt cohort drift')
        bh,base_receipt=baseline_for(j,d,r,hs)
        rows=[horse_audit(h,bh[ident] if bh is not None else None,d['target_date'],isnew) for ident,h in sorted(hs.items())]
        agg=aggregate(r,rows,base_receipt,a['population_scope']);require(agg['counts']['jpdb_evidence']==a['jpdb_evidence'] and agg['counts']['brdb_observations']==a['brdb_observations'],'R3 evidence count drift')
        if isnew:require(agg['counts']['restricted_refs']==a['restricted_refs'],'R3 restricted count drift')
        agg.update(target_date=d['target_date'],detail_sha256=j['detail']['sha256'],preview_sha256=j['preview']['sha256'],paci_sha256=j['paci']['sha256'],contract_version=d['contract_version'])
        private.append({'race':agg,'horses':rows});public.append(agg)
    require(done_news==set(news) and done_others==set(others),'incomplete accepted R3 target set')
    grouped={}
    for cohort in ('NEWCOMER_A1','OTHER_NON_A1'):
        rs=[r for r in public if r['cohort']==cohort];counts=Counter()
        for r in rs:counts.update(r['counts'])
        grouped[cohort]={'races':len(rs),'baseline_matched_races':sum(r['baseline']['status']=='PASS_SEALED_V056_READER_MATCH' for r in rs),'counts':dict(counts)}
    status='PARTIAL_R4_SHADOW_RESEARCH' # B5 same-field lane intentionally not certified by this contract.
    result={'schema_version':VERSION,'status':status,'source_commit':m['source_commit'],'input_manifest_sha256':pin,
            'research_only':True,'prediction_safe':False,'production_authorized':False,'r5_authorized':False,
            'no_target_outcomes_opened':True,'no_prediction_or_confidence_generated':True,'no_production_mutation':True,
            'races':public,'cohorts':grouped,'b5_reference':{'status':'PASS_OTHER_FIELDS_ONLY_NOT_TARGET','reference_races':len(b5keys),'reference_horses':b5['summary']['horses'],'receipt_sha256':m['b5_reference_receipt']['sha256']},
            'nonclaims':['TRUE_FORWARD_R4','STRICT_HISTORICAL_ASOF','B5_SAME_FIELD_ACCEPTANCE','PREDICTION_EFFECT','R5_AB','PRODUCTION_AUTHORIZATION']}
    private_payload={'schema_version':VERSION,'research_only':True,'prediction_safe':False,'production_authorized':False,'races':private}
    output=Path(output).resolve();require(not output.is_relative_to(REPO),'private output inside repository');output.mkdir(parents=True,exist_ok=False)
    raw=r3.encode(private_payload);(output/'PRIVATE_shadow.json').write_bytes(raw);result['private_shadow_sha256']=hashlib.sha256(raw).hexdigest();(output/'receipt.json').write_bytes(r3.encode(result))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.manifest,a.manifest_sha256,a.output_dir),ensure_ascii=False,sort_keys=True))
