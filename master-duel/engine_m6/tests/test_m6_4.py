"""M6-4 synthetic conservative cost and MD regulation tests (no real card data)."""
import copy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from engine_m6.evaluate import evaluate_structural_candidate
from engine_m6.inputs import request_from_interpretation
from engine_m6.schema import SCHEMA, REQUIRED_PINS, SHA_PINS


def h(data):
    return sha256(data).hexdigest()


def base():
    """13*3 + 1 = 40 MAIN, 7 EXTRA. One fake UR in MAIN/EX."""
    cards = [{"card_id":f"konami:{100+i}","quantity":3 if i<13 else 1,
              "section":"MAIN","role":"FAKE","essentiality":"UNKNOWN",
              "reason":"fictional reference","evidence_ids":["fake-src"]}
             for i in range(14)]
    cards.extend({"card_id":f"konami:{300+i}","quantity":1,"section":"EXTRA",
                  "role":"FAKE","essentiality":"UNKNOWN",
                  "reason":"fictional reference","evidence_ids":["fake-src"]}
                 for i in range(7))
    cand={"schema":SCHEMA,"candidate_id":"fake-deck","theme":"FICTIONAL",
          "source_kind":"M5C_VARIANT","lineage":{"synthetic":True},
          "cards":cards,"required_core_ids":[],"route_ids":[],
          "reasons_by_card":{row["card_id"]:"fictional" for row in cards},
          "reasons_by_omitted_owned_card":{},"m5_status":"REVIEW_REQUIRED",
          "declared_main":40,"declared_extra":7}
    request=request_from_interpretation(
        request_id="fake",as_of="2026-11-11T10:00:00+09:00",
        theme_query="FICTIONAL")
    policy={"cp_per_card":{"N":30,"R":30,"SR":30,"UR":30},
            "verification":"USER_CONFIRMED","effective_on":"2026-11-10"}
    policy_raw=json.dumps(policy,sort_keys=True).encode()
    pins={key:"a"*64 if key in SHA_PINS else "synthetic" for key in REQUIRED_PINS}
    pins.update({"head_generation":3,"head_zip_generation":3,
                 "inventory_generation":3,"m3_generation":3,
                 "cp_policy_sha":h(policy_raw),
                 "cp_effective_on":policy["effective_on"],
                 "m3_snapshot":"fake-ban","m3_effective_on":"2026-11-01",
                 "m3_verification":"UNVERIFIED_SOURCE",
                 "missing_reasons":{}})
    return cand,request,pins,policy_raw


