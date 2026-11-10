"""Synthetic private-DB candidate staging regression tests; no real cards."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from regulation_m3.catalog_store import stage_candidate_snapshot, read_candidate_snapshot
from regulation_m3.snapshots import legacy_vector_to_candidate


class CandidateStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"fixture.sqlite"
        s=Store.create(self.path)
        s.add_card("konami:1001",1001,"架空甲")
        s.add_card("konami:1002",1002,"架空乙")
        s.set_inventory("fixture-inventory",[{"card_id":"konami:1001","owned_count":2}])
        s.close()
        self.raw=b'{"date":"2026-11-05","regulation":{"1001":0,"1002":1}}'
        self.snap=legacy_vector_to_candidate(self.raw,checked_at="2026-11-10T13:00:00+09:00")

    def tearDown(self):
        self.tmp.cleanup()

    def test_insert_and_exact_readback(self):
        r=stage_candidate_snapshot(self.path,self.snap)
        self.assertEqual(r["status"],"INSERTED")
        self.assertEqual(r["rule_count"],2)
        x=read_candidate_snapshot(self.path,self.snap["snapshot_id"])
        self.assertEqual(x["verification"],"UNVERIFIED_SOURCE")
        self.assertEqual(x["distribution"],{"0":1,"1":1,"2":0,"3":0})
        db=sqlite3.connect(self.path)
        try:
            self.assertEqual(db.execute("select owned_count from inventory where card_id='konami:1001'").fetchone()[0],2)
            self.assertEqual(db.execute("select count(*) from inventory_history").fetchone()[0],1)
        finally: db.close()

    def test_idempotent_replay(self):
        stage_candidate_snapshot(self.path,self.snap)
        self.assertEqual(stage_candidate_snapshot(self.path,self.snap)["status"],"ALREADY_PRESENT")
        self.assertEqual(sqlite3.connect(self.path).execute("select count(*) from banlist_entries").fetchone()[0],2)

    def test_snapshot_id_collision_fails(self):
        stage_candidate_snapshot(self.path,self.snap)
        changed=dict(self.snap)
        changed["rules"]={"konami:1001":1,"konami:1002":1}
        with self.assertRaisesRegex(ValueError,"rule mismatch"):
            stage_candidate_snapshot(self.path,changed)

    def test_same_effective_date_duplicate_rejected(self):
        stage_candidate_snapshot(self.path,self.snap)
        another=dict(self.snap)
        another["snapshot_id"]="different"
        with self.assertRaisesRegex(ValueError,"same-date"):
            stage_candidate_snapshot(self.path,another)

    def test_unknown_card_rolls_back(self):
        bad=dict(self.snap)
        bad["rules"]={"konami:1001":1,"konami:2001":0}
        with self.assertRaisesRegex(ValueError,"canonical"):
            stage_candidate_snapshot(self.path,bad)
        db=sqlite3.connect(self.path)
        try:
            self.assertEqual(db.execute("select count(*) from banlist_snapshots").fetchone()[0],0)
        finally: db.close()

    def test_reject_game_verified_spoof(self):
        bad=dict(self.snap)
        bad["verification"]="GAME_VERIFIED"
        with self.assertRaisesRegex(ValueError,"refuses"):
            stage_candidate_snapshot(self.path,bad)

    def test_no_false_3_copies_for_absent_card(self):
        stage_candidate_snapshot(self.path,self.snap)
        db=sqlite3.connect(self.path)
        try:
            entries=dict(db.execute("SELECT card_id,max_copies FROM banlist_entries"))
            self.assertEqual(entries["konami:1001"],0)
            self.assertNotIn("konami:7777",entries)
        finally: db.close()

    def test_empty_candidate_rejected(self):
        bad=dict(self.snap)
        bad["rules"]={}
        with self.assertRaisesRegex(ValueError,"empty"):
            stage_candidate_snapshot(self.path,bad)


if __name__=="__main__":unittest.main()
