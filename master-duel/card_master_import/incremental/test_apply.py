"""Synthetic U3 tests. No actual card records or private fixtures."""
import json, sqlite3, tempfile, unittest
from contextlib import closing
from pathlib import Path
from card_master_import.incremental.apply import apply, digest, plan, write_plan, table_hashes, material

# Minimal schema-v4 fixture mirroring write columns; production constraints are
# additionally checked by the private real-data run, not simulated here.
DDL='''
CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY);
INSERT INTO schema_migrations VALUES(1),(2),(3),(4);
CREATE TABLE cards(card_id TEXT PRIMARY KEY,konami_id INTEGER UNIQUE,name TEXT,source TEXT,acquired_at TEXT,verification TEXT);
CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY REFERENCES cards,kind TEXT,attribute TEXT,race TEXT,level INTEGER,rank INTEGER,link INTEGER,atk INTEGER,def INTEGER,source TEXT,acquired_at TEXT,verification TEXT);
CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY REFERENCES cards,rarity TEXT,rarity_source TEXT,craftable TEXT,source TEXT,acquired_at TEXT,verification TEXT);
CREATE TABLE card_texts(card_id TEXT REFERENCES cards,language TEXT,version TEXT,body TEXT,source TEXT,acquired_at TEXT,verification TEXT,PRIMARY KEY(card_id,language,version));
CREATE TABLE card_monster_types(card_id TEXT REFERENCES cards,monster_type TEXT,source TEXT,verification TEXT,PRIMARY KEY(card_id,monster_type));
CREATE TABLE card_spell_trap_properties(card_id TEXT PRIMARY KEY REFERENCES cards,property TEXT,source TEXT,verification TEXT);
CREATE TABLE card_link_markers(card_id TEXT REFERENCES cards,arrow TEXT,source TEXT,verification TEXT,PRIMARY KEY(card_id,arrow));
CREATE TABLE card_pendulum_details(card_id TEXT PRIMARY KEY REFERENCES cards,scale INTEGER,ja_pendulum_effect TEXT,source TEXT,verification TEXT);
CREATE TABLE card_extra_material_requirements(card_id TEXT PRIMARY KEY REFERENCES cards,summon_method TEXT,material_header TEXT,material_header_sha256 TEXT,pre_effect_restrictions TEXT,source_text_sha256 TEXT,grammar TEXT,min_materials INTEGER,level_required INTEGER,qualifier TEXT,material_labels_json TEXT,material_verification TEXT,simultaneous_materials_verified INTEGER,summon_route_verified INTEGER,source TEXT);
CREATE TABLE inventory(card_id TEXT PRIMARY KEY REFERENCES cards,owned_count INTEGER);
'''
STAMP='2026-01-01T00:00:00+09:00'
def card(n=100):
    s=dict(url='https://example.invalid/ocg',observed_at=STAMP,konami_id=n,verification='OCG_SHARED')
    md=[dict(url='https://example.invalid/md',observed_at=STAMP)]
    return dict(card_id=f'konami:{n}',konami_id=n,name_ja='合成テスト'+str(n),kind='MONSTER',attribute='LIGHT',race='Warrior',level=4,rank=None,link=None,atk=100,**{'def':200},rarity='R',craftable='UNKNOWN',ja_text='合成効果',monster_types=['EFFECT'],spell_trap_property=None,link_markers=[],pendulum_scale=None,ja_pendulum_effect=None,effective_on='2026-01-01',channels=['PACK_REPORTED'],verification='UNVERIFIED_SOURCE',extra_material_requirement=None,sources=dict(identity=s,attributes=s,ja_text=s,md_implementation=md,md_rarity=md,craftable=None,ja_pendulum_effect=None))