def fake_db(path, *, ur_ids=(), inventory=None, rarity_verification="UNVERIFIED_SOURCE",
            banlist_verification="UNVERIFIED_SOURCE", banned=None,
            craftable="UNKNOWN", ban_effective="2026-11-01"):
    inventory = inventory or {}
    banned=banned or {}
    c=sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT,
            craftable TEXT,verification TEXT);
        CREATE TABLE inventory(card_id TEXT PRIMARY KEY,known_state TEXT,owned_count INTEGER);
        CREATE TABLE banlist_snapshots(snapshot_id TEXT PRIMARY KEY,
            format_id TEXT,effective_on TEXT,verification TEXT);
        CREATE TABLE banlist_entries(snapshot_id TEXT,card_id TEXT,max_copies INTEGER,
            PRIMARY KEY(snapshot_id,card_id));
    """)
    all_ids=[f"konami:{100+i}" for i in range(14)]+[f"konami:{300+i}" for i in range(7)]
    for cid in all_ids:
        c.execute("INSERT INTO md_catalog VALUES (?,?,?,?)",
                  (cid,"UR" if cid in ur_ids else "SR" if cid=="konami:101" else "R",
                   craftable,rarity_verification))
        if cid in inventory:
            owned=inventory[cid]
            c.execute("INSERT INTO inventory VALUES (?,?,?)",
                      (cid,"KNOWN_ZERO" if owned==0 else "KNOWN_POSITIVE",owned))
    c.execute("INSERT INTO banlist_snapshots VALUES(?,?,?,?)",
              ("fake-ban","MD_STANDARD",ban_effective,banlist_verification))
    for cid,count in banned.items():
        c.execute("INSERT INTO banlist_entries VALUES(?,?,?)",("fake-ban",cid,count))
    c.commit()
    c.close()
    return h(Path(path).read_bytes())


class M64EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/"fake.sqlite"
        self.candidate,self.request,self.pins,self.policy_raw=base()

    def evaluate(self, *, ur_ids=(), inventory=None, banned=None,
                 banlist_verification="UNVERIFIED_SOURCE",craftable="UNKNOWN",
                 rarity_verification="UNVERIFIED_SOURCE",ban_effective="2026-11-01",
                 trusted_core_ids=(),core_verification="UNKNOWN",cp_balance=None,
                 pins_override=None,request_override=None,candidate_override=None,
                 policy_bytes=None):
        self.file.unlink(missing_ok=True)
        digest=fake_db(self.file,ur_ids=ur_ids,inventory=inventory,banned=banned,
                       banlist_verification=banlist_verification,craftable=craftable,
                       rarity_verification=rarity_verification,ban_effective=ban_effective)
        pins=copy.deepcopy(self.pins)
        pins["sqlite_sha"]=digest
        pins["m3_verification"]=banlist_verification
        pins["m3_effective_on"]=ban_effective
        if pins_override:pins.update(pins_override)
        return evaluate_structural_candidate(self.file,candidate_override or self.candidate,
            request_override or self.request,source_pins=pins,
            cp_policy_bytes=self.policy_raw if policy_bytes is None else policy_bytes,
            trusted_core_ids=trusted_core_ids,core_verification=core_verification,
            cp_balance=cp_balance)

    def test_all_r_no_ur_configurational_but_core_unknown(self):
        out=self.evaluate()
        self.assertEqual("PASS",out["mode_gates"]["STRICT_NO_UR"])
        self.assertEqual("PASS",out["mode_gates"]["NEW_UR_CRAFT_ZERO"])
        self.assertEqual("INDETERMINATE",out["mode_gates"]["CORE_UR_ZERO"])
        self.assertEqual("REVIEW_REQUIRED",out["outcome"])
        self.assertFalse(out["recommendation_eligible"])

    def test_all_ur_owned_can_pass_new_ur_but_not_strict(self):
        out=self.evaluate(ur_ids={"konami:100"},inventory={"konami:100":3})
        self.assertEqual("PASS",out["mode_gates"]["NEW_UR_CRAFT_ZERO"])
        self.assertEqual("FAIL",out["mode_gates"]["STRICT_NO_UR"])
        self.assertEqual("INDETERMINATE",out["requested_mode_gate"])

    def test_known_missing_ur_fails_default(self):
        out=self.evaluate(ur_ids={"konami:100"},inventory={"konami:100":1})
        self.assertEqual("FAIL",out["mode_gates"]["NEW_UR_CRAFT_ZERO"])
        self.assertEqual(2,out["new_needed_lower_by_rarity"]["UR"])
        self.assertEqual("BLOCKED",out["outcome"])

    def test_unknown_ur_not_assumed_owned_or_zero(self):
        out=self.evaluate(ur_ids={"konami:100"})
        self.assertEqual("INDETERMINATE",out["mode_gates"]["NEW_UR_CRAFT_ZERO"])
        self.assertEqual(0,out["required_cp_lower_by_rarity"]["UR"])
        self.assertEqual(90,out["required_cp_upper_by_rarity"]["UR"])
        self.assertIsNone(next(x for x in out["cards"]
                               if x["card_id"]=="konami:100")["new_needed"])

    def test_verified_core_ur_fails_core_gate_even_if_owned(self):
        out=self.evaluate(ur_ids={"konami:100"},inventory={"konami:100":3},
                          trusted_core_ids=["konami:100"],core_verification="REVIEWED")
        self.assertEqual("FAIL",out["mode_gates"]["CORE_UR_ZERO"])
        self.assertEqual("PASS",out["mode_gates"]["NEW_UR_CRAFT_ZERO"])
        self.assertEqual("BLOCKED",out["outcome"])

    def test_source_only_core_cannot_pass_even_if_r(self):
        out=self.evaluate(trusted_core_ids=["konami:101"],
                          core_verification="REVIEW_REQUIRED")
        self.assertEqual("INDETERMINATE",out["mode_gates"]["CORE_UR_ZERO"])

    def test_trusted_sr_core_non_ur_passes_core_gate(self):
        out=self.evaluate(trusted_core_ids=["konami:101"],core_verification="REVIEWED")
        self.assertEqual("PASS",out["mode_gates"]["CORE_UR_ZERO"])
        self.assertEqual("PASS",out["requested_mode_gate"])
        self.assertEqual("REVIEW_REQUIRED",out["outcome"])

    def test_ur_budget_bounds(self):
        req=copy.deepcopy(self.request)
        req["mode"]="UR_BUDGET"
        req["mode_origin"]="EXPLICIT"
        req["constraints"]["new_ur_max"]=1
        out=self.evaluate(ur_ids={"konami:100"},request_override=req)
        self.assertEqual("INDETERMINATE",out["requested_mode_gate"])
        out=self.evaluate(ur_ids={"konami:100"},
                          inventory={"konami:100":0},request_override=req)
        self.assertEqual("FAIL",out["requested_mode_gate"])

    def test_cp_budget_by_rarity_not_cross_substituted(self):
        req=copy.deepcopy(self.request)
        req["mode"]="CP_BUDGET"
        req["mode_origin"]="EXPLICIT"
        req["constraints"]["cp_budget_by_rarity"]={"SR":0,"R":9999}
        out=self.evaluate(inventory={"konami:101":0},request_override=req)
        self.assertEqual("FAIL",out["requested_mode_gate"])

    def test_cp_balance_not_assumed_when_absent(self):
        out=self.evaluate()
        self.assertEqual("INDETERMINATE",out["cp_balance_status"])
        out=self.evaluate(inventory={"konami:101":0},
                          cp_balance={"N":0,"R":10000,"SR":0,"UR":0})
        self.assertEqual("FAIL",out["cp_balance_status"])

    def test_candidate_banlist_zero_is_warning_not_certified(self):
        out=self.evaluate(banned={"konami:100":0})
        self.assertIn("UNVERIFIED_BANLIST_CONFLICT:konami:100",out["warnings"])
        self.assertEqual("UNVERIFIED_SOURCE",out["m3"]["verification"])
        self.assertFalse(out["m3"]["official_md_legality_verified"])

    def test_game_verified_banlist_zero_blocks(self):
        out=self.evaluate(banned={"konami:100":0},
                          banlist_verification="GAME_VERIFIED")
        self.assertIn("CONFIRMED_BANLIST_VIOLATION:konami:100",out["blocking_reasons"])
        self.assertEqual("BLOCKED",out["outcome"])

    def test_wrong_m3_snapshot_pin_fails(self):
        with self.assertRaisesRegex(ValueError,"M3 snapshot pin"):
            self.evaluate(pins_override={"m3_snapshot":"not-the-source"})

    def test_wrong_db_sha_fails(self):
        with self.assertRaisesRegex(ValueError,"SQLite bytes"):
            self.evaluate(pins_override={"sqlite_sha":"f"*64})

    def test_wrong_cp_raw_sha_fails(self):
        with self.assertRaisesRegex(ValueError,"CP policy raw byte"):
            self.evaluate(policy_bytes=b"{}")

    def test_uncraftable_owned_shortage_blocks(self):
        out=self.evaluate(inventory={"konami:101":0},craftable="NO")
        self.assertIn("UNCRAFTABLE_MISSING:konami:101",out["blocking_reasons"])

    def test_craftable_unknown_keeps_cost_bound_but_not_guarantee(self):
        out=self.evaluate(inventory={"konami:101":0},craftable="UNKNOWN")
        self.assertIn("CRAFTABILITY_UNVERIFIED",out["warnings"])
        self.assertEqual(90,out["required_cp_lower_by_rarity"]["SR"])

    def test_extra_seven_is_not_complete_fifteen(self):
        out=self.evaluate()
        self.assertEqual({"used":7,"unused":8,"suitability":"NOT_ASSESSED"},out["extra_deck"])
        self.assertIn("EXTRA_DECK_UNUSED_SLOTS_NOT_OPTIMIZED",out["warnings"])

    def test_extra_fifteen_has_no_unused_warning(self):
        c=copy.deepcopy(self.candidate)
        # 8 additional distinct fake EX cards unavailable in synthetic DB,
        # so this test uses remaining EX slots only with extra cards duplicated
        # up to 3 allowed, retaining 15 total.
        for row in c["cards"]:
            if row["section"]=="EXTRA" and row["card_id"] in {
                "konami:300","konami:301","konami:302","konami:303"}:
                row["quantity"]=3
        c["declared_extra"]=15
        out=self.evaluate(candidate_override=c)
        self.assertEqual(0,out["extra_deck"]["unused"])
        self.assertNotIn("EXTRA_DECK_UNUSED_SLOTS_NOT_OPTIMIZED",out["warnings"])

    def test_regulation_future_effective_date_blocks(self):
        out=self.evaluate(ban_effective="2026-11-15")
        self.assertIn("REGULATION_SNAPSHOT_FROM_FUTURE",out["blocking_reasons"])

    def test_readonly_has_no_data_mutation(self):
        out=self.evaluate()
        before=self.file.read_bytes()
        out=self.evaluate()
        self.assertEqual(before,self.file.read_bytes())

    def test_incomplete_master_never_passes_ur0(self):
        c=copy.deepcopy(self.candidate)
        c["cards"][-1]["card_id"]="konami:9999"
        c["reasons_by_card"].pop("konami:306")
        c["reasons_by_card"]["konami:9999"]="unknown card reference"
        out=self.evaluate(candidate_override=c)
        self.assertEqual("INDETERMINATE",out["mode_gates"]["STRICT_NO_UR"])
        self.assertIn("UNKNOWN_MASTER_CARD:konami:9999",out["blocking_reasons"])


if __name__=="__main__":
    unittest.main()
