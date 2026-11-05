#!/usr/bin/env python3
"""BRDB ④: research-only canonical maternal siblings and aunts/uncles.

Target facts are PACI UKC; older relatives are guarded canonical IDs in the
hash-pinned BRDB research generation. Historical profile availability is not
certified by a full historical replay. No prediction, score or CURRENT update.
"""
from __future__ import annotations
import argparse
import json
import re
import time
from pathlib import Path

import duckdb
from run_brdb_sire_bms_evidence import _field_from_paci, _paths, _sql_path, sha256, distance_band

VERSION = 'brdb-maternal-relatives-evidence-v0.1'
TEMPORAL_STATUS = 'RESEARCH_PROFILE_DATE_CHECKED_NOT_HISTORICALLY_REPLAYED'


def _research_assets(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('validation_status') != 'PASS' or manifest.get('research_only') is not True:
        raise ValueError('validated research generation required')
    paths = []
    for file in ('pedigree_fact.parquet', 'parent_relation.parquet'):
        p = (root / file).resolve()
        if not p.is_relative_to(root) or sha256(p) != manifest['output_sha256'][file]:
            raise ValueError('research pedigree asset hash mismatch')
        paths.append(p)
    return manifest['generation_id'], paths


def _target_profiles(paci, race_key):
    # Existing common fixed-width reader; no independent JRDB byte offsets.
    field = _field_from_paci(paci, race_key)
    from jrdb_raw import Parser, iter_archive_records
    ids = {h['horse_id'] for h in field['horses']}
    parser = Parser()
    profiles = {}
    for _, raw in iter_archive_records(paci, 'UKC'):
        h = parser.ukc(raw)
        if h['horse_id'] in ids:
            if h['horse_id'] in profiles and h != profiles[h['horse_id']]:
                raise ValueError('conflicting target UKC')
            profiles[h['horse_id']] = h
    if set(profiles) != ids:
        raise ValueError('target UKC incomplete')
    return field, profiles


def _scope_definitions(field):
    return [
        ('VENUE_COURSE_EXACT', 'venue_code=? AND track_type=? AND distance=? AND course_code=?',
         [field['venue_code'], field['surface_code'], field['distance'], field['course_code']]),
        ('VENUE_DISTANCE', 'venue_code=? AND track_type=? AND distance=?',
         [field['venue_code'], field['surface_code'], field['distance']]),
        ('VENUE_BAND', 'venue_code=? AND track_type=? AND band=?',
         [field['venue_code'], field['surface_code'], distance_band(field['distance'])]),
        ('ALL_VENUES_DISTANCE', 'track_type=? AND distance=?',
         [field['surface_code'], field['distance']]),
        ('ALL_VENUES_BAND', 'track_type=? AND band=?',
         [field['surface_code'], distance_band(field['distance'])]),
    ]


def _records(con, field, ids):
    if not ids:
        return {}
    marks = ','.join('?' for _ in ids)
    scopes = {}
    for key, where, args in _scope_definitions(field):
        rows = con.execute(f"""SELECT horse_id, count(*)::INT AS starts,
            count(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish=1)::INT AS wins,
            count(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3)::INT AS top3
            FROM history WHERE {where} AND horse_id IN ({marks}) GROUP BY 1""",
                           [*args, *ids]).fetchall()
        scopes[key] = {
            row[0]: {'starts': row[1], 'wins': row[2], 'top3': row[3],
                     'top3_rate': round(row[3] / row[1], 4)} for row in rows
        }
    return {
        id: {scope: scopes[scope].get(id, {'starts': 0, 'wins': 0, 'top3': 0,
                                           'top3_rate': None}) for scope in scopes}
        for id in ids
    }


def analyze(paci, race_key, research_root, analysis_root):
    t0 = time.perf_counter()
    field, target = _target_profiles(Path(paci), race_key)
    generation, assets = _research_assets(research_root)
    analysis_generation, parts = _paths(analysis_root)
    con = duckdb.connect(database=':memory:')
    try:
        con.execute('CREATE TEMP VIEW pedigree AS SELECT * FROM ' + _sql_path(assets[0]))
        con.execute('CREATE TEMP VIEW relations AS SELECT * FROM ' + _sql_path(assets[1]))
        all_found, ret = [], []
        target_date = field['target_date'].replace('-', '')
        for h in field['horses']:
            t = target[h['horse_id']]
            year = t['dam_birth_year']
            # Uniqueness and independent guards: mother name, birth year, female,
            # target BMS name and target BMS official sire-line code.
            candidates = con.execute('''SELECT horse_id, profile_data_date FROM pedigree
                WHERE horse_name=? AND substr(birth_date,1,4)=? AND sex_code='2'
                AND sire_name=? AND sire_line_code=?''', [
                    t['dam_name'], str(year) if year is not None else '',
                    t['broodmare_sire_name'], t['broodmare_sire_line_code']
                ]).fetchall()
            candidates = [
                r for r in candidates if r[1] and re.fullmatch(r'[0-9]{8}', r[1])
                and r[1] <= target_date
            ]
            # A full-sibling claim also needs a canonically resolved sire ID.
            sire_candidates = con.execute('''SELECT horse_id,profile_data_date FROM pedigree
                WHERE horse_name=? AND substr(birth_date,1,4)=? AND sex_code='1'
                AND sire_line_code=?''', [
                    t['sire_name'],
                    str(t['sire_birth_year']) if t['sire_birth_year'] is not None else '',
                    t['sire_line_code'],
                ]).fetchall()
            sire_candidates = [
                row for row in sire_candidates if row[1] and re.fullmatch(r'[0-9]{8}', row[1])
                and row[1] <= target_date
            ]
            sire_id = sire_candidates[0][0] if len(sire_candidates) == 1 else None
            relatives, mother_id, granddam_id = [], None, None
            if len(candidates) == 1:
                mother_id = candidates[0][0]
                sibs = con.execute('''SELECT p.horse_id,p.horse_name,p.sire_name,
                    p.birth_date,p.profile_data_date
                    FROM relations r JOIN pedigree p ON r.child_horse_id=p.horse_id
                    WHERE r.role='dam'
                    AND r.resolution_status IN ('RESOLVED_EXACT','RESOLVED_ALIAS')
                    AND r.resolved_parent_horse_id=?
                    ORDER BY p.birth_date,p.horse_id''', [mother_id]).fetchall()
                for hid, name, sire, birth, profile_date in sibs:
                    if hid == h['horse_id'] or not birth or birth >= t['birth_date']:
                        continue
                    if not profile_date or not re.fullmatch(r'[0-9]{8}', profile_date) or profile_date > target_date:
                        continue
                    sibling_sire = con.execute('''SELECT resolved_parent_horse_id
                        FROM relations WHERE child_horse_id=? AND role='sire'
                        AND resolution_status IN ('RESOLVED_EXACT','RESOLVED_ALIAS')''',
                        [hid]).fetchall()
                    verified_full = (sire_id is not None and len(sibling_sire) == 1
                                     and sibling_sire[0][0] == sire_id)
                    relationship = ('FULL_SIBLING' if verified_full else
                                    'SAME_DAM_SAME_SIRE_NAME_UNVERIFIED'
                                    if sire == t['sire_name'] else 'MATERNAL_HALF_SIBLING')
                    relatives.append(dict(
                        horse_id=hid, horse_name=name,
                        relationship=relationship,
                        birth_date=birth, profile_data_date=profile_date,
                    ))
                grandma = con.execute('''SELECT resolved_parent_horse_id
                    FROM relations WHERE child_horse_id=? AND role='dam'
                    AND resolution_status IN ('RESOLVED_EXACT','RESOLVED_ALIAS')''',
                    [mother_id]).fetchall()
                if len(grandma) == 1 and grandma[0][0]:
                    granddam_id = grandma[0][0]
                    other = con.execute('''SELECT p.horse_id,p.horse_name,p.birth_date,
                        p.profile_data_date
                        FROM relations r JOIN pedigree p ON r.child_horse_id=p.horse_id
                        WHERE r.role='dam'
                        AND r.resolution_status IN ('RESOLVED_EXACT','RESOLVED_ALIAS')
                        AND r.resolved_parent_horse_id=? AND r.child_horse_id<>?
                        ORDER BY p.birth_date,p.horse_id''',
                        [granddam_id, mother_id]).fetchall()
                    for hid, name, birth, profile_date in other:
                        if (not profile_date or not re.fullmatch(r'[0-9]{8}', profile_date)
                                or profile_date > target_date or not birth
                                or birth >= t['birth_date']):
                            continue
                        relatives.append(dict(
                            horse_id=hid, horse_name=name,
                            relationship='MATERNAL_AUNT_UNCLE',
                            birth_date=birth, profile_data_date=profile_date,
                        ))
            ids_here = [r['horse_id'] for r in relatives]
            if len(ids_here) != len(set(ids_here)):
                raise ValueError('repeated relative ID')
            all_found.extend(ids_here)
            ret.append(dict(
                horse_id=h['horse_id'], horse_no=h['horse_no'], horse_name=h['horse_name'],
                mother_horse_id=mother_id, maternal_granddam_horse_id=granddam_id,
                status=('SOURCE_UNAVAILABLE' if mother_id is None else
                        'NO_SAMPLE' if not relatives else 'DESCRIPTIVE_RELATION'),
                relatives=relatives,
            ))
        parts_sql = '[' + ','.join(_sql_path(p) for p in parts) + ']'
        con.execute(f'''CREATE TEMP TABLE history AS SELECT
            race_date,venue_code,course_code,track_type,distance,horse_id,
            finish,abnormal_code,
            CASE WHEN distance<1400 THEN 'SHORT'
                 WHEN distance<1800 THEN 'MILE'
                 WHEN distance<2400 THEN 'MIDDLE' ELSE 'LONG' END AS band
            FROM read_parquet({parts_sql})
            WHERE race_date<? AND abnormal_code IN ('0','3','4','5','6')
            AND track_type IN ('1','2')''', [field['target_date']])
        details = _records(con, field, sorted(set(all_found)))
        for horse in ret:
            for rel in horse['relatives']:
                rel['scope_stats'] = details[rel['horse_id']]
                rel['has_target_surface_band_history'] = (
                    rel['scope_stats']['ALL_VENUES_BAND']['starts'] > 0)
            horse['relative_counts'] = {
                role: sum(r['relationship'] == role for r in horse['relatives'])
                for role in ('FULL_SIBLING', 'SAME_DAM_SAME_SIRE_NAME_UNVERIFIED',
                             'MATERNAL_HALF_SIBLING', 'MATERNAL_AUNT_UNCLE')
            }
            horse['with_relevant_starts'] = sum(
                r['has_target_surface_band_history'] for r in horse['relatives'])
        return dict(
            version=VERSION, research_only=True, prediction_safe=False,
            pedigree_temporal_status=TEMPORAL_STATUS,
            race={k: v for k, v in field.items() if k != 'horses'},
            pedigree_generation=generation, analysis_generation=analysis_generation,
            relationship_policy='GUARDED_CANONICAL_DAM_ID_ONLY',
            older_birth_only=True, as_of_exclusive=field['target_date'],
            sample_policy='NO_RESULTS_IS_NOT_NEGATIVE_APTITUDE',
            horses=ret, timing_ms={'total': round((time.perf_counter() - t0) * 1000, 1)},
        )
    finally:
        con.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--paci', type=Path, required=True)
    p.add_argument('--race-key', required=True)
    p.add_argument('--research-generation-root', type=Path, required=True)
    p.add_argument('--analysis-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = analyze(a.paci, a.race_key, a.research_generation_root, a.analysis_root)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
    print(json.dumps({
        'horses': len(result['horses']),
        'time_ms': result['timing_ms']['total'],
        'status_counts': {s: sum(h['status'] == s for h in result['horses'])
                          for s in sorted(set(h['status'] for h in result['horses']))},
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
