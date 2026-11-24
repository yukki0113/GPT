#!/usr/bin/env python3
"""JPDB R2 research-only descriptive comparisons on validated R1 inputs.
No target market/results, score, causal label, or production change.
"""
from __future__ import annotations
from collections import defaultdict, Counter
from dataclasses import dataclass
import math
import re
from jpdb_r1_profile_builder import PHYSICAL, SCOPED_SELECT, COUNTS, VERSION as R1_VERSION
from jpdb_history_reader import JPDBHistoryReaderError, validate_jockey

VERSION='jpdb-r2-condition-context-v0.1-candidate'
MIN_N=30
MARGIN=0.05
# fixed parent columns, compared columns. The first set is never varied.
AXES={
    'ALL_FLAT':((),()), 'SURFACE':((),('surface_code',)),
    'VENUE':((),('venue_code',)), 'VENUE_SURFACE':(('surface_code',),('venue_code',)),
    'SURFACE_DISTANCE_EXACT':(('surface_code',),('distance_m',)),
    'CLASS_GRADE_RAW':((),('race_class_code','grade_code')),
    'CLASS_ONLY':((),('race_class_code',)), 'CLASS_SURFACE':(('surface_code',),('race_class_code',)),
    'NEWCOMER_ALL_FLAT':((),('race_class_code',)),
    'NEWCOMER_SURFACE':(('race_class_code',),('surface_code',)),
    'NEWCOMER_VENUE_SURFACE':(('race_class_code','surface_code'),('venue_code',)),
    'NEWCOMER_SURFACE_DISTANCE_EXACT':(('race_class_code','surface_code'),('distance_m',)),
    'GOING_RAW':(('surface_code',),('track_condition_code',)),
    **{k:((),(v,)) for k,v in PHYSICAL.items()},
}
MARKET_AXES=('SURFACE','VENUE_SURFACE','SURFACE_DISTANCE_EXACT','NEWCOMER_ALL_FLAT','NEWCOMER_SURFACE','NEWCOMER_VENUE_SURFACE','NEWCOMER_SURFACE_DISTANCE_EXACT')
ANNUAL_AXES=tuple(k for k in AXES if k not in ('ALL_FLAT','GOING_RAW'))
WINDOWS=('ROLLING_3Y','RECENT_365D','RECENT_90D')
COMPARISONS={'within_rider':(1,-1,0,0),'same_condition_peers':(1,0,-1,0),'relative_condition_contrast':(1,-1,-1,1)}
ZERO=(0,)*len(COUNTS)


def require(ok,msg):
    if not ok: raise JPDBHistoryReaderError('R2: '+msg)


def add(a,b): return tuple(x+y for x,y in zip(a,b,strict=True))
def subtract(a,b):
    r=tuple(0.0 if isinstance(x-y,float) and -1e-8<x-y<0 else x-y for x,y in zip(a,b,strict=True))
    require(all(x>=0 for x in r),'non-disjoint group subtraction')
    return r


def valid_value(x): return x is not None and (not isinstance(x,str) or bool(x.strip()))
def valid_jockey(x): return isinstance(x,str) and bool(re.fullmatch('[0-9]{5}',x)) and x!='00000'


