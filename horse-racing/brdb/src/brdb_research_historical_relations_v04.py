"""As-of parent identities and ancestor graph for an explicit research generation.

Each date builds a master index only from profiles available on that date.
The alias ledger has no proven availability date, so matching is exact only.
Distribution time within a date is unknown. No production pointer is read.
"""
from __future__ import annotations
from copy import deepcopy
from brdb_research_history_reader_v03 import ResearchHistoryReader
from brdb_research_reader_v02 import valid_date
from brdb_pedigree_reader import BloodReviewReaderError
from brdb_parent_relation import HorseMasterIndex, AliasIndex, resolve_first_generation
from brdb_ancestor_graph import ancestor_graph

ROLES = ('sire', 'dam', 'broodmare_sire')


class HistoricalRelationsReader:
    def __init__(self, generation_path, *, expected_generation_id, expected_manifest_sha256):
        self.history = ResearchHistoryReader(generation_path, expected_generation_id=expected_generation_id,
                                             expected_manifest_sha256=expected_manifest_sha256)
        self._date = None
        self._relations = {}
        self._profiles = {}
        self._master = None
        self._aliases = AliasIndex()  # no timestamped evidence for alias ledger
        self._coverage_end = max(row['archive_date'] for rows in self.history.history.values() for row in rows if valid_date(row['archive_date']))

    def _prepare(self, as_of):
        if not valid_date(as_of):
            raise ValueError('as_of must be valid YYYYMMDD')
        if as_of > self._coverage_end:
            raise ValueError('as_of exceeds available daily observation coverage')
        if self._date == as_of:
            return
        h = self.history
        profiles = {hid: fact for hid, fact in h.facts.items()
                    if hid not in h.latest.added_ids and h.latest.available_from[hid] <= as_of}
        for hid in sorted(h.latest.added_ids):
            result = h.horse_profile(hid, as_of=as_of)
            if result['status'] in ('INVALID_SOURCE', 'HISTORY_CONFLICT'):
                # The missing candidate's historical name/sex/line are unknowable.
                # Resolving any other candidate as unique would be unsound.
                raise BloodReviewReaderError('candidate population has invalid or conflicting history')
            if result['profile'] is not None:
                profiles[hid] = result['profile']
        self._master = HorseMasterIndex(profiles.values())
        self._profiles = profiles
        self._relations = {}
        self._date = as_of

    def horse_profile(self, horse_id, *, as_of):
        if not valid_date(as_of) or as_of > self._coverage_end:
            raise ValueError('as_of outside valid daily observation coverage')
        return self.history.horse_profile(horse_id, as_of=as_of)

    def parent_relations(self, horse_id, *, as_of):
        self._prepare(as_of)
        hid = self.history.latest._reader._require_horse_id(horse_id)
        if hid in self._relations:
            return deepcopy(self._relations[hid])
        child = self.history.horse_profile(hid, as_of=as_of)
        if child['profile'] is None:
            rows = [{'child_horse_id': hid, 'role': role, 'resolution_status': child['status'],
                     'resolved_parent_horse_id': None, 'candidate_count': 0,
                     'guard_result': 'child_profile_unavailable', 'as_of': as_of,
                     'child_source': None, 'parent_source': None} for role in ROLES]
        else:
            resolved = resolve_first_generation(child['profile'], master=self._master, aliases=self._aliases)
            rows = []
            for role in ROLES:
                v = resolved[role]
                parent = self.history.horse_profile(v.resolved_horse_id, as_of=as_of) if v.resolved_horse_id else None
                if parent is not None and parent['profile'] is None:
                    raise BloodReviewReaderError('resolved parent is not available as of date')
                rows.append({'child_horse_id': hid, 'role': role, 'parent_name': v.requested_name,
                             'parent_birth_year': v.requested_birth_year, 'parent_lineage_code': v.requested_lineage_code,
                             'resolved_parent_horse_id': v.resolved_horse_id, 'resolution_status': v.status,
                             'candidate_count': v.candidate_count, 'guard_result': v.guard,
                             'resolution_method': v.resolution_method, 'as_of': as_of,
                             'child_source': child['source'], 'child_status': child['status'],
                             'parent_source': parent['source'] if parent else None,
                             'parent_status': parent['status'] if parent else None,
                             'parent_profile_data_date': parent['profile_data_date'] if parent else None,
                             'parent_observed_date': parent['observed_date'] if parent else None,
                             'alias_policy': 'EXACT_ONLY_UNDATED_LEDGER', 'research_only': True})
        self._relations[hid] = rows
        return deepcopy(rows)

    def relations_for_horses(self, horse_ids, *, as_of):
        return {hid: self.parent_relations(hid, as_of=as_of) for hid in horse_ids}

    def ancestor_graph(self, horse_id, *, as_of, max_depth=5):
        self._prepare(as_of)
        profile = self.history.horse_profile(horse_id, as_of=as_of)
        if profile['profile'] is None:
            return {'horse_id': horse_id, 'as_of': as_of, 'status': profile['status'],
                    'paths': [], 'coverage': 'UNKNOWN', 'max_depth': max_depth}
        graph = ancestor_graph(horse_id, lambda hid: self.parent_relations(hid, as_of=as_of), max_depth=max_depth)
        graph.update(as_of=as_of, research_only=True, absence_is_proven=False,
                     interpretation='OBSERVED_ONLY', broodmare_sire_semantics='dam-sire is generation 2')
        return graph
