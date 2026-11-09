"""Synthetic text-only tests: never distribute actual card effect text."""
import tempfile
import unittest
from pathlib import Path
from sqlite_store import Store
from zip_store.archive import pack, unpack, NAME
from card_master_import.text_import import add_japanese_effects


class JapaneseEffectImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / 'fixture.sqlite'
        store = Store.create(path)
        store.add_card('konami:9001',9001,'架空A')
        store.add_card('konami:9002',9002,'架空B')
        store.close()
        self.base, _ = pack(path)
        self.md = [{'ja_text':'架空の効果テキストA'},{'ja_text':'架空の効果テキストB'}]
        self.rows = [{'card_id':'konami:9001'}, {'card_id':'konami:9002'}]
        self.meta = {'md_sha256':'a'*64}

    def tearDown(self): self.temp.cleanup()

    def test_import_and_idempotent_rerun(self):
        result, meta = add_japanese_effects(self.base,self.md,self.rows,self.meta,acquired_at='2026-11-10')
        path=Path(self.temp.name)/'verified.sqlite'
        unpack(result,path)
        s=Store(path)
        try:
            self.assertEqual(s.db.execute('SELECT count(*) FROM card_texts').fetchone()[0],2)
            self.assertEqual(s.db.execute('SELECT count(*) FROM inventory').fetchone()[0],0)
            self.assertTrue(s.integrity_check()['ok'])
        finally: s.close()
        result2, meta2=add_japanese_effects(result,self.md,self.rows,self.meta,acquired_at='2026-11-10')
        path2=Path(self.temp.name)/'verified2.sqlite'
        unpack(result2,path2)
        s=Store(path2)
        try:
            self.assertEqual(s.db.execute('SELECT count(*) FROM card_texts').fetchone()[0],2)
        finally: s.close()

    def test_missing_text_and_mismatched_identity_rejected(self):
        with self.assertRaises(ValueError):
            add_japanese_effects(self.base,[{'ja_text':''},self.md[1]],self.rows,self.meta,acquired_at='2026-11-10')
        with self.assertRaises(ValueError):
            add_japanese_effects(self.base,self.md,list(reversed(self.rows)),self.meta,acquired_at='2026-11-10')
        with self.assertRaises(ValueError):
            add_japanese_effects(self.base,self.md,self.rows,{'md_sha256':'bad'},acquired_at='2026-11-10')

    def test_conflicting_existing_text_rejected(self):
        data,_=add_japanese_effects(self.base,self.md,self.rows,self.meta,acquired_at='2026-11-10')
        with self.assertRaises(ValueError):
            add_japanese_effects(data,[{'ja_text':'改ざん'},self.md[1]],self.rows,self.meta,acquired_at='2026-11-10')


if __name__=='__main__': unittest.main()