@dataclass
class Cube:
    axis: str
    rows: list
    zero: tuple=ZERO
    def __post_init__(self):
        self.parents,self.conditions=AXES[self.axis]
        self.own=defaultdict(lambda:self.zero);self.own_parent=defaultdict(lambda:self.zero)
        self.peer=defaultdict(lambda:self.zero);self.peer_parent=defaultdict(lambda:self.zero)
        self.unknown=0;self.invalid_identity=0
        for rider,keys,counts in self.rows:
            if not valid_jockey(rider):
                self.invalid_identity+=counts[0];continue
            if not all(valid_value(x) for x in keys):
                self.unknown+=counts[0];continue
            p=keys[:len(self.parents)]; c=keys[len(self.parents):]
            self.own[rider,p,c]=add(self.own[rider,p,c],counts)
            self.own_parent[rider,p]=add(self.own_parent[rider,p],counts)
            self.peer[p,c]=add(self.peer[p,c],counts)
            self.peer_parent[p]=add(self.peer_parent[p],counts)
    def key(self,condition):
        require(set(condition)==set(self.parents+self.conditions),'unexpected dimension condition keys')
        return tuple(condition[k] for k in self.parents),tuple(condition[k] for k in self.conditions)
    def groups(self,rider,p,c):
        a=self.own.get((rider,p,c),self.zero)
        b=subtract(self.own_parent.get((rider,p),self.zero),a)
        cc=subtract(self.peer.get((p,c),self.zero),a)
        d=subtract(subtract(self.peer_parent.get(p,self.zero),self.peer.get((p,c),self.zero)),b)
        return (a,b,cc,d)
    def candidates(self):
        for rider,p,c in sorted(self.own):
            if self.axis.startswith('NEWCOMER'):
                cond=dict(zip(self.parents+self.conditions,p+c,strict=True))
                if cond['race_class_code']!='A1':continue
            yield rider,p,c


def query_cube(db,axis,periods,*,market=False):
    """Only allowlisted SQL expressions and parameterized, half-open periods.
    Market path solely for the offline sensitivity report, never profile path.
    """
    p,c=AXES[axis];cols=p+c
    require(bool(periods) and all(a<b for a,b in periods),'invalid period')
    date_filter=' OR '.join('(race_date>=? AND race_date<?)' for _ in periods)
    keys=(','+','.join(cols)) if cols else ''
    group=','.join(str(i+1) for i in range(len(cols)+1))
    if market:
        relation='r2_market_facts'; expr='COUNT(*),SUM(win),SUM(market_p)'
    else:
        relation='jpdb_course_facts';expr=SCOPED_SELECT
    sql=f"SELECT jockey_code{keys},{expr} FROM {relation} WHERE surface_code IN ('1','2') AND ({date_filter}) GROUP BY {group} ORDER BY {group}"
    rows=db.execute(sql,[x for pair in periods for x in pair]).fetchall()
    return Cube(axis,[(row[0],tuple(row[1:1+len(cols)]),tuple(row[1+len(cols):] if market else row[1+len(cols):-2])) for row in rows],(0,0,0.0) if market else ZERO)


def stats(counts):
    x=dict(zip(COUNTS,counts,strict=True));n=x['normal_finishers']+x['dnf']; u=x['demotion_review']+x['unknown_codes']+x['invalid_normal_finish']
    require(all(v>=0 for v in counts) and sum(x[k] for k in COUNTS[1:8])==x['entries'] and 0<=x['wins']<=x['top2']<=x['top3']<=x['normal_finishers'],'result classification')
    out={**x,'resolved_starts':n,'unresolved':u}
    for k in ('wins','top3'):
        out[k+'_rate_resolved']=x[k]/n if n else None
        out[k+'_unresolved_bounds']=[x[k]/(n+u),(x[k]+u)/(n+u)] if n+u else None
    return out


def contrast(groups,weights):
    used=[(i,g,w) for i,(g,w) in enumerate(zip(groups,weights,strict=True)) if w]
    if any(g['resolved_starts']==0 for _,g,_ in used):status='UNAVAILABLE'
    elif any(g['unresolved'] for i,g,_ in used if i in (0,1)):status='REVIEW_REQUIRED'
    elif any(g['resolved_starts']<MIN_N for _,g,_ in used):status='INSUFFICIENT'
    else:status='CONTEXTUAL'
    out={'status':status,'direction':'UNCLASSIFIED'}
    for k in ('wins','top3'):
        if any(g[k+'_rate_resolved'] is None for _,g,_ in used):
            out[k+'_delta_pp']=None;out[k+'_unresolved_bounds_pp']=None;continue
        diff=math.fsum(w*g[k+'_rate_resolved'] for _,g,w in used)
        lo=math.fsum(w*g[k+'_unresolved_bounds'][int(w<0)] for _,g,w in used)
        hi=math.fsum(w*g[k+'_unresolved_bounds'][int(w>0)] for _,g,w in used)
        out[k+'_delta_pp']=round(diff*100,8);out[k+'_unresolved_bounds_pp']=[round(lo*100,8),round(hi*100,8)]
        if k=='top3' and status=='CONTEXTUAL':
            out['direction']='POSITIVE' if lo>=MARGIN else 'NEGATIVE' if hi<=-MARGIN else 'NEAR_ZERO' if lo>-MARGIN and hi<MARGIN else 'UNCLASSIFIED'
    return out


