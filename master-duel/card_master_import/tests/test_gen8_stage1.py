"""Synthetic Gen8 classification tests, independent of private DB."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from sqlite_store import Store
from card_master_import.importer import extra_properties, subtype_flags


class Gen8Stage1Test(unittest.TestCase):
    def test_source_properties(self):
        self.assertEqual('Quick-Play',extra_properties(
            {'property':'Quick-Play'},'SPELL',())[0])
        self.assertEqual('Counter',extra_properties(
            {'property':'Counter'},'TRAP',())[0])
        with self.assertRaises(ValueError):
            extra_properties({'property':'Impossible'},'SPELL',())
        with self.assertRaises(ValueError):
            extra_properties({},'TRAP',())
        prop,markers,scale,ja=extra_properties(
            {'link_arrows':'Top-Left, Bottom-Right'},'MONSTER',('LINK','EFFECT'))
        self.assertEqual(('Top-Left','Bottom-Right'),markers)
        with self.assertRaises(ValueError):
            extra_properties({'link_arrows':'Top-Left, Top-Left'},'MONSTER',('LINK',))
        self.assertEqual((None,(),0,None),extra_properties(
            {'pendulum_scale':'0'},'MONSTER',('PENDULUM','EFFECT')))
        with self.assertRaises(ValueError):
            extra_properties({'pendulum_scale':'14'},'MONSTER',('PENDULUM',))

    def test_v3_schema_checks_are_strict(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'m.sqlite'
            st=Store.create(p)
            st.db.executescript("""
                CREATE TABLE card_monster_types(card_id TEXT NOT NULL REFERENCES cards(card_id),
                  monster_type TEXT NOT NULL,source TEXT NOT NULL,
                  verification TEXT NOT NULL,PRIMARY KEY(card_id,monster_type));
                CREATE INDEX idx_card_monster_types_type ON card_monster_types(monster_type,card_id);
                INSERT INTO schema_migrations(version) VALUES(2);
                CREATE TABLE card_spell_trap_properties(card_id TEXT PRIMARY KEY REFERENCES cards(card_id),
                  property TEXT NOT NULL,source TEXT NOT NULL,verification TEXT NOT NULL);
                CREATE INDEX idx_card_spell_trap_property ON card_spell_trap_properties(property,card_id);
                CREATE TABLE card_link_markers(card_id TEXT NOT NULL REFERENCES cards(card_id),
                  arrow TEXT NOT NULL,source TEXT NOT NULL,verification TEXT NOT NULL,
                  PRIMARY KEY(card_id,arrow));
                CREATE INDEX idx_card_link_markers_arrow ON card_link_markers(arrow,card_id);
                CREATE TABLE card_pendulum_details(card_id TEXT PRIMARY KEY REFERENCES cards(card_id),
                  scale INTEGER NOT NULL,ja_pendulum_effect TEXT,source TEXT NOT NULL,
                  verification TEXT NOT NULL);
                INSERT INTO schema_migrations(version) VALUES(3);
            """)
            st.close()
            st=Store(p)
            self.assertEqual(3,st.version())
            st.close()
            cx=sqlite3.connect(p)
            cx.execute('DROP INDEX idx_card_link_markers_arrow')
            cx.commit();cx.close()
            with self.assertRaisesRegex(ValueError,'missing v3'):
                Store(p)


if __name__=='__main__': unittest.main()
