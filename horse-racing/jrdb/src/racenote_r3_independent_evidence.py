#!/usr/bin/env python3
"""Research-only composition of accepted JPDB R1/R2 and BRDB M7.

No consumer integration, ranking, market, target results, or suitability scoring.
Use canonical R1 PACI roster parser. Full upstream files remain private.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from jpdb_r1_profile_builder import read_target_paci

VERSION = 'racenote-independent-evidence-v0.1-candidate'
WINDOWS = ('ROLLING_3Y', 'RECENT_365D', 'RECENT_90D')
COMPONENTS = ('sire', 'broodmare_sire', 'pairing', 'relatives')
AXES = frozenset(('ALL_FLAT','SURFACE','VENUE','SURFACE_DISTANCE_EXACT','CLASS_GRADE_RAW','GOING_RAW','COURSE_KEY','GEOMETRY_KEY','TURN_DIRECTION','FINAL_SLOPE','COURSE_SIZE','FINAL_STRAIGHT_M','VENUE_SURFACE','CLASS_ONLY','CLASS_SURFACE','NEWCOMER_ALL_FLAT','NEWCOMER_SURFACE','NEWCOMER_VENUE_SURFACE','NEWCOMER_SURFACE_DISTANCE_EXACT'))
CONDITION_KEYS = frozenset(('surface_code','venue_code','distance_m','distance_band','course_code','course_key','geometry_key','turn_direction','final_straight_slope_flag','course_size_class','final_straight_m','race_class_code','grade_code','track_condition_code'))
GROUPS = ('own_match','own_other','peer_match','peer_other')
COMPARE = ('within_rider','same_condition_peers','relative_condition_contrast')
STATUSES = frozenset(('CONTEXTUAL','INSUFFICIENT','UNAVAILABLE','CONFLICTED','REVIEW_REQUIRED','OBSERVED','DESCRIPTIVE_ONLY','NO_HISTORY','NO_OBSERVED_HISTORY','TARGET_CONDITION_UNAVAILABLE','UNCLASSIFIED','LOW_SAMPLE','NO_SAMPLE','DESCRIPTIVE','NOT_APPLICABLE','AVAILABLE','AS_OF_UNVERIFIED','SOURCE_UNAVAILABLE','NOT_IMPLEMENTED'))
DIRECTIONS = frozenset(('POSITIVE','NEGATIVE','NEAR_ZERO','UNCLASSIFIED'))
REL_SCOPE = frozenset(('VENUE_COURSE_EXACT','VENUE_DISTANCE','VENUE_BAND','ALL_VENUES_DISTANCE','ALL_VENUES_BAND'))

def require(ok, message):
    if not ok:
        raise ValueError(message)

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def load(path, sha):
    require(re.fullmatch('[0-9a-f]{64}',sha or '') and digest(path)==sha,'input SHA mismatch')
    def unique(pairs):
        out={}
        for k,v in pairs:
            require(k not in out,'duplicate JSON key')
            out[k]=v
        return out
    return json.loads(Path(path).read_bytes(),object_pairs_hook=unique,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def keyed(rows,key):
    out={}
    for row in rows:
        k=key(row);require(k not in out,'duplicate identity');out[k]=row
    return out

def identity(h):
    require(type(h['horse_no']) is int and 1<=h['horse_no']<=99,'horse number invalid')
    require(isinstance(h['horse_id'],str) and re.fullmatch('[0-9]{8}',h['horse_id']) and h['horse_id']!='00000000','horse ID invalid')
    return h['horse_no'],h['horse_id']

def state(x):
    require(x in STATUSES,'unknown upstream status');return x

def direction(x):
    require(x in DIRECTIONS,'unknown or unapproved direction');return x

def condition(c):
    require(isinstance(c,dict) and set(c)<=CONDITION_KEYS,'unknown condition field')
    require(all(v is None or type(v) in (str,int,float,bool) for v in c.values()),'non-scalar condition')
    return dict(c)

def day(s):
    require(isinstance(s,str) and date.fromisoformat(s).isoformat()==s,'invalid date');return s

def count(x):
    require(type(x) is int and x>=0,'invalid count');return x

def rate(x):
    require(x is None or type(x) in (float,int) and 0<=x<=1,'invalid rate');return x

def number(x):
    require(x is None or type(x) in (float,int) and -200<=x<=200,'invalid difference');return x

def bounds(x):
    if x is None:return None
    require(len(x)==2 and x[0]<=x[1],'invalid bounds');return [number(v) for v in x]

def label(x):
    require(isinstance(x,str) and 0<len(x)<=200,'invalid label');return x

def obs(n,w,t,*,top2=None,unique=None,win_rate=None,top3_rate=None,unresolved=None,denominator):
    n,w,t=map(count,(n,w,t));require(w<=t<=n,'inconsistent count')
    if top2 is not None:require(w<=count(top2)<=t,'inconsistent top2')
    if unique is not None:require(count(unique)<=n,'inconsistent unique horses')
    if unresolved is not None:count(unresolved)
    require(n>0 or win_rate is None and top3_rate is None,'zero starts must be null')
    if n:
        if win_rate is not None:require(abs(win_rate-w/n)<=0.000051,'win rate mismatch')
        if top3_rate is not None:require(abs(top3_rate-t/n)<=0.000051,'top3 rate mismatch')
    return {'n':n,'wins':w,'top2':top2,'top3':t,'unique_horses':unique,'win_rate':rate(win_rate),'top3_rate':rate(top3_rate),'unresolved':unresolved,'denominator':denominator}

def item(eid,family,scope,c,source_ref,source_status,sample_status,asof,period_from,target,observation,comparison,uncertainty,source_group,relation):
    return {'evidence_id':eid,'family':family,'scope':scope,'condition':condition(c),'source_ref':source_ref,'source_status':state(source_status),'sample_status':state(sample_status),'as_of_status':asof,'period_from_inclusive':period_from,'period_to_exclusive':target,'observation':observation,'comparison':comparison,'uncertainty':uncertainty,'redundancy_group_id':'SHARED_JRDB_HISTORY_NOT_INDEPENDENT','native_overlap_group':source_group,'condition_relation':relation}

def jp_items(h1,h2,key,target):
    require(identity(h1)==identity(h2) and h1['scheduled_jockey_code']==h2['scheduled_jockey_code'] and h1['entry_cancel_flag_raw']==h2['entry_cancel_flag_raw'],'R1/R2 identity mismatch')
    require(set(h1['windows'])==set(WINDOWS),'unexpected R1 windows')
    axes=keyed(h2['axes'],lambda x:x['dimension']);require(set(axes)<=AXES,'unknown axis')
    entries=[]
    for window in WINDOWS:
        w=h1['windows'][window];start=day(w['period_from_inclusive']);require(start<target and w['period_to_exclusive']==target,'R1 cutoff mismatch')
        cells=keyed(w['evidence'],lambda e:e['dimension']);require(set(cells)==set(axes),'R1/R2 axis mismatch')
        for dim,e in cells.items():
            a=axes[dim];v=a['windows'][window];require(set(a['windows'])==set(WINDOWS),'R2 window mismatch')
            require(a['condition']==e['condition'] and a['redundancy_group_id']==e['redundancy_group_id'] and v['period_from_inclusive']==start and v['period_to_exclusive']==target and v['r1_evidence_id']==e['evidence_id'],'R1/R2 evidence binding mismatch')
            eid=f'{key}:{h1["horse_no"]:02d}:{window}:{dim}';require(eid==e['evidence_id'],'R1 evidence ID mismatch')
            m=e['metrics'];g=v['groups'];o=None;cmp=None;unc={'interpretation':'DESCRIPTIVE_ONLY_NOT_CAUSAL','window':window,'first_observed':None,'last_observed':None,'group_counts':None,'excluded_unknown_condition':None,'excluded_invalid_jockey':None}
            if m is not None:
                for t in ('first_observed','last_observed'):
                    if m[t] is not None:require(start<=day(m[t])<target,'future observation');unc[t]=m[t]
                o=obs(m['actual_starts_candidate'],m['wins'],m['top3'],top2=m['top2'],win_rate=m['start_basis_win_rate_candidate'],top3_rate=m['start_basis_top3_rate_candidate'],unresolved=m['unresolved_count'],denominator='JPDB_CANDIDATE_STARTS')
                if g is not None:
                    require(set(g)==set(GROUPS),'R2 group mismatch')
                    own=g['own_match'];require(own['resolved_starts']+own['unresolved']==o['n'] and own['wins']==o['wins'] and own['top3']==o['top3'],'R1/R2 count mismatch')
                    unc['group_counts']={name:{'resolved_n':count(g[name]['resolved_starts']),'unresolved_n':count(g[name]['unresolved']),'top3':count(g[name]['top3']),'wins':count(g[name]['wins']),'top3_rate':rate(g[name]['top3_rate_resolved'])} for name in GROUPS}
                    unc['excluded_unknown_condition']=count(v['excluded_unknown_condition_entries_in_window']);unc['excluded_invalid_jockey']=count(v['excluded_invalid_jockey_entries_in_window'])
                    require(set(v['comparisons'])<=set(COMPARE) and set(a['window_summary'])<=set(COMPARE),'unknown comparison')
                    cmp={}
                    for name,c in v['comparisons'].items():
                        s=a['window_summary'][name];status=state(c['status']);d=direction(c['direction']);ss=state(s['status']);sd=direction(s['direction'])
                        if ss=='CONFLICTED':sd='UNCLASSIFIED'
                        if status!='CONTEXTUAL':d='UNCLASSIFIED'
                        cmp[name]={'status':status,'direction':d,'top3_delta_pp':number(c['top3_delta_pp']),'wins_delta_pp':number(c['wins_delta_pp']),'top3_unresolved_bounds_pp':bounds(c['top3_unresolved_bounds_pp']),'wins_unresolved_bounds_pp':bounds(c['wins_unresolved_bounds_pp']),'across_windows_status':ss,'across_windows_direction':sd}
                else:require(not v['comparisons'],'missing groups with comparisons')
            else:require(g is None and not v['comparisons'],'unavailable R1 has R2 values')
            entries.append(item('JPDB:'+eid,'JPDB',dim,e['condition'],{'asset':'jpdb_r1+r2','id':eid},e['source_status'],e['status'],'PRIOR_DAY_ASSUMED_NOT_STRICTLY_ATTESTED',start,target,o,cmp,unc,e['redundancy_group_id'],'TARGET_CONDITION_OR_BROAD_CONTEXT'))
    return entries

def br_items(h,rel,raw,key,target,surface,history_from):
    require(identity(h)==identity(rel)==identity(raw),'BRDB relative/①② identity mismatch')
    require(h['confidence']=='UNASSESSED' and h['summary'] is None and all(not x for x in h['factors'].values()),'unexpected BRDB suitability verdict')
    require(set(h['components'])==set(COMPONENTS),'BRDB component set mismatch')
    ev=keyed(h['evidence'],lambda e:e['evidence_id']);require(set(ev)=={i for c in h['components'].values() for i in c['evidence_ids']},'BRDB reference mismatch')
    require(all(len(c['evidence_ids'])==len(set(c['evidence_ids'])) for c in h['components'].values()),'BRDB duplicate refs')
    items=[];restricted=[];base=f'{key}:{h["horse_no"]:02d}:'
    target_band=next(e['condition']['distance_band'] for e in ev.values() if e['component']=='sire' and e['scope_key']=='ALL_VENUES_BAND')
    require(target_band in ('SHORT','MILE','MIDDLE','LONG'),'unknown BRDB band')
    for eid,e in ev.items():
        family=e['component'];require(family in COMPONENTS and eid in h['components'][family]['evidence_ids'] and e['as_of_exclusive']==target,'BRDB evidence scope/cutoff mismatch')
        avail=state(h['components'][family]['availability']);ss=state(e['sample_status']);c=condition(e['condition']);scope=label(e['scope_key']);ref={'asset':'brdb_v03','id':eid}
        if family in ('pairing','relatives'):
            require(avail=='AS_OF_UNVERIFIED','unverified family promotion');restricted.append({'evidence_id':'BRDB:'+base+eid,'family':family,'scope':scope,'source_ref':ref,'source_status':avail,'sample_status':ss,'as_of_status':'AS_OF_UNVERIFIED','reason':'NOT_IN_READER_NUMERIC_LANE'});continue
        require(family in ('sire','broodmare_sire') and e['evidence_kind']=='OBSERVED_CONDITIONAL_RESULT','unsupported BRDB observation')
        m=e['observations']
        if family=='sire':
            orig=raw['sire_evidence']['scopes'][scope]
        elif scope.startswith('SURFACE_'):
            orig=raw['bms_evidence']['surface'][c['surface_code']]
        else:orig=raw['bms_evidence']['surface_band'][scope]
        require(orig['status']==ss and orig['horses']==m['unique_horses'] and all(orig[k]==m[k] for k in ('starts','wins','top3','win_rate','top3_rate','top3_wilson95','baseline_starts','baseline_top3_rate','top3_delta_pp')),'BRDB ①② observation drift')
        o=obs(m['starts'],m['wins'],m['top3'],unique=m['unique_horses'],win_rate=m['win_rate'],top3_rate=m['top3_rate'],denominator='BRDB_ACTUAL_STARTS')
        require((o['n']==0)==(ss=='NO_SAMPLE'),'BRDB zero sample mismatch')
        relation=('OTHER_SURFACE_CONTEXT' if c.get('surface_code')!=surface else 'OTHER_DISTANCE_BAND_CONTEXT' if c.get('distance_band') not in (None,target_band) else 'TARGET_CONDITION_OR_BROAD_CONTEXT')
        cmp={'baseline_n':count(m['baseline_starts']),'baseline_top3_rate':rate(m['baseline_top3_rate']),'top3_delta_pp':number(m['top3_delta_pp'])}
        u={'interpretation':'DESCRIPTIVE_ONLY_NOT_CAUSAL','top3_wilson95':None if m['top3_wilson95'] is None else [rate(x) for x in m['top3_wilson95']]}
        items.append(item('BRDB:'+base+eid,'BRDB:'+family,scope,c,ref,avail,ss,'STORED_HISTORY_RESEARCH_NOT_STRICTLY_ATTESTED',history_from,target,o,cmp,u,e['overlap_group'],relation))
    # Preserve precise native references, not unverified numeric content. No invented baseline.
    rel_ids=set()
    for j,r in enumerate(rel['relatives']):
        eid=f'REL_{h["horse_id"]}_{r["horse_id"]}_{r["relationship"]}'
        require(eid in ev and ev[eid]['component']=='relatives' and eid not in rel_ids,'relative evidence mismatch');rel_ids.add(eid)
        require(set(r['scope_stats'])==REL_SCOPE,'relative scope mismatch')
        for scope,m in sorted(r['scope_stats'].items()):
            obs(m['starts'],m['wins'],m['top3'],top3_rate=m['top3_rate'],denominator='BRDB_ACTUAL_STARTS')
            restricted.append({'evidence_id':'BRDB_DETAIL:'+base+eid+':'+scope,'family':'relatives','scope':scope,'source_ref':{'asset':'brdb_relatives_detail','id':eid+':'+scope},'source_status':'AS_OF_UNVERIFIED','sample_status':'NO_SAMPLE' if m['starts']==0 else 'DESCRIPTIVE','as_of_status':'AS_OF_UNVERIFIED','reason':'NOT_IN_READER_NUMERIC_LANE'})
    require(rel_ids==set(h['components']['relatives']['evidence_ids']),'relative reference set mismatch')
    for j,s in enumerate(h['supplemental_insights']):
        require(s['contribution_to_score'] is None and s['interpretation_status']=='OBSERVATION_ONLY_AS_OF_UNVERIFIED','unexpected supplemental promotion')
        restricted.append({'evidence_id':'BRDB_D4:'+base+str(j),'family':'supplemental','scope':label(s['scope_key']),'source_ref':{'asset':'brdb_v03','id':f'supplemental_insights/{j}'},'source_status':'AS_OF_UNVERIFIED','sample_status':'NOT_APPLICABLE','as_of_status':'AS_OF_UNVERIFIED','reason':'NOT_IN_READER_NUMERIC_LANE'})
    return items,restricted,{k:state(h['components'][k]['availability']) for k in COMPONENTS}

def build(r1,r2,paci_path,paci_sha,*,source_assets,brdb=None,relatives=None,sire_bms=None):
    require(r1['schema_version']=='jpdb-r1-jockey-profile-v0.1-candidate' and r2['schema_version']=='jpdb-r2-condition-context-v0.1-candidate','unsupported JPDB version')
    target=day(r1['target_date']);require(r2['target_date']==target and r1['source']==r2['source'] and r1['source']['target_paci_sha256']==paci_sha,'JPDB source/cutoff mismatch')
    require(r1['prediction_safe'] is False and r2['prediction_safe'] is False and r1['source']['strict_asof_certified'] is False and r2['policy']['suggestive_allowed'] is False,'research status mismatch')
    bac,rosters=read_target_paci(Path(paci_path),target_date=target,expected_sha256=paci_sha)
    races1=keyed(r1['races'],lambda r:r['race_key_raw']);races2=keyed(r2['races'],lambda r:r['race_key_raw']);require(set(races1)==set(races2) and set(races1)<=set(bac),'JPDB race mismatch')
    require((brdb is None)==(relatives is None)==(sire_bms is None),'BRDB incomplete input set')
    bkey=None
    if brdb is not None:
        require(brdb['contract_version']=='brdb-integrated-blood-review-v0.3-candidate' and brdb['release_status']=='RESEARCH_CANDIDATE' and brdb['supplemental_research']['prediction_safe'] is False and brdb['supplemental_research']['historical_asof_status']=='AS_OF_UNVERIFIED' and brdb['as_of_exclusive']==target,'BRDB version/cutoff mismatch')
        require(relatives['contract_version']=='brdb-m7-relatives-detail-v0.1-candidate' and relatives['prediction_safe'] is False and relatives['historical_asof_status']=='AS_OF_UNVERIFIED' and relatives['source_metadata']['as_of_exclusive']==target,'BRDB detail version/cutoff mismatch')
        bkey=brdb['race']['race_key'];require(bkey in races1 and brdb['source_generations']['paci']==paci_sha,'BRDB PACI binding mismatch')
        require(brdb['source_generations']['brdb']==relatives['source_metadata']['pedigree_generation'] and brdb['source_generations']['jrdb_analysis']==relatives['source_metadata']['analysis_generation'],'BRDB generation mismatch')
        require(hashlib.sha256(encode(brdb)).hexdigest()==relatives['integrated_v03_canonical_sha256'],'BRDB detail canonical binding mismatch')
        require(hashlib.sha256(encode({**relatives['source_metadata'],'horses':relatives['horses']})).hexdigest()==relatives['source_canonical_sha256'],'BRDB original detail tree mismatch')
        bh=keyed(brdb['horses'],identity);rh=keyed(relatives['horses'],identity);sh=keyed(sire_bms['horses'],identity)
        require(sire_bms['version']=='brdb-sire-bms-field-evidence-v0.2' and sire_bms['source_generation']==brdb['source_generations']['jrdb_analysis'] and sire_bms['policy']['as_of_exclusive']==target and sire_bms['race']==relatives['source_metadata']['race'],'BRDB ①② source mismatch')
        history_from=day(sire_bms['policy']['historical_window_start']);require(history_from<target,'BRDB invalid history window')
        require(set(bh)==set(rh)==set(sh),'BRDB full-field identity mismatch')
        rc=relatives['aggregate_coverage'];nrel=sum(len(h['relatives']) for h in rh.values());require(rc['field_size']==rc['reviewed_horses']==len(rh) and rc['relative_records']==nrel and rc['scope_observations']==nrel*5 and rc['zero_start_cells']==sum(s['starts']==0 for h in rh.values() for rel in h['relatives'] for s in rel['scope_stats'].values()),'BRDB detail coverage mismatch')
    out=[]
    for key,r in sorted(races1.items()):
        s=races2[key];b=bac[key];roster=keyed(rosters[key].values(),identity);h1=keyed(r['horses'],identity);h2=keyed(s['horses'],identity)
        require(set(h1)==set(h2)==set(roster) and len({hid for _,hid in roster})==len(roster) and len(roster)==r['entry_count']==s['entry_count']==b['field_size'],'PACI/JPDB full-field mismatch')
        require(r['surface_code']==b['surface_code'] and r['distance_m']==int(b['distance_raw']) and r['venue_code']==b['venue_code'] and r['race_class_code']==b['race_class_code'] and r['is_newcomer_race']==s['is_newcomer_race']==(b['race_class_code']=='A1'),'PACI race condition mismatch')
        present=key==bkey
        if present:
            br=brdb['race'];rd=relatives['source_metadata']['race'];require(set(bh)==set(roster) and br['field_size']==len(roster),'BRDB roster mismatch')
            require(br['target_date']==rd['target_date']==target and br['race_key']==rd['race_key']==key and br['surface_code']==rd['surface_code']==b['surface_code'] and br['venue_code']==rd['venue_code']==b['venue_code'] and br['distance_m']==rd['distance']==int(b['distance_raw']) and br['course_code']==rd['course_code']==b['course_code'],'BRDB target condition mismatch')
        horses=[]
        for ident,h in sorted(roster.items()):
            require(all(h[k]==h1[ident][k] for k in ('scheduled_jockey_code','entry_cancel_flag_raw')),'PACI scheduled jockey mismatch')
            je=jp_items(h1[ident],h2[ident],key,target)
            be,restricted,components=br_items(bh[ident],rh[ident],sh[ident],key,target,b['surface_code'],history_from) if present else ([],[],{k:'SOURCE_UNAVAILABLE' for k in COMPONENTS})
            require(len({e['evidence_id'] for e in je+be+restricted})==len(je)+len(be)+len(restricted),'duplicate evidence ID')
            horses.append({'horse_no':ident[0],'horse_id':ident[1],'scheduled_jockey_code':h['scheduled_jockey_code'],'entry_cancel_flag_raw':h['entry_cancel_flag_raw'],'jpdb_status':'RESEARCH_CONTEXT_ONLY','brdb_status':'RESEARCH_DESCRIPTIVE_PARTIAL' if present else 'SOURCE_UNAVAILABLE','brdb_components':components,'evidence':je+be,'restricted_refs':restricted})
        out.append({'race_key_raw':key,'venue_code':b['venue_code'],'surface_code':b['surface_code'],'distance_m':int(b['distance_raw']),'race_class_code':b['race_class_code'],'is_newcomer_race':r['is_newcomer_race'],'entry_count':len(roster),'coverage_status':'DUAL_SOURCE_RESEARCH' if present else 'JPDB_ONLY_BRDB_UNAVAILABLE','horses':horses})
    return {'contract_version':VERSION,'research_only':True,'prediction_safe':False,'production_authorized':False,'target_date':target,'as_of_exclusive':target,'target_paci_sha256':paci_sha,'source_assets':source_assets,'policy':'NO_ADDITIVE_VOTES_NO_FIT_VERDICT_NO_TARGET_RESULTS','races':out}

CORE_AXES = ('ALL_FLAT','SURFACE','VENUE_SURFACE','SURFACE_DISTANCE_EXACT',
             'NEWCOMER_ALL_FLAT','NEWCOMER_SURFACE','NEWCOMER_VENUE_SURFACE','NEWCOMER_SURFACE_DISTANCE_EXACT')

JOCKEY_COLUMNS = ('evidence_id','scope','condition','source_status','sample_status','period_from','n','wins','top2','top3','win_rate','top3_rate','unresolved','comparison_kind','comparison_3y_status','comparison_top3_delta_pp','comparison_unresolved_bounds_pp','across_windows_status','across_windows_direction','group_counts')
BLOOD_COLUMNS = ('evidence_id','family','scope','condition','source_status','sample_status','period_from','n','unique_horses','wins','top3','win_rate','top3_rate','baseline_n','baseline_top3_rate','top3_delta_pp','top3_wilson95')
GROUP_COLUMNS = ('resolved_n','unresolved_n','wins','top3')

def reader_preview(sidecar, race_key, sidecar_sha):
    """Fixed, value-independent display subset; details remain hash-addressable.

    Row arrays use one explicit column dictionary per race. The independent
    detailed sidecar is the source of short-window facts and all omitted rows.
    No production Reader accepts this contract without a separate adapter.
    """
    require(sidecar['contract_version']==VERSION and sidecar['prediction_safe'] is False,'wrong sidecar contract')
    require(hashlib.sha256(encode(sidecar)).hexdigest()==sidecar_sha,'sidecar SHA mismatch')
    race=keyed(sidecar['races'],lambda r:r['race_key_raw'])[race_key]
    horses=[]
    for h in race['horses']:
        jockey=[];blood=[]
        for e in h['evidence']:
            is_j=e['family']=='JPDB';o=e['observation'] or {}
            if is_j:
                if e['scope'] not in CORE_AXES or e['uncertainty']['window']!='ROLLING_3Y':continue
                name='same_condition_peers' if e['scope']=='ALL_FLAT' else 'relative_condition_contrast'
                v=(e['comparison'] or {}).get(name,{})
                status=v.get('across_windows_status');direction=v.get('across_windows_direction') if status=='CONTEXTUAL' else 'UNCLASSIFIED'
                groups=e['uncertainty']['group_counts']
                row=[e[k] for k in ('evidence_id','scope','condition','source_status','sample_status','period_from_inclusive')]+[o.get(k) for k in ('n','wins','top2','top3','win_rate','top3_rate','unresolved')]+[name if v else None,v.get('status'),v.get('top3_delta_pp'),v.get('top3_unresolved_bounds_pp'),status,direction,[[groups[g][k] for k in GROUP_COLUMNS] for g in GROUPS] if groups is not None else None]
                require(len(row)==len(JOCKEY_COLUMNS),'preview jockey width');jockey.append(row)
            else:
                if e['condition_relation']!='TARGET_CONDITION_OR_BROAD_CONTEXT':continue
                row=[e[k] for k in ('evidence_id','family','scope','condition','source_status','sample_status','period_from_inclusive')]+[o.get(k) for k in ('n','unique_horses','wins','top3','win_rate','top3_rate')]+[e['comparison'][k] for k in ('baseline_n','baseline_top3_rate','top3_delta_pp')]+[e['uncertainty']['top3_wilson95']]
                require(len(row)==len(BLOOD_COLUMNS),'preview blood width');blood.append(row)
        horses.append({k:h[k] for k in ('horse_no','horse_id','scheduled_jockey_code','entry_cancel_flag_raw','jpdb_status','brdb_status','brdb_components')}|{'jockey':jockey,'blood':blood,'detail_evidence_count':len(h['evidence']),'omitted_detail_count':len(h['evidence'])-len(jockey)-len(blood),'restricted_ref_count':len(h['restricted_refs'])})
    return {'contract_version':'racenote-independent-evidence-preview-v0.1-candidate','research_only':True,'prediction_safe':False,'production_authorized':False,'target_date':sidecar['target_date'],'as_of_exclusive':sidecar['as_of_exclusive'],'target_paci_sha256':sidecar['target_paci_sha256'],'detail_sha256':sidecar_sha,'policy':'FIXED_DISPLAY_SUBSET_NOT_EVIDENCE_WEIGHT; NO_ADDITIVE_VOTES; AS_OF_NOT_STRICTLY_ATTESTED','jockey_window':'ROLLING_3Y','jockey_denominator':'JPDB_CANDIDATE_STARTS','jockey_asof':'PRIOR_DAY_ASSUMED_NOT_STRICTLY_ATTESTED','blood_denominator':'BRDB_ACTUAL_STARTS','blood_asof':'STORED_HISTORY_RESEARCH_NOT_STRICTLY_ATTESTED','blood_interpretation':'DESCRIPTIVE_ONLY_NO_DIRECTION','redundancy_group_id':'SHARED_JRDB_HISTORY_NOT_INDEPENDENT','columns':{'jockey':JOCKEY_COLUMNS,'blood':BLOOD_COLUMNS,'group_order':GROUPS,'group_counts':GROUP_COLUMNS},'race':{k:v for k,v in race.items() if k!='horses'},'horses':horses}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--manifest-sha256',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--preview-dir',type=Path);a=ap.parse_args()
    manifest=load(a.manifest,a.manifest_sha256);require(manifest['schema_version']=='racenote-r3-private-input-manifest-v1','unsupported manifest')
    files=manifest['assets'];required={'jpdb_r1','jpdb_r2','paci','jpdb_r1_receipt','jpdb_r2_receipt'};optional={'brdb_v03','brdb_relatives_detail','brdb_m7_receipt','brdb_detail_receipt','brdb_sire_bms'};require(set(files)==required or set(files)==required|optional,'asset set mismatch')
    paths={k:Path(v['path']) for k,v in files.items()};sha={k:v['sha256'] for k,v in files.items()};obj={k:load(paths[k],sha[k]) for k in files if k!='paci'};d=obj['jpdb_r1']['target_date']
    p1=keyed(obj['jpdb_r1_receipt']['proofs'],lambda x:x['target_date'])[d];p2=keyed(obj['jpdb_r2_receipt']['profile_proofs'],lambda x:x['date'])[d];require(obj['jpdb_r1_receipt']['status']=='PASS' and obj['jpdb_r2_receipt']['status']=='PASS_RESEARCH_CONTEXT_ONLY' and p1['profile_sha256']==p2['r1_profile_sha256']==sha['jpdb_r1'] and p1['target_paci_sha256']==sha['paci'] and p2['r2_context_sha256']==sha['jpdb_r2'],'JPDB receipt mismatch')
    if 'brdb_v03' in obj:
        m=obj['brdb_m7_receipt'];r=obj['brdb_detail_receipt'];require(m['status']=='RESEARCH_FIELD_COMPOSITION_PASS' and r['status']=='RESEARCH_ONLY_PASS' and m['output_sha256']['v03']==r['input_sha256']['integrated_v03_bytes']==sha['brdb_v03'] and r['output_sha256']['relatives_detail']==sha['brdb_relatives_detail'] and m['inputs_sha256']['paci']==sha['paci'] and m['inputs_sha256']['sire_bms']==sha['brdb_sire_bms'],'BRDB receipt mismatch')
    source_assets={k:{'sha256':sha[k]} for k in sorted(files)};source_assets['jpdb_r1+r2']={'sha256':sha['jpdb_r1'],'context_sha256':sha['jpdb_r2']};source_assets['jpdb_history']={k:obj['jpdb_r1']['source'][k] for k in ('historical_generation','historical_manifest_sha256','daily_sed_manifest_sha256','daily_paci_bac_manifest_sha256','course_seed_sha256','asof_policy','target_version_status')}
    if 'brdb_v03' in obj:source_assets['brdb_generations']=obj['brdb_v03']['source_generations']
    result=build(obj['jpdb_r1'],obj['jpdb_r2'],paths['paci'],sha['paci'],source_assets=source_assets,brdb=obj.get('brdb_v03'),relatives=obj.get('brdb_relatives_detail'),sire_bms=obj.get('brdb_sire_bms'));a.output.write_bytes(encode(result))
    if a.preview_dir is not None:
        a.preview_dir.mkdir(parents=True,exist_ok=True)
        for race in result['races']:
            preview=reader_preview(result,race['race_key_raw'],digest(a.output));(a.preview_dir/f"{race['race_key_raw']}.json").write_bytes(encode(preview))

if __name__=='__main__':main()
