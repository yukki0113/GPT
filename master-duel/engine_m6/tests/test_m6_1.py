"""M6-1 synthetic read-only integration tests. No private card/owned rows."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile
import json
import sqlite3
import unittest

from engine_m6.preflight import preflight_from_verified_bytes


def digest(raw):
    return sha256(raw).hexdigest()


def fixture():
    with TemporaryDirectory() as d:
        p = Path(d) / "master_duel.sqlite"
        c = sqlite3.connect(p)
        c.executescript("""
        CREATE TABLE cards(card_id TEXT PRIMARY KEY);
        CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT);
        CREATE TABLE inventory(card_id TEXT PRIMARY KEY, known_state TEXT,
                               owned_count INTEGER, updated_at TEXT);
        CREATE TABLE banlist_snapshots(snapshot_id TEXT PRIMARY KEY,
            format_id TEXT,effective_on TEXT,verification TEXT);
        CREATE TABLE banlist_entries(snapshot_id TEXT,card_id TEXT,max_copies INTEGER);
        INSERT INTO cards VALUES ('konami:101'),('konami:102'),('konami:103');
        INSERT INTO md_catalog VALUES ('konami:101','UR'),('konami:102','R'),('konami:103','SR');
        INSERT INTO inventory VALUES ('konami:101','KNOWN_POSITIVE',2,'2026-11-11 00:00:01');
        INSERT INTO inventory VALUES ('konami:102','KNOWN_ZERO',0,'2026-11-11 00:00:02');
        INSERT INTO banlist_snapshots VALUES ('fake-b1','MD_STANDARD','2026-11-01','UNVERIFIED_SOURCE');
        INSERT INTO banlist_entries VALUES ('fake-b1','konami:101',0);
        """)
        c.commit()
        c.close()
        raw = p.read_bytes()
    sink = BytesIO()
    with ZipFile(sink,"w") as z:
        z.writestr("master_duel.sqlite",raw)
    zipped = sink.getvalue()
    head={"scope":"PRODUCTION","system":"master-duel","generation":3,
          "current_snapshot":{"schema_version":1,"db_sha256":digest(raw),
                              "zip_sha256":digest(zipped),
                              "drive_file_id":"fake-file-id"}}
    h=json.dumps(head,sort_keys=True).encode()
    cp=json.dumps({"cp_per_card":{"N":30,"R":30,"SR":30,"UR":30},
                   "effective_on":"2026-11-10",
                   "verification":"USER_CONFIRMED"}).encode()
    return {"head_before":h,"head_after":h,"expected_head_sha256":digest(h),
            "snapshot_zip":zipped,"cp_policy_bytes":cp,
            "expected_cp_policy_sha256":digest(cp),
            "m5_zip":b"synthetic-sidecar","m5_manifest":b"synthetic-manifest",
            "expected_m5_zip_sha256":digest(b"synthetic-sidecar"),
            "expected_m5_manifest_sha256":digest(b"synthetic-manifest"),
            "retrieved_at":"2026-11-11T05:00:00+00:00"}


class TestM61(unittest.TestCase):
    def setUp(self):
        self.p=patch("engine_m6.preflight.open_sidecar",
                     return_value={"knowledge":{"knowledge_version":4}})
        self.mock=self.p.start()
        self.addCleanup(self.p.stop)

    def run_gate(self, **overrides):
        args=fixture()
        args.update(overrides)
        return preflight_from_verified_bytes(**args)

    def test_two_card_inventory_fully_enumerated(self):
        r=self.run_gate()
        self.assertEqual(2,r["stats"]["registered_count"])
        self.assertEqual(2,r["audit"]["inventory_rows_reviewed"])
        self.assertEqual("PARTIAL",r["preflight_status"])
        self.assertEqual(2,r["stats"]["unadjudicated_count"])
        self.assertEqual({"KNOWN_ZERO":1,"KNOWN_POSITIVE":1,"UNKNOWN":0},r["stats"]["states"])

    def test_candidate_banlist_zero_not_confirmed(self):
        r=self.run_gate()
        self.assertEqual("UNVERIFIED_SOURCE",r["stats"]["m3_verification"])
        for row in r["audit"]["owned_inventory_decisions"]:
            self.assertIsNone(row["regulation_limit"])
        self.assertFalse(r["current_md_legality_verified"])

    def test_no_undocumented_ownership_guess(self):
        r=self.run_gate()
        self.assertEqual({"konami:101","konami:102"},
                         {x["card_id"] for x in r["audit"]["owned_inventory_decisions"]})
        self.assertNotIn("konami:103",
                         {x["card_id"] for x in r["audit"]["owned_inventory_decisions"]})

    def test_no_decision_override_outside_registered(self):
        with self.assertRaises(ValueError):
            self.run_gate(decision_overrides={"konami:103":{
                "disposition":"ADOPT","reason":"fake","main_or_extra":"MAIN",
                "selected_quantity":1}})

    def test_candidate_zero_stays_review_even_if_considered(self):
        r=self.run_gate(decision_overrides={
            "konami:101":{"disposition":"CONSIDER","reason":"candidate generic",
                           "main_or_extra":"NONE","selected_quantity":0},
            "konami:102":{"disposition":"EXCLUDE","reason":"no deck role",
                           "main_or_extra":"NONE","selected_quantity":0}})
        self.assertEqual("PARTIAL",r["preflight_status"])
        self.assertTrue(any(x["disposition"] == "REVIEW_REQUIRED" for x in
                            r["audit"]["owned_inventory_decisions"]))
        self.assertFalse(r["current_md_legality_verified"])

    def test_unverified_candidate_zero_cannot_be_adopted(self):
        with self.assertRaisesRegex(ValueError,"candidate banned"):
            self.run_gate(decision_overrides={"konami:101":{
                "disposition":"ADOPT","reason":"wish to use",
                "main_or_extra":"MAIN","selected_quantity":1}})

    def test_adopt_cannot_exceed_known_copies(self):
        with self.assertRaisesRegex(ValueError,"exceeds confirmed"):
            self.run_gate(decision_overrides={"konami:102":{
                "disposition":"ADOPT","reason":"wish to use",
                "main_or_extra":"MAIN","selected_quantity":1}})

    def test_head_changed_during_read_rejected(self):
        with self.assertRaisesRegex(ValueError,"HEAD"):
            self.run_gate(head_after=b"other head")

    def test_head_external_sha_rejected(self):
        with self.assertRaisesRegex(ValueError,"HEAD"):
            self.run_gate(expected_head_sha256="0"*64)

    def test_zip_tampering_rejected(self):
        with self.assertRaisesRegex(ValueError,"ZIP"):
            self.run_gate(snapshot_zip=b"not zip")

    def test_unexpected_zip_member_rejected(self):
        a=fixture()
        io=BytesIO()
        with ZipFile(io,"w") as z:z.writestr("other.db",b"anything")
        a["snapshot_zip"]=io.getvalue()
        obj=json.loads(a["head_before"])
        obj["current_snapshot"]["zip_sha256"]=digest(a["snapshot_zip"])
        a["head_before"]=json.dumps(obj,sort_keys=True).encode()
        a["head_after"]=a["head_before"]
        a["expected_head_sha256"]=digest(a["head_before"])
        with self.assertRaisesRegex(ValueError,"members"):
            self.run_gate(**a)

    def test_missing_c5_is_fail_closed(self):
        with self.assertRaises(ValueError):
            self.run_gate(m5_zip=None)

    def test_unsupported_cp_policy_rejected(self):
        p=json.dumps({"cp_per_card":{"UR":0},"verification":"USER_CONFIRMED"}).encode()
        with self.assertRaises(ValueError):
            self.run_gate(cp_policy_bytes=p)

    def test_cp_external_pin_rejected(self):
        with self.assertRaisesRegex(ValueError,"CP policy external SHA"):
            self.run_gate(expected_cp_policy_sha256="a"*64)

    def test_owned_catalog_requires_external_pin(self):
        raw=b'{"catalog_generation":2}'
        with self.assertRaisesRegex(ValueError,"owned catalog external SHA"):
            self.run_gate(owned_deck_catalog_bytes=raw)
        r=self.run_gate(owned_deck_catalog_bytes=raw,
                        expected_owned_deck_catalog_sha256=digest(raw))
        self.assertEqual(digest(raw),r["source_pins"]["owned_deck_catalog_sha"])

    def test_m5_external_pins_passed_to_adapter(self):
        self.run_gate()
        self.assertEqual(digest(b"synthetic-sidecar"),
                         self.mock.call_args.kwargs["expected_zip_sha256"])

    def test_source_pins_partial_only_for_not_fetched_indexes(self):
        r=self.run_gate()
        self.assertEqual("PARTIAL",r["source_pin_contract_status"])
        self.assertIn("m4_index_sha",r["source_pins"]["missing_reasons"])
        self.assertEqual(3,r["source_pins"]["inventory_generation"])
        self.assertEqual(3,r["source_pins"]["m3_generation"])

    def test_sidecar_wrong_master_pin_fails_with_real_adapter_requirement(self):
        self.mock.side_effect=ValueError("master DB pin mismatch")
        with self.assertRaisesRegex(ValueError,"master DB"):
            self.run_gate()

    def test_full_result_not_persisted(self):
        r=self.run_gate()
        self.assertFalse(r["m5_recommendation_eligible"])
        self.assertFalse(r["owned_deck_counts_are_inventory"])


if __name__=="__main__":
    unittest.main()
