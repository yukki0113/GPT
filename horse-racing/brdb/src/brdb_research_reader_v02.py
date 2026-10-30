"""Manifest-bound read-only research Reader v0.2; preserves legacy v0.1 access."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from brdb_pedigree_reader import BloodReviewReader, BloodReviewReaderError, _safe_relative, _sha256
from brdb_research_reader import ResearchPedigreeReader

CONTRACT_VERSION='research-reader-v0.2'
ID_SET_ENCODING='sorted-utf8-lines-v1'


def ids_sha256(ids):
    return hashlib.sha256(('\n'.join(sorted(set(ids)))+'\n').encode('utf-8')).hexdigest()


def valid_date(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{8}',value):return False
    try:datetime.strptime(value,'%Y%m%d');return True
    except ValueError:return False


class ResearchGenerationReader:
    def __init__(self,generation_path):
        self.root=Path(generation_path).resolve()
        self._reader=BloodReviewReader(self.root,research_generation=True)
        self.manifest=self._reader.manifest
        self._legacy=None
        contract=self.manifest.get('research_reader_contract')
        if contract is None:
            if self.manifest.get('builder_version')!='research-paci-v0.1':
                raise BloodReviewReaderError('research v0.2 contract missing')
            self._legacy=ResearchPedigreeReader(self.root)
            self._reader=self._legacy._reader
            self.first_seen=dict(self._legacy.first_seen)
            self.latest_profile_available_from=dict(self._legacy.latest_profile_available_from)
            self.available_from=dict(self.latest_profile_available_from)
            self.added_ids=set(self.first_seen)
            return
        if (contract.get('version')!=CONTRACT_VERSION or contract.get('id_set_encoding')!=ID_SET_ENCODING
            or contract.get('as_of_policy')!='selected_latest_observation_date'):
            raise BloodReviewReaderError('unsupported research Reader contract')
        count=contract.get('added_count');annual_count=contract.get('annual_count')
        if (type(count) is not int or count<1 or type(annual_count) is not int or annual_count<1):
            raise BloodReviewReaderError('invalid manifest-bound research cohort counts')

        def verified_path(key):
            ref=contract.get(key)
            if not isinstance(ref,dict):raise BloodReviewReaderError('missing research file binding: '+key)
            name=ref.get('path');digest=ref.get('sha256')
            if not isinstance(name,str) or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
                raise BloodReviewReaderError('invalid research file binding')
            path=_safe_relative(self.root,name)
            if (self.manifest['output_sha256'].get(name)!=digest or not path.is_file() or _sha256(path)!=digest):
                raise BloodReviewReaderError('research file SHA mismatch: '+key)
            return path

        audit_path=verified_path('added_audit')
        daily_path=verified_path('observation_history')
        annual_path=verified_path('annual_availability')
        rows=json.loads(audit_path.read_text(encoding='utf-8'))
        if not isinstance(rows,list) or len(rows)!=count:
            raise BloodReviewReaderError('added audit count mismatch')
        ids=[r.get('horse_id') for r in rows]
        if any(not isinstance(h,str) or not h for h in ids) or len(set(ids))!=count:
            raise BloodReviewReaderError('added audit IDs invalid or duplicated')
        self.added_ids=set(ids)
        if ids_sha256(ids)!=contract.get('added_ids_sha256'):
            raise BloodReviewReaderError('added ID-set SHA mismatch')
        self.first_seen={r['horse_id']:r['first_observed_archive_date'] for r in rows}
        audit_by_id={r['horse_id']:r for r in rows}
        con=self._reader._connect()
        try:
            meta=self._reader._rows(con.execute('SELECT horse_id,profile_data_date,semantic_hash FROM read_parquet(?)',
                                                [str(self._reader._paths['pedigree_fact.parquet'])]))
            facts={r['horse_id']:r for r in meta}
            if len(meta)!=len(facts) or len(facts)!=annual_count+count:
                raise BloodReviewReaderError('fact/contract cohort cardinality mismatch')
            annual=self._reader._rows(con.execute('SELECT * FROM read_parquet(?)',[str(annual_path)]))
            annual_by_id={r['horse_id']:r for r in annual}
            annual_ids=set(facts)-self.added_ids
            if (len(annual)!=annual_count or len(annual_by_id)!=annual_count or set(annual_by_id)!=annual_ids
                    or ids_sha256(annual_ids)!=contract.get('annual_ids_sha256')):
                raise BloodReviewReaderError('annual availability ID binding mismatch')
            daily_count=con.execute('SELECT count(*) FROM read_parquet(?)',[str(daily_path)]).fetchone()[0]
            if daily_count!=self.manifest['row_counts'].get('daily_observation_history'):
                raise BloodReviewReaderError('observation history row count mismatch')
            selected=self._reader._rows(con.execute('''SELECT horse_id,archive_date,profile_data_date,semantic_hash,input_status
                FROM read_parquet(?) WHERE selected = 1''',[str(daily_path)]))
            selected_by_id={r['horse_id']:r for r in selected}
            if len(selected)!=count or set(selected_by_id)!=self.added_ids:
                raise BloodReviewReaderError('selected history ID binding mismatch')
            first=self._reader._rows(con.execute('''SELECT horse_id,min(archive_date) AS first_date
                FROM read_parquet(?) GROUP BY horse_id''',[str(daily_path)]))
            first_by_id={r['horse_id']:r['first_date'] for r in first}
        finally:con.close()
        self.latest_profile_available_from={}
        self.available_from={}
        for hid,a in annual_by_id.items():
            if (not valid_date(a['archive_date']) or not valid_date(a['profile_data_date'])
                or a['profile_data_date']!=facts[hid]['profile_data_date']
                or a['semantic_hash']!=facts[hid]['semantic_hash']):
                raise BloodReviewReaderError('annual selected profile provenance mismatch')
            self.available_from[hid]=max(a['archive_date'],a['profile_data_date'])
        for hid in self.added_ids:
            a=audit_by_id[hid];history=selected_by_id[hid];fact=facts.get(hid)
            observed=history['archive_date'];first_date=self.first_seen[hid]
            if (not fact or not valid_date(first_date) or not valid_date(observed)
                or history['input_status']!='VALID'
                or first_by_id.get(hid)!=first_date or observed<first_date
                or a['selected_observation_date']!=observed
                or history['profile_data_date']!=fact['profile_data_date']
                or history['semantic_hash']!=fact['semantic_hash']
                or a['profile_data_date']!=fact['profile_data_date']
                or a['semantic_hash']!=fact['semantic_hash']
                or not valid_date(fact['profile_data_date']) or fact['profile_data_date']>observed):
                raise BloodReviewReaderError('daily selected latest profile provenance mismatch')
            self.latest_profile_available_from[hid]=observed
            self.available_from[hid]=observed

    @property
    def generation_id(self):return self._reader.generation_id

    def _available(self,horse_id,as_of):
        if not valid_date(as_of):raise ValueError('as_of must be a valid YYYYMMDD')
        if self._legacy:return self._legacy._available(horse_id,as_of)
        return horse_id in self.available_from and self.available_from[horse_id]<=as_of

    def horse_profile(self,horse_id,*,as_of):
        hid=self._reader._require_horse_id(horse_id)
        return self._reader.horse_profile(hid) if self._available(hid,as_of) else None

    def profiles_for_horses(self,horse_ids,*,as_of):
        ids=[self._reader._require_horse_id(h) for h in horse_ids]
        return self._reader.profiles_for_horses([h for h in ids if self._available(h,as_of)])

    def _safe_relation(self,row,as_of):
        parent=row.get('resolved_parent_horse_id')
        if parent and not self._available(parent,as_of):
            return {**row,'resolved_parent_horse_id':None,'resolution_status':'INSUFFICIENT_GUARD',
                    'guard_result':'parent_latest_profile_not_yet_observed'}
        return row

    def parent_relations(self,horse_id,*,as_of):
        hid=self._reader._require_horse_id(horse_id)
        if not self._available(hid,as_of):return []
        rows=self._reader.parent_relations(hid)
        return rows if self._legacy else [self._safe_relation(r,as_of) for r in rows]

    def horse_pedigree(self,horse_id,*,as_of):
        hid=self._reader._require_horse_id(horse_id)
        if self._legacy:return self._legacy.horse_pedigree(hid,as_of=as_of)
        if not self._available(hid,as_of):return None
        value=self._reader.horse_pedigree(hid)
        if value:
            for role in ('sire','dam','broodmare_sire'):
                if value[role].get('relation'):value[role]['relation']=self._safe_relation(value[role]['relation'],as_of)
            value['provenance'].update(research_only=True,research_reader_contract=CONTRACT_VERSION,
                                       selected_profile_available_from=self.available_from[hid],as_of=as_of)
        return value
