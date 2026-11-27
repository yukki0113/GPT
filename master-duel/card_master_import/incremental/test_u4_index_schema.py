"""Regression: M4/M5-A source readers accept contiguous supported migrations."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from effect_semantics_m4.index import build_private_index
from engine_m5.index import build_private_m5_index, _verify_source


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fixture(p, versions):
    with sqlite3.connect(p) as db:
        db.executescript('''CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY);
            CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
            CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,attribute TEXT,race TEXT,level INTEGER,rank INTEGER,link INTEGER);
            CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT);
            CREATE TABLE card_texts(card_id TEXT,language TEXT,body TEXT,source TEXT,version TEXT,acquired_at TEXT);
            INSERT INTO cards VALUES('konami:1','架空カード');
            INSERT INTO card_attributes VALUES('konami:1','MONSTER','LIGHT','Warrior',4,NULL,NULL);
            INSERT INTO md_catalog VALUES('konami:1','N');
            INSERT INTO card_texts VALUES('konami:1','ja','①：自分は１枚ドローする。','synthetic','v1','2026-01-01');''')
        db.executemany('INSERT INTO schema_migrations VALUES (?)', [(v,) for v in versions])


class IndexSchemaTests(unittest.TestCase):
    def test_supported_versions(self):
        for v in range(1,5):
            with self.subTest(version=v), tempfile.TemporaryDirectory() as td:
                d=Path(td); src=d/'source.sqlite'; m4=d/'m4.sqlite'; m5=d/'m5.sqlite'; seed=d/'seed.json'
                fixture(src,list(range(1,v+1))); pin=digest(src)
                res=build_private_index(src,m4,expected_source_sha256=pin)
                self.assertEqual(res['cards'],1)
                seed.write_text(json.dumps(dict(schema_version=1,as_of='2026-01-01',source_db_sha256=pin,m4_index_sha256=digest(m4),themes=[dict(theme_id='SYNTH',name='架空',name_patterns=[dict(text='架空',mode='CONTAINS')],quoted_targets=[])],generic_cards=[],engines=[])))
                res=build_private_m5_index(src,m4,seed,m5,expected_source_sha256=pin,expected_m4_sha256=digest(m4),expected_seed_sha256=digest(seed))
                self.assertEqual(res['counts']['cards'],1); self.assertEqual(digest(src),pin)
    def test_invalid_versions(self):
        for versions in ([],[2],[1,3],[1,2,3,4,5]):
            with self.subTest(versions=versions), tempfile.TemporaryDirectory() as td:
                d=Path(td); src=d/'source.sqlite'; fixture(src,versions)
                with self.assertRaisesRegex(ValueError,'unsupported source schema'):
                    build_private_index(src,d/'m4.sqlite',expected_source_sha256=digest(src))
                with sqlite3.connect(src) as db:
                    with self.assertRaisesRegex(ValueError,'unsupported production schema'):
                        _verify_source(db,digest(src),False)
                self.assertFalse((d/'m4.sqlite').exists())


if __name__ == '__main__': unittest.main()
