"""Non-lossy, research-only M7 ④ relatives sidecar. No prediction or publication.

Existing v0.2/v0.3 candidate contracts stay unchanged. Canonical JRDB IDs only.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date

CONTRACT = 'brdb-m7-relatives-detail-v0.1-candidate'
SRC_VERSION = 'brdb-maternal-relatives-evidence-v0.1'
V03_VERSION = 'brdb-integrated-blood-review-v0.3-candidate'
SCOPES = ('VENUE_COURSE_EXACT', 'VENUE_DISTANCE', 'VENUE_BAND',
          'ALL_VENUES_DISTANCE', 'ALL_VENUES_BAND')
KINDS = ('FULL_SIBLING', 'SAME_DAM_SAME_SIRE_NAME_UNVERIFIED',
         'MATERNAL_HALF_SIBLING', 'MATERNAL_AUNT_UNCLE')
REQUIRED_META = ('version', 'research_only', 'prediction_safe',
                 'pedigree_temporal_status', 'race', 'pedigree_generation',
                 'analysis_generation', 'relationship_policy', 'older_birth_only',
                 'as_of_exclusive', 'historical_window_start', 'sample_policy',
                 'timing_ms')


class RelativesDetailError(ValueError):
    pass


def check(value, message):
    if not value:
        raise RelativesDetailError(message)


def digest(obj):
    return hashlib.sha256((json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                      separators=(',', ':')) + '\n').encode()).hexdigest()


def _day(value):
    try:
        if not isinstance(value, str):
            raise TypeError()
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise RelativesDetailError('invalid ISO date') from exc


def _yyyymmdd(value):
    check(isinstance(value, str) and re.fullmatch(r'\d{8}', value),
          'invalid profile/birth date')
    return _day(value[:4] + '-' + value[4:6] + '-' + value[6:])


def _identity(value):
    return isinstance(value, str) and re.fullmatch(r'\d{8}', value) is not None


def build(v03, relatives):
    """Attach full original ④ metadata + per-horse records in a separate sidecar."""
    check(isinstance(v03, dict) and isinstance(relatives, dict), 'objects required')
    check(v03.get('contract_version') == V03_VERSION and
          v03.get('release_status') == 'RESEARCH_CANDIDATE', 'unsupported v0.3')
    sup = v03.get('supplemental_research', {})
    check(sup.get('research_only') is True and
          sup.get('prediction_safe') is False and
          sup.get('historical_asof_status') == 'AS_OF_UNVERIFIED' and
          sup.get('no_forecast_or_score') is True, 'unsafe v0.3 supplement')
    check(set(relatives) == set(REQUIRED_META) | {'horses'},
          'unrecognized or missing ④ source keys')
    check(relatives['version'] == SRC_VERSION and
          relatives['research_only'] is True and
          relatives['prediction_safe'] is False and
          relatives['pedigree_temporal_status'] ==
          'RESEARCH_PROFILE_DATE_CHECKED_NOT_HISTORICALLY_REPLAYED' and
          relatives['relationship_policy'] == 'GUARDED_CANONICAL_DAM_ID_ONLY' and
          relatives['older_birth_only'] is True and
          relatives['sample_policy'] == 'NO_RESULTS_IS_NOT_NEGATIVE_APTITUDE',
          '④ safety status drift')
    race = v03.get('race', {})
    source_race = relatives['race']
    check(set(source_race) == {'race_key', 'target_date', 'venue_code',
                              'surface_code', 'distance', 'course_code'},
          '④ race fields mismatch')
    for s, t in [('race_key','race_key'),('target_date','target_date'),
                 ('venue_code','venue_code'),('surface_code','surface_code'),
                 ('distance','distance_m'),('course_code','course_code')]:
        check(source_race[s] == race.get(t), '④ race mismatch: '+s)
    target = _day(race['target_date'])
    check(relatives['as_of_exclusive'] == race['target_date'] and
          _day(relatives['historical_window_start']) < target,
          '④ historical cutoff mismatch')
    gen = v03.get('source_generations', {})
    check(relatives['pedigree_generation'] == gen.get('brdb') and
          relatives['analysis_generation'] == gen.get('jrdb_analysis'),
          '④ source generation mismatch')
    base_horses, src_horses = v03.get('horses'), relatives['horses']
    check(isinstance(base_horses, list) and isinstance(src_horses, list) and
          len(src_horses) == len(base_horses) == race['field_size'],
          '④ field size mismatch')
    total, zero, roots = 0, 0, 0
    for base, src in zip(base_horses, src_horses):
        horse_id, horse_no = src.get('horse_id'), src.get('horse_no')
        check(_identity(horse_id) and type(horse_no) is int and
              horse_id == base.get('horse_id') and horse_no == base.get('horse_no'),
              '④ horse identity/order mismatch')
        check(src.get('horse_name') == base.get('horse_name'),
              '④ horse display name mismatch')
        check(base.get('status') == 'AS_OF_UNVERIFIED' and
              base.get('factors') == {'positive':[], 'negative':[], 'unknown':[]} and
              base.get('summary') is None and base.get('confidence') == 'UNASSESSED',
              'unsafe v0.3 horse interpretation')
        mother = src.get('mother_horse_id')
        granddam = src.get('maternal_granddam_horse_id')
        check(mother is None or _identity(mother), 'invalid canonical mother ID')
        check(granddam is None or (_identity(granddam) and mother is not None),
              'invalid maternal granddam ID')
        if mother:
            roots += 1
        records = src.get('relatives')
        check(isinstance(records, list), 'missing ④ relatives')
        status = ('SOURCE_UNAVAILABLE' if mother is None else
                  'NO_SAMPLE' if not records else 'DESCRIPTIVE_RELATION')
        check(src.get('status') == status, '④ relation status mismatch')
        state = 'SOURCE_UNAVAILABLE' if mother is None else 'AS_OF_UNVERIFIED'
        check(base['coverage']['relatives'] == state and
              base['components']['relatives']['availability'] == state,
              '④ availability promotion or drift')
        actual_ids, seen = [], set()
        counts = {k:0 for k in KINDS}
        relevant_starts = 0
        for record in records:
            rid = record.get('horse_id')
            kind = record.get('relationship')
            check(_identity(rid) and rid not in seen and rid != horse_id and
                  kind in KINDS, '④ invalid/duplicate relative identity')
            seen.add(rid)
            check(_yyyymmdd(record.get('birth_date')) < target and
                  _yyyymmdd(record.get('profile_data_date')) <= target,
                  '④ future relative birth/profile')
            scopes = record.get('scope_stats')
            check(isinstance(scopes, dict) and set(scopes) == set(SCOPES),
                  '④ incomplete/unknown scope set')
            for s in SCOPES:
                stat = scopes[s]
                check(isinstance(stat, dict) and set(stat) ==
                      {'starts','wins','top3','top3_rate'}, '④ scope fields drift')
                n, w, t = stat['starts'], stat['wins'], stat['top3']
                check(all(type(x) is int for x in (n,w,t)) and 0<=w<=t<=n,
                      '④ invalid start/win/top3 counts')
                rate = stat['top3_rate']
                if n == 0:
                    check(rate is None, '④ zero starts must yield null rate')
                    zero += 1
                else:
                    check(type(rate) in (int, float) and
                          abs(rate-round(t/n,4)) <= 1e-8,
                          '④ rate differs from observed counts')
            has_starts = scopes['ALL_VENUES_BAND']['starts'] > 0
            check(record.get('has_target_surface_band_history') is has_starts,
                  '④ relevant-start flag mismatch')
            relevant_starts += int(has_starts)
            counts[kind] += 1
            eid = f'REL_{horse_id}_{rid}_{kind}'
            actual_ids.append(eid)
            # Frozen v0.3 identity fact must still match this exact relationship.
            evidence = [x for x in base['evidence'] if x.get('evidence_id') == eid]
            check(len(evidence) == 1 and
                  evidence[0]['component'] == 'relatives' and
                  evidence[0]['evidence_kind'] == 'PEDIGREE_FACT' and
                  evidence[0]['observations'] is None and
                  evidence[0]['sample_status'] == 'NOT_APPLICABLE' and
                  evidence[0]['scope_key'] == 'RELATION:'+kind+':'+rid and
                  evidence[0]['source_generation'] == relatives['pedigree_generation'],
                  '④ identity evidence inconsistent with v0.3')
        check(src.get('relative_counts') == counts and
              src.get('with_relevant_starts') == relevant_starts,
              '④ source aggregate mismatch')
        check(base['components']['relatives']['evidence_ids'] == actual_ids and
              [x['evidence_id'] for x in base['evidence']
               if x['component']=='relatives'] == actual_ids,
              '④ v0.3 evidence cohort inconsistent')
        total += len(records)
    source_metadata = {k:copy.deepcopy(v) for k,v in relatives.items() if k!='horses'}
    output = {
        'contract_version': CONTRACT,
        'release_status': 'RESEARCH_SIDECAR_ONLY',
        'research_only': True, 'prediction_safe': False,
        'historical_asof_status': 'AS_OF_UNVERIFIED',
        'no_forecast_or_score': True,
        'source_canonical_sha256': digest(relatives),
        'integrated_v03_canonical_sha256': digest(v03),
        'source_metadata': source_metadata,
        'horses': copy.deepcopy(src_horses),
        'aggregate_coverage': {'field_size':len(src_horses),
                               'reviewed_horses':len(src_horses),
                               'mother_roots_resolved':roots,
                               'relative_records':total,
                               'scope_observations':total*len(SCOPES),
                               'zero_start_cells':zero},
    }
    # Lossless relative to the source JSON tree, including the timing receipt.
    reconstructed = {**output['source_metadata'], 'horses':output['horses']}
    check(reconstructed == relatives and digest(reconstructed) ==
          output['source_canonical_sha256'], '④ non-lossless projection')
    return output