"""Synthetic-only private index contract checks."""
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from effect_semantics_m4 import build_private_index,search_private_index

FIXTURES=(
 ('konami:1001','架空カードA','MONSTER','N','自分は２枚ドローする。'),
 ('konami:1002','架空カードB','SPELL','SR','デッキから「架空」カード１枚を手札に加える。'),
 ('konami:1003','架空カードC','TRAP','R','相手が特殊召喚する度に、自分は１枚ドローする。'),
 ('konami:1004','架空カードD','MONSTER','UR','●デッキからカードを手札に加える効果'),
)

def testdb(path):
    con=sqlite3.connect(path)
    con.executescript('''CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY);
        INSERT INTO schema_migrations VALUES (1);
        CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
        CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT);
        CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT);
        CREATE TABLE card_texts(card_id TEXT,language TEXT,version TEXT,body TEXT,
                                source TEXT,acquired_at TEXT,PRIMARY KEY(card_id,language,version));''')
    for cid,name,kind,rarity,body in FIXTURES:
        con.execute('INSERT INTO cards VALUES(?,?)',(cid,name))
        con.execute('INSERT INTO card_attributes VALUES(?,?)',(cid,kind))
        con.execute('INSERT INTO md_catalog VALUES(?,?)',(cid,rarity))
        con.execute('INSERT INTO card_texts VALUES(?,?,?,?,?,?)',
                    (cid,'ja','v1',body,'SYNTHETIC','2026-11-10'))
    con.commit();con.close()

class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.src=self.root/'catalog.sqlite';self.index=self.root/'private-index.sqlite'
        testdb(self.src);self.sha=hashlib.sha256(self.src.read_bytes()).hexdigest()

    def tearDown(self):self.tmp.cleanup()

    def build(self,**kwargs):
        return build_private_index(self.src,self.index,expected_source_sha256=self.sha,**kwargs)

    def test_build_query_role_filter_and_source_immutability(self):
        r=self.build();self.assertEqual(r['cards'],4)
        self.assertEqual(self.sha,hashlib.sha256(self.src.read_bytes()).hexdigest())
        self.assertEqual(r['index_sha256'],hashlib.sha256(self.index.read_bytes()).hexdigest())
        rows=search_private_index(self.index,facets=['DRAW'],roles=['ACTION'],expected_source_sha256=self.sha)['results']
        self.assertEqual({x['card_id'] for x in rows},{'konami:1001','konami:1003'})
        rows=search_private_index(self.index,facets=['SEARCH_FROM_DECK'],roles=['ACTION'])['results']
        self.assertEqual([x['card_id'] for x in rows],['konami:1002'])
        rows=search_private_index(self.index,facets=['SEARCH_FROM_DECK'],roles=['REFERENCED'])['results']
        self.assertEqual([x['card_id'] for x in rows],['konami:1004'])

    def test_structured_filters(self):
        self.build()
        r=search_private_index(self.index,facets=['DRAW'],rarity='N',kind='MONSTER')['results']
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['card_id'],'konami:1001')

    def test_stale_source_sha_rejected(self):
        with self.assertRaisesRegex(ValueError,'source SQLite SHA-256 mismatch'):
            build_private_index(self.src,self.index,expected_source_sha256='f'*64)
        self.build()
        with self.assertRaisesRegex(ValueError,'stale facet index'):
            search_private_index(self.index,facets=['DRAW'],expected_source_sha256='f'*64)

    def test_existing_index_not_overwritten_without_permission(self):
        self.build()
        with self.assertRaisesRegex(ValueError,'explicit replace'):
            self.build()
        self.build(replace=True)

    def test_invalid_filter_rejected(self):
        self.build()
        for req in (dict(facets=['BOGUS']),dict(facets=['DRAW'],rarity='X'),
                    dict(facets=['DRAW'],limit=0),dict(facets=['DRAW'],roles=['UNKNOWN'])):
            with self.subTest(req=req),self.assertRaises(ValueError):
                search_private_index(self.index,**req)

    def test_source_and_destination_must_differ(self):
        with self.assertRaisesRegex(ValueError,'source database'):
            build_private_index(self.src,self.src,expected_source_sha256=self.sha)

    def test_text_version_change_can_be_rebuilt_without_touching_source(self):
        self.build()
        with sqlite3.connect(self.src) as con:
            con.execute('INSERT INTO card_texts VALUES (?,?,?,?,?,?)',
                        ('konami:1001','ja','v2','デッキからモンスター１体を手札に加える。','SYNTHETIC','2026-11-11'))
        other_sha=hashlib.sha256(self.src.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'source SQLite SHA-256 mismatch'):
            self.build(replace=True)
        updated=build_private_index(self.src,self.index,expected_source_sha256=other_sha,replace=True)
        self.assertEqual(updated['source_sha256'],other_sha)
        r=search_private_index(self.index,facets=['DRAW'],roles=['ACTION'])['results']
        self.assertEqual([x['card_id'] for x in r],['konami:1003'])

if __name__=='__main__':unittest.main()