def compare(cube,rider,p,c):
    groups=[stats(x) for x in cube.groups(rider,p,c)]
    comparisons={k:contrast(groups,w) for k,w in COMPARISONS.items() if cube.axis!='ALL_FLAT' or k=='same_condition_peers'}
    return {'groups':dict(zip(('own_match','own_other','peer_match','peer_other'),groups,strict=True)),
            'comparisons':comparisons}


def summarize_windows(windows):
    result={}
    for kind in COMPARISONS:
        items=[x['comparisons'][kind] for x in windows if kind in x['comparisons']]
        if not items:continue
        observed={x['direction'] for x in items if x['status']=='CONTEXTUAL'}
        first=items[0]
        conflict={'POSITIVE','NEGATIVE'}<=observed
        result[kind]={'status':'CONFLICTED' if conflict else first['status'],
                      'direction':'UNCLASSIFIED' if conflict else first['direction'],
                      'reference_window':WINDOWS[0], 'supported_window_count':sum(x['status']=='CONTEXTUAL' for x in items)}
    return result


def build_context(db,profile):
    require(profile['schema_version']==R1_VERSION and profile['prediction_safe'] is False and profile['source']['strict_asof_certified'] is False,'R1 source policy')
    day=profile['target_date'];cache={}; output=[]; matches=0
    for race in profile['races']:
        horses=[]
        for horse in race['horses']:
            rider=validate_jockey(horse['scheduled_jockey_code']);axes={}
            require(set(horse['windows'])==set(WINDOWS),'window roster')
            for w in WINDOWS:
                block=horse['windows'][w];lower=block['period_from_inclusive']; upper=block['period_to_exclusive']
                require(lower<upper==day,'cutoff mismatch')
                for e in block['evidence']:
                    axis=e['dimension'];condition=e['condition'];m=e['metrics']
                    require(axis in AXES,'unsupported R1 dimension')
                    if axis not in axes:axes[axis]={'dimension':axis,'condition':condition,'redundancy_group_id':e['redundancy_group_id'],'windows':{}}
                    a=axes[axis];require(a['condition']==condition and a['redundancy_group_id']==e['redundancy_group_id'] and w not in a['windows'],'R1 axis drift')
                    base={'r1_evidence_id':e['evidence_id'],'period_from_inclusive':lower,'period_to_exclusive':upper}
                    if m is None:
                        require(e['status']=='TARGET_CONDITION_UNAVAILABLE','unexpected missing metrics')
                        a['windows'][w]={**base,'status':'UNAVAILABLE','groups':None,'comparisons':{}};continue
                    key=(axis,lower,upper)
                    if key not in cache:cache[key]=query_cube(db,axis,[(lower,upper)])
                    cube=cache[key];p,c=cube.key(condition);require(all(valid_value(x) for x in p+c),'unresolved condition')
                    result=compare(cube,rider,p,c)
                    require(all(result['groups']['own_match'][k]==m[k] for k in COUNTS),'R1 own matched counts differ')
                    matches+=1
                    a['windows'][w]={**base,'status':'OBSERVED','excluded_unknown_condition_entries_in_window':cube.unknown,
                                     'excluded_invalid_jockey_entries_in_window':cube.invalid_identity,**result}
            require(all(set(a['windows'])==set(WINDOWS) for a in axes.values()),'incomplete window axes')
            for a in axes.values():a['window_summary']=summarize_windows([a['windows'][w] for w in WINDOWS])
            horses.append({'horse_no':horse['horse_no'],'horse_id':horse['horse_id'],'scheduled_jockey_code':rider,'entry_cancel_flag_raw':horse['entry_cancel_flag_raw'],'axes':list(axes.values())})
        require(len(horses)==race['entry_count'],'R1 field count')
        output.append({'race_key_raw':race['race_key_raw'],'is_newcomer_race':race['is_newcomer_race'],'entry_count':race['entry_count'],'horses':horses})
    return {'schema_version':VERSION,'target_date':day,'source':profile['source'],'prediction_safe':False,
            'policy':{'comparison':'NONCAUSAL_RESOLVED_OUTCOME_RESEARCH','primary':'top3','min_resolved_starts':MIN_N,'display_margin_pp':MARGIN*100,'no_additive_votes':True,'suggestive_allowed':False},
            'r1_matched_count_cells':matches,'races':output}


