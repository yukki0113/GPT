"""Research input gate only: no profile, prediction or as-of certification."""
import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import zipfile

SCHEMA = 'jpdb-forward-input-gate-v0.1'
POLICY = 'JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def iso_day(value):
    day = date.fromisoformat(value)
    require(day.isoformat() == value and day.year == 2026, 'date outside 2026 scope')
    return day


def instant(value):
    t = datetime.fromisoformat(value)
    require(t.utcoffset() is not None, 'timezone required')
    return t.astimezone(timezone.utc)


def pinned_json(path, expected):
    raw = path.read_bytes()
    require(re.fullmatch('[0-9a-f]{64}', expected) and sha(raw) == expected, 'JSON SHA mismatch')
    return json.loads(raw)


def validate(plan_path, expected_sha, *, now):
    """Check pins and date separation. Capture/calendar claims still need external audit."""
    plan_path = Path(plan_path)
    plan = pinned_json(plan_path, expected_sha)
    require(plan['schema_version'] == SCHEMA, 'unsupported plan')
    target = iso_day(plan['target_date'])
    require(instant(plan['captured_at']) <= now < instant(plan['first_post_at']), 'not pre-race')
    require(instant(plan['first_post_at']).astimezone(timezone(timedelta(hours=9))).date() == target, 'post date mismatch')
    assets = plan['assets']
    require(set(assets) == {'calendar', 'daily_sed', 'historical_paci', 'target_paci'}, 'asset set mismatch')
    def path(key):
        return plan_path.parent / assets[key]['path']
    def obj(key):
        return pinned_json(path(key), assets[key]['sha256'])
    cal, sed, paci = (obj(k) for k in ('calendar', 'daily_sed', 'historical_paci'))
    require(cal['source'] == 'PACI_DRIVE_DATE_INVENTORY' and cal['through_date'] == target.isoformat(), 'calendar scope mismatch')
    days = [iso_day(d) for d in cal['race_dates']]
    require(days == sorted(set(days)) and days[-1:] == [target] and len(days) > 1, 'calendar ordering/target mismatch')
    history = [d.isoformat() for d in days[:-1]]
    require(target <= days[-2] + timedelta(days=7), 'history snapshot stale')
    for spec, prefix, version in ((sed, 'SED', 'jpdb-p12-daily-sed-pinned-v1'),
                                  (paci, 'PACI', 'jpdb-p2-paci-bac-pinned-v1')):
        require(spec['schema_version'] == version, 'history manifest version mismatch')
        require(spec['expected_race_dates'] == history and spec['coverage_to_inclusive'] == history[-1], 'history calendar mismatch')
        require([x['race_date'] for x in spec['selected']] == history, 'missing/extra history day')
        for x in spec['selected']:
            require(x['name'] == prefix + iso_day(x['race_date']).strftime('%y%m%d') + '.zip', 'history filename mismatch')
            require(type(x['size']) is int and x['size'] > 0 and re.fullmatch('[0-9a-f]{64}', x['zip_sha256']), 'invalid history pin')
    require(sed['calendar_source'] == 'PACI_DRIVE_DATE_INVENTORY' and sed['asof_policy'] == POLICY, 'SED policy mismatch')
    t = path('target_paci')
    pin = assets['target_paci']
    require(t.name == 'PACI' + target.strftime('%y%m%d') + '.zip' and t.stat().st_size == pin['size'], 'target name/size mismatch')
    require(sha(t.read_bytes()) == pin['sha256'], 'target SHA mismatch')
    require(isinstance(pin['drive_file_id'], str) and bool(pin['drive_file_id'].strip()), 'target Drive identity missing')
    with zipfile.ZipFile(t) as z:
        require(z.testzip() is None, 'target ZIP CRC mismatch')
    return {'schema_version': SCHEMA, 'status': 'PASS_INPUT_CONTRACT_ONLY',
            'target_date': target.isoformat(), 'history_days': len(history), 'history_to': history[-1],
            'plan_sha256': expected_sha, 'asset_sha256': {k: v['sha256'] for k, v in sorted(assets.items())},
            'capture_claim_externally_attested': False, 'historical_raw_validated': False,
            'profile_built': False, 'research_only': True, 'prediction_safe': False, 'production_authorized': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--plan-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    receipt = validate(a.plan, a.plan_sha256, now=datetime.now(timezone.utc))
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write('\n')


if __name__ == '__main__':
    main()
