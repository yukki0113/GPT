import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Store(Path(self.tmp.name)/'test.sqlite')
        self.s.initialize()
        self.s.add_card('a', 1001, '架空　竜')
        self.s.add_card('b', 1002, '架空 竜')
    def tearDown(self):
        self.s.close(); self.tmp.cleanup()
    def test_init_version_integrity(self):
        self.s.initialize(); self.assertEqual(self.s.version(),1); self.assertTrue(self.s.integrity_check()['ok'])
        self.assertEqual(self.s.db.execute('PRAGMA foreign_keys').fetchone()[0],1)
    def test_identity_and_update(self):
        with self.assertRaises(sqlite3.IntegrityError): self.s.add_card('a',1003,'別')
        with self.assertRaises(sqlite3.IntegrityError): self.s.add_card('c',1001,'別')
        self.assertEqual(self.s.update_card('a',name='架空鳥')['name'],'架空鳥')
        with self.assertRaises(ValueError): self.s.update_card('a',konami_id=2)
    def test_names_and_injection(self):
        self.assertEqual(self.s.resolve_name('架空竜')['status'],'AMBIGUOUS')
        self.assertEqual(len(self.s.search_cards(query='架空　竜')),2)
        self.assertEqual(self.s.resolve_name('不存在')['status'],'UNRESOLVED')
        self.assertEqual(self.s.search_cards(kind="x' OR 1=1 --"),[])
    def test_unknown_zero_and_history(self):
        self.assertEqual(self.s.get_inventory('a')['known_state'],'UNKNOWN')
        diff=self.s.set_inventory('one',[{'card_id':'a','owned_count':0},{'card_id':'b','owned_count':3}])
        self.assertEqual(diff[0]['before_state'],'UNKNOWN')
        self.assertEqual(self.s.get_inventory('a')['known_state'],'KNOWN_ZERO')
        self.assertEqual(self.s.history('b')[0]['after_count'],3)
    def test_replay_conflict_and_rollback(self):
        updates=[{'card_id':'a','owned_count':2}]
        first=self.s.set_inventory('one',updates)
        self.assertEqual(self.s.set_inventory('one',updates),first)
        self.assertEqual(len(self.s.history('a')),1)
        with self.assertRaises(ValueError): self.s.set_inventory('one',[{'card_id':'a','owned_count':3}])
        with self.assertRaises(ValueError): self.s.set_inventory('bad',[{'card_id':'a','owned_count':1},{'card_id':'z','owned_count':1}])
        self.assertEqual(self.s.get_inventory('a')['owned_count'],2)
        with self.assertRaises(ValueError): self.s.batch_diff('bad')
    def test_undo_and_later_change(self):
        self.s.set_inventory('one',[{'card_id':'a','owned_count':2}])
        self.s.undo_batch('one','undo')
        self.assertEqual(self.s.get_inventory('a')['known_state'],'UNKNOWN')
        self.assertEqual(len(self.s.history('a')),2)
        self.s.undo_batch('one','undo')
        self.s.set_inventory('two',[{'card_id':'b','owned_count':2}])
        self.s.set_inventory('three',[{'card_id':'b','owned_count':3}])
        with self.assertRaises(ValueError): self.s.undo_batch('two','undo2')
        self.assertEqual(self.s.get_inventory('b')['owned_count'],3)
    def test_banlist_absence(self):
        self.s.db.execute("INSERT INTO banlist_snapshots(snapshot_id,format_id,effective_on) VALUES ('s','standard','2026-01-01')")
        self.assertIsNone(self.s.db.execute("SELECT max_copies FROM banlist_entries WHERE snapshot_id='s' AND card_id='a'").fetchone())
    def test_constraints(self):
        with self.assertRaises(sqlite3.IntegrityError): self.s.db.execute("INSERT INTO inventory(card_id,owned_count,known_state) VALUES ('a',0,'UNKNOWN')")
        with self.assertRaises(sqlite3.IntegrityError): self.s.db.execute("INSERT INTO md_catalog(card_id,rarity,rarity_source) VALUES ('a','UR','OCG:source')")
        with self.assertRaises(ValueError): self.s.set_inventory('x',[{'card_id':'a','owned_count':True}])

if __name__=='__main__': unittest.main()
