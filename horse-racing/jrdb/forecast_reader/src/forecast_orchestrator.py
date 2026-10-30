"""Pure evidence bundle builder for independently validated normalized history."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from contract_validator import validate_evidence

from sampling import select
from trend_aggregator import aggregate, AXES


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def build(target, races, rows, runners, rules):
    selected = select(target, races, rules)
    keys = [(r['race_key'], r['horse_id']) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('DUPLICATE_RACE_OR_RUN')
    if any(r['race_date'] >= target['date'] for r in rows):
        raise ValueError('FUTURE_LEAK')
    by_key = {(r['race_key'], r['horse_id']): r for r in rows}
    prepared = []
    for row in rows:
        item = dict(row)
        previous = by_key.get((row.get('prev_race_key_1'), row['horse_id']))
        if previous:
            if previous['race_date'] >= row['race_date']:
                raise ValueError('FUTURE_LEAK')
            item['previous_distance'] = previous.get('distance')
            item['previous_class'] = previous.get('race_class')
        prepared.append(item)
    trends = {}
    for label, key_field in [('exact_only', 'exact_race_keys'), ('supplement_only', 'supplement_race_keys')]:
        subset = [r for r in prepared if r['race_key'] in selected[key_field]]
        trends[label] = aggregate(subset)
    for runner in runners:
        previous = runner.get('previous_run') or {}
        values = {'frame': runner.get('frame'), 'running_style': runner.get('running_style_code'),
                  'jockey': runner.get('jockey'), 'previous_distance': previous.get('distance_m'),
                  'previous_class': previous.get('race_class_code')}
        runner['trend_matches'] = []
        for axis in AXES:
            value = values.get(axis)
            groups = trends['exact_only'][axis]['groups']
            observed = [g for g in groups if str(value) == g['group']]
            runner['trend_matches'].append({'dimension': axis, 'result': 'unknown' if value is None or not groups else ('match' if observed else 'mismatch'),
                                           'reason': 'current_value_missing' if value is None else ('historical_groups_missing' if not groups else None),
                                           'interpretation': 'observed historical group membership; no prediction', 'evidence': observed})
        runner['data_coverage'] = {'previous_run': 'available' if runner.get('previous_run') else 'missing'}
    represented = {r['race_key'] for r in prepared}
    incomplete = bool((set(selected['exact_race_keys']) | set(selected['supplement_race_keys'])) - represented) or any(axis['missing_count'] for table in trends.values() for axis in table.values())
    missing_previous = any(not r.get('previous_run') for r in runners)
    status = 'PARTIAL' if incomplete or missing_previous or selected['failure_code'] or not selected['exact_count'] else 'PASS'
    return {'schema_version': 'forecast-evidence.v1', 'status': status, 'target': target,
            'sampling': selected, 'trends': trends, 'runners': runners,
            'gate_status': {'A': 'PASS' if not selected['failure_code'] else 'PARTIAL',
                            'B': 'PARTIAL' if incomplete or not selected['exact_count'] else 'PASS', 'C': 'PARTIAL' if missing_previous else 'PASS'},
            'limitations': ['Runner comparisons describe observed groups and do not estimate outcomes.']}


def publish(output_dir, request, evidence, sampling_audit, source_audit):
    validate_evidence(evidence)
    request_hash = hashlib.sha256(canonical(request)).hexdigest()
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / request_hash
    if destination.exists():
        expected = {'forecast_evidence.json': evidence, 'sampling_audit.json': sampling_audit, 'source_audit.json': source_audit}
        if all((destination / name).is_file() and (destination / name).read_bytes() == canonical(value) for name,value in expected.items()):
            return destination
        raise ValueError('SOURCE_CHANGED: output exists')
    with tempfile.TemporaryDirectory(dir=root) as scratch:
        stage = Path(scratch) / 'bundle'
        stage.mkdir()
        files = {'forecast_evidence.json': evidence, 'sampling_audit.json': sampling_audit, 'source_audit.json': source_audit}
        hashes = {}
        for name, value in files.items():
            content = canonical(value)
            (stage / name).write_bytes(content)
            hashes[name] = hashlib.sha256(content).hexdigest()
        (stage / 'manifest.json').write_bytes(canonical({'request_sha256': request_hash, 'outputs': hashes, 'reader_version': '1.0.0', 'code_sha256': hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()}))
        os.rename(stage, destination)
    return destination
