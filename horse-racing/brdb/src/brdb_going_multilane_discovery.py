#!/usr/bin/env python3
"""BRDB v0.6 research-only multi-lane going-state discovery.

Splits JRDB going into 良/稍重/重/不良 and observes the target horse's
sire, broodmare-sire and sire-line x broodmare-sire-line pairing on the same
surface/scope. Optionally projects existing M7 maternal-relative condition
observations. Cross-lane alignment is descriptive only: overlapping cohorts,
shared ancestry and historical-profile as-of limitations mean it is never
independent corroboration or an aptitude/prediction claim.
"""
from __future__ import annotations

import math
from collections import Counter

VERSION = 'brdb-going-multilane-discovery-v0.6-candidate'
GOING_STATES = ('良','稍重','重','不良')
NON_GOOD = ('稍重','重','不良')
SCOPE_PRIORITY = ('VENUE_COURSE_DISTANCE','VENUE_DISTANCE','ALL_VENUES_DISTANCE','VENUE_BAND','ALL_VENUES_BAND')
REL_SCOPE_MAP = {
    'VENUE_COURSE_DISTANCE':'VENUE_COURSE_EXACT',
    'VENUE_DISTANCE':'VENUE_DISTANCE',
    'ALL_VENUES_DISTANCE':'ALL_VENUES_DISTANCE',
    'VENUE_BAND':'VENUE_BAND',
    'ALL_VENUES_BAND':'ALL_VENUES_BAND',
}


def require(ok, why):
    if not ok: raise ValueError(why)


def rate(n, k): return round(k/n, 6) if n else None


def wilson(k, n, z=1.959963984540054):
    require(type(k) is int and type(n) is int and 0 <= k <= n, 'invalid Wilson counts')
    if not n: return {'low':None,'high':None}
    p=k/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return {'low':round(max(0.0,center-half),6),'high':round(min(1.0,center+half),6)}


def stat(n,w,t):
    require(all(type(x) is int and x>=0 for x in (n,w,t)) and w<=t<=n,'invalid counts')
    return {'starts':n,'wins':w,'top3':t,'win_rate':rate(n,w),'top3_rate':rate(n,t)}


def compare_state(good, state_counts):
    g=stat(*good); s=stat(*state_counts)
    observed=g['starts']>0 and s['starts']>0
    delta=round(100*(s['top3_rate']-g['top3_rate']),2) if observed else None
    tier='NONE'
    separated=False
    if observed:
        gw=wilson(g['top3'],g['starts']); sw=wilson(s['top3'],s['starts'])
        separated=(sw['low']>gw['high']) or (gw['low']>sw['high'])
        mn=min(g['starts'],s['starts']); ad=abs(delta)
        if mn>=30 and ad>=8 and separated: tier='STRONG_DESCRIPTIVE'
        elif mn>=20 and ad>=5: tier='NOTABLE_DESCRIPTIVE'
        elif mn>=5 and ad>=10: tier='LOW_SAMPLE_SIGNAL'
    else:
        gw=wilson(g['top3'],g['starts']); sw=wilson(s['top3'],s['starts'])
    return {
        'good':g,'state_counts':s,
        'comparison_status':'OBSERVED' if observed else 'INSUFFICIENT_COMPARISON',
        'difference_top3_pp':delta,
        'direction':None if delta is None else ('STATE_HIGHER' if delta>0 else 'GOOD_HIGHER' if delta<0 else 'EQUAL'),
        'tier':tier,'wilson95_nonoverlap':separated,
        'good_wilson95':gw,'state_wilson95':sw,
        'interpretation_status':'OBSERVATION_ONLY','prediction_eligible':False,
        'display_eligible':False,'suitability_claim':False,
    }


def _lane_evidence_id(horse_id,lane,scope,state):
    return f'GOING06:{horse_id}:{lane}:{scope}:{state}'


def _primary(selected):
    if not selected:return None
    rank={s:i for i,s in enumerate(SCOPE_PRIORITY)}
    return sorted(selected,key=lambda x:(rank[x['scope_key']], {'STRONG_DESCRIPTIVE':0,'NOTABLE_DESCRIPTIVE':1,'LOW_SAMPLE_SIGNAL':2}[x['tier']], -abs(x['difference_top3_pp'])))[0]



