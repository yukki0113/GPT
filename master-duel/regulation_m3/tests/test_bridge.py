"""Synthetic-only end-to-end checks of HEAD ZIP + banlist + CP policy."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from zip_store.archive import pack
from regulation_m3.bridge import assess_from_private_sources

class M3PrivateBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        dbpath=self.root/"source.sqlite"
        store=Store.create(dbpath)
        self.recipe=[]
        for n in range(40):
            cid="konami:"+str(1000+n)
            store.add_card(cid,1000+n,"架空"+str(n))
            rarity="SR" if n==0 else "N"
            store.set_md_catalog(cid,rarity=rarity,rarity_source="MD:SYNTHETIC",
                                 craftable="YES")
            store.set_inventory("batch-"+cid,[{"card_id":cid,"owned_count":0 if n==0 else 1}])
            self.recipe.append({"card_id":cid,"quantity":1,"section":"MAIN","core":True})
        store.db.execute("INSERT INTO banlist_snapshots "
                         "(snapshot_id,format_id,effective_on,source,acquired_at,verification) "
                         "VALUES (?,?,?,?,?,?)",
                         ("synthetic-ban","MD_STANDARD","2026-11-05",
                          "SYNTHETIC_TEST [sha256:"+"a"*64+"]",
                          "2026-11-10T12:00:00+09:00","UNVERIFIED_SOURCE"))
        for item in self.recipe:
            store.db.execute("INSERT INTO banlist_entries VALUES (?,?,?)",
                             ("synthetic-ban",item["card_id"],3))
        store.close()
        self.source,self.meta=pack(dbpath)
        self.head={"system":"master-duel","scope":"SYNTHETIC_TEST",
                   "generation":3,"writer_policy":"SINGLE_WRITER_NO_ATOMIC_CAS",
                   "sqlite_schema_version":1,
                   "current_snapshot":{
                       "snapshot_id":"synthetic-gen3","drive_file_id":"fiction-id",
                       "classification":"SYNTHETIC_FIXTURE","schema_version":1,
                       "zip_sha256":self.meta["zip_sha256"],"db_sha256":self.meta["db_sha256"]}}
        self.path=self.root/"cp.json"
        self.policy={"policy_id":"fixture-cp-2026-11-10",
            "effective_on":"2026-11-10",
            "checked_at":"2026-11-10T12:00:00+09:00",
            "source":"USER_CONFIRMATION: synthetic test",
            "verification":"USER_CONFIRMED",
            "cp_per_card":{"N":30,"R":30,"SR":30,"UR":30}}
        self._write_policy()

    def _write_policy(self):
        self.path.write_text(json.dumps(self.policy,sort_keys=True),encoding="utf-8")
        self.policy_sha=sha256(self.path.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def assess(self,*,as_of="2026-11-10",head=None,raw=None,sha=None):
        return assess_from_private_sources(
            self.head if head is None else head,
            self.source if raw is None else raw,
            self.path,self.policy_sha if sha is None else sha,self.recipe,
            as_of=as_of,mode="CP_BUDGET",
            cp_budget_by_rarity={"SR":30},scope="SYNTHETIC_TEST")

    def test_verified_policy_and_candidate_banlist_have_independent_status(self):
        old=sha256(self.source).hexdigest()
        r=self.assess()
        self.assertEqual(r["cp_estimate"]["SR"],30)
        self.assertEqual(r["source_context"]["head_generation"],3)
        self.assertEqual(r["source_context"]["cp_policy_status"],"USER_CONFIRMED")
        self.assertTrue(r["crafting_context"]["estimate_is_confirmed"])
        self.assertEqual(r["regulation_context"]["candidate_card_count"],40)
        self.assertEqual(r["status"],"INDETERMINATE")
        self.assertIn("UNKNOWN_BANLIST:konami:1000",r["unknowns"])
        self.assertEqual(sha256(self.source).hexdigest(),old)

    def test_future_policy_not_silently_used(self):
        r=self.assess(as_of="2026-11-09")
        self.assertEqual(r["source_context"]["cp_policy_status"],"NO_APPLICABLE_POLICY")
        self.assertIsNone(r["cp_estimate"])
        self.assertFalse(r["crafting_context"]["price_rule_confirmed"])

    def test_tampered_policy_rejected(self):
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            self.assess(sha="1"*64)

    def test_tampered_zip_or_head_rejected(self):
        with self.assertRaisesRegex(ValueError,"ZIP SHA-256 mismatch"):
            self.assess(raw=self.source+b"x")
        bad=json.loads(json.dumps(self.head))
        bad["current_snapshot"]["db_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"SQLite integrity/version mismatch"):
            self.assess(head=bad)

    def _recorded_no_registry(self):
        from regulation_m3 import record_exception
        base={"schema_version":1,"registry_id":"synthetic-test-v1",
              "updated_at":"2026-11-10T14:16:00+09:00","entries":[]}
        result=record_exception(base,card_id="konami:1000",
                 observed_at="2026-11-10T14:16:00+09:00",
                 source="USER_REPORT",reason="Craft button unavailable")
        path=self.root/"exceptions.json"
        path.write_text(json.dumps(result,sort_keys=True),encoding="utf-8")
        return path,sha256(path.read_bytes()).hexdigest()

    def test_private_exception_registry_blocks_reported_no_shortage(self):
        path,digest=self._recorded_no_registry()
        r=assess_from_private_sources(
            self.head,self.source,self.path,self.policy_sha,self.recipe,
            as_of="2026-11-10",mode="CP_BUDGET",
            cp_budget_by_rarity={"SR":30},scope="SYNTHETIC_TEST",
            craftability_registry_path=path,
            craftability_registry_sha256=digest)
        self.assertEqual(r["candidate_recommendation"]["status"],"HOLD")
        self.assertEqual(r["craftability_gate"]["status"],"HOLD_CONFIRMED_NO")
        self.assertIn("UNCRAFTABLE_SHORTAGE:konami:1000",r["errors"])
        self.assertEqual(r["source_context"]["craftability_registry_sha256"],digest)

    def test_exception_registry_requires_exact_verified_sha(self):
        path,_=self._recorded_no_registry()
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            assess_from_private_sources(self.head,self.source,self.path,
                self.policy_sha,self.recipe,as_of="2026-11-10",
                scope="SYNTHETIC_TEST",
                craftability_registry_path=path,
                craftability_registry_sha256="a"*64)
        with self.assertRaisesRegex(ValueError,"required together"):
            assess_from_private_sources(self.head,self.source,self.path,
                self.policy_sha,self.recipe,as_of="2026-11-10",
                scope="SYNTHETIC_TEST",craftability_registry_path=path)

if __name__=="__main__":
    unittest.main()
