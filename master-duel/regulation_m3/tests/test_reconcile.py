"""Synthetic tests for banlist provenance reconciliation. No real card lists."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from regulation_m3.reconcile import reconcile_vectors
from regulation_m3.snapshots import legacy_vector_to_candidate


def encoded(day, rules):
    return (json.dumps({"date":day,"regulation":rules},
                       sort_keys=True, ensure_ascii=False)+"\n").encode()


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/"fixture.sqlite"
        self.prev=encoded("2026-10-06",{"1001":0,"1002":2})
        self.cur=encoded("2026-11-05",{"1001":1,"1002":2,"1003":0})
        self.current=legacy_vector_to_candidate(
            self.cur,checked_at="2026-11-10T14:16:00+09:00")
        self.store=Store.create(self.db)
        for card_id in ["konami:1001","konami:1002","konami:1003"]:
            self.store.add_card(card_id,int(card_id.split(":")[1]),"Fiction "+card_id)
        s=self.current
        self.store.db.execute(
            "INSERT INTO banlist_snapshots "
            "(snapshot_id,format_id,effective_on,source,acquired_at,verification)"
            " VALUES (?,?,?,?,?,?)",
            (s["snapshot_id"],s["format_id"],s["effective_on"],
             "fixture #SHA256="+s["source_sha256"],s["checked_at"],
             "UNVERIFIED_SOURCE"))
        for key,val in s["rules"].items():
            self.store.db.execute("INSERT INTO banlist_entries VALUES (?,?,?)",
                                  (s["snapshot_id"],key,val))
        self.store.close()

    def tearDown(self):
        self.tmp.cleanup()

    def call(self,prev=None,current=None):
        return reconcile_vectors(
            self.prev if prev is None else prev,
            self.cur if current is None else current,
            self.db,checked_at="2026-11-10T14:16:00+09:00")

    def test_full_row_check_and_explicit_previous_absence(self):
        d=self.call()
        self.assertEqual(d["verification"],"INTERNAL_SOURCE_MATCH_NOT_OFFICIAL_GAME_VERIFIED")
        self.assertEqual(d["entries"],3)
        self.assertEqual((d["forbidden"],d["limited"],d["semi_limited"]),(1,1,1))
        self.assertEqual(len(d["changes"]),2)
        self.assertEqual(d["changes"][0]["prior"],0)
        self.assertEqual(d["changes"][0]["current"],1)
        self.assertIsNone(d["changes"][1]["prior"])
        self.assertFalse(d["changes"][1]["prior_listed"])

    def test_detect_disagreement_even_if_totals_same(self):
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE banlist_entries SET max_copies=1 WHERE card_id='konami:1003'")
        with self.assertRaisesRegex(ValueError,"disagree"):
            self.call()

    def test_candidate_verified_promotion_is_not_accepted(self):
        import sqlite3
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE banlist_snapshots SET verification='GAME_VERIFIED'")
        with self.assertRaisesRegex(ValueError,"status mismatch"):
            self.call()

    def test_future_previous_snapshot_rejected(self):
        previous=encoded("2026-12-01",{"1001":0})
        with self.assertRaisesRegex(ValueError,"older"):
            self.call(prev=previous)


if __name__=="__main__":
    unittest.main()
