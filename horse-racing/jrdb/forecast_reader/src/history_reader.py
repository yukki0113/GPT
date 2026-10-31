"""Canonical Data Storage query routing and validated normalized history input."""
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools/data-storage'))


def read_history(path, target_date):
    # Explicit normalized fixture/export route. Class/eligibility semantics must
    # be established upstream and versioned; this adapter never guesses codes.
    if path.suffix == '.json':
        value = json.loads(path.read_text())
        if value.get('artifact_type') == 'jrdb_analysis':
            return read_generation(value, path.parent, target_date)
        if value.get('schema_version') != 'forecast-history.v1':
            raise ValueError('INVALID_REQUEST: history schema')
        return value['races'], value['rows'], {**coverage(value['rows'], target_date), 'engine': 'normalized-json', 'query': None}
    if '.tar' in path.name:
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as scratch:
            subprocess.run([sys.executable, str(root / 'tools/data-storage/scripts/safe_unpack_staged_archive.py'), '--archive', str(path), '--output-dir', scratch], check=True, capture_output=True)
            base = Path(scratch)
            pointer = json.loads((base / 'current.json').read_text())
            manifest_path = (base / pointer['manifest']).resolve()
            if not manifest_path.is_relative_to(base):
                raise ValueError('INVALID_REQUEST: manifest path')
            manifest = json.loads(manifest_path.read_text())
            return read_generation(manifest, base, target_date)
    from data_storage.query import execute_query
    # Projection excludes payouts/odds. The target year is excluded at the query
    # boundary; earlier rows can supply previous runs for the ten-year cohort.
    columns, values = execute_query(path, "SELECT race_date,race_key,horse_id,horse_no,frame_no,age,sire_name,broodmare_sire_name,jockey_name,running_style,finish,final_win_popularity,prev_race_key_1,distance,race_condition_code,grade_code,race_name,venue_code,track_type,course_code FROM data WHERE race_date < '" + target_date[:4] + "-01-01'")
    rows = [dict(zip(columns, row)) for row in values]
    # Analysis Lite lacks eligibility and weight rule: preserve UNKNOWN rather
    # than manufacture same-condition evidence from grade alone.
    races = {}
    for row in rows:
        key = row['race_key']
        races[key] = {'race_key': key, 'date': str(row['race_date']), 'name': row['race_name'], 'venue': row['venue_code'],
                      'surface': row['track_type'], 'distance': row['distance'], 'race_class': None,
                      'eligibility': None, 'course': row['course_code'], 'weight_rule': None}
    return list(races.values()), rows, {**coverage(rows, target_date), 'engine': 'tools/data-storage', 'query': 'historical projection, year < target.year', 'missing_conditions': ['race_class', 'eligibility', 'weight_rule']}


def coverage(rows, target_date):
    keys = [(r['race_key'], r['horse_id']) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('DUPLICATE_RACE_OR_RUN')
    years = sorted({int(str(r['race_date'])[:4]) for r in rows})
    expected = set(range(int(target_date[:4]) - 10, int(target_date[:4])))
    return {'years_present': years, 'years_missing': sorted(expected - set(years)),
            'starts': len(rows), 'race_count': len({r['race_key'] for r in rows}), 'unique_race_horse': True}


def read_generation(manifest, base, target_date):
    if manifest.get('validation_status') not in ('PASS','success'):
        raise ValueError('INVALID_REQUEST: Analysis generation not validated')
    historical, audit = [], []
    years = [int(p['year']) for p in manifest['fact_table']['partitions'] if int(p['year']) < int(target_date[:4])]
    if len(years) != len(set(years)):
        raise ValueError('DUPLICATE_RACE_OR_RUN: partition year')
    for part in manifest['fact_table']['partitions']:
        if int(part['year']) >= int(target_date[:4]):
            continue
        asset = (base / part['relative_path']).resolve()
        if not asset.is_relative_to(base.resolve()) or asset.stat().st_size != part['size_bytes'] or hashlib.sha256(asset.read_bytes()).hexdigest() != part['sha256']:
            raise ValueError('HASH_MISMATCH')
        _, rows, _ = read_history(asset,target_date)
        if len(rows) != part['rows'] or any(int(str(r['race_date'])[:4]) != int(part['year']) for r in rows):
            raise ValueError('SOURCE_CHANGED: partition rows/year')
        historical.extend(rows)
        audit.append({'year':part['year'],'sha256':part['sha256'],'rows':len(rows)})
    return [],historical,{**coverage(historical,target_date),'partitions':audit,'engine':'tools/data-storage','missing_conditions':['race_class','eligibility','weight_rule'],'generation':manifest['generation_id']}
