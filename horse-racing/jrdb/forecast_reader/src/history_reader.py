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
        if value.get('schema_version') != 'forecast-history.v1':
            raise ValueError('INVALID_REQUEST: history schema')
        return value['races'], value['rows'], {'engine': 'normalized-json', 'query': None}
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
            historical = []
            for part in manifest['fact_table']['partitions']:
                if int(part['year']) >= int(target_date[:4]):
                    continue
                asset = (base / part['relative_path']).resolve()
                if not asset.is_relative_to(base) or hashlib.sha256(asset.read_bytes()).hexdigest() != part['sha256']:
                    raise ValueError('HASH_MISMATCH')
                _, rows, _ = read_history(asset, target_date)
                historical.extend(rows)
            return [], historical, {'engine': 'tools/data-storage', 'missing_conditions': ['race_class', 'eligibility', 'weight_rule'], 'generation': manifest['generation_id']}
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
    return list(races.values()), rows, {'engine': 'tools/data-storage', 'query': 'historical projection, year < target.year', 'missing_conditions': ['race_class', 'eligibility', 'weight_rule']}
