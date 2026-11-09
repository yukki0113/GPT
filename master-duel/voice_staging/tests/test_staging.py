import json, sys, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from zip_store.archive import pack, digest
from zip_store import inspect, prepare
from voice_staging import parse_json, parse_csv, save_batch, load_batch, preview, prepare_update

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); p=self.root/'db'
        s=Store.create(p); s.add_card('a',1001,'架空　竜'); s.add_card('b',1002,'架空鳥'); s.close()
        self.zip,_=pack(p)
        self.target={'head_name':'P2B_TEST_CURRENT_HEAD.json','scope':'SYNTHETIC_TEST','snapshot_id':'p','zip_sha256':digest(self.zip)}
        self.batch={'batch_id':'voice-1','scope':'SYNTHETIC_TEST','entries':[{'raw_name':'架空竜','owned_count':3},{'raw_name':'架空鳥','owned_count':0}]}
    def tearDown(self): self.tmp.cleanup()
    def test_json_csv_and_preview(self):
        self.assertEqual(parse_json(json.dumps(self.batch)),self.batch)
        self.assertEqual(parse_csv('raw_name,owned_count\n架空竜,3\n架空鳥,0\n',batch_id='voice-1',scope='SYNTHETIC_TEST'),self.batch)
        p=preview(self.batch,self.zip,self.target); self.assertTrue(p['can_apply'])
        self.assertEqual([(r['card_id'],r['current_state'],r['requested_count']) for r in p['rows']],[('a','UNKNOWN',3),('b','UNKNOWN',0)])
        result=prepare_update(self.batch,self.zip,self.target,'next',p['preview_sha256'])
        self.assertEqual(inspect(result['zip'],'get_inventory',card_id='b')['result']['known_state'],'KNOWN_ZERO')
        self.assertEqual(len(inspect(result['zip'],'history',card_id='a')['result']),1)
        undo=prepare(result['zip'],'next','undo',{'operation_id':'undo-1','operation_type':'UNDO_INVENTORY','batch_id':'voice-1'})
        self.assertEqual(inspect(undo['zip'],'get_inventory',card_id='a')['result']['known_state'],'UNKNOWN')
    def test_staging_replay_collision_correction(self):
        save_batch(self.root,self.batch); save_batch(self.root,self.batch)
        self.assertEqual(load_batch(self.root,'voice-1'),self.batch)
        changed={**self.batch,'entries':[{'raw_name':'別','owned_count':1}]}
        with self.assertRaisesRegex(ValueError,'conflict'): save_batch(self.root,changed)
        corrected={**changed,'batch_id':'voice-2','supersedes':'voice-1'}
        save_batch(self.root,corrected); self.assertEqual(load_batch(self.root,'voice-1'),self.batch)
        self.assertEqual(load_batch(self.root,'voice-2'),corrected)
    def test_unresolved_reresolve(self):
        batch={**self.batch,'entries':[{'raw_name':'架空花','owned_count':1}]}
        save_batch(self.root,batch); p=preview(load_batch(self.root,'voice-1'),self.zip,self.target)
        self.assertEqual(p['rows'][0]['status'],'UNRESOLVED')
        with self.assertRaises(ValueError): prepare_update(batch,self.zip,self.target,'next',p['preview_sha256'])
        path=self.root/'newdb'; s=Store.create(path); s.add_card('c',1003,'架空花'); s.close(); data,_=pack(path)
        target={**self.target,'snapshot_id':'new','zip_sha256':digest(data)}
        self.assertTrue(preview(load_batch(self.root,'voice-1'),data,target)['can_apply'])
    def test_ambiguous_and_duplicates(self):
        p=self.root/'db2'; s=Store.create(p); s.add_card('a',1,'架空竜'); s.add_card('b',2,'架空竜'); s.close(); data,_=pack(p)
        target={**self.target,'zip_sha256':digest(data)}
        result=preview(self.batch,data,target); self.assertEqual(result['rows'][0]['status'],'AMBIGUOUS'); self.assertFalse(result['can_apply'])
        with self.assertRaises(ValueError): prepare_update(self.batch,data,target,'next',result['preview_sha256'])
        dup={**self.batch,'entries':[{'raw_name':'架空竜','owned_count':1},{'raw_name':'架空　竜','owned_count':2}]}
        self.assertEqual(preview(dup,self.zip,self.target)['rows'][0]['reason'],'DUPLICATE_CARD_ID')
    def test_invalid_counts(self):
        for value in (-1,1.2,True,None,'3'):
            bad={**self.batch,'entries':[{'raw_name':'架空竜','owned_count':value}]}
            with self.subTest(value=value), self.assertRaises(ValueError): parse_json(json.dumps(bad))
        for val in ('-1','1.2','３'):
            with self.assertRaises(ValueError): parse_csv('raw_name,owned_count\n架空竜,'+val,batch_id='x',scope='SYNTHETIC_TEST')
    def test_scope_head_hash_preview_mismatch(self):
        for target in [{**self.target,'head_name':'MD_CURRENT_HEAD.json'},{**self.target,'scope':'PRODUCTION'},{**self.target,'zip_sha256':'0'*64}]:
            with self.assertRaises(ValueError): preview(self.batch,self.zip,target)
        p=preview(self.batch,self.zip,self.target)
        with self.assertRaisesRegex(ValueError,'preview mismatch'): prepare_update(self.batch,self.zip,self.target,'next','bad')
        changed={**self.batch,'entries':[{'raw_name':'架空竜','owned_count':2}]}
        with self.assertRaisesRegex(ValueError,'preview mismatch'): prepare_update(changed,self.zip,self.target,'next',p['preview_sha256'])
    def test_mid_update_failure_keeps_original(self):
        original=Store._apply
        def fail_after_apply(store, batch_id, updates):
            original(store,batch_id,updates)
            raise RuntimeError('simulated failure')
        p=preview(self.batch,self.zip,self.target)
        with patch.object(Store,'_apply',fail_after_apply):
            with self.assertRaises(RuntimeError): prepare_update(self.batch,self.zip,self.target,'next',p['preview_sha256'])
        self.assertEqual(inspect(self.zip,'get_inventory',card_id='a')['result']['known_state'],'UNKNOWN')
        self.assertEqual(inspect(self.zip,'history',card_id='a')['result'],[])

    def test_resend_and_operation_conflict(self):
        p=preview(self.batch,self.zip,self.target); first=prepare_update(self.batch,self.zip,self.target,'next',p['preview_sha256'])
        target={**self.target,'snapshot_id':'next','zip_sha256':digest(first['zip'])}
        next_preview=preview(self.batch,first['zip'],target)
        again=prepare_update(self.batch,first['zip'],target,'next2',next_preview['preview_sha256'])
        self.assertEqual(first['diff'],again['diff'])
        modified={**self.batch,'entries':[{'raw_name':'架空竜','owned_count':1}]}
        p2=preview(modified,first['zip'],target)
        with self.assertRaises(ValueError): prepare_update(modified,first['zip'],target,'next2',p2['preview_sha256'])
        self.assertEqual(inspect(first['zip'],'get_inventory',card_id='a')['result']['owned_count'],3)

if __name__=='__main__': unittest.main()
