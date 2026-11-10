"""M3 candidate archive import: synthetic fixtures only."""
import hashlib
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from zip_store.archive import pack, unpack, NAME, digest
from regulation_m3.importer import preview_candidate, prepare_candidate
from regulation_m3.database import load_snapshots
from regulation_m3.snapshots import resolve_limit
from inventory_m2 import build_verified_head

def synthetic():
    return {
        "schema_version":1,"snapshot_id":"fixture-2026-11",
        "format_id":"MD_STANDARD","effective_on":"2026-11-05",
        "checked_at":"2026-11-10T13:00:00+09:00",
        "source":"SYNTHETIC_TEST","source_sha256":"f"*64,
        "verification":"UNVERIFIED_SOURCE",
        "rules":{"konami:1001":0,"konami:1002":1},
    }

class CandidateImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        p=self.root/"source.sqlite"
        store=Store.create(p)
        store.add_card("konami:1001",1001,"架空の一号")
        store.add_card("konami:1002",1002,"架空の二号")
        store.set_inventory("existing-inventory",[{"card_id":"konami:1001","owned_count":2}])
        store.close()
        self.data,_=pack(p)

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_is_readonly_and_has_approval_hash(self):
        original=digest(self.data)
        pre=preview_candidate(self.data,synthetic())
        self.assertEqual(pre["old_snapshots"],0)
        self.assertEqual(pre["old_entries"],0)
        self.assertEqual(pre["inventory_before"],1)
        self.assertEqual(pre["rules"],2)
        self.assertEqual(len(pre["preview_sha256"]),64)
        self.assertEqual(original,digest(self.data))

    def test_import_retains_inventory_and_marks_candidate_only(self):
        item=synthetic()
        p=preview_candidate(self.data,item)
        new=prepare_candidate(self.data,"parent","child",item,p["preview_sha256"])
        self.assertEqual(new["manifest"]["regulation_verification"],"UNVERIFIED_SOURCE")
        self.assertNotEqual(digest(new["zip"]),digest(self.data))
        dbpath=self.root/"new.sqlite"
        meta=unpack(new["zip"],dbpath)
        store=Store(dbpath)
        try:
            self.assertEqual(store.get_inventory("konami:1001")["owned_count"],2)
            self.assertEqual(len(store.history("konami:1001")),1)
            snap=store.db.execute("SELECT verification FROM banlist_snapshots").fetchone()[0]
            self.assertEqual(snap,"UNVERIFIED_SOURCE")
            self.assertEqual(store.db.execute("SELECT count(*) FROM banlist_entries").fetchone()[0],2)
            self.assertEqual(store.db.execute("SELECT max_copies FROM banlist_entries WHERE card_id='konami:1001'").fetchone()[0],0)
            self.assertEqual(store.integrity_check()["ok"],True)
        finally:
            store.close()
        self.assertEqual(new["manifest"]["output_zip_sha256"],meta["zip_sha256"])

    def test_private_sqlite_loader_stays_candidate_only(self):
        item=synthetic()
        approved=preview_candidate(self.data,item)
        prepared=prepare_candidate(self.data,"parent","child",item,approved["preview_sha256"])
        path=self.root/"roundtrip.sqlite"
        unpack(prepared["zip"],path)
        loaded=load_snapshots(path,as_of="2026-11-10")
        self.assertEqual(len(loaded),1)
        self.assertEqual(loaded[0]["source_sha256"],"f"*64)
        r=resolve_limit(loaded,card_id="konami:1001",as_of="2026-11-10")
        self.assertEqual(r["status"],"CANDIDATE_ONLY")
        self.assertIsNone(r["allowed"])
        self.assertEqual(r["candidate_max_copies"],0)
        self.assertEqual(load_snapshots(path,as_of="2026-10-01"),[])

    def test_m2_head_promotion_gate_accepts_verified_candidate_zip(self):
        item=synthetic()
        pre=preview_candidate(self.data,item)
        prepared=prepare_candidate(self.data,"parent","child",item,pre["preview_sha256"])
        source_meta=pre["source_db_sha256"]
        head={"system":"master-duel","scope":"SYNTHETIC_TEST","generation":1,
              "sqlite_schema_version":1,"writer_policy":"SINGLE_WRITER_NO_ATOMIC_CAS",
              "current_snapshot":{"snapshot_id":"parent","drive_file_id":"fixture-parent",
                                  "classification":"SYNTHETIC_ONLY","schema_version":1,
                                  "zip_sha256":digest(self.data),"db_sha256":source_meta}}
        promoted=build_verified_head(head,head,self.data,prepared,self.data,prepared["zip"],
                                    backup_file_id="fixture-backup",
                                    candidate_file_id="fixture-candidate",
                                    scope="SYNTHETIC_TEST")
        self.assertEqual(promoted["generation"],2)
        self.assertEqual(promoted["last_operation_type"],"ADD_REGULATION_CANDIDATE")

    def test_loader_handles_previous_private_provenance_serialization(self):
        item=synthetic()
        pre=preview_candidate(self.data,item)
        prepared=prepare_candidate(self.data,"parent","child",item,pre["preview_sha256"])
        path=self.root/"legacy_source.sqlite"
        unpack(prepared["zip"],path)
        store=Store(path)
        try:
            store.db.execute("UPDATE banlist_snapshots SET source=? WHERE snapshot_id=?",
                             ("SYNTHETIC_TEST #SHA256="+"f"*64,item["snapshot_id"]))
            store.db.commit()
        finally:
            store.close()
        loaded=load_snapshots(path,as_of="2026-11-10")
        self.assertEqual(len(loaded),1)
        self.assertEqual(loaded[0]["source_sha256"],"f"*64)
        self.assertEqual(loaded[0]["verification"],"UNVERIFIED_SOURCE")

    def test_mismatched_preview_and_changed_rule_rejected(self):
        item=synthetic()
        preview=preview_candidate(self.data,item)
        changed=deepcopy(item)
        changed["rules"]["konami:1001"]=1
        with self.assertRaisesRegex(ValueError,"approval"):
            prepare_candidate(self.data,"parent","child",changed,preview["preview_sha256"])
        with self.assertRaisesRegex(ValueError,"approval"):
            prepare_candidate(self.data,"parent","child",item,"f"*64)

    def test_unknown_card_rejected_without_mutation(self):
        item=synthetic()
        item["rules"]["konami:9999"]=0
        with self.assertRaisesRegex(ValueError,"unresolved"):
            preview_candidate(self.data,item)
        self.assertEqual(digest(self.data),hashlib.sha256(self.data).hexdigest())

    def test_automatic_import_cannot_promote_game_verified(self):
        item=synthetic()
        item["verification"]="GAME_VERIFIED"
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_SOURCE"):
            preview_candidate(self.data,item)

    def test_duplicate_snapshot_cannot_rewrite_previous_regulation(self):
        item=synthetic()
        first=preview_candidate(self.data,item)
        prepared=prepare_candidate(self.data,"parent","child",item,first["preview_sha256"])
        with self.assertRaisesRegex(ValueError,"already exists"):
            preview_candidate(prepared["zip"],item)

    def test_no_candidate_when_identity_or_parent_invalid(self):
        item=synthetic()
        pre=preview_candidate(self.data,item)
        for parent,child in (("same","same"),("","new"),("old","")):
            with self.subTest(parent=parent,child=child),self.assertRaises(ValueError):
                prepare_candidate(self.data,parent,child,item,pre["preview_sha256"])

    def test_snapshot_zero_rules_rejected(self):
        item=synthetic()
        item["rules"]={}
        with self.assertRaisesRegex(ValueError,"empty"):
            preview_candidate(self.data,item)

if __name__=="__main__": unittest.main()
