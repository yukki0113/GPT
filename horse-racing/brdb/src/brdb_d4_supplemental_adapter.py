"""D4 research-only adapter: D3 descriptive evidence -> non-scoring sidecar.

Never mutate frozen BRDB review or integrated v0.2 candidate schema. Research
cohort was selected retrospectively, so as-of correctness is unverified.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Mapping

SCHEMA = 'brdb-d4-supplemental-research-v0.1'
D3_SCHEMA = 'brdb-d3-condition-research-v0.1'
TEMPORAL_SCHEMA = 'brdb-d3-temporal-diagnostic-v0.1'
APPROVED_SCOPES = {
    'SURFACE': ('track_type',),
    'SURFACE_BAND': ('track_type', 'distance_band'),
    'SURFACE_DISTANCE': ('track_type', 'distance'),
    'VENUE_SURFACE_BAND': ('venue_code', 'track_type', 'distance_band'),
    'SURFACE_GOING_CODE': ('track_type', 'track_condition_code'),
    'VENUE_SURFACE_GOING_CODE': ('venue_code', 'track_type', 'track_condition_code'),
}
BANDS = ((0,1399,'SHORT'), (1400,1799,'MILE'), (1800,2399,'MIDDLE'), (2400,10000,'LONG'))


class D4ContractError(ValueError):
    """Invalid identity, provenance, scope, or source-timing contract."""


def ensure(valid: bool, why: str) -> None:
    if not valid:
        raise D4ContractError(why)


def _band(distance: int) -> str:
    for start, stop, label in BANDS:
        if start <= distance <= stop:
            return label
    raise D4ContractError('unsupported distance')


def _date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except (ValueError, TypeError) as exc:
        raise D4ContractError('invalid ISO race date') from exc


def _key(row: Mapping) -> tuple:
    return (row['lane'], row['name'], row['scope'], tuple(sorted(row['dimensions'].items())))


def _sample(row: Mapping) -> dict:
    """Only retain precomputed evidence values; never recompute rates."""
    fields = ('starts', 'distinct_horses', 'wins', 'top3', 'win_rate',
              'top3_rate', 'wilson95_top3', 'baseline_starts',
              'baseline_top3', 'baseline_top3_rate',
              'top3_delta_percentage_points', 'sample_status')
    ensure(row.get('sample_status') in ('DESCRIPTIVE','LOW_SAMPLE','NO_SAMPLE'),
           'unrecognized sample status')
    starts, unique, wins, top3 = [row.get(k) for k in ('starts','distinct_horses','wins','top3')]
    ensure(all(type(x) is int for x in (starts,unique,wins,top3)) and
           0 <= wins <= top3 <= starts and 0 <= unique <= starts,
           'invalid source sample numbers')
    ensure(row.get('interpretation') == 'OBSERVED_ONLY_NOT_CAUSAL_NOT_PREDICTION',
           'source attempts prediction interpretation')
    ensure((row['sample_status'] == 'NO_SAMPLE') == (starts == 0),
           'missing sample and zero sample conflated')
    if row['sample_status'] == 'DESCRIPTIVE':
        ensure(starts >= 30 and unique >= 10, 'unqualified DESCRIPTIVE label')
    if row['sample_status'] == 'LOW_SAMPLE':
        ensure(starts > 0 and (starts < 30 or unique < 10), 'incorrect low sample')
    if starts == 0:
        ensure(row.get('top3_rate') is None and row.get('wilson95_top3') is None,
               'zero-start rates must be null')
    return {key:row.get(key) for key in fields}


def _check_sources(d3: Mapping, temporal: Mapping, receipt: Mapping) -> None:
    ensure(d3.get('schema_version') == D3_SCHEMA, 'D3 version drift')
    ensure(temporal.get('schema_version') == TEMPORAL_SCHEMA,
           'temporal version drift')
    ensure(d3.get('research_only') is True and d3.get('prediction_safe') is False
           and d3.get('historical_asof_status') == 'AS_OF_UNVERIFIED',
           'D3 promoted outside research')
    ensure(temporal.get('research_only') is True and
           temporal.get('prediction_safe') is False,
           'temporal output promoted outside research')
    ensure(receipt.get('status') == 'PASS' and
           receipt.get('research_only') is True and
           receipt.get('prediction_safe') is False and
           receipt.get('as_of') == 'AS_OF_UNVERIFIED',
           'D3 receipt not accepted')
    ensure(receipt.get('source_generation') == d3.get('source_snapshot_generation')
           and receipt.get('selection_generation') == d3.get('selection_generation'),
           'D3 generation mismatch')
    ensure(d3.get('as_of_exclusive') == '2026-11-02' and
           d3.get('period_start') == '2016-01-01',
           'D3 must be full frozen retrospective cohort')
    ensure(d3.get('source_sha256', {}).get('top50') ==
           '89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0',
           'subject SHA drift')
    ensure(temporal.get('source_sha256', {}).get('top50') ==
           d3['source_sha256']['top50'], 'temporal cohort drift')
    ensure(temporal.get('source_sha256', {}).get('train_current') ==
           d3['source_sha256']['manifest'] and
           temporal.get('source_sha256', {}).get('test_current') ==
           d3['source_sha256']['manifest'], 'temporal source drift')
    ensure(receipt.get('condition_evidence_by_lane') ==
           d3.get('counts',{}).get('evidence_by_lane') and
           receipt.get('pair_observed_cells') ==
           d3.get('counts',{}).get('pair_observed_cells') and
           receipt.get('historical_starts') ==
           d3.get('population',{}).get('historical_starts'),
           'receipt counts differ from D3')
    ensure(temporal.get('counts') == receipt.get('temporal_counts'),
           'temporal counts differ from receipt')


def build(d3: Mapping, temporal: Mapping, receipt: Mapping,
          race: Mapping, entrants: list[Mapping]) -> dict:
    """Supply display-only D3 evidence for an explicitly dated research field.

    The adapter does not authorize a historical backtest or race-day review:
    its D3 source window ends Nov 2026 and may be post-race for past fields.
    """
    _check_sources(d3, temporal, receipt)
    ensure(race.get('research_only') is True and
           race.get('target_date') is not None,
           'D4 requires an explicit research-only race context')
    target = _date(race['target_date'])
    ensure(target >= _date(d3['as_of_exclusive']),
           'D3 includes future outcomes relative to target race')
    surface = race.get('track_type')
    distance = race.get('distance')
    venue = race.get('venue_code')
    ensure(surface in ('1','2') and type(distance) is int and 600 <= distance <= 5000,
           'unsupported turf/dirt race condition')
    ensure(isinstance(venue,str) and venue != '', 'missing venue code')
    going = race.get('track_condition_code')
    if going is not None:
        ensure(isinstance(going,str) and going, 'malformed track condition code')
    ensure(isinstance(entrants,list) and entrants, 'field is empty')
    ensure(type(race.get('field_size')) is int and race['field_size'] == len(entrants),
           'field size mismatch')
    subject_names = {s['name'] for s in d3['population']['source_subjects']}
    by_lane = {}
    for row in d3['evidence_rows']:
        ensure(row.get('lane') in ('SIRE','BMS') and row.get('scope') in APPROVED_SCOPES,
               'unknown D3 evidence lane/scope')
        ensure(set(row['dimensions']) == set(APPROVED_SCOPES[row['scope']]),
               'unexpected D3 condition dimensions')
        _sample(row)
        key = _key(row)
        ensure(key not in by_lane, 'duplicate D3 group')
        by_lane[key] = row
    by_pair = {}
    for row in d3['pair_rows']:
        _sample(row)
        key=(row['sire_name'], row['bms_name'], tuple(sorted(row['dimensions'].items())))
        ensure(set(row['dimensions']) == {'track_type','distance_band'} and
               key not in by_pair, 'duplicate or ambiguous pair')
        by_pair[key] = row
    by_stability = {}
    for row in temporal['rows']:
        ensure(row.get('scope') == 'SURFACE_BAND' and
               row.get('stability_status') in (
                   'SAME_SIGN_DESCRIPTIVE_ONLY','DIRECTION_CHANGED',
                   'INSUFFICIENT_WINDOW_SAMPLE','PERIOD_MISSING',
                   'INSUFFICIENT_BASELINE','NO_DIRECTION'),
               'unknown stability contract')
        key=_key(row)
        ensure(key not in by_stability, 'duplicate temporal group')
        by_stability[key]=row
    canonical_context = {
        'track_type':surface, 'distance_band':_band(distance),
        'distance':distance,
        'venue_code':venue,
    }
    if going is not None:
        canonical_context['track_condition_code']=going
    seen_ids,seen_no=set(),set()
    reviewed=[]
    aggregate=Counter()
    for entry in entrants:
        horse_id,horse_no=entry.get('horse_id'),entry.get('horse_no')
        ensure(isinstance(horse_id,str) and horse_id.isdigit() and len(horse_id)==8,
               'JRDB canonical horse ID required; no name fallback')
        ensure(type(horse_no) is int and horse_no>=1, 'invalid horse number')
        ensure(horse_id not in seen_ids and horse_no not in seen_no,
               'duplicate field horse identity/number')
        seen_ids.add(horse_id);seen_no.add(horse_no)
        sire,bms=entry.get('sire_name'),entry.get('broodmare_sire_name')
        ensure(sire is None or isinstance(sire,str), 'sire must be a string or null')
        ensure(bms is None or isinstance(bms,str), 'BMS must be a string or null')
        items=[]
        for lane,name in (('SIRE',sire),('BMS',bms)):
            if not name or name not in subject_names:
                continue
            for scope, columns in APPROVED_SCOPES.items():
                if not all(col in canonical_context for col in columns):
                    continue
                dims={k:canonical_context[k] for k in columns}
                key=(lane,name,scope,tuple(sorted(dims.items())))
                found=by_lane.get(key)
                if found is None:
                    continue
                observation=_sample(found)
                stability=by_stability.get(key) if scope=='SURFACE_BAND' else None
                items.append({
                    'source_lane':lane, 'source_name_exact':name,
                    'scope_key':scope, 'condition':dims,
                    'observations':observation,
                    'temporal_diagnostic':(
                        {'status':stability['stability_status'],
                         'train_starts':stability['train_starts'],
                         'test_starts':stability['test_starts']}
                        if stability else None),
                    'interpretation_status':'OBSERVATION_ONLY_AS_OF_UNVERIFIED',
                    'contribution_to_score':None,
                })
        if sire and bms and sire in subject_names and bms in subject_names:
            pair_key=(sire,bms,tuple(sorted({'track_type':surface,
                                            'distance_band':_band(distance)}.items())))
            found=by_pair.get(pair_key)
            if found is not None:
                items.append({
                    'source_lane':'PAIR','source_name_exact':{'sire':sire,'bms':bms},
                    'scope_key':'SURFACE_BAND',
                    'condition':{'track_type':surface,'distance_band':_band(distance)},
                    'observations':_sample(found),
                    'temporal_diagnostic':None,
                    'interpretation_status':'OBSERVATION_ONLY_AS_OF_UNVERIFIED',
                    'contribution_to_score':None,
                })
        items.sort(key=lambda x:(x['source_lane'],x['scope_key']))
        aggregate['research_evidence_items']+=len(items)
        reviewed.append({
            'horse_id':horse_id,'horse_no':horse_no,
            'availability':'AS_OF_UNVERIFIED',
            'supplemental_insights':items,
            'factors':{'positive':[], 'negative':[], 'unknown':[]},
            'summary':None,'confidence':'UNASSESSED',
        })
    reviewed.sort(key=lambda x:x['horse_no'])
    return {
        'schema_version':SCHEMA,
        'base_review_contract':'brdb-review-v0.1 (FROZEN, NOT MODIFIED)',
        'integrated_review_contract':'brdb-integrated-blood-review-v0.2-candidate (NOT MODIFIED)',
        'research_only':True,'prediction_safe':False,
        'release_status':'RESEARCH_SIDECAR_ONLY',
        'historical_asof_status':'AS_OF_UNVERIFIED',
        'no_forecast_or_score':True,
        'race':{'target_date':race['target_date'],'venue_code':venue,
                'track_type':surface,'distance':distance,
                'field_size':len(entrants),
                'track_condition_code':going},
        'source_generations':{'jrdb_analysis':d3['source_snapshot_generation'],
                              'top50_selection':d3['selection_generation']},
        'source_time_guard':'TARGET_AFTER_RETROSPECTIVE_CUTOFF_BUT_ORIGINAL_RACE_DAY_FEATURE_AVAILABILITY_UNVERIFIED',
        'aggregate_coverage':{'field_size':len(entrants),
                              'reviewed_horses':len(reviewed),
                              'research_evidence_items':aggregate['research_evidence_items']},
        'horses':reviewed,
    }