def relative_links_from_lanes(lanes, relative_condition):
    """Link only each lane/state primary signal to existing relative condition observations."""
    if not relative_condition:
        return []
    grouped=relative_condition.get('grouped_scopes',[])
    rel_index={}
    for r in grouped:
        n=r['counts']['starts']; t=r['counts']['top3']; rr=r['counts']['top3_rate']
        require((rr is None and n==0) or (n>0 and rr is not None and abs(rr-t/n)<0.00011),'relative rate mismatch')
        rel_index.setdefault(r['scope_key'],[]).append(r)
    links=[]
    for state_name in NON_GOOD:
        for lane_name in ('sire','broodmare_sire','pairing'):
            p=lanes[lane_name]['primary_by_state'].get(state_name)
            if not p or p['direction']!='STATE_HIGHER':
                continue
            rel_scope=REL_SCOPE_MAP[p['scope_key']]
            rel_rows=[r for r in rel_index.get(rel_scope,[]) if r['counts']['starts']>0]
            if rel_rows:
                links.append({
                    'kind':'PARENT_GOING_SIGNAL_WITH_RELATIVE_CONDITION_OBSERVATION',
                    'state':state_name,'parent_lane':lane_name,'parent_evidence_ref':p['evidence_id'],
                    'parent_scope_key':p['scope_key'],'relative_scope_key':rel_scope,
                    'relative_relation_count':len(rel_rows),
                    'relative_starts_sum_not_unique':sum(r['counts']['starts'] for r in rel_rows),
                    'relative_top3_sum_not_unique':sum(r['counts']['top3'] for r in rel_rows),
                    'relative_going_state_known':False,
                    'independent_support':False,'causal_claim':False,'distance_compensation_claim':False,
                    'suitability_claim':False,'prediction_eligible':False,'display_eligible':False,
                    'interpretation_status':'PARALLEL_OBSERVATION_ONLY',
                })
    return links


def attach_relative_conditions(existing_result, relative_condition_by_horse):
    require(existing_result.get('contract_version')==VERSION,'v0.6 contract mismatch')
    require(existing_result.get('release_status')=='RESEARCH_ONLY','v0.6 release status')
    policy=existing_result.get('policy',{})
    require(policy.get('prediction_safe') is False and policy.get('production_authorized') is False and policy.get('display_authorized') is False,'v0.6 authorization')
    import copy
    out=copy.deepcopy(existing_result)
    target_ids={h['horse_id'] for h in out['horses']}
    require(set(relative_condition_by_horse)<=target_ids,'relative map outside target cohort')
    for h in out['horses']:
        h['relative_condition_links']=relative_links_from_lanes(h['lanes'],relative_condition_by_horse.get(h['horse_id']))
    out['summary']=summarize(out['horses'])
    return out

