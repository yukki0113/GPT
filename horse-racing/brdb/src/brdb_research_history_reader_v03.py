"""Point-in-time UKC profiles for explicitly selected research generations.

Calendar dates are inclusive; publication time is unknown. Annual profiles are
only the selected annual snapshot. Parent IDs are intentionally UNKNOWN because
current parent relations are not a historical graph.
"""
from __future__ import annotations
import json
import re
import sys
from collections import defaultdict
from dataclasses import fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'jrdb' / 'src'))
from jrdb_ukc import UKCRecord
from brdb_research_reader_v02 import ResearchGenerationReader, valid_date
from brdb_pedigree_reader import BloodReviewReaderError, _sha256

ROLES = ('sire', 'dam', 'broodmare_sire')


def validate_observation(row):
    """Validate a candidate including its full semantic payload and provenance."""
    try:
        raw = json.loads(row['profile_json'])
        if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(UKCRecord)}:
            raise ValueError('profile fields mismatch')
        years = {'sire_birth_year', 'dam_birth_year', 'broodmare_sire_birth_year'}
        if any((value is not None and type(value) is not int) if key in years else not isinstance(value, str)
               for key, value in raw.items()):
            raise ValueError('profile field types invalid')
        rec = UKCRecord(**raw)
        if (not re.fullmatch(r'[0-9]{8}', rec.horse_id) or rec.horse_id != row['horse_id']
                or not valid_date(rec.data_date) or rec.data_date != row['profile_data_date']
                or not valid_date(row['archive_date']) or rec.data_date > row['archive_date']
                or row['archive'] != 'PACI' + row['archive_date'][2:] + '.zip'
                or not row['member'] or type(row['line_number']) is not int or row['line_number'] < 1
                or any(not re.fullmatch(r'[0-9a-f]{64}', row[k] or '') for k in
                       ('semantic_hash', 'archive_sha256', 'member_sha256', 'record_sha256'))
                or rec.semantic_hash() != row['semantic_hash']):
            raise ValueError('observation provenance or semantic hash mismatch')
        return raw
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError('invalid daily source') from exc


def choose_observation(rows, as_of):
    """Choose latest available data date, rejecting semantic conflicts at any date."""
    if not valid_date(as_of):
        raise ValueError('as_of must be valid YYYYMMDD')
    eligible = []
    for row in rows:
        if row.get('input_status') != 'VALID':
            continue
        # Invalid dates cannot be ordered safely, hence fail closed.
        if not valid_date(row.get('archive_date')) or not valid_date(row.get('profile_data_date')):
            return 'INVALID_SOURCE', None, None
        if row['archive_date'] > as_of:
            continue
        if row['profile_data_date'] > row['archive_date']:
            return 'INVALID_SOURCE', None, None
        if row['profile_data_date'] > as_of:
            continue
        try:
            raw = validate_observation(row)
        except ValueError:
            return 'INVALID_SOURCE', None, None
        eligible.append((row, raw))
    if not eligible:
        return 'NOT_YET_OBSERVED', None, None
    by_date = defaultdict(set)
    for row, _ in eligible:
        by_date[row['profile_data_date']].add(row['semantic_hash'])
    if any(len(hashes) > 1 for hashes in by_date.values()):
        return 'HISTORY_CONFLICT', None, None
    # Builder selects the greatest tuple, including ZIP/member/line.
    eligible.sort(key=lambda x: (x[0]['profile_data_date'], x[0]['archive_date'],
                                 x[0]['archive'], x[0]['member'], x[0]['line_number']), reverse=True)
    row, raw = eligible[0]
    return 'AVAILABLE_LATEST_DAILY' if row['selected'] else 'AVAILABLE_HISTORICAL_DAILY', row, raw


class ResearchHistoryReader:
    def __init__(self, generation_path, *, expected_generation_id, expected_manifest_sha256):
        if not re.fullmatch(r'[0-9a-f]{64}', expected_manifest_sha256 or '') or _sha256(Path(generation_path) / 'manifest.json') != expected_manifest_sha256:
            raise BloodReviewReaderError('generation manifest SHA mismatch')
        self.latest = ResearchGenerationReader(generation_path)
        if self.latest._legacy or self.latest.generation_id != expected_generation_id:
            raise BloodReviewReaderError('unexpected research generation')
        self.generation_id = self.latest.generation_id
        reader = self.latest._reader
        contract = self.latest.manifest['research_reader_contract']
        con = reader._connect()
        try:
            def load(path):
                return reader._rows(con.execute('SELECT * FROM read_parquet(?)', [str(path)]))
            facts = load(reader._paths['pedigree_fact.parquet'])
            history = load(self.latest.root / contract['observation_history']['path'])
            annual = load(self.latest.root / contract['annual_availability']['path'])
            relations = con.execute('SELECT count(*) FROM read_parquet(?)', [str(reader._paths['parent_relation.parquet'])]).fetchone()[0]
            if relations != self.latest.manifest['row_counts']['parent_relation']:
                raise BloodReviewReaderError('parent relation row count mismatch')
        finally:
            con.close()
        self.facts = {r['horse_id']: r for r in facts}
        self.annual = {r['horse_id']: r for r in annual}
        self.history = defaultdict(list)
        for row in history:
            if row['horse_id'] in self.latest.added_ids:
                self.history[row['horse_id']].append(row)
        if set(self.history) != self.latest.added_ids:
            raise BloodReviewReaderError('daily history IDs differ from added cohort')

    def horse_profile(self, horse_id, *, as_of):
        if not valid_date(as_of):
            raise ValueError('as_of must be valid YYYYMMDD')
        hid = self.latest._reader._require_horse_id(horse_id)
        base = {'horse_id': hid, 'research_only': True, 'as_of': as_of,
                'generation_id': self.generation_id, 'profile': None, 'source': None,
                'profile_data_date': None, 'observed_date': None,
                'publication_time': 'UNKNOWN', 'parent_ids': {role: None for role in ROLES}}
        if hid not in self.facts:
            return {**base, 'status': 'UNKNOWN_HORSE_ID'}
        if hid not in self.latest.added_ids:
            a = self.annual[hid]
            if self.latest.available_from[hid] > as_of:
                return {**base, 'status': 'UNSUPPORTED_ANNUAL_HISTORY'}
            return {**base, 'status': 'AVAILABLE_ANNUAL_SNAPSHOT', 'profile': self.facts[hid],
                    'profile_data_date': a['profile_data_date'], 'observed_date': a['archive_date'],
                    'source': {k: a[k] for k in ('archive', 'archive_sha256', 'member', 'line_number')}}
        status, row, raw = choose_observation(self.history[hid], as_of)
        if row is None:
            return {**base, 'status': status}
        return {**base, 'status': status, 'profile': raw, 'profile_data_date': row['profile_data_date'],
                'observed_date': row['archive_date'], 'source': {k: row[k] for k in
                ('archive', 'archive_sha256', 'member', 'member_sha256', 'line_number', 'record_sha256', 'semantic_hash')}}

    def profiles_for_horses(self, horse_ids, *, as_of):
        return [self.horse_profile(hid, as_of=as_of) for hid in horse_ids]

    def parent_relations(self, horse_id, *, as_of):
        result = self.horse_profile(horse_id, as_of=as_of)
        if result['profile'] is None:
            return []
        p = result['profile']
        return [{'role': role, 'parent_name': p.get(role + '_name'),
                 'resolved_parent_horse_id': None, 'resolution_status': 'UNKNOWN',
                 'guard_result': 'historical_parent_resolution_not_implemented'} for role in ROLES]
