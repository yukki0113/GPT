import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Store.create(Path(self.tmp.name)/'test.sqlite')
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
    def test_details_search_and_validation(self):
        self.s.set_attributes('a', kind='MONSTER', verification='GAME_VERIFIED')
        md = self.s.set_md_catalog('a', rarity='SR', rarity_source='MD:fixture')
        self.assertEqual(md['craftable'], 'UNKNOWN')
        self.assertEqual(self.s.search_cards(kind='MONSTER', rarity='SR', craftable='UNKNOWN')[0]['card_id'], 'a')
        self.s.set_md_catalog('a', craftable='NO')
        self.assertEqual(self.s.get_md_catalog('a')['craftable'], 'NO')
        self.assertEqual(self.s.get_attributes('a')['verification'], 'GAME_VERIFIED')
        with self.assertRaises(ValueError): self.s.set_attributes('a', verification='GUESS')
        with self.assertRaises(sqlite3.IntegrityError): self.s.set_md_catalog('a', rarity_source='OCG:fixture')
        with self.assertRaises(sqlite3.IntegrityError): self.s.set_md_catalog('b', rarity='UR')
        self.assertEqual(self.s.get_md_catalog('a')['rarity_source'], 'MD:fixture')

    def test_existing_only_and_invalid_schema(self):
        path = Path(self.tmp.name)/'missing.sqlite'
        with self.assertRaises(sqlite3.OperationalError): Store(path)
        self.assertFalse(path.exists())
        sqlite3.connect(path).close()
        with self.assertRaises(ValueError): Store(path)
        with StoreContext(Store.create(path)) as created: self.assertEqual(created.version(), 1)
        with StoreContext(Store(path)) as opened: self.assertTrue(opened.integrity_check()['ok'])
        broken = Path(self.tmp.name)/'broken.sqlite'
        db=sqlite3.connect(broken); db.execute('CREATE TABLE schema_migrations(version INTEGER)'); db.execute('INSERT INTO schema_migrations VALUES (1)'); db.commit(); db.close()
        with self.assertRaises(ValueError): Store(broken)
        with self.assertRaises(ValueError): Store.create(broken)
        newer = Path(self.tmp.name)/'newer.sqlite'
        with StoreContext(Store.create(newer)) as db: db.db.execute('INSERT INTO schema_migrations(version) VALUES (2)')
        with self.assertRaises(ValueError): Store(newer)
        with self.assertRaises(ValueError): Store.create(newer)

    def test_replay_after_undo_and_order(self):
        updates=[{'card_id':'a','owned_count':1},{'card_id':'b','owned_count':2}]
        original=self.s.set_inventory('one',updates)
        self.assertEqual(self.s.set_inventory('one', list(reversed(updates))), original)
        self.s.undo_batch('one','undo')
        self.assertEqual(self.s.set_inventory('one',updates), original)
        self.assertEqual(self.s.get_inventory('a')['known_state'], 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'batch ID conflict'): self.s.set_inventory('undo',updates)
        self.s.set_inventory('two',[{'card_id':'a','owned_count':3}])
        with self.assertRaisesRegex(ValueError, 'batch ID conflict'): self.s.undo_batch('two','one')
        self.assertEqual(self.s.get_inventory('a')['owned_count'],3)

    def test_undo_partial_conflict_is_atomic(self):
        self.s.set_inventory('one',[{'card_id':'a','owned_count':1},{'card_id':'b','owned_count':2}])
        self.s.set_inventory('later',[{'card_id':'b','owned_count':3}])
        with self.assertRaises(ValueError): self.s.undo_batch('one','undo')
        self.assertEqual(self.s.get_inventory('a')['owned_count'],1)
        self.assertEqual(self.s.get_inventory('b')['owned_count'],3)
        with self.assertRaises(ValueError): self.s.batch_diff('undo')
        self.assertEqual(len(self.s.history('a')),1)

    def test_cli_details_and_missing_db(self):
        root = Path(__file__).resolve().parents[2]
        def call(operation, **args):
            return subprocess.run([sys.executable, '-m', 'sqlite_store'], cwd=root,
                input=json.dumps({'db':str(Path(self.tmp.name)/'test.sqlite'), 'operation':operation, 'args':args}),
                text=True, capture_output=True, check=True)
        call('set_attributes', card_id='a', kind='MONSTER')
        call('set_md_catalog', card_id='a', rarity='SR', rarity_source='MD:fixture')
        result=json.loads(call('search_cards', kind='MONSTER', rarity='SR', craftable='UNKNOWN').stdout)
        self.assertEqual(result['result'][0]['card_id'], 'a')
        missing = Path(self.tmp.name)/'absent.sqlite'
        result=subprocess.run([sys.executable,'-m','sqlite_store'], cwd=root,
            input=json.dumps({'db':str(missing),'operation':'version'}), text=True, capture_output=True)
        self.assertEqual(result.returncode,1)
        self.assertFalse(missing.exists())

    def test_constraints(self):
        with self.assertRaises(sqlite3.IntegrityError): self.s.db.execute("INSERT INTO inventory(card_id,owned_count,known_state) VALUES ('a',0,'UNKNOWN')")
        with self.assertRaises(sqlite3.IntegrityError): self.s.db.execute("INSERT INTO md_catalog(card_id,rarity,rarity_source) VALUES ('a','UR','OCG:source')")
        with self.assertRaises(ValueError): self.s.set_inventory('x',[{'card_id':'a','owned_count':True}])

class StoreContext:
    def __init__(self, store): self.store=store
    def __enter__(self): return self.store
    def __exit__(self, *args): self.store.close()

if __name__=='__main__': unittest.main()
