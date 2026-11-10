"""M3 pure synthetic checks; no private card texts, card lists or Drive data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from regulation_m3 import (validate_snapshot, legacy_vector_to_candidate, resolve_limit,
                           audit_catalog_ids, available_owned_copies, validate_cp_policy,
                           assess_deck_with_m3)

CHECKED = "2026-11-10T12:00:00+09:00"
def fixture_snapshot(*, date="2026-11-05", verified=False, rules=None, sid="fiction-snapshot"):
    return validate_snapshot({
        "schema_version":1, "snapshot_id":sid, "format_id":"MD_STANDARD",
        "effective_on":date, "checked_at":CHECKED, "source":"SYNTHETIC_FIXTURE",
        "source_sha256":"a"*64,
        "verification":"GAME_VERIFIED" if verified else "UNVERIFIED_SOURCE",
        "rules":{"konami:1001":1, "konami:1002":2} if rules is None else rules
    })

def cp_policy(verified=True):
    return {"policy_id":"fiction-cp","effective_on":"2026-11-01","checked_at":CHECKED,
            "source":"SYNTHETIC_FIXTURE",
            "verification":"GAME_VERIFIED" if verified else "UNVERIFIED_SOURCE",
            "cp_per_card":{"N":30,"R":30,"SR":30,"UR":30}}


class M3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/"fake.sqlite"
        s=Store.create(self.db)
        for card, rarity, owned in [
                ("konami:1001", "UR", 1), ("konami:1002", "SR", 0)]:
            s.add_card(card,int(card.split(":")[1]),"架空"+card)
            s.set_md_catalog(card,rarity=rarity,rarity_source="MD:SYNTHETIC",craftable="YES")
            s.set_inventory("batch-"+card,[{"card_id":card,"owned_count":owned}])
        self.recipe=[
            {"card_id":"konami:1001","quantity":1,"section":"MAIN","core":False},
            {"card_id":"konami:1002","quantity":3,"section":"MAIN","core":True},
        ]
        for n in range(36):
            card="konami:"+str(2000+n)
            s.add_card(card,2000+n,"架空"+card)
            s.set_md_catalog(card,rarity="N",rarity_source="MD:SYNTHETIC",craftable="YES")
            s.set_inventory("batch-"+card,[{"card_id":card,"owned_count":1}])
            self.recipe.append({"card_id":card,"quantity":1,"section":"MAIN","core":True})
        s.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_conversion_never_game_verified(self):
        raw=b'{"date":"2026-11-05","regulation":{"1001":0,"1002":2}}'
        s=legacy_vector_to_candidate(raw,checked_at=CHECKED)
        self.assertEqual(s["source_sha256"],hashlib.sha256(raw).hexdigest())
        self.assertEqual(s["verification"],"UNVERIFIED_SOURCE")
        self.assertEqual(s["rules"]["konami:1001"],0)
        self.assertEqual(audit_catalog_ids(self.db,s)["missing_catalog_ids"],0)
        with self.assertRaisesRegex(ValueError,"limit"):
            legacy_vector_to_candidate(b'{"date":"2026-11-05","regulation":{"1001":4}}',checked_at=CHECKED)

    def test_unlisted_and_no_snapshot_do_not_mean_three(self):
        s=fixture_snapshot(verified=True)
        r=resolve_limit([s],card_id="konami:2035",as_of="2026-11-10")
        self.assertEqual(r["status"],"UNLISTED_UNKNOWN")
        self.assertIsNone(r["allowed"])
        self.assertEqual(resolve_limit([s],card_id="konami:1001",as_of="2026-11-04")["status"],"NO_APPLICABLE_SNAPSHOT")
        self.assertEqual(resolve_limit([s],card_id="konami:1001",as_of="2026-11-10",format_id="MD_EVENT")["status"],"NO_APPLICABLE_SNAPSHOT")

    def test_boundary_zero_one_two_three_and_invalid(self):
        for bound in range(4):
            s=fixture_snapshot(verified=True,rules={"konami:1001":bound})
            r=resolve_limit([s],card_id="konami:1001",as_of="2026-11-10")
            self.assertEqual(r["allowed"],bound)
        with self.assertRaisesRegex(ValueError,"limit"):
            fixture_snapshot(rules={"konami:1001":True})
        with self.assertRaisesRegex(ValueError,"limit"):
            fixture_snapshot(rules={"konami:1001":-1})
        with self.assertRaisesRegex(ValueError,"limit"):
            fixture_snapshot(rules={"konami:1001":4})

    def test_new_unverified_blocks_verified_old(self):
        old=fixture_snapshot(date="2026-10-06",verified=True,rules={"konami:1001":3},sid="old")
        new=fixture_snapshot(date="2026-11-05",rules={"konami:1001":0},sid="new")
        old_answer=resolve_limit([old,new],card_id="konami:1001",as_of="2026-11-01")
        self.assertEqual(old_answer["allowed"],3)
        current=resolve_limit([old,new],card_id="konami:1001",as_of="2026-11-10")
        self.assertEqual(current["status"],"CANDIDATE_ONLY")
        self.assertIsNone(current["allowed"])
        self.assertEqual(current["candidate_max_copies"],0)

    def test_duplicate_date_fails_closed(self):
        s=fixture_snapshot(verified=True,sid="one")
        s2=fixture_snapshot(verified=True,sid="two")
        r=resolve_limit([s,s2],card_id="konami:1001",as_of="2026-11-10")
        self.assertEqual(r["status"],"AMBIGUOUS_SNAPSHOT")
        self.assertIsNone(r["allowed"])

    def test_invalid_snapshot_provenance_and_date(self):
        s=fixture_snapshot()
        for key,value in (("effective_on","2026/11/05"),("checked_at","2026-11-10"),
                          ("source",""),("verification","OFFICIAL"),("source_sha256","0"),
                          ("format_id","OCG"),("schema_version",True)):
            bad=deepcopy(s)
            bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate_snapshot(bad)

    def test_candidate_rule_cannot_fail_or_pass_legality(self):
        s=fixture_snapshot(rules={"konami:1001":0,"konami:1002":2})
        r=assess_deck_with_m3(self.db,self.recipe,snapshots=[s],as_of="2026-11-10",
                              cp_policy=cp_policy(False))
        self.assertEqual(r["status"],"INDETERMINATE")
        self.assertEqual(r["regulation_context"]["candidate_card_count"],2)
        self.assertIn("UNKNOWN_BANLIST:konami:1002",r["unknowns"])
        self.assertNotIn("BANLIST_EXCEEDED:konami:1002",r["errors"])
        self.assertIn("CP_POLICY_UNVERIFIED",r["unknowns"])

    def test_verified_rule_can_reject_over_limit(self):
        s=fixture_snapshot(verified=True)
        r=assess_deck_with_m3(self.db,self.recipe,snapshots=[s],as_of="2026-11-10",
                              cp_policy=cp_policy(True))
        self.assertEqual(r["status"],"FAIL")
        self.assertIn("BANLIST_EXCEEDED:konami:1002",r["errors"])
        self.assertEqual(r["cards"][0]["available_owned_copies"],1)

    def test_available_owned_is_min_and_unknown_stays_unknown(self):
        verified={"status":"VERIFIED","allowed":2}
        self.assertEqual(available_owned_copies(3,verified),2)
        self.assertIsNone(available_owned_copies(None,verified))
        self.assertEqual(available_owned_copies(None,{"status":"VERIFIED","allowed":0}),0)
        self.assertIsNone(available_owned_copies(3,{"status":"CANDIDATE_ONLY","allowed":None}))

    def test_cp_by_currency_not_interchangeable(self):
        # 3 SR cards are missing => 90 CP-SR; plentiful N CP cannot cover it.
        s=fixture_snapshot(verified=True,rules={"konami:1001":1,"konami:1002":3})
        r=assess_deck_with_m3(self.db,self.recipe,snapshots=[s],as_of="2026-11-10",
                              cp_policy=cp_policy(True),mode="CP_BUDGET",
                              cp_budget_by_rarity={"SR":60,"N":10000})
        self.assertEqual(r["cp_estimate"]["SR"],90)
        self.assertIn("CP_SR_BUDGET_EXCEEDED",r["errors"])
        self.assertEqual(r["crafting_context"]["estimate_is_confirmed"],True)
        self.assertNotIn("CP_BUDGET_UNVERIFIABLE",r["unknowns"])

    def test_candidate_cp_budget_is_not_confirmed_failure(self):
        s=fixture_snapshot(verified=True,rules={"konami:1001":1,"konami:1002":3})
        r=assess_deck_with_m3(self.db,self.recipe,snapshots=[s],as_of="2026-11-10",
                              cp_policy=cp_policy(False),mode="CP_BUDGET",
                              cp_budget_by_rarity={"SR":60})
        self.assertEqual(r["status"],"INDETERMINATE")
        self.assertNotIn("CP_SR_BUDGET_EXCEEDED",r["errors"])
        self.assertIn("CP_RARITY_BUDGET_UNVERIFIABLE",r["unknowns"])

    def test_cp_budget_validation(self):
        s=fixture_snapshot(verified=True)
        with self.assertRaises(ValueError):
            assess_deck_with_m3(self.db,self.recipe,snapshots=[s],as_of="2026-11-10",
                                cp_policy=cp_policy(True),cp_budget_by_rarity={"SR":True})
        bad=cp_policy()
        bad["cp_per_card"]["UR"]=0
        with self.assertRaisesRegex(ValueError,"CP amount"): validate_cp_policy(bad)

    def test_real_snapshot_requires_name_binding_not_inventory(self):
        s=fixture_snapshot(verified=True,rules={"konami:1001":1,"konami:1002":3})
        p=cp_policy(True)
        # No profile or personal inventory input is sent to the regulation source.
        r=assess_deck_with_m3(self.db,self.recipe,snapshots=[s],as_of="2026-11-10",cp_policy=p)
        self.assertEqual(r["main_count"],40)
        self.assertEqual(r["cp_estimate"]["SR"],90)
        self.assertEqual(r["crafting_context"]["verification"],"GAME_VERIFIED")
        self.assertEqual(r["status"],"INDETERMINATE")  # 36 unlisted rules fail closed.


    def _confirmed_cp(self):
        p=cp_policy(True)
        p["verification"]="USER_CONFIRMED"
        p["source"]="USER_CONFIRMATION: synthetic test"
        return p

    def _complete_verified_regulation(self):
        rules={item["card_id"]:3 for item in self.recipe}
        rules["konami:1001"]=1
        return fixture_snapshot(verified=True,rules=rules)

    def test_user_confirmed_cp_can_pass_with_complete_evidence(self):
        r=assess_deck_with_m3(self.db,self.recipe,
            snapshots=[self._complete_verified_regulation()],
            as_of="2026-11-10", mode="CP_BUDGET",
            cp_policy=self._confirmed_cp(),
            cp_budget_by_rarity={"SR":90})
        self.assertEqual(r["status"],"PASS")
        self.assertEqual(r["cp_estimate"]["SR"],90)
        self.assertTrue(r["crafting_context"]["price_rule_confirmed"])
        self.assertTrue(r["crafting_context"]["estimate_is_confirmed"])
        self.assertEqual(r["crafting_context"]["verification"],"USER_CONFIRMED")
        self.assertNotIn("CP_POLICY_UNVERIFIED",r["unknowns"])

    def test_user_confirmed_cp_cannot_spend_another_rarity(self):
        r=assess_deck_with_m3(self.db,self.recipe,
            snapshots=[self._complete_verified_regulation()],
            as_of="2026-11-10", mode="CP_BUDGET",
            cp_policy=self._confirmed_cp(),
            cp_budget_by_rarity={"SR":60,"N":9999})
        self.assertEqual(r["status"],"FAIL")
        self.assertIn("CP_SR_BUDGET_EXCEEDED",r["errors"])

    def test_missing_currency_balance_is_not_silent_infinity(self):
        r=assess_deck_with_m3(self.db,self.recipe,
            snapshots=[self._complete_verified_regulation()],
            as_of="2026-11-10", mode="CP_BUDGET",
            cp_policy=self._confirmed_cp(),
            cp_budget_by_rarity={"N":9999})
        self.assertEqual(r["status"],"INDETERMINATE")
        self.assertIn("CP_BALANCE_UNKNOWN:SR",r["unknowns"])

    def test_user_confirmation_needs_attributable_source(self):
        p=self._confirmed_cp()
        p["source"]="SYNTHETIC_FIXTURE"
        with self.assertRaisesRegex(ValueError,"provenance"):
            validate_cp_policy(p)

    def test_craftability_unknown_blocks_confirmed_spend(self):
        import sqlite3
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE md_catalog SET craftable='UNKNOWN' WHERE card_id='konami:1002'")
        r=assess_deck_with_m3(self.db,self.recipe,
            snapshots=[self._complete_verified_regulation()],
            as_of="2026-11-10", mode="CP_BUDGET",
            cp_policy=self._confirmed_cp(),
            cp_budget_by_rarity={"SR":90})
        self.assertEqual(r["status"],"INDETERMINATE")
        self.assertTrue(r["crafting_context"]["price_rule_confirmed"])
        self.assertFalse(r["crafting_context"]["estimate_is_confirmed"])
        self.assertIn("UNKNOWN_CRAFTABILITY:konami:1002",r["unknowns"])
        self.assertIn("CP_RARITY_BUDGET_UNVERIFIABLE",r["unknowns"])

if __name__ == "__main__": unittest.main()
