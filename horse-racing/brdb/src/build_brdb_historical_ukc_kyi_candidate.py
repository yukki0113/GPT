#!/usr/bin/env python3
"""Build a PRIVATE historical UKC/KYI day-member candidate, NEVER as-of-certified.

Join each KYI entrant to the latest observed UKC for that horse with
UKC data_date <= target_date. The original annual ZIPs may have been revised:
embedded dates and ZIP mtimes do NOT certify historical distribution bytes.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'jrdb' / 'src'))
from jrdb_raw import raw_field
from jrdb_ukc import parse_ukc_record

VERSION = 'brdb-m6-historical-daily-ukc-kyi-candidate-v0.1'
HEADERS = (
    'target_date','race_key','horse_no','horse_id',
    'sire_name','dam_name','broodmare_sire_name',
    'sire_line_code','broodmare_sire_line_code','ukc_data_date',
    'source_ukc_zip_sha256','source_kyi_zip_sha256',
    'source_ukc_member_sha256','source_kyi_member_sha256',
    'selection_method','evidence_level',
)
PARENT_FIELDS = (
    'sire_name','dam_name','broodmare_sire_name',
    'sire_line_code','broodmare_sire_line_code',
)

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1<<20),b''):
            h.update(chunk)
    return h.hexdigest()

def assemble(ukc_root:Path, kyi_root:Path, output:Path, *, years:tuple[int,...]):
    if not years or years != tuple(sorted(set(years))) or any(y < 2010 or y > 2026 for y in years):
        raise ValueError('invalid year range')
    if output.resolve().is_relative_to(ukc_root.resolve()) or output.resolve().is_relative_to(kyi_root.resolve()):
        raise ValueError('private output must not overwrite source folders')
    output.mkdir(parents=True,exist_ok=True)
    latest={};first_seen={};changes={f:set() for f in PARENT_FIELDS}
    all_counts=Counter();annual={};sources={};anomalies=[]
    private_output=output/'private_historical_ukc_kyi_candidate.csv.gz'
    with private_output.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0,compresslevel=6) as zipped:
            with io.TextIOWrapper(zipped,encoding='utf-8',newline='') as textfile:
                writer=csv.DictWriter(textfile,fieldnames=HEADERS)
                writer.writeheader()
                for year in years:
                    up=ukc_root / f'UKC_{year}.zip'
                    kp=kyi_root / f'KYI_{year}.zip'
                    if not up.is_file() or not kp.is_file():
                        raise ValueError(f'year {year} original ZIP pair missing')
                    sources[str(year)]={'ukc_sha256':digest(up),'kyi_sha256':digest(kp)}
                    stat=Counter()
                    with ZipFile(up) as uz,ZipFile(kp) as kz:
                        umembers=sorted(n for n in uz.namelist() if re.fullmatch(r'UKC\d{6}\.txt',n))
                        kmembers=sorted(n for n in kz.namelist() if re.fullmatch(r'KYI\d{6}\.txt',n))
                        if (len(umembers)!=len(uz.namelist()) or
                            len(kmembers)!=len(kz.namelist()) or
                            sorted('KYI'+n[3:] for n in umembers)!=kmembers):
                            raise ValueError(f'year {year}: incompatible or unexpected ZIP members')
                        for umember in umembers:
                            kmember='KYI'+umember[3:]
                            day='20'+umember[3:9]
                            if not day.startswith(str(year)):
                                raise ValueError('ZIP member year mismatch')
                            ub=uz.read(umember);kb=kz.read(kmember)
                            ulines=ub.splitlines();klines=kb.splitlines()
                            if any(len(x)!=290 for x in ulines) or any(len(x)!=1022 for x in klines):
                                raise ValueError('noncanonical UKC/KYI row length')
                            today={};daystats=Counter()
                            for row in ulines:
                                record=parse_ukc_record(row)
                                if record.data_date != day:
                                    raise ValueError('UKC data_date differs from labeled member')
                                prior=today.get(record.horse_id)
                                if prior is not None:
                                    if prior.semantic_hash()!=record.semantic_hash():
                                        raise ValueError('conflicting UKC same-day duplicate')
                                    daystats['same_semantic_ukc_duplicates']+=1
                                    continue
                                today[record.horse_id]=record
                                first=first_seen.setdefault(record.horse_id,record)
                                for field in PARENT_FIELDS:
                                    if getattr(first,field)!=getattr(record,field):
                                        changes[field].add(record.horse_id)
                            for hid,record in today.items():
                                latest[hid]=(record,day,sources[str(year)]['ukc_sha256'],hashlib.sha256(ub).hexdigest())
                            seen=set();entrants=set();ush=hashlib.sha256(ub).hexdigest();ksh=hashlib.sha256(kb).hexdigest()
                            for row in klines:
                                race=raw_field(row,1,8)
                                no=raw_field(row,9,2)
                                horse=raw_field(row,11,8)
                                if len(race)!=8 or not no.isdigit() or int(no)<=0 or not re.fullmatch(r'\d{8}',horse):
                                    raise ValueError('invalid canonical KYI entry key')
                                key=(race,no)
                                if key in seen:raise ValueError('duplicate race/horse KYI identity')
                                seen.add(key);entrants.add(horse)
                                previous=latest.get(horse)
                                if previous is None:
                                    daystats['missing_ukc']+=1
                                    continue
                                ukc,source_day,uzip,source_member_hash=previous
                                if source_day>day:
                                    raise ValueError('future UKC source leak')
                                method='SAME_DAY_MEMBER' if source_day==day else 'PRIOR_DATE_LAST_OBSERVED'
                                writer.writerow(dict(zip(HEADERS,(
                                    day,race,no,horse,ukc.sire_name,ukc.dam_name,
                                    ukc.broodmare_sire_name,ukc.sire_line_code,
                                    ukc.broodmare_sire_line_code,ukc.data_date,
                                    uzip,sources[str(year)]['kyi_sha256'],
                                    source_member_hash,ksh,method,
                                    'UNATTESTED_ANNUAL_ZIP_DAY_MEMBER'))))
                                daystats['matched']+=1
                                daystats[method]+=1
                            daystats['kyi_entries']=len(klines)
                            daystats['ukc_entries']=len(ulines)
                            daystats['extra_ukc_profiles']=len(set(today)-entrants)
                            if (len(ulines)!=len(klines) or daystats['missing_ukc'] or
                                daystats['PRIOR_DATE_LAST_OBSERVED']):
                                anomalies.append({'date':day,**daystats})
                            stat.update(daystats);stat['members']+=1
                    annual[str(year)]=dict(stat)
                    all_counts.update(stat)
    result={
        'version':VERSION,'status':'PASS_RESEARCH_ONLY',
        'prediction_safe':False,'independently_attested_asof_entries':0,
        'year_count':len(years),'annual_zip_pairs':len(years),
        'member_days':all_counts['members'],
        'kyi_entries':all_counts['kyi_entries'],
        'matched_entries':all_counts['matched'],
        'same_day_ukc_entries':all_counts['SAME_DAY_MEMBER'],
        'prior_day_ukc_entries':all_counts['PRIOR_DATE_LAST_OBSERVED'],
        'missing_ukc_entries':all_counts['missing_ukc'],
        'duplicate_identical_ukc_rows':all_counts['same_semantic_ukc_duplicates'],
        'annual':annual,'source_zip_sha256':sources,'partial_days':anomalies,
        'horses_with_value_change_vs_first_observed':{field:len(ids) for field,ids in changes.items()},
        'private_csv_gzip_sha256':digest(private_output),
        'private_csv_gzip_bytes':private_output.stat().st_size,
        'no_provider_version_receipt':True,
        'note':'KYI/UKC annual ZIP date member is a retrospectively retained candidate. Do not use for prediction or M6 P1-6/P1-7 without independent historically released-source attestation.',
    }
    (output/'historical_daily_candidate_aggregate.json').write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ukc-root',type=Path,required=True)
    p.add_argument('--kyi-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--years',default='2016:2025')
    p.add_argument('--require-prediction-safe',action='store_true')
    a=p.parse_args()
    if a.require_prediction_safe:
        raise ValueError('historical as-of delivery/provenance not independently verified; prediction is HOLD')
    if not re.fullmatch(r'20\d\d:20\d\d',a.years):
        raise ValueError('years must be inclusive YYYY:YYYY')
    lo,hi=map(int,a.years.split(':'))
    result=assemble(a.ukc_root,a.kyi_root,a.out,years=tuple(range(lo,hi+1)))
    print(json.dumps({k:result[k] for k in (
        'status','kyi_entries','matched_entries','same_day_ukc_entries',
        'prior_day_ukc_entries','missing_ukc_entries','prediction_safe')},
        ensure_ascii=False,sort_keys=True))
