from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SRC=Path(__file__).resolve().parents[1]/'src';sys.path.insert(0,str(SRC))
import pyarrow as pa
import pyarrow.parquet as pq
from brdb_pedigree_reader import BloodReviewReaderError
from brdb_research_reader import ResearchPedigreeReader
from brdb_research_reader_v02 import ResearchGenerationReader,CONTRACT_VERSION,ID_SET_ENCODING,ids_sha256
from build_brdb_research_generation_v02 import scan_all_daily
import jrdb_ukc


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def make_fixture(root,legacy=False):
    ids=[f'{i:08d}' for i in range(1,106 if legacy else 4)];added=ids[1:]
    profiles=[]
    for i,hid in enumerate(ids):
        profiles.append({'horse_id':hid,'horse_name':'H'+hid,'birth_date':'20200101','sex_code':'1',
            'sire_name':'S','sire_birth_year':2000,'dam_name':'D','dam_birth_year':2005,
            'broodmare_sire_name':'B','broodmare_sire_birth_year':1990,
            'sire_line_code':'1206','broodmare_sire_line_code':'1206','breeding_place':'P',
            'profile_data_date':'20251228' if i==0 else '20260101','semantic_hash':str(i%10)*64,
            'source_family':'UKC' if i==0 else 'UKC_PACI','source_generation':'fixture'})
    relations=[]
    for hid in ids:
        for role in ('sire','dam','broodmare_sire'):
            resolved=not legacy and hid==ids[0] and role=='sire'
            relations.append({'child_horse_id':hid,'role':role,'parent_name':'P','parent_birth_year':2000,
                'parent_lineage_code':'1206','resolved_parent_horse_id':ids[1] if resolved else None,
                'resolution_status':'RESOLVED_EXACT' if resolved else 'NO_CANDIDATE',
                'resolution_method':'UKC_EXACT_NAME_BIRTH_YEAR' if resolved else None,
                'candidate_count':int(resolved),'guard_result':'fixture','resolver_version':'v0.1','source_generation':'fixture'})
    files={}
    def parquet(name,rows):
        pq.write_table(pa.Table.from_pylist(rows),root/name);files[name]=sha(root/name)
    parquet('pedigree_fact.parquet',profiles);parquet('parent_relation.parquet',relations)
    parquet('pedigree_name_alias.parquet',[{'observed_name':'A','canonical_name':'B'}])
    parquet('lineage_code_master.parquet',[{'lineage_code':'1206','major_name':'Major','minor_name':'Minor'}])
    (root/'audit.json').write_text('{}');files['audit.json']=sha(root/'audit.json')
    added_rows=[{'horse_id':h,'first_observed_archive_date':'20260104','selected_observation_date':'20260201',
                 'profile_data_date':'20260101','semantic_hash':profiles[i+1]['semantic_hash']} for i,h in enumerate(added)]
    history=[]
    for i,h in enumerate(added):
        for date,selected in [('20260104',0),('20260201',1)]:
            history.append({'horse_id':h,'archive_date':date,'profile_data_date':'20260101',
                            'semantic_hash':profiles[i+1]['semantic_hash'],'input_status':'VALID',
                            'selected':bool(selected) if legacy else selected})
    manifest={'artifact_type':'brdb_pedigree','generation_id':'fixture','schema_version':'v0.1',
        'builder_version':'research-paci-v0.1' if legacy else 'research-paci-v0.2','research_only':True,
        'source_min_data_date':'20251228','source_max_data_date':'20260201','alias_version':'v0.1',
        'validation_status':'PASS','row_counts':{'pedigree_fact':len(ids),'parent_relation':len(ids)*3},
        'output_sha256':files}
    if legacy:
        for name,rows in [('added_104.json',added_rows),('observation_history.json',history)]:
            (root/name).write_text(json.dumps(rows));files[name]=sha(root/name)
    else:
        (root/'added_horses.json').write_text(json.dumps(added_rows));files['added_horses.json']=sha(root/'added_horses.json')
        parquet('daily_observation_history.parquet',history)
        parquet('annual_availability.parquet',[{'horse_id':ids[0],'profile_data_date':'20251228',
                  'semantic_hash':profiles[0]['semantic_hash'],'archive_date':'20251228'}])
        manifest['row_counts']['daily_observation_history']=len(history)
        manifest['research_reader_contract']={'version':CONTRACT_VERSION,'id_set_encoding':ID_SET_ENCODING,
            'as_of_policy':'selected_latest_observation_date',
            'added_count':len(added),'added_ids_sha256':ids_sha256(added),'annual_count':1,'annual_ids_sha256':ids_sha256(ids[:1]),
            **{k:{'path':n,'sha256':files[n]} for k,n in [('added_audit','added_horses.json'),
               ('observation_history','daily_observation_history.parquet'),('annual_availability','annual_availability.parquet')]}}
    (root/'manifest.json').write_text(json.dumps(manifest));return ids