class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name);self.base=self.p/'base.sqlite'
        d=sqlite3.connect(self.base);d.executescript(DDL);d.close()
    def tearDown(self): self.tmp.cleanup()
    def batch(self,*cards): return dict(schema='md-card-incremental-update-v1',batch_id='synthetic',observed_at=STAMP,base_generation=1,base_sqlite_sha256=digest(self.base.read_bytes()),cards=list(cards),unresolved=[])
    def run_batch(self,b,**kwargs):
        inp=self.p/'batch.json';inp.write_text(json.dumps(b));return apply(self.base,inp,self.p/'out.sqlite',self.p/'diff.json',expected_batch_sha=digest(inp.read_bytes()),expected_generation=1,expected_base_sha=digest(self.base.read_bytes()),**kwargs)
    def seed(self,c):
        d=sqlite3.connect(self.base);d.row_factory=sqlite3.Row;d.execute('PRAGMA foreign_keys=ON');write_plan(d,plan(d,self.batch(c)));d.commit();d.close()
    def test_insert_replay(self):
        r=self.run_batch(self.batch(card(),card(101)));self.assertEqual(r['actions'],{'INSERT':2});self.assertEqual(r['replay_noop'],2)
    def test_rollback(self):
        with self.assertRaisesRegex(RuntimeError,'INJECTED'): self.run_batch(self.batch(card(),card(101)),fail_after=1)
        with closing(sqlite3.connect(self.base)) as a,closing(sqlite3.connect(self.p/'out.sqlite')) as b:self.assertEqual(table_hashes(a),table_hashes(b))
    def test_stale(self):
        b=self.batch(card());b['base_sqlite_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'BASE_SHA'):self.run_batch(b)
        self.assertFalse((self.p/'out.sqlite').exists())
    def test_duplicate(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):self.run_batch(self.batch(card(),card()))
    def test_invalid_anchor(self):
        c=card();c['monster_types']=['SYNCHRO','EFFECT'];c['ja_text']='合成素材\n合成効果';c['extra_material_requirement']=material(c);c['extra_material_requirement']['source_text_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'MATERIAL_ANCHOR'):self.run_batch(self.batch(c))
    def test_update_text_and_anchor_history(self):
        c=card();c['monster_types']=['SYNCHRO','EFFECT'];c['ja_text']='合成素材\n旧効果';c['extra_material_requirement']=material(c);self.seed(c);c['ja_text']='合成素材\n新効果';c['extra_material_requirement']=material(c);r=self.run_batch(self.batch(c));self.assertEqual(r['actions']['UPDATE_TEXT'],1)
        diff=json.loads((self.p/'diff.json').read_text());self.assertIn('旧効果',diff['changes'][0]['before']['card_texts'][0]['body']);self.assertEqual(r['replay_noop'],1)
    def test_unknown_retains_known(self):
        c=card();self.seed(c);c['rarity']=None;c['atk']=None;c['def']=None;self.assertEqual(self.run_batch(self.batch(c))['actions'],{'NO_CHANGE':1})
    def test_rarity_update_preserve_inventory(self):
        c=card();self.seed(c)
        with closing(sqlite3.connect(self.base)) as d:d.execute('INSERT INTO inventory VALUES(?,?)',(c['card_id'],2));d.commit()
        c['rarity']='UR';r=self.run_batch(self.batch(c));self.assertEqual(r['actions'],{'UPDATE_RARITY':1});self.assertTrue(r['non_target_hashes_equal'])
    def test_game_verified_conflict(self):
        c=card();self.seed(c)
        with closing(sqlite3.connect(self.base)) as d:d.execute("UPDATE card_texts SET verification='GAME_VERIFIED'");d.commit()
        c['ja_text']='別効果'
        with self.assertRaisesRegex(ValueError,'GAME_VERIFIED_CONFLICT'):self.run_batch(self.batch(c))
    def test_pending_overlap(self):
        b=self.batch(card());b['unresolved']=[{'card_id':'konami:100'}]
        with self.assertRaisesRegex(ValueError,'PENDING_OVERLAP'):self.run_batch(b)
    def test_wrong_cid(self):
        c=card();c['card_id']='konami:999'
        with self.assertRaisesRegex(ValueError,'CID'):self.run_batch(self.batch(c))
    def test_no_target(self): self.assertEqual(self.run_batch(self.batch())['actions'],{})
if __name__=='__main__': unittest.main()
