#!/usr/bin/env python3
"""Read-only, historical JRDB Analysis (Parquet) + one PACI race sire/BMS evidence.

No score, sibling-sire proxy, regional-type inference or CURRENT publication.
JRDB raw byte parsing is delegated to the canonical jrdb_raw Reader.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
import re
import datetime as dt
import time
from pathlib import Path

import duckdb

SOURCE_VERSION = 'brdb-sire-bms-field-evidence-v0.1'
STARTER_CODES = ('0', '3', '4', '5', '6') # JRDB: normal / DNF / disqualified / demoted / remounted
# Non-overlapping bands; intentionally not the overlapping RaceNote P2 ranges.
BANDS = ((0, 1399, 'SHORT'), (1400, 1799, 'MILE'),
         (1800, 2399, 'MIDDLE'), (2400, 9999, 'LONG'))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for buf in iter(lambda: f.read(1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def distance_band(distance):
    return next(label for lo, hi, label in BANDS if lo <= distance <= hi)


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    a = 1 + z * z / n
    c = (p + z * z / (2 * n)) / a
    r = z / a * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(max(0, c-r), 4), round(min(1, c+r), 4)]


def _paths(root):
    root = Path(root).resolve()
    ptr = json.loads((root / 'current.json').read_text('utf-8'))
    if ptr['status'] != 'CURRENT':
        raise ValueError('Analysis pointer is not CURRENT')
    mf = (root / ptr['manifest']).resolve()
    if not mf.is_relative_to(root):
        raise ValueError('unsafe manifest path')
    manifest = json.loads(mf.read_text('utf-8'))
    if manifest.get('generation_id') != ptr['generation_id'] or manifest.get('schema_version') != 'v1.4':
        raise ValueError('unexpected Analysis manifest')
    paths = []
    for row in manifest['fact_table']['partitions']:
        p = (root / row['relative_path']).resolve()
        if not p.is_relative_to(root) or sha256(p) != row['sha256']:
            raise ValueError('Analysis partition missing or hash mismatch')
        paths.append(p)
    return ptr['generation_id'], paths


def _sql_path(p):
    return "'" + str(p).replace("'", "''") + "'"


def _field_from_paci(paci, race_key):
    # Prefer the existing repository's canonical fixed-width parser. No local offsets.
    jrdb_src = Path(__file__).resolve().parents[2] / "jrdb" / "src"
    if jrdb_src.is_dir() and str(jrdb_src) not in sys.path:
        sys.path.insert(0, str(jrdb_src))
    from jrdb_raw import Parser, iter_archive_records
    if not re.fullmatch(r"[0-9A-Fa-f]{8}", race_key):
        raise ValueError("invalid race key")
    parser = Parser()
    races = [parser.bac(raw) for _, raw in iter_archive_records(paci, 'BAC')
             if raw[:8].decode('ascii') == race_key]
    if len(races) != 1:
        raise ValueError(f'expected one BAC race for {race_key}, found {len(races)}')
    race = races[0]
    entries = [parser.kyi(raw) for _, raw in iter_archive_records(paci, 'KYI')
               if raw[:8].decode('ascii') == race_key]
    if len(entries) != race['field_size'] or not entries:
        raise ValueError('BAC/KYI field mismatch')
    ids = [e['blood_registration_no'] for e in entries]
    if not all(ids) or len(set(ids)) != len(ids) or len(set(e['horse_no'] for e in entries)) != len(ids):
        raise ValueError('duplicate/missing entry keys')
    lookup = {}
    for _, raw in iter_archive_records(paci, 'UKC'):
        key = raw[:8].decode('ascii')
        if key in ids:
            row = parser.ukc(raw)
            if key in lookup and lookup[key] != row:
                raise ValueError('conflicting UKC rows')
            lookup[key] = row
    if any(k not in lookup for k in ids):
        raise ValueError('missing UKC profile; return UNKNOWN rather than fuzzy fallback')
    if not paci.name.upper().endswith(race['date_raw'][2:] + '.ZIP'):
        raise ValueError('PACI archive date / BAC date mismatch')
    if any(x['data_date'] > race['date_raw'] for x in lookup.values()):
        raise ValueError('future-dated target UKC')
    return {
        'race_key': race_key, 'target_date': '-'.join((race['date_raw'][:4], race['date_raw'][4:6], race['date_raw'][6:])),
        'venue_code': race_key[:2], 'surface_code': race['surface_code'],
        'distance': int(race['distance_raw']), 'course_code': race['course_code'],
        'horses': [dict(horse_id=e['blood_registration_no'], horse_no=int(e['horse_no']),
                        horse_name=e['horse_name'], sire=lookup[e['blood_registration_no']]['sire_name'],
                        bms=lookup[e['blood_registration_no']]['broodmare_sire_name'],
                        sire_line_code=lookup[e['blood_registration_no']]['sire_line_code'],
                        bms_line_code=lookup[e['blood_registration_no']]['broodmare_sire_line_code'])
                   for e in sorted(entries, key=lambda x: x['horse_no'])],
    }


def _stats(row, baseline):
    starts, horses, wins, top3 = map(int, row)
    b_starts, b_horses, b_wins, b_top3 = map(int, baseline)
    n3 = top3 / starts if starts else None
    b3 = b_top3 / b_starts if b_starts else None
    return {
        'starts': starts, 'horses': horses, 'wins': wins, 'top3': top3,
        'win_rate': round(wins / starts, 4) if starts else None,
        'top3_rate': round(n3, 4) if n3 is not None else None,
        'top3_wilson95': wilson(top3, starts),
        'baseline_starts': b_starts,
        'baseline_top3_rate': round(b3, 4) if b3 is not None else None,
        'top3_delta_pp': round(100 * (n3 - b3), 2) if n3 is not None and b3 is not None else None,
        'status': 'NO_SAMPLE' if starts == 0 else ('LOW_SAMPLE' if starts < 30 or horses < 10 else 'DESCRIPTIVE'),
    }


def _batch_summaries(conn, name_col, names, where, args):
    """Aggregate all named groups in a single query; keep a common, scoped baseline."""
    if name_col not in ('sire_name', 'broodmare_sire_name'):
        raise ValueError('unapproved dimension')
    if not names:
        return {}
    measure = "COUNT(*)::BIGINT, count(distinct horse_id)::BIGINT, " \
              "count(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish=1)::BIGINT, " \
              "count(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3)::BIGINT"
    base = conn.execute(f'SELECT {measure} FROM history WHERE {where}', args).fetchone()
    placeholders = ','.join('?' for _ in names)
    rows = conn.execute(f'SELECT {name_col}, {measure} FROM history WHERE {where} '
                        f'AND {name_col} IN ({placeholders}) GROUP BY 1',
                        [*args, *names]).fetchall()
    counts = {row[0]: row[1:] for row in rows}
    return {name: _stats(counts.get(name, (0, 0, 0, 0)), base) for name in names}


def analyse(field, root, *, years=10):
    t0 = time.perf_counter()
    gen, partitions = _paths(root)
    t_manifest = time.perf_counter()
    if field['surface_code'] not in ('1', '2') or not field['horses']:
        raise ValueError('only turf/dirt races with entries supported')
    target_date = field['target_date']
    try:
        dt.date.fromisoformat(target_date)
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid target_date') from exc
    if not (1 <= years <= 20):
        raise ValueError('years must be 1..20')
    first_date = dt.date.fromisoformat(target_date).replace(year=int(target_date[:4]) - years).isoformat() if target_date[5:] != '02-29' else f'{int(target_date[:4])-years:04d}-02-28'
    conn = duckdb.connect(database=':memory:')
    try:
        paths_sql = '[' + ','.join(_sql_path(p) for p in partitions) + ']'
        # Explicitly select only completed earlier starts. No target/post-race leakage.
        conn.execute(f'''CREATE TEMP TABLE history AS SELECT
               race_date, year, venue_code, course_code, track_type, distance,
               CASE WHEN distance < 1400 THEN 'SHORT'
                    WHEN distance < 1800 THEN 'MILE'
                    WHEN distance < 2400 THEN 'MIDDLE' ELSE 'LONG' END AS band,
               horse_id, sire_name, broodmare_sire_name, finish, abnormal_code
               FROM read_parquet({paths_sql})
               WHERE race_date < ? AND race_date >= ? AND abnormal_code IN ('0','3','4','5','6')
                     AND track_type IN ('1','2') AND horse_id IS NOT NULL''',
                     [target_date, first_date])
        t_input = time.perf_counter()
        names_sire = sorted({h['sire'] for h in field['horses']})
        names_bms = sorted({h['bms'] for h in field['horses']})
        args_venue = [field['venue_code'], field['surface_code'], field['distance']]
        scope_queries = [
            ('VENUE_COURSE_EXACT', 'venue_code=? AND track_type=? AND distance=? AND course_code=?', [*args_venue, field['course_code']]),
            ('VENUE_DISTANCE', 'venue_code=? AND track_type=? AND distance=?', args_venue),
            ('ALL_VENUES_DISTANCE', 'track_type=? AND distance=?', [field['surface_code'], field['distance']]),
            ('ALL_VENUES_BAND', 'track_type=? AND band=?', [field['surface_code'], distance_band(field['distance'])]),
        ]
        s_agg = {label: _batch_summaries(conn, 'sire_name', names_sire, where, params)
                 for label, where, params in scope_queries}
        bs_agg = {surface: _batch_summaries(conn,'broodmare_sire_name',names_bms,
                                           'track_type=?',[surface]) for surface in ('1','2')}
        bb_agg = {f'{surface}:{band}': _batch_summaries(conn,'broodmare_sire_name',names_bms,
                                     'track_type=? AND band=?',[surface,band])
                  for surface in ('1','2') for band in ('SHORT','MILE','MIDDLE','LONG')}
        rows = []
        for h in field['horses']:
            sire_scopes = {label: s_agg[label][h['sire']] for label, _, _ in scope_queries}
            selected_scope = next((k for k,v in sire_scopes.items() if v['status']=='DESCRIPTIVE'),None)
            bms = {'surface': {surface:bs_agg[surface][h['bms']] for surface in ('1','2')},
                   'surface_band': {key:agg[h['bms']] for key,agg in bb_agg.items()}}
            rows.append({**h, 'sire_evidence': {'scopes':sire_scopes,'best_supported_scope':selected_scope,
                                               'no_sire_substitution':True},
                         'bms_evidence': {**bms,'interpretation':'DESCRIPTIVE_ONLY_NO_AUTOMATIC_TURF_DIRT_TYPE'}})
        t_query=time.perf_counter()
        return {'version':SOURCE_VERSION,'source_generation':gen,'race':{k:v for k,v in field.items() if k!='horses'},
                'policy':{'historical_window_start':first_date,'as_of_exclusive':target_date,
                          'starter_codes': list(STARTER_CODES),'low_sample':'starts<30 or horses<10',
                          'no_related_sire_pooling': True,'no_score': True,'no_ranking': True},
                'horses':rows,'timing_ms':{'manifest_integrity':round((t_manifest-t0)*1000,1),
                                         'history_scan':round((t_input-t_manifest)*1000,1),
                                         'stat_queries':round((t_query-t_input)*1000,1),
                                         'total':round((t_query-t0)*1000,1)}}
    finally:
        conn.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--paci',type=Path,required=True)
    p.add_argument('--race-key',required=True)
    p.add_argument('--analysis-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--years',type=int,default=10)
    args=p.parse_args()
    if args.years<1 or args.years>20:
        p.error('years must be 1..20')
    field=_field_from_paci(args.paci,args.race_key)
    result=analyse(field,args.analysis_root,years=args.years)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output), 'horses':len(result['horses']), 'timing_ms':result['timing_ms']},ensure_ascii=False))


if __name__ == '__main__':
    main()
