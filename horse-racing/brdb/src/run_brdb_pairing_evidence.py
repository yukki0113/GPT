#!/usr/bin/env python3
"""BRDB ③ read-only sire-line x BMS-line descriptive evidence.

Historical UKC lineage availability as-of each old race is NOT attested by
Analysis v1.4. Do not use this output as validated historical pre-race prediction.
Does not score, rank, assign positive factors or publish CURRENT.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path

import duckdb
from run_brdb_sire_bms_evidence import _paths, _sql_path, _stats, distance_band

VERSION = 'brdb-lineage-pair-evidence-research-v0.1'
TEMPORAL_STATUS = 'HISTORICAL_LINEAGE_PROFILE_ASOF_UNVERIFIED'


def _code(value):
    """Keep official JRDB codes as four-character strings; never guess."""
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}', value):
        return None
    return value


def _read_field(source):
    if source.get('version') != 'brdb-sire-bms-field-evidence-v0.2':
        raise ValueError('requires ①② v0.2 output')
    race = source.get('race')
    horses = source.get('horses')
    if not isinstance(race, dict) or not isinstance(horses, list) or not horses:
        raise ValueError('missing race / field')
    if not re.fullmatch(r'[0-9a-zA-Z]{8}', str(race.get('race_key', ''))):
        raise ValueError('invalid race_key')
    if race.get('surface_code') not in ('1', '2'):
        raise ValueError('unsupported surface')
    date = dt.date.fromisoformat(race['target_date'])
    if not isinstance(race.get('distance'), int) or not 600 <= race['distance'] <= 5000:
        raise ValueError('invalid distance')
    if not re.fullmatch(r'[0-9]{2}', race['venue_code']):
        raise ValueError('invalid venue')
    ids = [h.get('horse_id') for h in horses]
    numbers = [h.get('horse_no') for h in horses]
    if len(set(ids)) != len(ids) or len(set(numbers)) != len(numbers):
        raise ValueError('duplicate horse cohort')
    if any(not re.fullmatch(r'[0-9]{8}', str(h)) for h in ids):
        raise ValueError('missing or invalid horse ID')
    if numbers != sorted(numbers) or any(not isinstance(n, int) or n < 1 for n in numbers):
        raise ValueError('horse numbers not sorted or invalid')
    policy = source['policy']
    if policy['as_of_exclusive'] != date.isoformat():
        raise ValueError('①② historical cutoff mismatch')
    start = policy['historical_window_start']
    if dt.date.fromisoformat(start) >= date:
        raise ValueError('invalid historical period')
    return race, horses, start


def _scope_definitions(race):
    surface, venue, distance = race['surface_code'], race['venue_code'], race['distance']
    band = distance_band(distance)
    return [
        ('VENUE_COURSE_EXACT', 'venue_code=? AND track_type=? AND distance=? AND course_code=?',
         [venue, surface, distance, race['course_code']]),
        ('VENUE_DISTANCE', 'venue_code=? AND track_type=? AND distance=?',
         [venue, surface, distance]),
        ('VENUE_BAND', 'venue_code=? AND track_type=? AND band=?', [venue, surface, band]),
        ('ALL_VENUES_DISTANCE', 'track_type=? AND distance=?', [surface, distance]),
        ('ALL_VENUES_BAND', 'track_type=? AND band=?', [surface, band]),
    ]


def _aggregate(con, clause, params):
    # Denominator: actual starters, excluding cancelled/excluded. Keep a common
    # comparison baseline for the pair and each parent lineage.
    measure = (
        "count(*)::BIGINT,count(DISTINCT horse_id)::BIGINT,"
        "count(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish=1)::BIGINT,"
        "count(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3)::BIGINT"
    )
    suffix = ' FROM history WHERE ' + clause
    base = con.execute('SELECT '+measure+suffix, params).fetchone()
    pairs = {(s,b): counts for s,b,*counts in con.execute(
        'SELECT sire_line_code,broodmare_sire_line_code,'+measure+suffix+
        ' AND sire_line_code IS NOT NULL AND broodmare_sire_line_code IS NOT NULL GROUP BY 1,2',
        params).fetchall()}
    sires = {s: counts for s,*counts in con.execute(
        'SELECT sire_line_code,'+measure+suffix+
        ' AND sire_line_code IS NOT NULL GROUP BY 1', params).fetchall()}
    bms = {b: counts for b,*counts in con.execute(
        'SELECT broodmare_sire_line_code,'+measure+suffix+
        ' AND broodmare_sire_line_code IS NOT NULL GROUP BY 1', params).fetchall()}
    return base, pairs, sires, bms


def analyze(source, analysis_root):
    """One PACI field -> all lineage pair observations, with no score or rank."""
    start_clock = time.perf_counter()
    race, horses, date_start = _read_field(source)
    generation, paths = _paths(analysis_root)
    files = '[' + ','.join(_sql_path(p) for p in paths) + ']'
    con = duckdb.connect(database=':memory:')
    try:
        # The RESULT cutoff is verified. Historical lineage profile publication
        # timing is not: this is descriptive-only, never an as-of-safe forecast.
        con.execute(f'''CREATE TEMP TABLE history AS
          SELECT race_date, venue_code, course_code, track_type, distance,
            horse_id, sire_line_code, broodmare_sire_line_code, finish, abnormal_code,
            CASE WHEN distance < 1400 THEN 'SHORT'
                 WHEN distance < 1800 THEN 'MILE'
                 WHEN distance < 2400 THEN 'MIDDLE' ELSE 'LONG' END AS band
          FROM read_parquet({files})
          WHERE race_date >= ? AND race_date < ?
            AND abnormal_code IN ('0','3','4','5','6')
            AND track_type IN ('1','2') AND horse_id IS NOT NULL''',
            [date_start, race['target_date']])
        scan_ms = round((time.perf_counter()-start_clock)*1000, 1)
        scopes = {name: _aggregate(con, clause, params)
                  for name, clause, params in _scope_definitions(race)}
        result_horses = []
        for horse in horses:
            sire = _code(horse.get('sire_line_code'))
            maternal = _code(horse.get('bms_line_code'))
            entries = []
            for name, (all_starts, pairs, sire_groups, maternal_groups) in scopes.items():
                known = sire is not None and maternal is not None
                if known:
                    pair = _stats(pairs.get((sire, maternal), (0,0,0,0)), all_starts)
                    sire_stat = _stats(sire_groups.get(sire, (0,0,0,0)), all_starts)
                    maternal_stat = _stats(maternal_groups.get(maternal, (0,0,0,0)), all_starts)
                    coverage = ('NO_SAMPLE' if pair['starts'] == 0 else
                                'LOW_SAMPLE' if pair['status'] == 'LOW_SAMPLE' else 'DESCRIPTIVE')
                else:
                    pair = sire_stat = maternal_stat = None
                    coverage = 'UNKNOWN_LINEAGE'
                def delta(a, b):
                    if a is None or b is None or a['top3_rate'] is None or b['top3_rate'] is None:
                        return None
                    return round(100*(a['top3_rate']-b['top3_rate']),2)
                entries.append({
                    'evidence_id': f"PAIR_{horse['horse_id']}_{name}",
                    'scope_key': name, 'coverage': coverage,
                    'pair': pair, 'sire_line': sire_stat, 'broodmare_sire_line': maternal_stat,
                    'pair_vs_sire_line_pp': delta(pair,sire_stat),
                    'pair_vs_bms_line_pp': delta(pair,maternal_stat),
                })
            result_horses.append({
                'horse_id':horse['horse_id'], 'horse_no':horse['horse_no'],
                'horse_name':horse.get('horse_name'),
                'sire_line_code':sire, 'broodmare_sire_line_code':maternal,
                'availability':'AS_OF_UNVERIFIED' if sire and maternal else 'SOURCE_UNAVAILABLE',
                'historical_counts_status':'DESCRIPTIVE_ONLY' if sire and maternal else 'NO_LINEAGE_ID',
                'scopes':entries,
            })
        return {
            'version':VERSION, 'research_only':True,'prediction_safe':False,
            'pairing_role':'sire_line_code × broodmare_sire_line_code',
            'pedigree_temporal_status':TEMPORAL_STATUS,
            'race':race,'as_of_exclusive':race['target_date'],
            'historical_window_start':date_start, 'analysis_generation':generation,
            'denominator':'ACTUAL_STARTS_EXCLUDING_CANCELLED_AND_EXCLUDED',
            'lineage_code_source':'JRDB Analysis v1.4 historical row (publication as-of unverified)',
            'scope_order':list(scopes),
            'pairing_interpretation':'DESCRIPTIVE_NOT_PROVEN_NICKS',
            'no_score':True,'no_ranking':True,
            'horses':result_horses,
            'timing_ms':{'history_scan_including_sha':scan_ms,
                         'total':round((time.perf_counter()-start_clock)*1000,1)},
        }
    finally:
        con.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sire-bms-json',type=Path,required=True)
    p.add_argument('--analysis-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    source = json.loads(a.sire_bms_json.read_text(encoding='utf-8'))
    result = analyze(source, a.analysis_root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'horses':len(result['horses']), 'timing_ms':result['timing_ms'],
                      'temporal_status':result['pedigree_temporal_status']},ensure_ascii=False))


if __name__ == '__main__':
    main()
