"""Read accepted BAC assets through common Data Storage; never parse new bytes."""
import hashlib
from pathlib import Path
from race_condition_resolver import condition


def read_conditions(manifest, assets, target_year):
    from data_storage.query import execute_query
    if manifest.get('artifact_type') != 'jrdb_normalized_warehouse_final_generation' or manifest.get('status') != 'PASS':
        raise ValueError('INVALID_REQUEST: unaccepted Warehouse manifest')
    races, audits = {}, []
    for asset in manifest['assets']:
        if asset.get('family') != 'bac' or not target_year - 11 <= int(asset['year']) < target_year:
            continue
        path = Path(assets[asset['relative_path']])
        if path.stat().st_size != asset['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
            raise ValueError('HASH_MISMATCH')
        columns, values = execute_query(path, 'SELECT * FROM data')
        if len(values) != asset['row_count']:
            raise ValueError('SOURCE_CHANGED: BAC row count')
        for values_row in values:
            row = dict(zip(columns, values_row))
            projected = condition(row)
            key = projected['race_key']
            if key in races and races[key] != projected:
                raise ValueError('DUPLICATE_RACE_OR_RUN: conflicting BAC conditions')
            races[key] = projected
        audits.append({'year':asset['year'],'sha256':asset['sha256'],'rows':len(values),'relative_path':asset['relative_path']})
    # SED contains the same published race-condition fields, parsed by the
    # shared Raw Parser upstream. Use only declared, hash-bound historical assets
    # to cover gaps in BAC; never query finish/popularity/payout columns here.
    for asset in manifest['assets']:
        if asset.get('family') != 'sed' or asset['relative_path'] not in assets or int(asset['year']) >= target_year:
            continue
        path = Path(assets[asset['relative_path']])
        if path.stat().st_size != asset['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
            raise ValueError('HASH_MISMATCH')
        columns, values = execute_query(path, 'SELECT race_key_raw,date_raw,race_name,distance_m,surface_code,turn_code,layout_code,race_type_code,race_class_code,race_symbol_code,weight_condition_code,grade_code FROM data')
        if len(values) != asset['row_count']:
            raise ValueError('SOURCE_CHANGED: SED row count')
        supplements = {}
        for values_row in values:
            row = dict(zip(columns, values_row))
            if row['race_key_raw'] in races:
                continue
            row.update(distance_raw=str(row['distance_m']), symbol_code=row['race_symbol_code'], weight_rule_code=row['weight_condition_code'])
            projected = condition(row)
            key = projected['race_key']
            if key in supplements and supplements[key] != projected:
                raise ValueError('DUPLICATE_RACE_OR_RUN: conflicting SED conditions')
            supplements[key] = projected
        races.update(supplements)
        audits.append({'family':'sed','year':asset['year'],'sha256':asset['sha256'],'rows':len(values),'supplement_races':len(supplements),'relative_path':asset['relative_path']})
    missing = sorted(set(range(target_year-10,target_year)) - {int(a['year']) for a in audits})
    if missing:
        raise ValueError('SOURCE_NOT_FOUND: BAC years '+str(missing))
    return sorted(races.values(), key=lambda r:r['race_key']), audits
