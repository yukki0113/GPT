"""User-accepted baseline into M6-4 and M6-1; synthetic DB only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import hashlib
import sqlite3
import unittest

from engine_m6.accepted_regulation import canonical_sha
from engine_m6.evaluate import evaluate_structural_candidate
from engine_m6.preflight import _read_only_audit
from test_m6_4 import base, fake_db


def policy(sha,entries,snapshot_id="fake-ban",effective="2026-11-01"):
    return {"schema":"md-regulation-accepted-baseline-v1","format":"MD_STANDARD",
            "master_sqlite_sha256":sha,
            "baseline_snapshot_id":snapshot_id,
            "baseline_effective_on":effective,
            "accepted_on":"2026-11-10",
            "acceptance":"USER_APPROVED_OPERATIONAL_BASELINE",
            "original_source_verification":"UNVERIFIED_SOURCE",
            "baseline_entries_sha256":canonical_sha(entries),
            "baseline_entries":entries,"events":[]}


class BaselineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"synthetic.sqlite"

    def test_evaluation_uses_approved_limit_instead_of_unknown(self):
        candidate,request,pins,cp=base()
        source_sha=fake_db(self.db,banned={"konami:100":1},
                           banlist_verification="UNVERIFIED_SOURCE")
        pins["sqlite_sha"]=source_sha
        p=policy(source_sha,{"konami:100":1})
        result=evaluate_structural_candidate(self.db,candidate,request,
                    source_pins=pins,cp_policy_bytes=cp,regulation_policy=p)
        self.assertEqual("BLOCKED",result["outcome"])
        self.assertIn("ACCEPTED_MD_REGULATION_VIOLATION:konami:100",
                      result["blocking_reasons"])
        self.assertTrue(result["m3"]["operational_baseline_accepted"])
        self.assertFalse(result["m3"]["official_md_legality_verified"])

    def test_unlisted_card_gets_three_and_no_unverified_warning(self):
        candidate,request,pins,cp=base()
        source_sha=fake_db(self.db,banlist_verification="UNVERIFIED_SOURCE")
        pins["sqlite_sha"]=source_sha
        p=policy(source_sha,{})
        result=evaluate_structural_candidate(self.db,candidate,request,
                    source_pins=pins,cp_policy_bytes=cp,regulation_policy=p)
        self.assertEqual("REVIEW_REQUIRED",result["outcome"])
        self.assertEqual([],result["blocking_reasons"])
        self.assertNotIn("MD_REGULATION_ONLY_UNVERIFIED_SOURCE",result["warnings"])
        self.assertNotIn("CARD_REGULATION_LIMIT_UNKNOWN",result["warnings"])
        self.assertNotIn("OFFICIAL_MD_LEGALITY_NOT_ESTABLISHED",result["warnings"])
        self.assertTrue(all(x["accepted_operational_limit"]==3
                            for x in result["cards"]))

    def _inventory_source(self):
        c=sqlite3.connect(self.db)
        c.executescript("""
            CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
            CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT);
            CREATE TABLE inventory(card_id TEXT PRIMARY KEY,known_state TEXT,
                                   owned_count INTEGER,updated_at TEXT);
            CREATE TABLE banlist_snapshots(snapshot_id TEXT PRIMARY KEY,
                format_id TEXT,effective_on TEXT,verification TEXT);
            CREATE TABLE banlist_entries(snapshot_id TEXT,card_id TEXT,max_copies INTEGER,
                PRIMARY KEY(snapshot_id,card_id));
        """)
        c.execute("INSERT INTO cards VALUES('konami:101','SYNTHETIC')")
        c.execute("INSERT INTO md_catalog VALUES('konami:101','R')")
        c.execute("INSERT INTO inventory VALUES('konami:101','KNOWN_POSITIVE',2,'2026-11-16')")
        c.execute("INSERT INTO banlist_snapshots VALUES('fake-ban','MD_STANDARD','2026-11-01','UNVERIFIED_SOURCE')")
        c.execute("INSERT INTO banlist_entries VALUES('fake-ban','konami:101',0)")
        c.commit();c.close()
        raw=self.db.read_bytes()
        return raw,hashlib.sha256(raw).hexdigest()

    def test_preflight_approved_banned_keeps_zero_and_rejects_adoption(self):
        raw,sha=self._inventory_source()
        p=policy(sha,{"konami:101":0})
        audit,stats=_read_only_audit(raw,sha,6,None,regulation_policy=p,
                                     as_of="2026-11-16")
        self.assertEqual(0,audit["owned_inventory_decisions"][0]["regulation_limit"])
        self.assertEqual("USER_APPROVED_OPERATIONAL_BASELINE",
                         audit["owned_inventory_decisions"][0]["regulation_confidence"])
        self.assertTrue(stats["operational_regulation_accepted"])
        with self.assertRaisesRegex(ValueError,"ACCEPTED_MD_REGULATION_BANNED_CARD"):
            _read_only_audit(raw,sha,6,{
                "konami:101":{"disposition":"ADOPT","reason":"fictional",
                              "main_or_extra":"MAIN","selected_quantity":1}},
                regulation_policy=p,as_of="2026-11-16")

    def test_approved_baseline_must_match_original_snapshot(self):
        raw,sha=self._inventory_source()
        p=policy(sha,{"konami:101":1})
        with self.assertRaisesRegex(ValueError,"SOURCE_SNAPSHOT_MISMATCH"):
            _read_only_audit(raw,sha,6,None,regulation_policy=p,
                             as_of="2026-11-16")

if __name__=="__main__":
    unittest.main()
