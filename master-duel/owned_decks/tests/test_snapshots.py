import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from owned_decks.__main__ import check, find, load, put


def sample(state="STAGED"):
    return {"schema": "md-owned-deck-v1", "deck_id": "synthetic-evil-twin",
            "name": "架空イビルツイン", "aliases": ["イビルツイン"],
            "version": 1, "supersedes": None, "state": state,
            "entries": [
                {"section": "MAIN", "spoken_name": "架空A", "card_id": "synthetic:a", "quantity": 40},
                {"section": "EXTRA", "spoken_name": "架空B", "card_id": "synthetic:b", "quantity": 1}]}


class TestOwnedDecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "cards.sqlite"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE cards(card_id TEXT PRIMARY KEY, name TEXT)")
            con.executemany("INSERT INTO cards VALUES (?, ?)", [
                ("synthetic:a", "架空A"), ("synthetic:b", "架空B")])

    def test_confirm_save_find_roundtrip(self):
        data = sample("CONFIRMED")
        report = put(self.tmp.name, data, self.db)
        self.assertEqual((40, 1), (report["main"], report["extra"]))
        self.assertEqual(data, load(self.tmp.name, report["sha256"]))
        self.assertEqual(1, len(find(self.tmp.name, "イビルツイン")))
        self.assertEqual(report["sha256"], put(self.tmp.name, data, self.db)["sha256"])

    def test_unresolved_staging_is_retained(self):
        data = sample()
        data["entries"][0]["card_id"] = None
        result = check(data, self.db)
        self.assertEqual(["UNRESOLVED_CARDS"], result["warnings"])
        data["state"] = "CONFIRMED"
        with self.assertRaises(ValueError):
            check(data, self.db)

    def test_no_unknown_ids(self):
        data = sample()
        data["entries"][0]["card_id"] = "synthetic:wrong"
        with self.assertRaises(ValueError):
            check(data, self.db)

    def test_no_duplicate_ids(self):
        data = sample()
        data["entries"].append(dict(data["entries"][0]))
        with self.assertRaises(ValueError):
            check(data, self.db)

    def test_excess_extra_remains_staged(self):
        data = sample()
        data["entries"][1]["quantity"] = 16
        self.assertIn("EXTRA_OVER_15", check(data)["warnings"])
        data["state"] = "CONFIRMED"
        with self.assertRaises(ValueError):
            check(data)

    def test_integrity_tamper(self):
        report = put(self.tmp.name, sample(), self.db)
        path = Path(self.tmp.name) / (report["sha256"] + ".json")
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            load(self.tmp.name, report["sha256"])


if __name__ == "__main__":
    unittest.main()
