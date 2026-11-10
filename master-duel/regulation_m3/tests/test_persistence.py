"""Synthetic M3 ZIP import tests. No private data or Drive writes."""
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from zip_store.archive import pack, digest, NAME
from regulation_m3.persistence import prepare_candidate_import, inspect_candidate_import
from regulation_m3.snapshots import legacy_vector_to_candidate


class CandidateImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        path=Path(self.temp.name)/"fixture.sqlite"
        store=Store.create(path)
        for id_, name in ((1001, "架空氷龍"), (1002, "架空天使"), (1003, "架空ロボ")):
            key="konami:"+str(id_)
            store.add_card(key,id_,name)
            store.set_md_catalog(key,rarity="UR",rarity_source="MD:FICTION")
        store.set_inventory("fixture-inventory",[
            {"card_id":"konami:1001","owned_count":3},
            {"card_id":"konami:1002","owned_count":0},
        ])
        store.close()
        self.zip,self.meta=pack(path)
        self.snapshot=legacy_vector_to_candidate(
            b'{"date":"2026-11-05","regulation":{"1001":1,"1003":0}}',
            checked_at="2026-11-10T10:00:00+09:00",
            source="SYNTHETIC_FIXTURE")
    def tearDown(self):
        self.temp.cleanup()
    def candidate(self,snapshot=None, source=None):
        return prepare_candidate_import(
            self.zip if source is None else source,
            "fiction-parent-2","fiction-child-3",
            self.snapshot if snapshot is None else snapshot)

    def test_creates_candidate_without_changing_source_or_inventory(self):
        original_sha=digest(self.zip)
        prepared=self.candidate()
        self.assertEqual(digest(self.zip),original_sha)
        self.assertNotEqual(digest(prepared["zip"]),original_sha)
        self.assertEqual(prepared["manifest"]["banlist_verification"],"UNVERIFIED_SOURCE")
        self.assertEqual(prepared["manifest"]["counts_before"],prepared["manifest"]["counts_after"])
        summary=inspect_candidate_import(prepared["zip"],self.snapshot["snapshot_id"])
        self.assertEqual(summary["total_entries"],2)
        self.assertEqual(summary["verification"],"UNVERIFIED_SOURCE")
        self.assertEqual(summary["entries_by_max_copies"],{0:1,1:1,2:0,3:0})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/NAME;p.write_bytes(zipfile.ZipFile(io.BytesIO(prepared["zip"])).read(NAME))
            store=Store(p)
            try:
                self.assertEqual(store.get_inventory("konami:1001")["owned_count"],3)
                self.assertEqual(store.get_inventory("konami:1002")["known_state"],"KNOWN_ZERO")
                self.assertEqual(store.get_inventory("konami:1003")["known_state"],"UNKNOWN")
                self.assertEqual(len(store.history("konami:1001")),1)
            finally:store.close()

    def test_missing_card_aborts_transaction_and_source_unchanged(self):
        bad={**self.snapshot,"rules":{**self.snapshot["rules"],"konami:9999":2}}
        sha=digest(self.zip)
        with self.assertRaisesRegex(ValueError,"nonexistent card"):
            self.candidate(bad)
        self.assertEqual(digest(self.zip),sha)
        with self.assertRaisesRegex(ValueError,"not found"):
            inspect_candidate_import(self.zip,self.snapshot["snapshot_id"])

    def test_duplicate_snapshot_is_not_overwritten(self):
        first=self.candidate()
        with self.assertRaisesRegex(ValueError,"already exists"):
            self.candidate(source=first["zip"])

    def test_verified_snapshot_cannot_be_imported_as_candidate(self):
        bad={**self.snapshot,"verification":"GAME_VERIFIED"}
        with self.assertRaisesRegex(ValueError,"cannot create GAME_VERIFIED"):
            self.candidate(bad)

    def test_corrupted_zip_or_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"invalid ZIP"):
            self.candidate(source=b"fake")
        with self.assertRaisesRegex(ValueError,"invalid snapshot chain"):
            prepare_candidate_import(self.zip,"same","same",self.snapshot)

    def test_unknown_or_empty_banlist_blocks_candidate(self):
        empty={**self.snapshot,"rules":{}}
        with self.assertRaisesRegex(ValueError,"empty candidate"):
            self.candidate(empty)

    def test_new_snapshot_is_immutable_and_can_accumulate_distinct_dates(self):
        first=self.candidate()
        old=inspect_candidate_import(first["zip"],self.snapshot["snapshot_id"])
        later={**self.snapshot,"snapshot_id":"md-standard-2026-12-05-fixture",
               "effective_on":"2026-12-05","rules":{"konami:1003":2}}
        second=prepare_candidate_import(first["zip"],"fiction-child-3","fiction-child-4",later)
        self.assertEqual(inspect_candidate_import(second["zip"],self.snapshot["snapshot_id"]),{
            **old,"archive":inspect_candidate_import(second["zip"],self.snapshot["snapshot_id"])["archive"]})
        self.assertEqual(inspect_candidate_import(second["zip"],later["snapshot_id"])["total_entries"],1)

if __name__=="__main__":unittest.main()
