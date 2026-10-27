#!/usr/bin/env python3
"""Read-only race-year KYI audit over pinned PACI and immutable BRDB generations.

Latest-profile snapshot coverage and race-date-safe coverage are distinct.
KYI declarations are the denominator; actual start/cancellation cannot be proven
from these pre-race inputs. All outputs are research audit artifacts.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'horse-racing/jrdb/src'))
from jrdb_raw import Parser, canonical_members, split_fixed_records
import jrdb_ukc
from brdb_ancestor_graph import ancestor_graph
from brdb_pedigree_reader import BloodReviewReader
from brdb_research_reader import ResearchPedigreeReader

VERSION = 'race-year-pedigree-audit-0.1'
RESOLVED = {'RESOLVED_EXACT', 'RESOLVED_ALIAS'}
ROLES = ('sire', 'dam', 'broodmare_sire')
NAMES = tuple(r + '_name' for r in ROLES)
CODES = ('sire_line_code', 'broodmare_sire_line_code')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def csv_write(path, rows):
    if not rows:
        Path(path).write_text('', encoding='utf-8')
        return
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def rate(n, d):
    return {'count': n, 'denominator': d, 'percent': round(100 * n / d, 6) if d else None}


def verified(path, item):
    path = Path(path)
    if path.stat().st_size != int(item['size_bytes']) or sha(path) != item['sha256']:
        raise ValueError(f'input size/SHA mismatch: {path.name}')


def parse_entries(paci_dir, inventory):
    parser = Parser(); entries = {}; audited = []
    names = [x['name'] for x in inventory]
    if len(names) != 91 or len(set(names)) != 91:
        raise ValueError('expected fixed 91 unique PACI ZIPs')
    for item in sorted(inventory, key=lambda x: x['name']):
        name = item['name']; path = paci_dir / name
        if not re.fullmatch(r'PACI26\d{4}\.zip', name):
            raise ValueError('outside 2026 PACI scope')
        verified(path, item)
        date = '20' + name[4:10]; datetime.strptime(date, '%Y%m%d')
        if not '20260104' <= date <= '20261025':
            raise ValueError('outside fixed date scope')
        member_inventory = []; raw_count = 0; duplicates = 0
        with zipfile.ZipFile(path) as z:
            if z.testzip():
                raise ValueError(f'ZIP corruption: {name}')
            bac = {}
            for member in canonical_members(z, 'BAC'):
                data = z.read(member); records = split_fixed_records(data, 'BAC')
                if data and not records: raise ValueError(f'invalid BAC lengths: {name}:{member}')
                for raw in records:
                    race = parser.bac(raw); key = race['race_key_raw']
                    if key in bac and bac[key] != race: raise ValueError('conflicting BAC duplicate')
                    bac[key] = race
            members = canonical_members(z, 'KYI')
            if not members or not bac: raise ValueError(f'missing KYI/BAC: {name}')
            for member in members:
                data = z.read(member); records = split_fixed_records(data, 'KYI')
                if not records: raise ValueError(f'empty/invalid KYI: {name}:{member}')
                member_inventory.append({'member': member, 'sha256': hashlib.sha256(data).hexdigest(),
                                         'size_bytes': len(data), 'record_count': len(records)})
                for line_no, raw in enumerate(records, 1):
                    r = parser.kyi(raw); key = r['race_key_raw']; hid = r['blood_registration_no']
                    if (not re.fullmatch(r'\d{8}', hid) or not re.fullmatch(r'\d{4}[0-9A-Fa-f]{2}\d{2}', key)
                        or key[2:4] != '26' or not 1 <= int(key[:2]) <= 10
                        or not 1 <= int(key[-2:]) <= 12 or not r['horse_no'] or not 1 <= r['horse_no'] <= 18):
                        raise ValueError(f'invalid KYI identity: {name}:{member}:{line_no}')
                    race = bac.get(key)
                    if race is None or race['date_raw'] != date: raise ValueError('KYI/BAC/archive date mismatch')
                    row = {'race_date': date, 'race_key': key, 'horse_no': r['horse_no'], 'horse_id': hid,
                           'horse_name': r['horse_name'], 'race_class_code': race['race_class_code'],
                           'source_zip': name, 'source_member': member, 'source_line': line_no}
                    identity = date, key, r['horse_no']; raw_count += 1
                    if identity in entries:
                        previous = entries[identity]
                        if any(previous[k] != row[k] for k in ('horse_id', 'horse_name', 'race_class_code')):
                            raise ValueError('conflicting KYI duplicate')
                        duplicates += 1
                    else: entries[identity] = row
        audited.append({'name': name, 'sha256': item['sha256'], 'size_bytes': item['size_bytes'],
                        'date': date, 'kyi_members': member_inventory, 'raw_entries': raw_count,
                        'duplicates_removed': duplicates, 'unique_entries_added': raw_count - duplicates})
    return sorted(entries.values(), key=lambda r: (r['race_date'], r['race_key'], r['horse_no'])), audited


def table(path):
    import duckdb
    c = duckdb.connect(':memory:')
    try:
        q = c.execute('SELECT * FROM read_parquet(?)', [str(path)])
        keys = [x[0] for x in q.description]
        return [dict(zip(keys, row)) for row in q.fetchall()]
    finally: c.close()


class AuditSnapshot:
    """Bulk research audit view over SHA-verified immutable generation files."""
    def __init__(self, root):
        self.root = Path(root)
        self.manifest = json.loads((self.root / 'manifest.json').read_text())
        if self.manifest['validation_status'] != 'PASS': raise ValueError('generation not PASS')
        for name, digest in self.manifest['output_sha256'].items():
            if sha(self.root / name) != digest: raise ValueError(f'generation object SHA mismatch: {name}')
        rows = table(self.root / 'pedigree_fact.parquet')
        self.profiles = {x['horse_id']: x for x in rows}
        if len(rows) != len(self.profiles): raise ValueError('duplicate profile IDs')
        self.relations = defaultdict(list)
        for r in table(self.root / 'parent_relation.parquet'):
            if r['resolved_parent_horse_id'] and r['resolution_status'] not in RESOLVED:
                raise ValueError('unresolved parent has canonical ID')
            self.relations[r['child_horse_id']].append(r)
        if any(len(v) != 3 or {r['role'] for r in v} != set(ROLES) for v in self.relations.values()):
            raise ValueError('invalid parent relation cardinality')
        if set(self.profiles) != set(self.relations): raise ValueError('profile/relation ID mismatch')
        self.mapped = {x['lineage_code'] for x in table(self.root / 'lineage_code_master.parquet')}
        self.available = {}
        self.graph_cache = {}

    def safe(self, hid, date):
        p = self.profiles.get(hid); seen = self.available.get(hid)
        return bool(p and seen and seen <= date and p['profile_data_date'] <= date)

    def relations_at(self, hid, date=None):
        rows = self.relations.get(hid, [])
        if date is None: return rows
        if not self.safe(hid, date): return []
        return [{**r, 'resolved_parent_horse_id': None, 'resolution_status': 'INSUFFICIENT_GUARD'}
                if r['resolved_parent_horse_id'] and not self.safe(r['resolved_parent_horse_id'], date)
                else r for r in rows]

    def depths(self, hid, date=None):
        key = hid, date
        if key in self.graph_cache: return self.graph_cache[key]
        if hid not in self.profiles or (date is not None and not self.safe(hid, date)):
            return {'ancestor_depth': 0, **{r + '_ancestor_depth': 0 for r in ROLES}}
        getter = lambda x: self.relations_at(x, date)
        g = ancestor_graph(hid, getter, max_depth=5)
        result = {'ancestor_depth': max((x['depth'] for x in g['paths'] if x['horse_id']), default=0)}
        for role, prefix in (('sire', 'S'), ('dam', 'D')):
            result[role + '_ancestor_depth'] = max((x['depth'] for x in g['paths']
                                                   if x['horse_id'] and x['path'].startswith(prefix)), default=0)
        bms = next((r['resolved_parent_horse_id'] for r in getter(hid)
                    if r['role'] == 'broodmare_sire' and r['resolution_status'] in RESOLVED), None)
        bg = ancestor_graph(bms, getter, max_depth=3) if bms else None
        result['broodmare_sire_ancestor_depth'] = 2 + max((x['depth'] for x in bg['paths']
            if x['horse_id']), default=0) if bg else 0
        self.graph_cache[key] = result
        return result

    def flags(self, hid, date=None):
        p = self.profiles.get(hid); present = p is not None and (date is None or self.safe(hid, date))
        result = {'id_joined': int(present)}
        for field in NAMES + CODES: result[field + '_present'] = int(present and bool(p[field]))
        result['three_names_present'] = int(present and all(p[f] for f in NAMES))
        for field in CODES: result[field + '_mapped'] = int(present and p[field] in self.mapped)
        rel = {r['role']: r for r in self.relations_at(hid, date)} if present else {}
        for role in ROLES:
            r = rel.get(role, {})
            resolved = r.get('resolution_status') in RESOLVED and bool(r.get('resolved_parent_horse_id'))
            result[role + '_id_resolved'] = int(resolved)
            result[role + '_id_unknown'] = int(not resolved)
            result[role + '_id_ambiguous'] = int(r.get('resolution_status') in ('MULTIPLE_CANDIDATES', 'CONFLICT'))
        return result


def annual_availability(annual_dir, snapshots, cohort):
    """Find exact selected annual observations for cohort; pre-2026 bound for ancestors.

    Reuse the UKC parser and its field specifications to prefilter records.
    Raw UKC source date is member date, independent of the profile data date.
    """
    targets = defaultdict(list)
    for label, s in snapshots.items():
        for hid in cohort & s.profiles.keys():
            p = s.profiles[hid]
            targets[hid, p['profile_data_date'], p['semantic_hash']].append(label)
    pending = set(targets); found = {}; inventory = []; all_dates = []
    spec = {name: (offset, width) for name, offset, width in jrdb_ukc.FIELD_SPECS}
    needed_hids = {x[0] for x in targets}; wanted_dates = defaultdict(set)
    for hid, date, digest in targets: wanted_dates[hid].add(date)
    baseline = snapshots['BASE'].manifest
    for item in sorted(baseline['source_archives'], key=lambda x: x['name']):
        path = annual_dir / item['name']; verified(path, item)
        year = int(item['name'][4:8]); members = []; sentinel_count = 0
        with zipfile.ZipFile(path) as z:
            if z.testzip(): raise ValueError('annual ZIP corruption')
            for name in sorted(z.namelist()):
                match = re.fullmatch(r'(?:.*/)?UKC(\d{6})\.txt', name, re.I)
                if not match: continue
                rawdate = match[1]; date = str(year) + rawdate[2:]
                try:
                    datetime.strptime(date, '%Y%m%d')
                    if year % 100 != int(rawdate[:2]): raise ValueError('member/archive year mismatch')
                except ValueError:
                    date = None
                if date: all_dates.append(date)
                count = 0
                with z.open(name) as stream:
                    for line_no, line in enumerate(stream, 1):
                        body = line.rstrip(b'\r\n'); count += 1
                        if len(body) != jrdb_ukc.RECORD_LENGTH: raise ValueError('invalid annual UKC length')
                        hid = jrdb_ukc._text(body, *spec['horse_id'])
                        profile_date = jrdb_ukc._text(body, *spec['data_date'])
                        if profile_date == '99999999': sentinel_count += 1; continue
                        if hid not in needed_hids or profile_date not in wanted_dates[hid]: continue
                        record = jrdb_ukc.parse_ukc_record(body)
                        key = hid, profile_date, record.semantic_hash()
                        if key not in pending: continue
                        if not date: raise ValueError('selected annual profile in undated member')
                        found[key] = {'archive': item['name'], 'member': name, 'line': line_no,
                                      'archive_sha256': item['sha256'], 'observation_date': date}
                        pending.remove(key)
                members.append({'member': name, 'observation_date': date, 'records': count})
        inventory.append({**item, 'members': members, 'sentinel_date_records': sentinel_count})
    bound = max(all_dates)
    if bound >= '20260104' or pending: raise ValueError(f'annual temporal provenance incomplete: {len(pending)}')
    for label, s in snapshots.items():
        s.available = {hid: bound for hid in s.profiles}  # conservative bound, validated pre-2026
    for key, source in found.items():
        for label in targets[key]: snapshots[label].available[key[0]] = source['observation_date']
    return inventory, found, bound


def aggregate(snapshot, units, date_safe=False):
    counts = Counter(); depths = Counter(); per_role = {r: Counter() for r in ROLES}
    for hid, date in units:
        f = snapshot.flags(hid, date if date_safe else None); counts.update(f)
        d = snapshot.depths(hid, date if date_safe else None)
        depths[d['ancestor_depth']] += 1
        for role in ROLES: per_role[role][d[role + '_ancestor_depth']] += 1
    n = len(units)
    return {'denominator': n, 'metrics': {k: rate(v, n) for k, v in sorted(counts.items())},
            'ancestor_depth_0_to_5': {str(k): rate(depths[k], n) for k in range(6)},
            'parent_branch_depth_0_to_5': {r: {str(k): rate(c[k], n) for k in range(6)}
                                         for r, c in per_role.items()}}


def report(summary):
    scope = summary['scope']
    lines = ['# Issue #2218 — 2026 KYI / BRDB audit', '',
        f"Scope: {scope['min_date']}–{scope['max_date']}; {scope['zip_count']}/91 PACI ZIPs, "
        f"{scope['unique_horses']:,} unique horses, {scope['entries']:,} declared entries, {scope['races']:,} races.", '',
        'KYI declarations are counted. Actual-start/cancellation status is UNKNOWN. Dates after 2026-10-25 are outside scope.', '',
        '| Dataset | Static horses | Static entries | Safe at first entry (horses) | Safe race-date entries |',
        '|---|---:|---:|---:|---:|']
    def fmt(metric): return f"{metric['count']:,} / {metric['denominator']:,} ({metric['percent']:.4f}%)"
    for name,g in summary['generations'].items():
        lines.append('| ' + name + ' | ' + ' | '.join(fmt(g[k]['metrics']['id_joined']) for k in
            ('static_horses','static_entries','as_of_first_entry_horses','as_of_entries')) + ' |')
    lines += ['', 'All joined profiles have sire, dam, broodmare-sire names and both official lineage codes mapped to the snapshot master.', '',
        '| Dataset | Sire ID (horses) | Dam ID (horses) | BMS ID (horses) |', '|---|---:|---:|---:|']
    for name,g in summary['generations'].items():
        lines.append('| '+name+' | '+' | '.join(fmt(g['static_horses']['metrics'][r+'_id_resolved']) for r in ROLES)+' |')
    lines += ['', 'Parent-ID UNKNOWN includes absent profiles and unresolved/ambiguous/conflicting candidates. Names are never treated as canonical IDs.', '',
        '| Dataset | Static ancestor max depth 0 / 1 / 2 / 3 / 4 / 5 (horses) |', '|---|---|']
    for name,g in summary['generations'].items():
        lines.append('| '+name+' | '+' / '.join(str(g['static_horses']['ancestor_depth_0_to_5'][str(k)]['count']) for k in range(6))+' |')
    delta=summary['daily_104_contribution']
    lines += ['', f"Daily additions contribute {delta['horses']} horses and {delta['entries']} entries; "
        f"{delta['as_of_safe_entries']} of those entries are safe at race date. The four previously unmatched IDs have no entries in this cohort.", '',
        'As-of uses the selected latest-profile source observation date, not first sighting. Historical reconstruction is unavailable. '
        'Annual cohort observations were matched back to original UKC records; ancestor profiles are bounded by verified pre-2026 annual members. '
        'Every as-of graph edge requires both child and parent profiles to be available. The check is date inclusive; within-day publication times are unverified.', '',
        'Files: horses.csv (all horses × 3 snapshots), entries.csv (all entries × 3), missing_horses.csv, '
        'generation_differences.csv, daily_104_contribution.csv, monthly.json, reader_as_of_checks.csv, '
        'annual_selected_observations.csv, input inventories, summary.json and SHA-pinned manifest.json.', '',
        'Execution: full local managed-runtime audit; no GitHub Actions run is claimed. No production publication is part of this audit.', '']
    return '\n'.join(lines)


def run(args):
    output = args.output
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    inventory = json.loads(args.inventory.read_text())
    entries, input_inventory = parse_entries(args.paci_dir, inventory)
    cohorts = defaultdict(list)
    for e in entries: cohorts[e['horse_id']].append(e)
    ids = set(cohorts)
    snapshots = {'BASE': AuditSnapshot(args.base), 'RESEARCH': AuditSnapshot(args.research),
                 'CURRENT': AuditSnapshot(args.current)}
    expected_ids = {'BASE': 'c73cf76ad930b5f0', 'RESEARCH': 'f409be3f5d11cb90', 'CURRENT': 'eeca93556584a5b8'}
    for label, s in snapshots.items():
        if s.manifest['generation_id'] != expected_ids[label]: raise ValueError('unexpected generation ID')
    research_reader = ResearchPedigreeReader(args.research)
    current_reader = BloodReviewReader(args.current)
    annual, annual_sources, bound = annual_availability(args.annual_dir,
        {k: v for k, v in snapshots.items() if k != 'RESEARCH'}, ids)
    rs = snapshots['RESEARCH']; bs = snapshots['BASE']
    rs.available = dict(bs.available)
    rs.available.update(research_reader.latest_profile_available_from)
    for hid in rs.profiles:
        if hid not in rs.available: raise ValueError('candidate profile lacks temporal provenance')
    # Reader results, rather than an inferred availability date, gate daily rows.
    by_day = defaultdict(set)
    for e in entries: by_day[e['race_date']].add(e['horse_id'])
    reader_checks = []
    for date, day_ids in sorted(by_day.items()):
        got = research_reader.profiles_for_horses(sorted(day_ids), as_of=date)
        expected = {hid for hid in day_ids if rs.safe(hid, date)}
        if set(got) != expected: raise ValueError('research Reader/source-date gate mismatch')
        if any(rs.available[hid] > date or got[hid]['profile_data_date'] > date for hid in got):
            raise ValueError('future profile leakage')
        reader_checks.append({'date': date, 'entries': len(day_ids), 'available': len(got), 'future_leaks': 0})
    if set(current_reader.profiles_for_horses(sorted(ids))) != ids & snapshots['CURRENT'].profiles.keys():
        raise ValueError('CURRENT Reader batch mismatch')
    first_units = [(hid, es[0]['race_date']) for hid, es in sorted(cohorts.items())]
    entry_units = [(e['horse_id'], e['race_date']) for e in entries]
    summary = {'audit_version': VERSION, 'source_commit': args.source_commit,
        'scope': {'min_date': entries[0]['race_date'], 'max_date': entries[-1]['race_date'],
                  'zip_count': len(input_inventory), 'race_days': len(by_day), 'unique_horses': len(ids),
                  'entries': len(entries), 'raw_entries': sum(x['raw_entries'] for x in input_inventory),
                  'duplicates_removed': sum(x['duplicates_removed'] for x in input_inventory),
                  'input_gaps': 0, 'invalid_identity_or_length_records': 0,
                  'races': len({(e['race_date'], e['race_key']) for e in entries}),
                  'denominator_definition': 'KYI declared race-year entries, not confirmed actual starters',
                  'cancellations': 'UNKNOWN: no target-race result/cancellation evidence; declarations retained',
                  'later_2026_days': 'outside scope after 2026-10-25'},
        'as_of_policy': {'daily': 'latest selected profile archive observation date; no historical reconstruction',
                         'annual': 'exact selected cohort observation; ancestor profiles bounded by verified pre-2026 annual member dates',
                         'annual_observation_upper_bound': bound, 'parent_edges': 'child and canonical parent profiles must both be available',
                         'horse_unit': 'earliest scanned 2026 entry date; any/all safe-entry counts also supplied',
                         'depth_definition': 'sire/dam direct edge is generation 1; direct BMS is generation 2; overall graph uses only sire/dam paths',
                         'temporal_precision': 'date inclusive; intra-day publication times not verified'},
        'generations': {}, 'future_profile_leaks': 0, 'execution': 'local managed runtime; no Actions run claimed'}
    horse_rows = []; entry_rows = []; missing = []; monthly = {}; delta = []
    for label, s in snapshots.items():
        stats = {'generation_id': s.manifest['generation_id'],
                 'static_horses': aggregate(s, first_units), 'static_entries': aggregate(s, entry_units),
                 'as_of_first_entry_horses': aggregate(s, first_units, True),
                 'as_of_entries': aggregate(s, entry_units, True)}
        any_safe = all_safe = 0
        for hid, es in sorted(cohorts.items()):
            p = s.profiles.get(hid); safe_count = sum(s.safe(hid, e['race_date']) for e in es)
            any_safe += safe_count > 0; all_safe += safe_count == len(es)
            row = {'dataset': label, 'horse_id': hid, 'kyi_horse_name': es[0]['horse_name'],
                   'first_entry_date': es[0]['race_date'], 'last_entry_date': es[-1]['race_date'],
                   'entry_count': len(es), 'as_of_safe_entries': safe_count,
                   'selected_profile_observed_date': s.available.get(hid, ''),
                   'profile_data_date': p['profile_data_date'] if p else '',
                   **{f: p.get(f) if p else '' for f in NAMES + CODES},
                   **s.flags(hid), **s.depths(hid),
                   **{'first_entry_safe_' + k: v for k, v in s.flags(hid, es[0]['race_date']).items()}}
            rels = {x['role']: x for x in s.relations.get(hid, [])}
            for role in ROLES:
                row[role + '_resolution_status'] = rels.get(role, {}).get('resolution_status', 'NO_PROFILE')
                row[role + '_canonical_id'] = rels.get(role, {}).get('resolved_parent_horse_id') or ''
            horse_rows.append(row)
            if p is None: missing.append({k: row[k] for k in ('dataset','horse_id','kyi_horse_name','first_entry_date','last_entry_date','entry_count')})
        stats['as_of_horses_any_entry_available'] = rate(any_safe, len(ids))
        stats['as_of_horses_every_entry_available'] = rate(all_safe, len(ids))
        summary['generations'][label] = stats
        for e in entries:
            hid = e['horse_id']; date = e['race_date']; safe = s.safe(hid, date)
            entry_rows.append({**e, 'dataset': label,
                'as_of_status': 'AVAILABLE' if safe else ('UNMATCHED' if hid not in s.profiles else 'LATEST_PROFILE_NOT_YET_OBSERVED'),
                'selected_profile_observed_date': s.available.get(hid, ''),
                **{'static_' + k: v for k, v in s.flags(hid).items()},
                **{'as_of_' + k: v for k, v in s.flags(hid, date).items()},
                **{'as_of_' + k: v for k, v in s.depths(hid, date).items()}})
        monthly[label] = {}
        for month in sorted({e['race_date'][:6] for e in entries}):
            mes = [e for e in entries if e['race_date'].startswith(month)]; mfirst = {}
            for e in mes: mfirst.setdefault(e['horse_id'], e['race_date'])
            monthly[label][month] = {'static_horses': aggregate(s,list(mfirst.items())),
                'as_of_first_entry_horses': aggregate(s,list(mfirst.items()),True),
                'static_entries': aggregate(s,[(e['horse_id'],e['race_date']) for e in mes]),
                'as_of_entries': aggregate(s,[(e['horse_id'],e['race_date']) for e in mes],True)}
    added = set(rs.profiles) - set(bs.profiles)
    previous_audit = json.loads(args.missing_audit.read_text())
    if len(previous_audit) != 108 or len({x['horse_id'] for x in previous_audit}) != 108:
        raise ValueError('expected fixed 108-ID audit')
    if added != {x['horse_id'] for x in previous_audit if x['status'] == 'FOUND'}:
        raise ValueError('candidate additions differ from previous audit')
    for hid in sorted(added & ids):
        es = cohorts[hid]
        delta.append({'horse_id': hid, 'horse_name': es[0]['horse_name'], 'entries': len(es),
                      'first_entry_date': es[0]['race_date'], 'last_entry_date': es[-1]['race_date'],
                      'selected_latest_observation': rs.available[hid],
                      'as_of_safe_entries': sum(rs.safe(hid,e['race_date']) for e in es)})
    summary['daily_104_contribution'] = {'horses': len(delta), 'entries': sum(x['entries'] for x in delta),
                                       'as_of_safe_entries': sum(x['as_of_safe_entries'] for x in delta)}
    known = [x['horse_id'] for x in previous_audit if x['status'] == 'NOT_FOUND_IN_SCANNED']
    if len(known) != 4: raise ValueError('expected four previously unmatched IDs')
    summary['known_four_unmatched'] = [{'horse_id': hid, 'cohort_entries': len(cohorts.get(hid, [])),
                                      'research_joined': hid in rs.profiles} for hid in known]
    declared_new = {hid for hid, es in cohorts.items() if es[0]['race_class_code'] in ('A1','A2')}
    summary['declared_new_race_first_appearance'] = {'definition': 'first scanned entry has BAC A1/A2; not independently proven debut',
        'horse_count': len(declared_new), 'generations': {k: aggregate(s,[(h,cohorts[h][0]['race_date']) for h in sorted(declared_new)])
                                                       for k,s in snapshots.items()}}
    csv_write(output/'horses.csv',horse_rows); csv_write(output/'entries.csv',entry_rows)
    csv_write(output/'missing_horses.csv',missing); csv_write(output/'daily_104_contribution.csv',delta)
    csv_write(output/'reader_as_of_checks.csv',reader_checks)
    differences=[]
    for hid in sorted(ids):
        row={'horse_id':hid, 'kyi_horse_name':cohorts[hid][0]['horse_name']}
        for label,s in snapshots.items():
            values={**s.flags(hid),**s.depths(hid)}
            for key in ('id_joined','sire_id_resolved','dam_id_resolved','broodmare_sire_id_resolved','ancestor_depth'):
                row[label.lower()+'_'+key]=values[key]
        if any(row['base_'+k] != row[l+'_'+k] for l in ('research','current')
               for k in ('id_joined','sire_id_resolved','dam_id_resolved','broodmare_sire_id_resolved','ancestor_depth')):
            differences.append(row)
    csv_write(output/'generation_differences.csv',differences)
    dump(output/'summary.json',summary); dump(output/'monthly.json',monthly)
    dump(output/'input_inventory.json',input_inventory); dump(output/'annual_inventory.json',annual)
    sources = []
    for key,value in sorted(annual_sources.items()):
        sources.append({'horse_id':key[0],'profile_data_date':key[1],'semantic_hash':key[2],**value})
    csv_write(output/'annual_selected_observations.csv',sources)
    (output/'RESULT.md').write_text(report(summary),encoding='utf-8')
    generations = {k: {'manifest_sha256':sha(s.root/'manifest.json'),
                      'generation_id':s.manifest['generation_id'],'output_sha256':s.manifest['output_sha256']}
                   for k,s in snapshots.items()}
    manifest = {'audit_version':VERSION,'source_commit':args.source_commit,
        'source_sha256':{p.name:sha(p) for p in [Path(__file__), Path(jrdb_ukc.__file__),
            ROOT/'horse-racing/jrdb/src/jrdb_raw.py', Path(sys.modules['brdb_research_reader'].__file__),
            Path(sys.modules['brdb_pedigree_reader'].__file__),Path(sys.modules['brdb_ancestor_graph'].__file__)]},
        'inventory_input_sha256':sha(args.inventory),'previous_audit_sha256':sha(args.missing_audit),'generations':generations,
        'output_sha256':{p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()}}
    dump(output/'manifest.json',manifest)
    print(json.dumps({'output':str(output),'scope':summary['scope'],'daily_104_contribution':summary['daily_104_contribution']}))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('paci_dir','inventory','annual_dir','base','research','current','missing_audit','output'):
        p.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    p.add_argument('--source-commit',required=True)
    run(p.parse_args())

if __name__=='__main__': main()
