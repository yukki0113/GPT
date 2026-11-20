"""Research-only actual SED going input producer via JRDB canonical Parser.

Place in horse-racing/brdb/src. No fixed-width field slicing is permitted here.
Call through horse-racing/jrdb/src/jrdb_raw.py and jrdb_ukc.py.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

VERSION = 'brdb-sed-going-ingest-v0.1-candidate'
GOING_CODE = {
    '10': '良', '11': '良', '12': '良',
    '20': '稍重', '21': '稍重', '22': '稍重',
    '30': '重', '31': '重', '32': '重',
    '40': '不良', '41': '不良', '42': '不良',
}
# JRDB SED source specifications official_specs 062_sedsiyo_doc.txt
# 0: normal; 1: canceled; 2: excluded; 3: DNF; 4: disqualified;
# 5: demoted; 6: remounted. This first research gate counts only abnormal 0.
ABNORMAL = set('0123456')


def must(expr, why):
    if not expr:
        raise ValueError(why)


def _raw_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _date8(iso):
    return date.fromisoformat(iso).strftime('%y%m%d')


def _validate_pair(paci_path, sed_path, target_date):
    p, s = Path(paci_path), Path(sed_path)
    pm = re.fullmatch(r'PACI(\d{6})\.zip', p.name, flags=re.I)
    sm = re.fullmatch(r'SED(\d{6})\.zip', s.name, flags=re.I)
    must(pm is not None and sm is not None and pm.group(1) == sm.group(1), 'PACI/SED date mismatch')
    yymmdd = pm.group(1)
    d = f'20{yymmdd[:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}'
    must(date.fromisoformat(d) < date.fromisoformat(target_date), 'target/post-target data leakage')
    return d, yymmdd


def normalize(pairs, race, as_of_exclusive):
    """Return (existing v0.3 going input contract, aggregate-only receipt).

    Each pair is a (PACI-zip, SED-zip) with one identical calendar day.
    Never use post-result UKC: the same-day official PACI UKC is the source.
    Require full-field KYI, SED and UKC canonical IDs/horse numbers to agree.
    """
    # `jrdb_raw` is the repository's authoritative fixed-width reader.
    jrdb_src = Path(__file__).resolve().parents[2] / "jrdb" / "src"
    if jrdb_src.is_dir() and str(jrdb_src) not in sys.path:
        sys.path.insert(0, str(jrdb_src))
    from jrdb_raw import Parser, iter_archive_records

    must(race['target_date'] == as_of_exclusive, 'race date mismatch')
    must(race['surface_code'] in ('1', '2'), 'invalid surface')
    must(pairs, 'no historical source pairs')
    p = Parser()
    seen_dates = set()
    seen_starts = set()
    out = []
    all_rows, abnormal, going, surface = Counter(), Counter(), Counter(), Counter()
    manifests=[]
    for paci, sed in sorted(pairs, key=lambda x: Path(x[0]).name):
        day, token = _validate_pair(paci,sed,as_of_exclusive)
        must(day not in seen_dates, 'duplicate historical date')
        seen_dates.add(day)
        # Independently recognized canonical names in ZIP: fail if absent.
        ukc = {u['horse_id']:u for _,raw in iter_archive_records(Path(paci),'UKC')
               for u in [p.ukc(raw)]}
        kyi = {(k['race_key_raw'],k['horse_no']):k for _,raw in iter_archive_records(Path(paci),'KYI')
               for k in [p.kyi(raw)]}
        sed_rows = [p.sed(raw) for _,raw in iter_archive_records(Path(sed),'SED')]
        must(ukc and kyi and sed_rows, f'empty or unsupported canonical member: {day}')
        must(len(ukc)==len(kyi)==len(sed_rows), f'cohort count mismatch {day}')
        must(all(u['data_date'] == day.replace('-','') for u in ukc.values()), 'UKC profile as-of mismatch')
        must(all(u['horse_id'].isdigit() and len(u['horse_id'])==8 and u['sire_name'] for u in ukc.values()), 'invalid UKC identity/sire')
        paired = set()
        for row in sed_rows:
            horse_id = row['blood_registration_no']
            key=(row['race_key_raw'],row['horse_no'])
            k=kyi.get(key); u=ukc.get(horse_id)
            must(k is not None and u is not None, 'SED missing KYI or UKC')
            must(k['blood_registration_no'] == horse_id, 'SED/KYI canonical horse id mismatch')
            must((key,horse_id) not in seen_starts, 'duplicate SED start')
            seen_starts.add((key,horse_id));paired.add(key)
            must(row['date_raw'] == day.replace('-',''), 'SED declared date mismatch')
            must(row['track_condition_code'] in GOING_CODE, 'unrecognized official going code')
            must(row['abnormal_code'] in ABNORMAL, 'unknown JRDB abnormal status')
            must(row['surface_code'] in ('1','2','3'), 'unknown JRDB surface')
            all_rows['total']+=1
            abnormal[row['abnormal_code']]+=1
            going[row['track_condition_code']]+=1
            surface[row['surface_code']]+=1
            if row['surface_code'] != race['surface_code']:
                continue
            # First accepted version is intentionally conservative: only
            # abnormal=0 + valid finish contributes to denominators.
            normal=(row['abnormal_code']=='0')
            finish=row['finish']
            must(not normal or type(finish) is int and 1 <= finish <= row['field_size'], 'normal finisher invalid rank')
            out.append({
              'race_date': day,'race_key':row['race_key_raw'],
              'horse_no':row['horse_no'],'horse_id':horse_id,
              'surface_code':row['surface_code'],
              'going_class':GOING_CODE[row['track_condition_code']],
              'sire_name':u['sire_name'],
              'outcome':'FINISHED' if normal else 'EXCLUDED',
              'finish_position':finish if normal else None,
            })
        must(set(kyi)==paired, 'PACI KYI has missing SED starts')
        manifests.append({'day':day, 'paci_zip_sha256':_raw_digest(paci),
                          'sed_zip_sha256':_raw_digest(sed),'all_rows':len(sed_rows)})
    manifest_digest=hashlib.sha256(json.dumps(manifests,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    payload={'contract_version':'brdb-going-observation-input-v0.1-candidate',
             'research_only':True,'prediction_safe':False,
             'race':race,'as_of_exclusive':as_of_exclusive,
             'source':{'reader':'JRDB_SED_COMMON_READER','source_sha256':manifest_digest,
                       'historical_parent_mapping_status':'AS_OF_UNVERIFIED'},
             'records':sorted(out,key=lambda r:(r['race_date'],r['race_key'],r['horse_no']))}
    receipt={'contract_version':VERSION,'source_manifest':manifests,
             'manifest_sha256':manifest_digest,'all_sed_rows':all_rows['total'],
             'normalized_target_surface_records':len(out),
             'abnormal_codes':dict(sorted(abnormal.items())),
             'going_codes':dict(sorted(going.items())),
             'surface_codes':dict(sorted(surface.items())),
             'historical_parent_mapping_status':'AS_OF_UNVERIFIED',
             'prediction_safe':False,'production_authorized':False}
    return payload,receipt


def cli(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--race-json',required=True)
    ap.add_argument('--paci-sed',nargs=2,action='append',required=True,metavar=('PACI','SED'))
    ap.add_argument('--output',required=True)
    ap.add_argument('--receipt',required=True)
    a=ap.parse_args(argv)
    race=json.loads(Path(a.race_json).read_text(encoding='utf-8'))
    payload, receipt=normalize(a.paci_sed,race,race['target_date'])
    Path(a.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    Path(a.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','total_sed_rows':receipt['all_sed_rows'],
                      'target_surface_records':len(payload['records'])},ensure_ascii=False))

if __name__=='__main__':
    cli()
