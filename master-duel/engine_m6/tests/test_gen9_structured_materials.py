"""Fictional regression only. No private card or inventory contents."""
import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from engine_m6.structured_materials import screen_structured_extra_materials
from card_master_import.stage2_gen9_migration import extract_material_requirement

class Stage2SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'fictional.sqlite'
        c=sqlite3.connect(self.path)
        c.executescript('''
        CREATE TABLE card_extra_material_requirements (card_id TEXT PRIMARY KEY,summon_method TEXT,
          material_header TEXT,material_header_sha256 TEXT,pre_effect_restrictions TEXT,
          source_text_sha256 TEXT,grammar TEXT,min_materials INTEGER,level_required INTEGER,
          qualifier TEXT,material_labels_json TEXT,material_verification TEXT,
          simultaneous_materials_verified INTEGER,summon_route_verified INTEGER,source TEXT);
        CREATE TABLE card_texts(card_id TEXT,language TEXT,body TEXT);
        CREATE TABLE card_attributes(card_id TEXT,kind TEXT,level INTEGER,link INTEGER);
        CREATE TABLE card_monster_types(card_id TEXT,monster_type TEXT);
        ''')
        cards=[('konami:501','XYZ','レベル4モンスター×2\nこのカードはX召喚でのみ特殊召喚できる。\n①：効果',4),
               ('konami:502','FUSION','「架空A」+「架空B」\n①：効果',7),
               ('konami:503','SYNCHRO','チューナー+チューナー以外のモンスター1体以上\n①：効果',6)]
        for cid,method,body,level in cards:
            header,pre,p=extract_material_requirement(method,body)
            c.execute('INSERT INTO card_texts VALUES (?,?,?)',(cid,'ja',body))
            c.execute('INSERT INTO card_attributes VALUES (?,?,?,?)',(cid,'MONSTER',level,None))
            c.execute('INSERT INTO card_monster_types VALUES (?,?)',(cid,method))
            c.execute('INSERT INTO card_extra_material_requirements VALUES ('+','.join('?'*15)+')',
                      (cid,method,header,hashlib.sha256(header.encode()).hexdigest(),pre,
                       hashlib.sha256(body.encode()).hexdigest(),p['grammar'],p['min_materials'],
                       p['level_required'],p['qualifier'],json.dumps(p['material_labels'],ensure_ascii=False),
                       'SOURCE_TEXT_ONLY',0,0,'FICTION'))
        for cid,level,flags in [('konami:11',4,['EFFECT']),('konami:12',4,['EFFECT']),
                                ('konami:13',2,['TUNER','EFFECT']),('konami:14',4,['EFFECT'])]:
            c.execute('INSERT INTO card_attributes VALUES (?,?,?,?)',(cid,'MONSTER',level,None))
            for flag in flags:c.execute('INSERT INTO card_monster_types VALUES (?,?)',(cid,flag))
        c.commit();c.close()
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
    def tearDown(self):self.tmp.cleanup()
    def route(self,target,method,materials):
        return dict(extra_card_id=target,summon_method=method,material_card_ids=materials,
                    evidence_ids=['SOURCE:fictional'],simultaneous_state_evidence_ids=['SCENE:fictional'],
                    summon_method_evidence_ids=['METHOD:fictional'],restriction_review='REVIEWED',
                    material_labels=[],link_material_ratings=[])
    def screen(self,ids,routes=()):
        return screen_structured_extra_materials(self.path,expected_sqlite_sha256=self.sha,
                           extra_card_ids=ids,proposed_routes=routes)['results']
    def test_no_board_assertion_no_paper_pass(self):
        self.assertEqual('REQUIRES_REVIEW',self.screen(['konami:501'])[0]['screen'])
    def test_exact_xyz_paper_only(self):
        r=self.route('konami:501','XYZ',['konami:11','konami:12'])
        x=self.screen(['konami:501'],[r])[0]
        self.assertEqual('POSSIBLE_ON_PAPER',x['screen'])
        self.assertFalse(x['gameplay_compatibility_verified'])
        r['restriction_review']='NOT_REVIEWED'
        self.assertEqual('REQUIRES_REVIEW',self.screen(['konami:501'],[r])[0]['screen'])
    def test_wrong_level_fail(self):
        r=self.route('konami:501','XYZ',['konami:11','konami:13'])
        self.assertEqual('REQUIRES_REVIEW',self.screen(['konami:501'],[r])[0]['screen'])
    def test_synchro_tuner_level_sum(self):
        r=self.route('konami:503','SYNCHRO',['konami:13','konami:14'])
        self.assertEqual('POSSIBLE_ON_PAPER',self.screen(['konami:503'],[r])[0]['screen'])
        r['material_card_ids']=['konami:14','konami:11']
        self.assertEqual('REQUIRES_REVIEW',self.screen(['konami:503'],[r])[0]['screen'])
    def test_fusion_literal_evidence(self):
        r=self.route('konami:502','FUSION',['konami:11','konami:12'])
        r['material_labels']=['「架空A」','「架空B」']
        self.assertEqual('POSSIBLE_ON_PAPER',self.screen(['konami:502'],[r])[0]['screen'])
        r['material_labels']=['「架空A」','「架空C」']
        self.assertEqual('REQUIRES_REVIEW',self.screen(['konami:502'],[r])[0]['screen'])
    def test_weak_evidence_rejected(self):
        r=self.route('konami:501','XYZ',['konami:11','konami:12'])
        r['simultaneous_state_evidence_ids']=[]
        with self.assertRaisesRegex(ValueError,'EVIDENCE_REQUIRED'):
            self.screen(['konami:501'],[r])

if __name__=='__main__':unittest.main()