#!/usr/bin/env python3
"""Read-only cause audit for the 3,794 static-unjoined 2026 KYI horses.

Exact IDs only. Source-supported recovery potential is not a generated master
or a historical backtest. Annual and daily absence claims are scope bounded.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from audit_race_year_pedigree import (ROOT, csv_write, dump, parse_entries, rate, sha, table, verified)
from brdb_research_reader import ResearchPedigreeReader
from build_brdb_research_candidate import select_daily
import jrdb_ukc
from jrdb_raw import Parser, canonical_members

VERSION = 'missing-daily-ukc-causes-0.1'
UPSTREAM_SHA = 'e3e5ee8b7eca9c0b1bd17d648683307aee52d6b9922266da491eb1d6b7e0089b'
REASONS = (
    'DAILY_UKC_PRESENT_OUTSIDE_104_OVERLAY',
    'PROFILE_DATE_OR_SELECTION_GUARD',
    'ANNUAL_VALID_PROFILE_NOT_IN_BASE_REVIEW_REQUIRED',
    'NOT_FOUND_IN_SCANNED_ANNUAL_OR_DAILY_UKC',
    'UNKNOWN_INPUT_GAP', 'UNKNOWN_PARSE_FAILURE', 'UNKNOWN_BUILD_DISCREPANCY')
NAMES = ('sire_name', 'dam_name', 'broodmare_sire_name')
CODES = ('sire_line_code', 'broodmare_sire_line_code')


def valid_date(text):
    if not isinstance(text,str) or not re.fullmatch(r'[0-9]{8}',text): return False
    try: datetime.strptime(text,'%Y%m%d'); return True
    except ValueError: return False


def profile_guards(record, observed):
    if record is None: return ['PARSER_ERROR']
    result=[];date=record['data_date']
    if date=='99999999': result.append('SENTINEL_PROFILE_DATE')
    elif not valid_date(date): result.append('INVALID_PROFILE_DATE')
    if not valid_date(observed): result.append('UNKNOWN_OBSERVATION_DATE')
    elif valid_date(date) and date>observed: result.append('PROFILE_AFTER_OBSERVATION')
    return result


def selected_profile(observations):
    """Reuse the actual candidate selection/conflict guard, never infer by name."""
    usable=[o for o in observations if not o['guards']]
    if not usable: return None,False
    shaped=[{'record':o['record'],'semantic_hash':o['semantic_hash'],'archive_date':o['observation_date'],
             'archive':o['source_zip'],'archive_sha256':o['source_zip_sha256'],
             'member':o['member'],'line_number':o['line_number']} for o in usable]
    try:
        _,history,_=select_daily({usable[0]['horse_id']:shaped},'AUDIT_ONLY_NOT_A_GENERATION')
    except ValueError as e:
        if 'same-date semantic conflict' not in str(e): raise
        return None,True
    chosen=next(x for x in history if x['selected'])
    result=next(o for o in usable if (o['source_zip'],o['member'],o['line_number'])==
                (chosen['archive'],chosen['member'],chosen['line_number']))
    return result,False


def primary_reason(annual,daily,overlay_member,complete=True):
    if not complete: return 'UNKNOWN_INPUT_GAP'
    if any('PARSER_ERROR' in o['guards'] for o in annual+daily): return 'UNKNOWN_PARSE_FAILURE'
    annual_selected,annual_conflict=selected_profile(annual)
    daily_selected,daily_conflict=selected_profile(daily)
    if annual_selected: return 'ANNUAL_VALID_PROFILE_NOT_IN_BASE_REVIEW_REQUIRED'
    if daily_conflict or annual_conflict: return 'PROFILE_DATE_OR_SELECTION_GUARD'
    if daily_selected:
        return 'UNKNOWN_BUILD_DISCREPANCY' if overlay_member else 'DAILY_UKC_PRESENT_OUTSIDE_104_OVERLAY'
    if annual or daily: return 'PROFILE_DATE_OR_SELECTION_GUARD'
    return 'NOT_FOUND_IN_SCANNED_ANNUAL_OR_DAILY_UKC'


def trustworthy_birth(observations):
    dates={o['record'].get('birth_date','') for o in observations if o['record'] is not None}
    if not dates: return '', 'UNKNOWN_NO_SOURCE'
    if len(dates)!=1: return '', 'UNKNOWN_CONFLICTING_SOURCE_BIRTH_DATES'
    date=next(iter(dates))
    if not valid_date(date): return '', 'UNKNOWN_INVALID_OR_MISSING_SOURCE_BIRTH_DATE'
    if any(valid_date(o['observation_date']) and date>o['observation_date'] for o in observations):
        return '', 'UNKNOWN_BIRTH_DATE_AFTER_SOURCE'
    return date[:4], 'EXACT_ID_UKC_BIRTH_DATE'


def dated_evidence(observations,date):
    available=[o for o in observations if not o['guards'] and o['observation_date']<=date
               and o['record']['data_date']<=date]
    return max(available,key=lambda o:(o['observation_date'],o['record']['data_date'],
                                      o['source_zip'],o['member'],o['line_number'])) if available else None


def latest_eligible(selected,date):
    return bool(selected and selected['observation_date']<=date and selected['record']['data_date']<=date)


def verify_upstream(path):
    if sha(path)!=UPSTREAM_SHA: raise ValueError('#2218 artifact ZIP SHA mismatch')
    with zipfile.ZipFile(path) as z:
        sums=json.loads(z.read('SHA256SUMS.json'))
        for name,digest in sums.items():
            if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('unsafe artifact path')
            if hashlib.sha256(z.read(name)).hexdigest()!=digest: raise ValueError('upstream internal SHA mismatch')
        manifest=json.loads(z.read('audit/manifest.json'))
        for name,digest in manifest['output_sha256'].items():
            if hashlib.sha256(z.read('audit/'+name)).hexdigest()!=digest: raise ValueError('upstream audit SHA mismatch')
        summary=json.loads(z.read('audit/summary.json'))
        if (summary['scope']['unique_horses'],summary['scope']['entries'],
            summary['generations']['RESEARCH']['static_horses']['metrics']['id_joined']['count'])!=(10680,39543,6886):
            raise ValueError('upstream denominator mismatch')
        horses={}
        with z.open('audit/horses.csv') as f:
            for row in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8')):
                if row['dataset']=='RESEARCH':
                    if row['horse_id'] in horses: raise ValueError('duplicate upstream horse')
                    horses[row['horse_id']]={k:row[k] for k in ('horse_id','kyi_horse_name','id_joined','entry_count','first_entry_date','last_entry_date')}
        target={h for h,r in horses.items() if r['id_joined']=='0'}
        with z.open('audit/missing_horses.csv') as f:
            missing=[r['horse_id'] for r in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8')) if r['dataset']=='RESEARCH']
        if len(horses)!=10680 or len(target)!=3794 or len(missing)!=3794 or set(missing)!=target:
            raise ValueError('3,794-ID static target mismatch')
        entries=[];blocked=0
        fields=('race_date','race_key','horse_no','horse_id','horse_name','race_class_code','source_zip','source_member','source_line')
        with z.open('audit/entries.csv') as f:
            for row in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8')):
                if row['dataset']!='RESEARCH': continue
                if row['static_id_joined']=='1' and row['as_of_id_joined']=='0': blocked+=1
                entries.append({k:row[k] for k in fields})
        if len(entries)!=39543 or len({(e['race_date'],e['race_key'],e['horse_no']) for e in entries})!=39543:
            raise ValueError('upstream entry denominator/uniqueness mismatch')
        if sum(e['horse_id'] in target for e in entries)!=10016 or blocked!=292:
            raise ValueError('static missing/as-of-only blocked confusion')
        result={'summary':summary,'horses':horses,'targets':target,'entries':entries,'asof_only_blocked_entries':blocked,
            'paci_inventory':json.loads(z.read('inputs/paci_source_manifest.json')),
            'annual_manifest':json.loads(z.read('inputs/base_manifest.json')),
            'research_manifest_bytes':z.read('inputs/research_manifest.json'),
            'annual_inventory':json.loads(z.read('audit/annual_inventory.json')),
            'overlay_ids':{r['horse_id'] for r in json.loads(z.read('inputs/research_added_104.json'))},
            'monthly':json.loads(z.read('audit/monthly.json')),
            'verified_internal_files':len(sums),'upstream_manifest_sha256':hashlib.sha256(z.read('audit/manifest.json')).hexdigest()}
    if len(result['overlay_ids'])!=104 or result['overlay_ids']&target: raise ValueError('overlay/target IDs inconsistent')
    return result


def scan_ukc(directory,inventory,targets,family):
    observations=defaultdict(list);audited=[];errors=[];races={};p=Parser()
    id_spec=next((offset,width) for field,offset,width in jrdb_ukc.FIELD_SPECS if field=='horse_id')
    for item in sorted(inventory,key=lambda x:x['name']):
        path=directory/item['name'];row={'name':item['name'],'sha256':item['sha256'],
            'size_bytes':item['size_bytes'],'family':family,'members':[],'records_identity_scanned':0,
            'target_records_parsed':0,'target_record_parse_errors':0,
            'non_numeric_source_id_count':0,'non_numeric_source_ids':[],'status':'SCANNED'}
        source_ids=set()
        try:
            if family=='DAILY':
                if not re.fullmatch(r'PACI26\d{4}\.zip',path.name): raise ValueError('outside daily scope')
                observed='20'+path.name[4:10]
            else:
                if not re.fullmatch(r'UKC_(?:1999|20[012][0-9])\.zip',path.name): raise ValueError('invalid annual archive')
                observed=None
            verified(path,item)
            with zipfile.ZipFile(path) as z:
                if z.testzip(): raise ValueError('corrupt ZIP member')
                members=canonical_members(z,'UKC')
                expected=item['ukc_members'] if family=='DAILY' else [m['member'] for m in item['members']]
                if not members or sorted(members)!=sorted(expected): raise ValueError('UKC member inventory mismatch')
                if family=='DAILY':
                    for member in canonical_members(z,'BAC'):
                        from jrdb_raw import split_fixed_records
                        for raw in split_fixed_records(z.read(member),'BAC'):
                            r=p.bac(raw);races[observed,r['race_key_raw']]=r
                for member in members:
                    if family=='ANNUAL':
                        mm=re.search(r'UKC(\d{6})\.txt$',member,re.I)
                        if mm and int(mm[1][:2])!=int(path.name[4:8])%100:raise ValueError('member/archive year mismatch')
                        observed=(path.name[4:8]+mm[1][2:]) if mm else None
                        if not valid_date(observed):observed=None
                    member_bytes=z.read(member);member_digest=hashlib.sha256(member_bytes).hexdigest();count=0
                    for line_no,body in enumerate(member_bytes.splitlines(),1):
                        count+=1;row['records_identity_scanned']+=1
                        if len(body)!=jrdb_ukc.RECORD_LENGTH: raise ValueError('UKC record length mismatch')
                        hid=jrdb_ukc._text(body,*id_spec)
                        if not re.fullmatch(r'[0-9]{8}',hid):
                            # Some old annual UKC records use alphanumeric source IDs.
                            # These cannot equal the fixed numeric KYI targets. Preserve
                            # them as anomalies, never normalize or rescue their identity.
                            row['non_numeric_source_id_count']+=1
                            row['non_numeric_source_ids'].append({'member':member,'line':line_no,
                                'source_id':hid,'raw_id_hex':body[:8].hex()})
                            continue
                        source_ids.add(hid)
                        if hid not in targets: continue
                        error='';record=None;digest=''
                        try:
                            parsed=jrdb_ukc.parse_ukc_record(body);record=asdict(parsed);digest=parsed.semantic_hash()
                            row['target_records_parsed']+=1
                        except (UnicodeError,ValueError) as e:
                            error=str(e);row['target_record_parse_errors']+=1
                        o={'family':family,'horse_id':hid,'source_zip':path.name,'source_zip_sha256':item['sha256'],
                           'member':member,'member_sha256':member_digest,
                           'line_number':line_no,'raw_record_sha256':hashlib.sha256(body).hexdigest(),
                           'observation_date':observed or '', 'record':record,'semantic_hash':digest,
                           'guards':profile_guards(record,observed),'parse_error':error}
                        observations[hid].append(o)
                    if family=='ANNUAL':
                        expected_count=next(m['records'] for m in item['members'] if m['member']==member)
                        if count!=expected_count:raise ValueError('annual record inventory mismatch')
                    row['members'].append({'member':member,'observation_date':observed,
                        'size_bytes':len(member_bytes),'sha256':hashlib.sha256(member_bytes).hexdigest(),'records':count})
                expected_total=item['ukc_record_count'] if family=='DAILY' else sum(m['records'] for m in item['members'])
                if row['records_identity_scanned']!=expected_total: raise ValueError('UKC count mismatch')
        except (OSError,ValueError,zipfile.BadZipFile,UnicodeError) as e:
            row['status']='INPUT_GAP';row['error']=str(e);errors.append({'archive':path.name,'error':str(e)})
        row['unique_numeric_source_ids']=len(source_ids)
        row['numeric_source_id_set_sha256']=hashlib.sha256(('\n'.join(sorted(source_ids))+'\n').encode()).hexdigest()
        if family=='DAILY':row['source_ids']=sorted(source_ids)
        audited.append(row)
    return observations,audited,errors,races


def group_rows(entries,targets,selected_map,dimension):
    buckets=defaultdict(list)
    for e in entries:buckets[dimension(e)].append(e)
    result=[]
    for key,es in sorted(buckets.items()):
        hids={e['horse_id'] for e in es};miss=hids&targets;missing_entries=[e for e in es if e['horse_id'] in targets]
        result.append({'group':key,'cohort_horses':len(hids),'missing_horses':len(miss),
            'missing_horse_percent':rate(len(miss),len(hids))['percent'],'cohort_entries':len(es),
            'missing_entries':len(missing_entries),'missing_entry_percent':rate(len(missing_entries),len(es))['percent'],
            'recoverable_static_missing_horses':sum(selected_map[h] is not None for h in miss),
            'conditional_latest_snapshot_safe_missing_entries':sum(latest_eligible(selected_map[e['horse_id']],e['race_date']) for e in missing_entries)})
    return result


def report(s):
    r=s['recovery_potential'];lines=['# Issue #2220 — static-unjoined KYI cause audit','',
        'Scope: 2026-01-04–2026-10-25 KYI declared entries; cancellations/actual starts are UNKNOWN.','',
        f"Upstream denominator: {s['cohort_horses']:,} horses / {s['cohort_entries']:,} entries; RESEARCH joins {s['research_joined_horses']:,}; static missing {s['target_horses']:,} horses / {s['target_entries']:,} entries.",'',
        '| Primary reason | Horses | % of 3,794 |','|---|---:|---:|']
    for k,v in s['primary_reasons'].items():lines.append(f"| {k} | {v['count']:,} | {v['percent']:.4f}% |")
    lines+=['',f"Input scans: annual {s['inputs']['annual_zip_count']}/27 ZIPs; daily {s['inputs']['daily_zip_count']}/91 ZIPs. "
        f"Target ID matches: annual {s['evidence_counts']['annual_raw_found']:,}; daily {s['evidence_counts']['daily_raw_found']:,}.",'',
        'When all targets have valid daily source profiles outside the overlay, the measured primary cause is the 104-ID overlay scope. '
        'Annual nonappearance does not imply that daily UKC lacks pedigree facts. The reason table above, including zero/UNKNOWN categories, controls the conclusion.','',
        f"Source-supported static recovery potential: +{r['additional_horses']:,} horses / +{r['additional_entries']:,} entries, "
        f"bringing a future extended candidate to {r['potential_static_horses']['count']:,}/{s['cohort_horses']:,} horses "
        f"({r['potential_static_horses']['percent']:.4f}%) and {r['potential_static_entries']['count']:,}/{s['cohort_entries']:,} entries "
        f"({r['potential_static_entries']['percent']:.4f}%). This is a source audit, not a completed candidate build.",'',
        f"A conditional single-latest-profile snapshot could add {r['conditional_latest_snapshot_safe_additional_entries']:,} race-date-safe entries. "
        f"Earlier dated raw-source evidence exists for {r['dated_source_evidence_entries']:,} missing entries; using it would require a separately implemented historical/profile-history reader. "
        'Do not equate static potential or dated-source evidence with availability through the current Reader.','',
        'The conditional latest-snapshot calculation preserves existing annual and 104-overlay profiles and appends only the newly found targets. '
        'Replacing existing profiles with newer daily observations would require a separate audit. Date comparisons are inclusive; intra-day publication timing remains unverified.','',
        f"The prior {s['upstream_asof_only_blocked_entries']} as-of-only blocked entries of already-joined horses are outside this static missing cohort.",'',
        '## Monthly active-cohort missingness','',
        '| Month | Missing horses / active horses | Missing entries / entries |','|---|---:|---:|']
    for x in s['monthly_active']:
        lines.append(f"| {x['group']} | {x['missing_horses']:,}/{x['cohort_horses']:,} ({x['missing_horse_percent']:.4f}%) | "
                     f"{x['missing_entries']:,}/{x['cohort_entries']:,} ({x['missing_entry_percent']:.4f}%) |")
    late=s['late_year_missingness_check']
    lines+=['',f"Within this fixed snapshot, entry missingness rises from {late['january_missing_entry_percent']:.4f}% in January "
        f"to {late['october_missing_entry_percent']:.4f}% through October 25. This supports a descriptive late-period coverage decline; "
        'it is not a causal claim that being a new horse removes UKC data. All classified targets still have daily UKC evidence.']
    lines+=['','## Birth year / declared new-race class','',
        '| Source birth year | Missing horses |','|---|---:|']
    for year,count in s['birth_year_counts'].items():lines.append(f'| {year} | {count:,} |')
    lines+=['','| First scanned BAC class | Missing / cohort horses |','|---|---:|']
    for x in s['first_declared_new_class']:
        lines.append(f"| {x['group']} | {x['missing_horses']:,}/{x['cohort_horses']:,} ({x['missing_percent']:.4f}%) |")
    lines+=['', 'A horse can be active in several months; these horse counts are non-additive. First-appearance month groups are disjoint. '
        'BAC A1/A2 identifies a declared new/unraced race class, not an independently confirmed debut. Birth years come only from consistent, valid exact-ID UKC birth dates. '
        'New-race and birth-year composition is descriptive evidence, not an asserted causal explanation.','',
        'Annual nonappearance is limited to the verified 1999–2025 archive inventory. Dates after 2026-10-25 and archives outside the inventory are unverified. '
        'Profile quality, sentinel dates, conflicts and input gaps remain explicit evidence flags; no name rescue is used.','',
        f"The annual scan encountered {s['inputs']['non_numeric_annual_source_ids']} source IDs outside the numeric KYI identity domain. "
        'They are retained in anomaly evidence without normalization and do not interrupt the exact target-ID scan.','',
        'Next research build inputs: the same SHA-pinned 27 annual ZIPs and all 91 PACI UKC members, with the 104-ID inclusion cap removed. '
        f"Under the preserved-profile assumption the master would have {r['conditional_expanded_master_profiles']:,} profiles. "
        'A separate immutable generation build, parent-resolution/regression audit and explicit research reader validation are still required.','',
        'Detailed artifacts: 3,794-row CSV/JSON, raw-record/source SHA provenance, source-observation JSONL/CSV, entry evidence, '
        'monthly/first-month/new-class/birth-year/race-type cross tables, unknown list, run/test logs and manifest. '
        'Execution is local managed runtime; no new generation, CURRENT change or production publication is part of this analysis.','']
    return '\n'.join(lines)


def run(args):
    if args.output.exists():raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    up=verify_upstream(args.upstream);targets=up['targets']
    entries,kyi_inventory=parse_entries(args.paci_dir,up['paci_inventory'])
    old={(e['race_date'],e['race_key'],int(e['horse_no'])):e for e in up['entries']}
    if len(old)!=len(entries):raise ValueError('KYI replay denominator mismatch')
    for e in entries:
        prev=old[e['race_date'],e['race_key'],e['horse_no']]
        if any(str(e[k])!=prev[k] for k in ('horse_id','horse_name','race_class_code','source_zip','source_member','source_line')):
            raise ValueError('KYI replay differs from #2218')
    manifest=args.research/'manifest.json'
    if sha(manifest)!=hashlib.sha256(up['research_manifest_bytes']).hexdigest():raise ValueError('research manifest mismatch')
    rm=json.loads(manifest.read_text())
    for name,digest in rm['output_sha256'].items():
        if sha(args.research/name)!=digest:raise ValueError('research object SHA mismatch')
    reader=ResearchPedigreeReader(args.research)
    profiles=reader.profiles_for_horses(sorted(up['horses']),as_of='20261025')
    if set(up['horses'])-set(profiles)!=targets:raise ValueError('research static join differs from #2218')
    mapped={r['lineage_code'] for r in table(args.research/'lineage_code_master.parquet')}
    daily,di,de,races=scan_ukc(args.paci_dir,up['paci_inventory'],targets,'DAILY')
    annual,ai,ae,_=scan_ukc(args.annual_dir,up['annual_inventory'],targets,'ANNUAL')
    errors=de+ae;complete=not errors and len(di)==91 and len(ai)==27
    daily_ids={h for item in di for h in item.get('source_ids',[])}
    by_horse=defaultdict(list)
    for e in entries:
        if (e['race_date'],e['race_key']) not in races:raise ValueError('BAC evidence missing')
        r=races[e['race_date'],e['race_key']]
        e.update(race_type_code=r['race_type_code'],surface_code=r['surface_code'],grade_code=r['grade_code'])
        by_horse[e['horse_id']].append(e)
    for hid,es in by_horse.items():
        before=up['horses'][hid]
        if (len(es),es[0]['race_date'],es[-1]['race_date'])!=(int(before['entry_count']),before['first_entry_date'],before['last_entry_date']):
            raise ValueError('horse chronology/count mismatch')
    primary=Counter();flag_counts=Counter();rows=[];selected_map={};entry_evidence=[]
    for hid in sorted(targets):
        a=annual.get(hid,[]);d=daily.get(hid,[]);sel,conflict=selected_profile(d);selected_map[hid]=sel
        ar,ac=selected_profile(a);es=by_horse[hid];birth,bst=trustworthy_birth(a+d)
        flags={'annual_raw_found':bool(a),'annual_not_found_in_scanned_inputs':not a and complete,
            'daily_raw_found':bool(d),'daily_not_found_in_scanned_inputs':not d and complete,
            'outside_104_overlay':hid not in up['overlay_ids'],'daily_selectable_profile':sel is not None,
            'annual_selectable_profile':ar is not None,'daily_latest_date_conflict':conflict,'annual_latest_date_conflict':ac,
            'any_sentinel_profile_date':any('SENTINEL_PROFILE_DATE' in o['guards'] for o in a+d),
            'any_invalid_profile_date':any('INVALID_PROFILE_DATE' in o['guards'] for o in a+d),
            'any_profile_after_observation':any('PROFILE_AFTER_OBSERVATION' in o['guards'] for o in a+d),
            'any_parser_error':any('PARSER_ERROR' in o['guards'] for o in a+d),
            'input_gap_or_unverified_inventory':not complete}
        reason=primary_reason(a,d,hid in up['overlay_ids'],complete);primary[reason]+=1;flag_counts.update(flags)
        rd=sel['record'] if sel else {};first_class=es[0]['race_class_code']
        first_new=first_class if first_class in ('A1','A2') else 'OTHER'
        row={'horse_id':hid,'kyi_horse_name':es[0]['horse_name'],'primary_reason':reason,
            'entry_count':len(es),'first_kyi_date':es[0]['race_date'],'last_kyi_date':es[-1]['race_date'],
            'first_appearance_month':es[0]['race_date'][:6],'first_bac_new_class':first_new,
            'birth_year':birth,'birth_year_status':bst,
            'first_daily_ukc_date':min((o['observation_date'] for o in d if o['observation_date']),default=''),
            'last_daily_ukc_date':max((o['observation_date'] for o in d if o['observation_date']),default=''),
            'last_annual_ukc_date':max((o['observation_date'] for o in a if o['observation_date']),default=''),
            'daily_observations':len(d),'annual_observations':len(a),
            'selected_profile_date':rd.get('data_date',''),'selected_observation_date':sel['observation_date'] if sel else '',
            'selected_source_zip':sel['source_zip'] if sel else '', 'selected_source_zip_sha256':sel['source_zip_sha256'] if sel else '',
            'selected_member':sel['member'] if sel else '', 'selected_line':sel['line_number'] if sel else '',
            'selected_record_sha256':sel['raw_record_sha256'] if sel else '',
            'selected_semantic_hash':sel['semantic_hash'] if sel else '',
            **{f:rd.get(f,'') for f in NAMES+CODES},
            'selected_three_names_present':bool(sel and all(rd.get(f) for f in NAMES)),
            'selected_both_codes_mapped':bool(sel and all(rd.get(f) in mapped for f in CODES)),
            **flags}
        evidence_count=latest_count=complete_count=0
        for e in es:
            evidence=dated_evidence(d,e['race_date']);latest_ok=latest_eligible(sel,e['race_date'])
            evidence_count+=evidence is not None;latest_count+=latest_ok
            basic=bool(evidence and all(evidence['record'].get(f) for f in NAMES)
                       and all(evidence['record'].get(f) in mapped for f in CODES));complete_count+=basic
            if evidence and (evidence['observation_date']>e['race_date'] or evidence['record']['data_date']>e['race_date']):
                raise ValueError('future source evidence leakage')
            entry_evidence.append({**e,'primary_reason':reason,'dated_raw_source_evidence':bool(evidence),
                'dated_source_names_and_mapped_codes':basic,'conditional_latest_profile_eligible_asof':latest_ok,
                'evidence_source_zip':evidence['source_zip'] if evidence else '',
                'evidence_member':evidence['member'] if evidence else '',
                'evidence_line':evidence['line_number'] if evidence else '',
                'evidence_observation_date':evidence['observation_date'] if evidence else '',
                'evidence_profile_date':evidence['record']['data_date'] if evidence else '',
                'evidence_record_sha256':evidence['raw_record_sha256'] if evidence else ''})
        row.update(dated_source_evidence_entries=evidence_count,
            dated_source_complete_basic_entries=complete_count,conditional_latest_safe_entries=latest_count)
        rows.append(row)
    if len(rows)!=3794 or len({r['horse_id'] for r in rows})!=3794:raise ValueError('classification denominator failure')
    monthly=group_rows(entries,targets,selected_map,lambda e:e['race_date'][:6])
    for m in monthly:
        original=up['monthly']['RESEARCH'][m['group']]
        if (m['cohort_horses'],m['cohort_entries'],m['missing_horses'],m['missing_entries'])!=(
            original['static_horses']['denominator'],original['static_entries']['denominator'],
            original['static_horses']['denominator']-original['static_horses']['metrics']['id_joined']['count'],
            original['static_entries']['denominator']-original['static_entries']['metrics']['id_joined']['count']):
            raise ValueError('monthly counts differ from #2218')
    first_groups=defaultdict(list);new_groups=defaultdict(list);cross=defaultdict(list)
    for h,es in by_horse.items():
        first_groups[es[0]['race_date'][:6]].append(h)
        new_groups[es[0]['race_class_code'] if es[0]['race_class_code'] in ('A1','A2') else 'OTHER'].append(h)
    def first_table(groups):
        return [{'group':k,'cohort_horses':len(h),'missing_horses':len(set(h)&targets),
            'missing_percent':rate(len(set(h)&targets),len(h))['percent'],
            'missing_entries':sum(len(by_horse[x]) for x in set(h)&targets)} for k,h in sorted(groups.items())]
    for row in rows:cross[row['first_appearance_month'],row['birth_year'] or 'UNKNOWN',row['first_bac_new_class'],row['primary_reason']].append(row)
    cross_rows=[{'first_month':k[0],'birth_year':k[1],'first_new_class':k[2],'primary_reason':k[3],
                 'horses':len(v),'entries':sum(r['entry_count'] for r in v)} for k,v in sorted(cross.items())]
    eligible={h for h,sel in selected_map.items() if sel is not None and primary_reason(annual.get(h,[]),daily.get(h,[]),False,complete)=='DAILY_UKC_PRESENT_OUTSIDE_104_OVERLAY'}
    eligible_entries=sum(len(by_horse[h]) for h in eligible)
    latest_increment=sum(r['conditional_latest_safe_entries'] for r in rows if r['horse_id'] in eligible)
    oldsafe=up['summary']['generations']['RESEARCH']['as_of_entries']['metrics']['id_joined']['count']
    summary={'audit_version':VERSION,'source_commit':args.source_commit,'status':'COMPLETE_FOR_SCOPE' if complete else 'PARTIAL_INPUT_GAP',
        'scope':{'min_date':'20260104','max_date':'20261025','population':'KYI declared entries, not confirmed actual starts',
                 'outside_inventory_period':'UNKNOWN; no claim for unscanned dates'},
        'cohort_horses':10680,'cohort_entries':39543,'research_joined_horses':6886,'target_horses':len(rows),
        'target_entries':sum(r['entry_count'] for r in rows),'upstream_asof_only_blocked_entries':up['asof_only_blocked_entries'],
        'inputs':{'annual_zip_count':len(ai),'daily_zip_count':len(di),'annual_records_identity_scanned':sum(r['records_identity_scanned'] for r in ai),
            'daily_records_identity_scanned':sum(r['records_identity_scanned'] for r in di),'input_errors':len(errors),
            'daily_unique_numeric_ids':len(daily_ids),'daily_ids_equal_kyi_cohort':daily_ids==set(up['horses']),
            'non_numeric_annual_source_ids':sum(r['non_numeric_source_id_count'] for r in ai),
            'non_numeric_daily_source_ids':sum(r['non_numeric_source_id_count'] for r in di),
            'annual_last_valid_observation_date':max(m['observation_date'] for r in ai for m in r['members'] if m['observation_date']),
            'annual_scan_semantics':'all identities/record lengths checked; full UKC profile parser invoked for exact target IDs only',
            'verified_upstream_internal_files':up['verified_internal_files']},
        'primary_reasons':{k:rate(primary[k],3794) for k in REASONS},'evidence_counts':dict(flag_counts),
        'birth_year_counts':dict(sorted(Counter(r['birth_year'] or 'UNKNOWN' for r in rows).items())),
        'birth_year_status_counts':dict(Counter(r['birth_year_status'] for r in rows)),
        'first_kyi_vs_first_daily_source':dict(Counter('SAME_DATE' if r['first_daily_ukc_date']==r['first_kyi_date']
            else 'SOURCE_BEFORE_KYI' if r['first_daily_ukc_date'] and r['first_daily_ukc_date']<r['first_kyi_date']
            else 'SOURCE_AFTER_KYI' if r['first_daily_ukc_date'] else 'UNKNOWN' for r in rows)),
        'recovery_potential':{'raw_daily_exact_id_upper_bound_horses':sum(bool(daily.get(h)) for h in targets),
            'additional_horses':len(eligible),'additional_entries':eligible_entries,
            'conditional_expanded_master_profiles':rm['row_counts']['pedigree_fact']+len(eligible),
            'conditional_assumption':'preserve annual and existing 104-overlay profiles; append missing eligible IDs only',
            'potential_static_horses':rate(6886+len(eligible),10680),
            'potential_static_entries':rate(29527+eligible_entries,39543),
            'selected_basic_names_complete_horses':sum(r['selected_three_names_present'] for r in rows),
            'selected_official_codes_mapped_horses':sum(r['selected_both_codes_mapped'] for r in rows),
            'conditional_latest_snapshot_safe_additional_entries':latest_increment,
            'conditional_latest_snapshot_safe_total_entries':rate(oldsafe+latest_increment,39543),
            'dated_source_evidence_entries':sum(r['dated_source_evidence_entries'] for r in rows),
            'dated_source_complete_basic_entries':sum(r['dated_source_complete_basic_entries'] for r in rows),
            'build_status':'NOT_BUILT: source-supported upper bound/selection eligibility audit only',
            'historical_reader_status':'NOT_IMPLEMENTED: dated-source evidence is not current Reader availability'},
        'monthly_active':monthly,'first_appearance_month':first_table(first_groups),'first_declared_new_class':first_table(new_groups),
        'late_year_missingness_check':{'january_missing_entry_percent':monthly[0]['missing_entry_percent'],
            'october_missing_entry_percent':monthly[-1]['missing_entry_percent'],
            'observed_increase_percentage_points':round(monthly[-1]['missing_entry_percent']-monthly[0]['missing_entry_percent'],6),
            'interpretation':'descriptive change in a fixed static snapshot; no causal new-horse claim; partial second-half period'},
        'observed_half_periods':group_rows(entries,targets,selected_map,lambda e:'JAN_JUN' if e['race_date']<'20260701' else 'JUL_OCT25'),
        'race_type_class_surface':group_rows(entries,targets,selected_map,lambda e:'|'.join(e[k] or 'EMPTY' for k in ('race_type_code','race_class_code','surface_code'))),
        'future_source_evidence_exposed':0,'unknown_primary_horses':sum(v for k,v in primary.items() if k.startswith('UNKNOWN')),
        'execution':'local managed runtime; no new generation or production writes'}
    csv_write(args.output/'missing_3794.csv',rows);dump(args.output/'missing_3794.json',rows)
    csv_write(args.output/'entry_evidence.csv',entry_evidence);csv_write(args.output/'monthly_active.csv',monthly)
    csv_write(args.output/'first_appearance_month.csv',summary['first_appearance_month'])
    csv_write(args.output/'first_declared_new_class.csv',summary['first_declared_new_class'])
    csv_write(args.output/'first_month_birth_new_class_reason.csv',cross_rows)
    csv_write(args.output/'race_type_class_surface.csv',summary['race_type_class_surface'])
    unknown=[r for r in rows if r['primary_reason'].startswith('UNKNOWN')]
    with (args.output/'unknown_primary.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(unknown)
    dump(args.output/'unknown_primary.json',unknown)
    provenance=[]
    with (args.output/'source_observations.jsonl').open('w',encoding='utf-8') as f:
        for h in sorted(targets):
            for o in annual.get(h,[])+daily.get(h,[]):
                f.write(json.dumps(o,ensure_ascii=False,sort_keys=True)+'\n')
                provenance.append({k:o[k] for k in ('family','horse_id','source_zip','source_zip_sha256','member','member_sha256','line_number','raw_record_sha256','observation_date','semantic_hash')}
                    | {'profile_date':o['record']['data_date'] if o['record'] else '', 'guards':'|'.join(o['guards'])})
    csv_write(args.output/'source_observations.csv',provenance)
    dump(args.output/'summary.json',summary);dump(args.output/'daily_inventory.json',di);dump(args.output/'annual_inventory.json',ai)
    dump(args.output/'input_errors.json',errors);dump(args.output/'kyi_replay_inventory.json',kyi_inventory)
    (args.output/'RESULT.md').write_text(report(summary),encoding='utf-8')
    files={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()}
    manifest_out={'audit_version':VERSION,'source_commit':args.source_commit,'upstream_zip_sha256':sha(args.upstream),
        'upstream_audit_manifest_sha256':up['upstream_manifest_sha256'],'research_manifest_sha256':sha(manifest),
        'source_sha256':{p.name:sha(p) for p in (Path(__file__),ROOT/'horse-racing/brdb/src/audit_race_year_pedigree.py',
            ROOT/'horse-racing/brdb/src/build_brdb_research_candidate.py',Path(jrdb_ukc.__file__),Path(sys.modules['jrdb_raw'].__file__))},
        'target_id_set_sha256':hashlib.sha256(('\n'.join(sorted(targets))+'\n').encode()).hexdigest(),
        'output_sha256':files,'read_only':True}
    dump(args.output/'manifest.json',manifest_out)
    print(json.dumps({'status':summary['status'],'target_horses':len(rows),'target_entries':summary['target_entries'],
        'primary_reasons':{k:v['count'] for k,v in summary['primary_reasons'].items()},'recovery_potential':summary['recovery_potential']},ensure_ascii=False))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('upstream','paci_dir','annual_dir','research','output'):p.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    p.add_argument('--source-commit',required=True)
    run(p.parse_args())

if __name__=='__main__':main()
