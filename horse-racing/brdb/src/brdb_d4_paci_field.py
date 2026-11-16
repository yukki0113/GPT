#!/usr/bin/env python3
"""Build a research-only D4 input from one exact PACI race, using JRDB parser.

PACI KYI/BAC + UKC provide *source observations*, not independently verified
pre-off-time evidence. No historical prediction, scores or CURRENT mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'horse-racing/jrdb/src'))
from jrdb_raw import Parser, canonical_members, split_fixed_records  # noqa: E402


class PACIFieldError(ValueError):
    pass


def require(test, reason):
    if not test:
        raise PACIFieldError(reason)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def dated(value):
    require(isinstance(value, str) and re.fullmatch(r'20\d{6}', value),
            'invalid YYYYMMDD source date')
    try:
        return date.fromisoformat(value[:4] + '-' + value[4:6] + '-' + value[6:])
    except ValueError as exc:
        raise PACIFieldError('invalid source calendar date') from exc


def assemble(*, archive_name, race_key, bac, kyi, ukc):
    """Pure validated join; all raw parsing belongs to jrdb_raw.Parser."""
    match = re.fullmatch(r'PACI(\d{6})\.zip', archive_name)
    require(match is not None, 'not an exact PACI archive name')
    archive_date = '20' + match.group(1)
    target_date = dated(archive_date)
    require(target_date >= date(2026, 11, 2), 'D3 retrospective cutoff exceeds race')
    require(re.fullmatch(r'\d{4}[0-9A-Fa-f]{2}\d{2}', race_key) is not None,
            'invalid race key')
    require(race_key[2:4] == archive_date[2:4] and race_key[:2].isdigit()
            and 1 <= int(race_key[:2]) <= 10 and
            1 <= int(race_key[-2:]) <= 12, 'race key/archive mismatch')
    races = [r for r in bac if r['race_key_raw'] == race_key]
    require(len(races) == 1, 'missing or duplicate BAC target')
    race = races[0]
    require(race['date_raw'] == archive_date, 'BAC archive date mismatch')
    require(race['surface_code'] in ('1', '2') and
            type(race['distance_raw']) is str and
            race['distance_raw'].isdigit(), 'unsupported surface/distance')
    distance = int(race['distance_raw'])
    require(600 <= distance <= 5000, 'unsupported distance')
    field = [r for r in kyi if r['race_key_raw'] == race_key]
    require(field, 'missing KYI target')
    require(type(race['field_size']) is int and race['field_size'] == len(field),
            'BAC field size vs KYI declarations mismatch')
    ids = set()
    numbers = set()
    for r in field:
        hid, no = r['blood_registration_no'], r['horse_no']
        require(isinstance(hid, str) and re.fullmatch(r'\d{8}', hid) is not None,
                'invalid JRDB horse ID')
        require(type(no) is int and 1 <= no <= 18, 'invalid horse number')
        require(hid not in ids and no not in numbers, 'duplicate KYI identity')
        ids.add(hid)
        numbers.add(no)
    source = {}
    for r in ukc:
        hid = r['horse_id']
        if hid not in ids:
            continue
        require(hid not in source, 'ambiguous duplicate UKC profile')
        source[hid] = r
    require(ids == set(source), 'UKC source not complete for target race')
    entrants = []
    for r in sorted(field, key=lambda row: row['horse_no']):
        profile = source[r['blood_registration_no']]
        rawdate = profile.get('data_date')
        require(isinstance(rawdate, str) and re.fullmatch(r'20\d{6}', rawdate) is not None,
                'invalid or sentinel UKC profile data date')
        require(dated(rawdate) <= target_date, 'future UKC profile detected')
        entrants.append({
            'horse_id':r['blood_registration_no'],
            'horse_no':r['horse_no'],
            'sire_name':profile.get('sire_name'),
            'broodmare_sire_name':profile.get('broodmare_sire_name'),
        })
    # BAC does not establish track_condition_code; intentionally omit it.
    result = {'race':{
        'research_only':True,
        'target_date':target_date.isoformat(),
        'venue_code':race_key[:2],
        'track_type':race['surface_code'],
        'distance':distance,
        'field_size':len(entrants),
    }, 'entrants':entrants}
    return result


def extract(path: Path, race_key: str):
    parser = Parser()
    raw_bytes = path.read_bytes()
    source_sha = sha256(raw_bytes)
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None, 'PACI ZIP CRC failure')
        groups = {}
        member_receipt = {}
        for kind in ('BAC', 'KYI', 'UKC'):
            members = canonical_members(z, kind)
            require(bool(members), 'missing ' + kind + ' members')
            rows = []
            for member in members:
                raw = z.read(member)
                records = split_fixed_records(raw, kind)
                require(bool(records), 'empty or malformed ' + kind + ' member')
                member_receipt[member] = {
                    'sha256':sha256(raw),'bytes':len(raw),'records':len(records)}
                parse = getattr(parser,kind.lower())
                rows.extend(parse(rec) for rec in records)
            groups[kind] = rows
    context = assemble(archive_name=path.name, race_key=race_key,
                       bac=groups['BAC'],kyi=groups['KYI'],ukc=groups['UKC'])
    receipt = {
        'status':'RESEARCH_INPUT_ONLY',
        'prediction_safe':False,
        'source_time_status':'SAME_DAY_RELEASE_TIME_UNVERIFIED',
        'source_archive':path.name,'source_archive_sha256':source_sha,
        'race_key':race_key,'member_inventory':member_receipt,
        'field_size':context['race']['field_size'],
        'ukc_joined_horses':len(context['entrants'])
    }
    return context, receipt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--paci',required=True,type=Path)
    p.add_argument('--race-key',required=True)
    p.add_argument('--context',required=True,type=Path)
    p.add_argument('--receipt',required=True,type=Path)
    a = p.parse_args()
    context,receipt = extract(a.paci,a.race_key)
    for path,payload in ((a.context,context),(a.receipt,receipt)):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+'\n',
                        encoding='utf-8')
    print(json.dumps({'status':'RESEARCH_INPUT_ONLY',
                      'field_size':context['race']['field_size'],
                      'archive_sha256':receipt['source_archive_sha256']},
                     sort_keys=True))


if __name__ == '__main__':
    main()