def analyze_horse(horse, lane_scope_state_counts, relative_condition=None):
    """Analyze already-aggregated counts for one horse.

    lane_scope_state_counts: {lane:{scope:{state:(n,w,t)}}}
    lane names are sire, broodmare_sire, pairing.
    relative_condition is the existing v0.3 relative-condition object, optional.
    """
    require(set(lane_scope_state_counts) <= {'sire','broodmare_sire','pairing'}, 'unknown lane')
    lanes={}; selected_by_state={s:[] for s in NON_GOOD}
    for lane in ('sire','broodmare_sire','pairing'):
        scopes=[]
        src=lane_scope_state_counts.get(lane,{})
        for scope in SCOPE_PRIORITY:
            states=src.get(scope,{})
            good=states.get('良',(0,0,0))
            comps=[]
            for state_name in NON_GOOD:
                c=compare_state(good,states.get(state_name,(0,0,0)))
                row={'state':state_name,'evidence_id':_lane_evidence_id(horse['horse_id'],lane,scope,state_name),**c}
                comps.append(row)
                if c['tier']!='NONE':
                    selected_by_state[state_name].append({'lane':lane,'scope_key':scope,'state':state_name,
                        'evidence_id':row['evidence_id'],'tier':c['tier'],'direction':c['direction'],
                        'difference_top3_pp':c['difference_top3_pp']})
            scopes.append({'scope_key':scope,'state_comparisons':comps})
        lane_selected=[x for vals in selected_by_state.values() for x in vals if x['lane']==lane]
        lane_primary={state_name:_primary([x for x in selected_by_state[state_name] if x['lane']==lane]) for state_name in NON_GOOD}
        lanes[lane]={'scopes':scopes,'selected_observations':lane_selected,'primary_by_state':lane_primary,
                     'historical_asof_status':'AS_OF_UNVERIFIED'}
    alignments=[]
    for state_name in NON_GOOD:
        primaries=[lanes[ln]['primary_by_state'][state_name] for ln in ('sire','broodmare_sire','pairing') if lanes[ln]['primary_by_state'][state_name] is not None]
        by_dir={d:[x for x in primaries if x['direction']==d] for d in ('STATE_HIGHER','GOOD_HIGHER')}
        for direction,rows in by_dir.items():
            lane_names=sorted(x['lane'] for x in rows)
            if len(lane_names)>=2:
                alignments.append({
                    'kind':'MULTILANE_GOING_DIRECTION_ALIGNMENT','state':state_name,'direction':direction,
                    'lanes':lane_names,'primary_evidence_refs':[x['evidence_id'] for x in rows],
                    'lane_count':len(lane_names),'independent_support':False,
                    'cohort_overlap':'KNOWN_OR_POSSIBLE','causal_claim':False,'suitability_claim':False,
                    'prediction_eligible':False,'display_eligible':False,
                    'interpretation_status':'COOBSERVATION_ONLY',
                })
    relative_links=relative_links_from_lanes(lanes,relative_condition)
    return {'horse_no':horse['horse_no'],'horse_id':horse['horse_id'],'lanes':lanes,
            'cross_lane_alignments':alignments,'relative_condition_links':relative_links,
            'policy':{'prediction_safe':False,'production_authorized':False,'display_authorized':False}}


def summarize(horses):
    candidate_counts=Counter(); primary_counts=Counter(); align=Counter(); rel=Counter(); state_horses=Counter()
    for h in horses:
        seen=set()
        for lane in h['lanes'].values():
            for x in lane['selected_observations']:
                candidate_counts[(x['state'],x['lane'],x['direction'],x['tier'])]+=1
                seen.add(x['state'])
        for s in seen:state_horses[s]+=1
        for lname,lane in h['lanes'].items():
            for state_name,p in lane['primary_by_state'].items():
                if p: primary_counts[(state_name,lname,p['direction'],p['tier'])]+=1
        for x in h['cross_lane_alignments']:align[(x['state'],x['direction'],x['lane_count'])]+=1
        for x in h['relative_condition_links']:rel[(x['state'],x['parent_lane'])]+=1
    def rows(c,names):
        return [{**dict(zip(names,k)),'count':v} for k,v in sorted(c.items())]
    return {'horse_count':len(horses),'horses_with_selected_signal_by_state':dict(sorted(state_horses.items())),
            'selected_observations':rows(candidate_counts,['state','lane','direction','tier']),
            'primary_observations':rows(primary_counts,['state','lane','direction','tier']),
            'cross_lane_alignments':rows(align,['state','direction','lane_count']),
            'relative_condition_links':rows(rel,['state','parent_lane']),
            'nested_and_related_samples_not_independent':True}


def build_from_aggregated(race, horses, lane_counts_by_horse, relative_condition_by_horse=None, source=None):
    require(type(race) is dict and race.get('field_size')==len(horses),'cohort size mismatch')
    relative_condition_by_horse=relative_condition_by_horse or {}
    out=[];seen=set()
    for h in sorted(horses,key=lambda x:x['horse_no']):
        key=(h['horse_no'],h['horse_id']);require(key not in seen,'duplicate target horse');seen.add(key)
        require(h['horse_id'] in lane_counts_by_horse,'missing lane counts')
        out.append(analyze_horse(h,lane_counts_by_horse[h['horse_id']],relative_condition_by_horse.get(h['horse_id'])))
    return {'contract_version':VERSION,'release_status':'RESEARCH_ONLY','race':race,
            'source':source or {},'policy':{'prediction_safe':False,'production_authorized':False,
            'display_authorized':False,'natural_language_review_authorized':False},
            'summary':summarize(out),'horses':out}
