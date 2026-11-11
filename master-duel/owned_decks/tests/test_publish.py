"""All data and Drive file IDs here are synthetic."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from owned_decks.catalog import canonical, empty_catalog, resolve, sha256
from owned_decks.publish import (
    PublicationConflict, prepare_catalog_update, verify_activated_catalog,
    verify_base_before_activation, verify_uploaded_snapshot,
)


def fixture(version, state, supersedes=None):
    entries = [
        {"section": "MAIN", "spoken_name": f"架空札{i:02d}", "card_id": f"synthetic:{i}", "quantity": 3}
        for i in range(13)
    ]
    entries.append({"section": "MAIN", "spoken_name": "架空札13", "card_id": "synthetic:13", "quantity": 1})
    entries.append({"section": "EXTRA", "spoken_name": "架空EX", "card_id": "synthetic:ex", "quantity": 1})
    if state == "STAGED":
        entries = entries[:5]
    return {"schema": "md-owned-deck-v1", "deck_id": "synthetic-twin-spright",
            "name": "架空ツイン", "aliases": ["架空ツイン型"], "version": version,
            "state": state, "supersedes": supersedes, "entries": entries}


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.catalog = empty_catalog("2026-11-11T00:00:00Z")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "cards.sqlite"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE cards (card_id TEXT PRIMARY KEY, name TEXT)")
            con.executemany("INSERT INTO cards VALUES (?, ?)",
                            [(f"synthetic:{i}", f"架空札{i}") for i in range(14)] +
                            [("synthetic:ex", "架空EX")])

    def next(self, catalog, snap, file_id):
        return prepare_catalog_update(catalog, sha256(catalog), snap, canonical(snap), file_id,
                                      "2026-11-11T00:02:00Z", str(self.db), variant="架空混合")

    def test_stage_then_confirm_without_mutating_base(self):
        staged = fixture(1, "STAGED")
        gen2 = self.next(self.catalog, staged, "fake-file-stage")
        self.assertEqual(1, gen2["decks"][0]["versions"][0]["version"])
        self.assertEqual(2, gen2["generation"])
        self.assertEqual([], self.catalog["decks"])
        self.assertEqual("STAGED_ONLY", resolve(gen2, "架空ツイン")["status"])
        confirmed = fixture(2, "CONFIRMED", sha256(staged))
        gen3 = self.next(gen2, confirmed, "fake-file-confirmed")
        self.assertEqual(3, gen3["generation"])
        self.assertEqual("READY", resolve(gen3, "架空ツイン")["status"])
        self.assertEqual(2, resolve(gen3, "架空ツイン")["matches"][0]["confirmed"]["version"])
        self.assertEqual(2, len(gen3["decks"][0]["versions"]))
        self.assertEqual(3, verify_activated_catalog(gen3, canonical(gen3))["generation"])
        self.assertEqual(2, verify_base_before_activation(gen2, canonical(gen2))["generation"])

    def test_stale_catalog_rejected(self):
        snap = fixture(1, "STAGED")
        with self.assertRaises(PublicationConflict):
            prepare_catalog_update(self.catalog, "0" * 64, snap, canonical(snap),
                                   "fake-file", "2026-11-11T00:02:00Z")
        with self.assertRaises(PublicationConflict):
            verify_base_before_activation(self.catalog, b"{}")

    def test_post_activation_mismatch_rejected(self):
        with self.assertRaises(PublicationConflict):
            verify_activated_catalog(self.catalog, b"{}")

    def test_upload_changed_rejected(self):
        s = fixture(1, "STAGED")
        with self.assertRaises(PublicationConflict):
            verify_uploaded_snapshot(s, canonical(dict(s, name="改竄")))

    def test_unverified_confirmed_card_ids_rejected(self):
        s = fixture(1, "CONFIRMED")
        with self.assertRaises(ValueError):
            verify_uploaded_snapshot(s, canonical(s))
        s["entries"][0]["card_id"] = "synthetic:wrong"
        with self.assertRaises(ValueError):
            verify_uploaded_snapshot(s, canonical(s), str(self.db))

    def test_no_reused_drive_file_id(self):
        staged = fixture(1, "STAGED")
        gen2 = self.next(self.catalog, staged, "fake-file-stage")
        confirmed = fixture(2, "CONFIRMED", sha256(staged))
        with self.assertRaises(PublicationConflict):
            self.next(gen2, confirmed, "fake-file-stage")

    def test_no_skip_version_or_wrong_parent(self):
        staged = fixture(1, "STAGED")
        gen2 = self.next(self.catalog, staged, "fake-file-stage")
        with self.assertRaises(PublicationConflict):
            self.next(gen2, fixture(3, "CONFIRMED", sha256(staged)), "fake-file-new")
        with self.assertRaises(PublicationConflict):
            self.next(gen2, fixture(2, "CONFIRMED", "e" * 64), "fake-file-new")

    def test_invalid_confirmed_cannot_publish(self):
        s = fixture(1, "CONFIRMED")
        s["entries"] = s["entries"][:1]
        with self.assertRaises(ValueError):
            self.next(self.catalog, s, "fake-bad")

    def test_incomplete_stage_can_be_preserved(self):
        s = fixture(1, "STAGED")
        s["entries"][0]["card_id"] = None
        gen2 = self.next(self.catalog, s, "fake-stage")
        self.assertEqual("STAGED_ONLY", resolve(gen2, "架空")["status"])


if __name__ == "__main__":
    unittest.main()
