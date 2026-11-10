"""Synthetic-only M2 lifecycle; no Drive writes or private card data."""
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from zip_store.archive import pack, digest
from inventory_m2 import (validate_head,target_from_head,preview_inventory,
                          prepare_inventory,build_verified_head,verify_activated_head)


class M2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        db=Path(self.tmp.name)/"fixture.sqlite"
        store=Store.create(db)
        store.add_card("fixture:a",1001,"架空の灰竜")
        store.add_card("fixture:b",1002,"架空の青鳥")
        store.close()
        self.source,meta=pack(db)
        self.head={"system":"master-duel","scope":"SYNTHETIC_TEST","generation":1,
                   "sqlite_schema_version":1,"writer_policy":"SINGLE_WRITER_NO_ATOMIC_CAS",
                   "current_snapshot":{"snapshot_id":"fixture-s1","drive_file_id":"fixture-parent",
                    "classification":"SYNTHETIC_ONLY","schema_version":1,
                    "zip_sha256":meta["zip_sha256"],"db_sha256":meta["db_sha256"]}}
        self.batch={"batch_id":"fixture-batch","scope":"SYNTHETIC_TEST",
                    "entries":[{"raw_name":"架空の灰竜","owned_count":3},
                               {"raw_name":"架空の青鳥","owned_count":0}]}

    def tearDown(self): self.tmp.cleanup()

    def candidate(self):
        p=preview_inventory(self.head,self.source,self.batch,scope="SYNTHETIC_TEST")
        self.assertTrue(p["can_apply"])
        return prepare_inventory(self.head,self.source,self.batch,"fixture-s2",
                                 p["preview_sha256"],scope="SYNTHETIC_TEST")

    def promotion(self,prepared=None,observed=None,backup=None,candidate=None,
                  backup_id="fixture-backup",candidate_id="fixture-new"):
        prepared=self.candidate() if prepared is None else prepared
        return build_verified_head(self.head,self.head if observed is None else observed,
                   self.source,prepared,self.source if backup is None else backup,
                   prepared["zip"] if candidate is None else candidate,
                   backup_file_id=backup_id,candidate_file_id=candidate_id,
                   scope="SYNTHETIC_TEST")

    def test_preview_unknown_to_positive_and_zero(self):
        target=target_from_head(self.head,self.source,scope="SYNTHETIC_TEST")
        self.assertEqual(target["snapshot_id"],"fixture-s1")
        p=preview_inventory(self.head,self.source,self.batch,scope="SYNTHETIC_TEST")
        self.assertEqual([r["current_state"] for r in p["rows"]],["UNKNOWN","UNKNOWN"])
        self.assertEqual([r["requested_count"] for r in p["rows"]],[3,0])

    def test_approved_prepare_and_candidate_promotion(self):
        result=self.candidate()
        h=self.promotion(result)
        self.assertEqual(h["generation"],2)
        self.assertEqual(h["previous_snapshot"],self.head["current_snapshot"])
        self.assertEqual(h["current_snapshot"]["snapshot_id"],"fixture-s2")
        self.assertEqual(h["current_snapshot"]["zip_sha256"],digest(result["zip"]))
        self.assertTrue(verify_activated_head(h,deepcopy(h),scope="SYNTHETIC_TEST"))
        self.assertEqual(self.head["generation"],1)

    def test_unapproved_and_changed_counts_fail_closed(self):
        p=preview_inventory(self.head,self.source,self.batch,scope="SYNTHETIC_TEST")
        with self.assertRaisesRegex(ValueError,"approval"):
            prepare_inventory(self.head,self.source,self.batch,"fixture-s2","bad",scope="SYNTHETIC_TEST")
        changed=deepcopy(self.batch)
        changed["entries"][0]["owned_count"]=1
        with self.assertRaisesRegex(ValueError,"approval"):
            prepare_inventory(self.head,self.source,changed,"fixture-s2",p["preview_sha256"],scope="SYNTHETIC_TEST")

    def test_scope_policy_zip_and_schema_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"scope"):
            target_from_head(self.head,self.source)
        with self.assertRaisesRegex(ValueError,"digest"):
            target_from_head(self.head,b"bad",scope="SYNTHETIC_TEST")
        bad=deepcopy(self.head)
        bad["writer_policy"]="UNSAFE"
        with self.assertRaisesRegex(ValueError,"policy"): validate_head(bad,"SYNTHETIC_TEST")
        bad=deepcopy(self.head)
        bad["current_snapshot"]["schema_version"]=2
        with self.assertRaisesRegex(ValueError,"schema"): validate_head(bad,"SYNTHETIC_TEST")

    def test_stale_parent_is_rejected(self):
        h=deepcopy(self.head)
        h["generation"]=2
        with self.assertRaisesRegex(ValueError,"changed"):
            self.promotion(observed=h)

    def test_backup_and_candidate_readback_tamper(self):
        with self.assertRaisesRegex(ValueError,"digest"): self.promotion(backup=b"changed")
        with self.assertRaisesRegex(ValueError,"digest"): self.promotion(candidate=b"changed")

    def test_duplicate_drive_ids_blocked(self):
        with self.assertRaisesRegex(ValueError,"distinct"):
            self.promotion(candidate_id="fixture-parent")
        with self.assertRaisesRegex(ValueError,"distinct"):
            self.promotion(candidate_id="fixture-backup")

    def test_forged_manifest_is_rejected(self):
        p=self.candidate()
        tampered=deepcopy(p)
        tampered["manifest"]["verification_status"]="NOT_VERIFIED"
        with self.assertRaisesRegex(ValueError,"unverified"): self.promotion(tampered)
        tampered=deepcopy(p)
        tampered["manifest"]["source_db_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"source"): self.promotion(tampered)
        tampered=deepcopy(p)
        tampered["manifest"]["counts"]["cards"]+=1
        with self.assertRaisesRegex(ValueError,"counts"): self.promotion(tampered)

    def test_head_post_write_readback_mismatch_is_rejected(self):
        h=self.promotion()
        changed=deepcopy(h)
        changed["generation"]=3
        with self.assertRaisesRegex(ValueError,"mismatch"):
            verify_activated_head(h,changed,scope="SYNTHETIC_TEST")

    def test_unresolved_and_duplicates_never_prepare(self):
        for names in (["架空の不明竜"],["架空の灰竜","架空の灰竜"]):
            b={"batch_id":"bad-batch","scope":"SYNTHETIC_TEST",
               "entries":[{"raw_name":name,"owned_count":1} for name in names]}
            p=preview_inventory(self.head,self.source,b,scope="SYNTHETIC_TEST")
            self.assertFalse(p["can_apply"])
            with self.assertRaisesRegex(ValueError,"unresolved"):
                prepare_inventory(self.head,self.source,b,"fixture-s2",p["preview_sha256"],scope="SYNTHETIC_TEST")

if __name__=="__main__": unittest.main()
