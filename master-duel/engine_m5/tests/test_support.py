"""M5-B property and dynamic name-group discovery on synthetic text only."""
from hashlib import sha256
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from effect_semantics_m4 import build_private_index
from engine_m5.support import (build_private_support_index,extract_property_support,
                                search_property_support,search_name_groups)

ROWS=(
 ('konami:1001','架空戦団・甲','MONSTER','LIGHT','Warrior',
  'デッキから光属性・戦士族モンスター１体を手札に加える。'),
 ('konami:1002','架空戦団・乙','MONSTER','LIGHT','Warrior',
  '墓地から「架空戦団」モンスター１体を手札に加える。'),
 ('konami:1003','架空戦団・丙','MONSTER','EARTH','Warrior',
  'デッキから「架空戦団」カード１枚を手札に加える。'),
 ('konami:1004','架空支援者','MONSTER','WIND','Machine',
  'デッキから風属性・機械族モンスター１体を特殊召喚する。'),
 ('konami:1005','架空不成立','MONSTER','DARK','Fiend',
  '相手が闇属性・悪魔族モンスターを特殊召喚した場合、自分は１枚ドローする。'),
 ('konami:1006','架空メタ','TRAP',None,None,
  '●デッキから光属性・戦士族モンスター１体を手札に加える効果'),
 ('konami:1007','架空追加','SPELL',None,None,
  '自分は手札から「架空戦団」モンスター１体を特殊召喚する。'),
)


def create_source(path):
    con=sqlite3.connect(path)
    con.executescript('''CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY);
       INSERT INTO schema_migrations VALUES (1);
       CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
       CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,
             attribute TEXT,race TEXT,level INTEGER,rank INTEGER,link INTEGER);
       CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT);
       CREATE TABLE card_texts(card_id TEXT,language TEXT,version TEXT,body TEXT,
             source TEXT,acquired_at TEXT,PRIMARY KEY(card_id,language,version));''')
    for cid,name,kind,attr,race,body in ROWS:
        con.execute('INSERT INTO cards VALUES (?,?)',(cid,name))
        con.execute('INSERT INTO card_attributes VALUES (?,?,?,?,?,?,?)',
                    (cid,kind,attr,race,3 if kind=='MONSTER' else None,None,None))
        con.execute('INSERT INTO md_catalog VALUES (?,?)',(cid,'N'))
        con.execute('INSERT INTO card_texts VALUES (?,?,?,?,?,?)',
                    (cid,'ja','v1',body,'SYNTHETIC','2026-11-10'))
    con.commit();con.close()

class SupportTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        p=Path(self.d.name)
        self.source=p/'source.sqlite';self.m4=p/'m4.sqlite';self.dest=p/'support.sqlite'
        create_source(self.source)
        self.sha=sha256(self.source.read_bytes()).hexdigest()
        build_private_index(self.source,self.m4,expected_source_sha256=self.sha)
        self.m4sha=sha256(self.m4.read_bytes()).hexdigest()

    def tearDown(self):self.d.cleanup()

    def build(self,**kwargs):
        return build_private_support_index(self.source,self.m4,self.dest,
            expected_source_sha256=self.sha,expected_m4_sha256=self.m4sha,**kwargs)

    def test_property_extract_pairs_with_role_guard(self):
        e='デッキから光属性・戦士族モンスター１体を手札に加える。'
        self.assertEqual(extract_property_support(e,action='SEARCH_FROM_DECK',role='ACTION'),
                         [('ATTRIBUTE','LIGHT'),('RACE','Warrior')])
        self.assertEqual(extract_property_support(e,action='SEARCH_FROM_DECK',role='CONDITION'),[])
        self.assertEqual(extract_property_support(e,action='SEARCH_FROM_DECK',role='REFERENCED'),[])

    def test_support_index_comprehensive_synthetic(self):
        data=self.build()
        self.assertEqual(data['metrics']['cards'],7)
        self.assertGreaterEqual(data['metrics']['property_support'],4)
        self.assertEqual(data['verification'],'UNVERIFIED_SUPPORT_CANDIDATES')

    def test_attribute_and_race_search(self):
        self.build()
        result=search_property_support(self.dest,attribute='LIGHT',action='SEARCH_FROM_DECK')
        self.assertIn('konami:1001',{x['source_card_id'] for x in result['results']})
        for row in result['results']:
            self.assertEqual(row['target_type'],'ATTRIBUTE')
            self.assertEqual(row['target_value'],'LIGHT')
            self.assertEqual(row['verification'],'UNVERIFIED_INTERPRETATION')
        byrace=search_property_support(self.dest,race='Machine',action='SPECIAL_SUMMON')
        self.assertIn('konami:1004',{x['source_card_id'] for x in byrace['results']})

    def test_composite_support_requires_same_clause(self):
        self.build()
        both=search_property_support(self.dest,attribute='LIGHT',race='Warrior',
                     match_mode='ALL',action='SEARCH_FROM_DECK')['results']
        self.assertEqual({r['source_card_id'] for r in both},{'konami:1001'})
        none=search_property_support(self.dest,attribute='LIGHT',race='Fiend',
                      match_mode='ALL')['results']
        self.assertFalse(none)

    def test_target_card_query_and_literal_roles(self):
        self.build()
        result=search_property_support(self.dest,target_card_id='konami:1002',
                                      action='SEARCH_FROM_DECK')
        self.assertEqual({x['source_card_id'] for x in result['results']},{'konami:1001'})
        self.assertEqual({x['target_type'] for x in result['results']},{'ATTRIBUTE','RACE'})

    def test_opponent_action_not_own_summon_support(self):
        self.build()
        rows=search_property_support(self.dest,race='Fiend',action='SPECIAL_SUMMON')['results']
        self.assertNotIn('konami:1005',{x['source_card_id'] for x in rows})

    def test_quoted_meta_effect_not_positive_search(self):
        self.build()
        result=search_property_support(self.dest,attribute='LIGHT',action='SEARCH_FROM_DECK')
        self.assertNotIn('konami:1006',{x['source_card_id'] for x in result['results']})

    def test_dynamic_name_groups_not_formal_membership(self):
        data=self.build()
        self.assertGreaterEqual(data['metrics']['name_groups'],1)
        results=search_name_groups(self.dest,query='架空戦団')['results']
        group=next(x for x in results if x['group_key']=='架空戦団')
        self.assertEqual(group['member_count'],3)
        self.assertGreaterEqual(group['reference_count'],2)

    def test_private_evidence_provenance(self):
        self.build()
        rows=search_property_support(self.dest,race='Warrior',action='SEARCH_FROM_DECK')['results']
        self.assertEqual(len(rows),1)
        row=rows[0]
        text=ROWS[0][-1]
        self.assertEqual(row['evidence'],text[row['start']:row['end']])
        self.assertEqual(row['text_sha256'],sha256(text.encode()).hexdigest())
        self.assertEqual(row['text_version'],'v1')

    def test_sha_mismatch_rejected_without_creating_output(self):
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            build_private_support_index(self.source,self.m4,self.dest,
                expected_source_sha256='f'*64,expected_m4_sha256=self.m4sha)
        self.assertFalse(self.dest.exists())

    def test_stale_m4_linkage_rejected(self):
        with sqlite3.connect(self.m4) as db:
            db.execute("UPDATE metadata SET value='"+'f'*64+"' WHERE key='source_sqlite_sha256'")
        other=sha256(self.m4.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'stale M4 source'):
            build_private_support_index(self.source,self.m4,self.dest,
                expected_source_sha256=self.sha,expected_m4_sha256=other)
        self.assertFalse(self.dest.exists())

    def test_no_overwrite_and_inputs_unchanged(self):
        self.build()
        with self.assertRaisesRegex(ValueError,'explicit replace'):self.build()
        self.assertEqual(sha256(self.source.read_bytes()).hexdigest(),self.sha)
        self.assertEqual(sha256(self.m4.read_bytes()).hexdigest(),self.m4sha)
        with sqlite3.connect(self.dest) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

    def test_filter_validation(self):
        self.build()
        for kw in (dict(attribute='NOT_A_REAL_ATTRIBUTE'),dict(race='bogus'),
                   dict(attribute='LIGHT',action='DROP TABLE'),
                   dict(attribute='LIGHT',limit=0),dict(attribute='LIGHT',match_mode='INVALID'),dict(target_card_id='konami:9999')):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                search_property_support(self.dest,**kw)
        with self.assertRaises(ValueError):search_property_support(self.dest)

    def test_support_not_proof_of_target_compatibility(self):
        self.build()
        result=search_property_support(self.dest,attribute='WIND',action='SPECIAL_SUMMON')
        self.assertTrue(result['results'])
        self.assertEqual(result['verification'],'UNVERIFIED_SUPPORT_CANDIDATES')


    def test_external_named_support_discovery(self):
        from engine_m5.support import search_name_group_support
        self.build()
        rows=search_name_group_support(self.dest,'架空戦団')['results']
        self.assertIn('konami:1007',{r['source_card_id'] for r in rows})
        self.assertFalse(any(r['same_group_name'] for r in rows))
        self.assertEqual(search_name_group_support(
             self.dest,'架空戦団')['verification'],
             'QUOTED_REFERENCE_CANDIDATE_NOT_VERIFIED_SUPPORT')

    def test_invalid_named_group(self):
        from engine_m5.support import search_name_group_support
        self.build()
        with self.assertRaisesRegex(ValueError,'unknown candidate'):
            search_name_group_support(self.dest,'存在しない名称')

if __name__=='__main__':unittest.main()
