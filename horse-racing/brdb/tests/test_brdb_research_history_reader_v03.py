import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from brdb_research_history_reader_v03 import UKCRecord, choose_observation


def row(date='20260101', observed='20260104', name='S', line=1, selected=0):
    p=UKCRecord(horse_id='12345678',horse_name='H',sex_code='1',coat_color_code='',horse_symbol_code='',
                sire_name=name,dam_name='D',broodmare_sire_name='B',birth_date='20200101',sire_birth_year=2000,
                dam_birth_year=2000,broodmare_sire_birth_year=1990,owner_name='',owner_group_code='',breeder_name='',
                breeding_place='',deregistered_flag='',data_date=date,sire_line_code='1206',broodmare_sire_line_code='1206')
    return {'horse_id':p.horse_id,'profile_data_date':date,'archive_date':observed,'archive':'PACI'+observed[2:]+'.zip',
            'member':'UKC.txt','line_number':line,'archive_sha256':'a'*64,'member_sha256':'b'*64,
            'record_sha256':'c'*64,'semantic_hash':p.semantic_hash(),'profile_json':json.dumps(asdict(p)),
            'input_status':'VALID','selected':selected}

class SelectionTest(unittest.TestCase):
    def test_pre_observation_is_hidden(self):
        self.assertEqual(choose_observation([row()], '20260103')[0], 'NOT_YET_OBSERVED')
    def test_order_and_duplicate(self):
        a=row(line=1); b=row(line=2,selected=1)
        for rows in ([a,b],[b,a],[a,b,b]):
            self.assertEqual(choose_observation(rows,'20260104')[1]['line_number'],2)
    def test_same_date_semantic_conflict(self):
        self.assertEqual(choose_observation([row(),row(name='T')],'20260104')[0],'HISTORY_CONFLICT')
    def test_future_conflict_not_visible(self):
        self.assertEqual(choose_observation([row(),row(observed='20260201',name='T')],'20260104')[0],'AVAILABLE_HISTORICAL_DAILY')
    def test_bad_json(self):
        a=row();a['profile_json']='bad';self.assertEqual(choose_observation([a],'20260104')[0],'INVALID_SOURCE')
    def test_bad_semantic_hash(self):
        a=row();a['semantic_hash']='f'*64;self.assertEqual(choose_observation([a],'20260104')[0],'INVALID_SOURCE')
    def test_profile_date_after_observation(self):
        a=row(date='20260105');self.assertEqual(choose_observation([a],'20260105')[0],'INVALID_SOURCE')
    def test_invalid_as_of(self):
        with self.assertRaises(ValueError): choose_observation([], '20260230')
    def test_versioned_parent_name(self):
        a=row();b=row(date='20260105',observed='20260105',name='T',selected=1)
        self.assertEqual(choose_observation([a,b],'20260104')[2]['sire_name'],'S')
        self.assertEqual(choose_observation([a,b],'20260105')[2]['sire_name'],'T')
    def test_quarantine_not_selected(self):
        a=row();a['input_status']='SENTINEL_DATE';self.assertEqual(choose_observation([a],'20260104')[0],'NOT_YET_OBSERVED')

if __name__=='__main__': unittest.main()