class ResearchV02Test(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.ids=make_fixture(self.root)

    def test_manifest_dynamic_count_and_latest_observation_gate(self):
        reader=ResearchGenerationReader(self.root)
        self.assertEqual(len(reader.added_ids),2)
        self.assertEqual(len(reader.profiles_for_horses(self.ids,as_of='20260104')),1)
        self.assertIsNone(reader.horse_pedigree(self.ids[1],as_of='20260131'))
        self.assertEqual(len(reader.profiles_for_horses(self.ids,as_of='20260201')),3)
        self.assertIsNotNone(reader.horse_pedigree(self.ids[1],as_of='20260201'))

    def test_2025_never_exposes_daily_profiles(self):
        r=ResearchGenerationReader(self.root)
        self.assertEqual(set(r.profiles_for_horses(self.ids,as_of='20251231')),{self.ids[0]})
        with self.assertRaises(ValueError):r.profiles_for_horses(self.ids,as_of='99999999')

    def test_future_parent_id_is_suppressed_until_observed(self):
        r=ResearchGenerationReader(self.root)
        self.assertIsNone(r.horse_pedigree(self.ids[0],as_of='20260104')['sire']['relation']['resolved_parent_horse_id'])
        self.assertEqual(r.horse_pedigree(self.ids[0],as_of='20260201')['sire']['relation']['resolved_parent_horse_id'],self.ids[1])

    def test_audit_tamper_fails_hash_validation(self):
        with (self.root/'added_horses.json').open('a') as f:f.write(' ')
        with self.assertRaises(BloodReviewReaderError):ResearchGenerationReader(self.root)

    def test_wrong_id_binding_fails(self):
        p=self.root/'manifest.json';m=json.loads(p.read_text());m['research_reader_contract']['added_ids_sha256']='0'*64;p.write_text(json.dumps(m))
        with self.assertRaisesRegex(BloodReviewReaderError,'ID-set SHA'):ResearchGenerationReader(self.root)

    def test_wrong_count_fails_without_104_fallback(self):
        p=self.root/'manifest.json';m=json.loads(p.read_text());m['research_reader_contract']['added_count']=104;p.write_text(json.dumps(m))
        with self.assertRaisesRegex(BloodReviewReaderError,'count mismatch'):ResearchGenerationReader(self.root)

    def test_missing_v02_contract_fails_closed(self):
        p=self.root/'manifest.json';m=json.loads(p.read_text());del m['research_reader_contract'];p.write_text(json.dumps(m))
        with self.assertRaisesRegex(BloodReviewReaderError,'contract missing'):ResearchGenerationReader(self.root)

    def test_selected_history_duplicate_is_rejected(self):
        path=self.root/'daily_observation_history.parquet';rows=pq.read_table(path).to_pylist();rows.append(rows[-1]);pq.write_table(pa.Table.from_pylist(rows),path)
        p=self.root/'manifest.json';m=json.loads(p.read_text());digest=sha(path)
        m['output_sha256'][path.name]=digest;m['research_reader_contract']['observation_history']['sha256']=digest
        m['row_counts']['daily_observation_history']=len(rows);p.write_text(json.dumps(m))
        with self.assertRaisesRegex(BloodReviewReaderError,'selected history ID'):ResearchGenerationReader(self.root)

    def test_legacy_104_generation_remains_compatible(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);ids=make_fixture(path,legacy=True);old=ResearchPedigreeReader(path);new=ResearchGenerationReader(path)
            self.assertEqual(len(new.added_ids),104)
            self.assertEqual(old.profiles_for_horses(ids,as_of='20260201'),new.profiles_for_horses(ids,as_of='20260201'))
            for date in ('20260104','20260201'):
                self.assertEqual(old.horse_pedigree(ids[1],as_of=date),new.horse_pedigree(ids[1],as_of=date))

    def test_id_set_identity_is_order_independent_but_content_sensitive(self):
        self.assertEqual(ids_sha256(['B','A']),ids_sha256(['A','B']))
        self.assertNotEqual(ids_sha256(['A']),ids_sha256(['B']))

    def test_daily_sentinel_is_retained_but_not_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'PACI260104.zip';records=[]
            for date in ('20260104','99999999'):
                body=bytearray(b' '*jrdb_ukc.RECORD_LENGTH)
                fields={'horse_id':'00000002','data_date':date,'horse_name':'H'}
                for field,offset,width in jrdb_ukc.FIELD_SPECS:
                    v=fields.get(field,'').encode('cp932');body[offset:offset+len(v)]=v
                records.append(bytes(body))
            with zipfile.ZipFile(path,'w') as z:z.writestr('UKC260104.txt',b'\r\n'.join(records)+b'\r\n')
            item={'name':path.name,'size_bytes':path.stat().st_size,'sha256':sha(path),
                  'ukc_members':['UKC260104.txt'],'ukc_record_count':2}
            history,valid,q,sources=scan_all_daily(root,[item],set(),set(),{'00000002'})
            self.assertEqual(len(history),2);self.assertEqual(len(valid['00000002']),1)
            self.assertEqual(q[0]['input_status'],'SENTINEL_DATE')

if __name__=='__main__':unittest.main()