PERIODS={'train_2023_2024':(('2023-01-01','2023-11-16'),('2024-01-01','2024-11-16')),
         'holdout_2025':(('2025-01-01','2025-11-16'),),'holdout_2026':(('2026-01-01','2026-11-16'),)}


def annual_stability(db):
    results={}
    for axis in ANNUAL_AXES:
        cubes={k:query_cube(db,axis,v) for k,v in PERIODS.items()};train=cubes['train_2023_2024'];selected=0;eligible=0;both=0;hold={k:Counter() for k in ('holdout_2025','holdout_2026')};by_sign=Counter()
        for rider,p,c in train.candidates():
            t=compare(train,rider,p,c)['comparisons']['relative_condition_contrast'];eligible+=int(t['status']=='CONTEXTUAL')
            if t['status']!='CONTEXTUAL' or t['direction'] not in ('POSITIVE','NEGATIVE'):continue
            selected+=1;by_sign[t['direction']]+=1;matches=[]
            for year,h in hold.items():
                s=compare(cubes[year],rider,p,c)['comparisons']['relative_condition_contrast']
                if s['status']!='CONTEXTUAL':outcome=s['status']
                elif s['direction']==t['direction']:outcome='MATCH'
                elif s['direction'] in ('POSITIVE','NEGATIVE'):outcome='REVERSED'
                else:outcome=s['direction']
                h[outcome]+=1;matches.append(outcome=='MATCH')
            both+=all(matches)
        require(all(sum(h.values())==selected for h in hold.values()),'holdout attrition hidden')
        results[axis]={'train_eligible_cells':eligible,'selected_train_cells':selected,'train_directions':dict(by_sign),
                       'holdouts':{k:dict(v) for k,v in hold.items()},'both_holdouts_match':both}
    return results


def market_delta(groups):
    if min(g[0] for g in groups)<MIN_N:return None
    w=COMPARISONS['relative_condition_contrast']
    raw=math.fsum(weight*g[1]/g[0] for weight,g in zip(w,groups,strict=True))
    adjusted=math.fsum(weight*(g[1]-g[2])/g[0] for weight,g in zip(w,groups,strict=True))
    return raw,adjusted


def market_sensitivity(db):
    out={}
    for axis in MARKET_AXES:
        out[axis]={}
        for period,dates in PERIODS.items():
            cube=query_cube(db,axis,dates,market=True);pairs=[]
            for rider,p,c in cube.candidates():
                value=market_delta(cube.groups(rider,p,c))
                if value is not None:pairs.append(value)
            corr=None
            if len(pairs)>1:
                try:corr=round(__import__('statistics').correlation(*zip(*pairs)),6)
                except __import__('statistics').StatisticsError:pass
            out[axis][period]={'cells':len(pairs),'same_sign':sum(a*b>0 for a,b in pairs),'opposite_sign':sum(a*b<0 for a,b in pairs),
                               'zero_sign':sum(a*b==0 for a,b in pairs),'correlation':corr,
                               'raw_abs_ge_5pp':sum(abs(a)>=MARGIN for a,b in pairs),
                               'raw_abs_ge_5pp_adjusted_below_5pp':sum(abs(a)>=MARGIN and abs(b)<MARGIN for a,b in pairs)}
    return out
