"""M5-C C3 synthetic-only tests; all card IDs and source names are fictitious."""
import unittest

from test_m5c_c0 import fixture
from engine_m5.low_cost_variant import assess_low_cost_variant as _assess, VariantError


def assess_low_cost_variant(bundle, recipe_id, master, **kwargs):
    return _assess(bundle, recipe_id, master, source_db_sha256="a" * 64, **kwargs)


def sample():
    b = fixture()
    b["recipe_refs"] = [{"recipe_id":"r1","profile_id":"p1","source_id":"s1",
        "article_revision":"synthetic","main_count":40,"extra_count":2,
        "game_scope":"MD","banlist_on":None}]
    def row(cid, section, count):
        return {"recipe_id":"r1","card_id":cid,"section":section,"quantity":count,
            "role":"REFERENCE","essentiality":"UNKNOWN","resolve_status":"RESOLVED"}
    b["recipe_cards"] = [
        row("konami:101","MAIN",3),row("konami:102","MAIN",3),
        row("konami:103","MAIN",3),row("konami:104","MAIN",3),
        row("konami:105","MAIN",3),row("konami:106","MAIN",3),
        row("konami:107","MAIN",3),row("konami:108","MAIN",3),
        row("konami:109","MAIN",3),row("konami:110","MAIN",3),
        row("konami:111","MAIN",3),row("konami:112","MAIN",3),
        row("konami:113","MAIN",3),row("konami:114","MAIN",1),
        row("konami:201","EXTRA",1),row("konami:202","EXTRA",1)]
    # 13 * 3 + 1 = 40, last baseline MAIN card and first EXTRA are UR.
    master = [("konami:"+str(i),"架空札"+str(i),
               "UR" if i in {114,201} else "R" if i < 200 else "SR")
              for i in [*range(101,115),201,202,115]]
    return b, master


def addition(cid="konami:115",section="MAIN",quantity=1):
    return {"section":section,"card_id":cid,"quantity":quantity,
        "rationale":"架空の低レア枠。実ゲーム未検証","verification":"HYPOTHESIS","source_ids":[]}


class LowCostVariantTests(unittest.TestCase):
    def test_strict_no_ur_reconstructs_main_and_preserves_ex(self):
        bundle, master = sample()
        result=assess_low_cost_variant(bundle,"r1",master,
            additions=[addition()],mandatory_core_ids=["konami:101"])
        self.assertEqual({"MAIN":40,"EXTRA":1},result["candidate"]["sizes"])
        self.assertEqual({"MAIN":1,"EXTRA":1},result["baseline"]["ur_copies"])
        self.assertEqual({"MAIN":0,"EXTRA":0},result["candidate"]["ur_copies"])
        self.assertEqual(1,len(result["change"]["removed_ex_ur"]))
        self.assertEqual("REVIEW_REQUIRED",result["outcome"])
        self.assertTrue(result["paths"]["no_preexisting_routes"])
        self.assertEqual("PASS_BY_NO_UR_IN_DECK",result["cost"]["new_ur_craft_zero"])
        self.assertEqual("PASS_FOR_SUPPLIED_CORE",result["cost"]["required_core_ur_zero"])

    def test_optional_non_ur_exclusion_with_reason(self):
        b,m=sample()
        # EX lower-rarity card excluded only by an explicit evidence note.
        result=assess_low_cost_variant(b,"r1",m,additions=[addition()],
            exclusions=[{"section":"EXTRA","card_id":"konami:202",
                         "rationale":"架空の依存先URが除去された","verification":"HYPOTHESIS",
                         "source_ids":[]}])
        self.assertEqual(0,result["candidate"]["sizes"]["EXTRA"])
        self.assertEqual(1,len(result["change"]["exclusion_evidence"]))

    def test_unknown_exclusion_rejected(self):
        b,m=sample()
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",m,additions=[addition()],
                exclusions=[{"section":"EXTRA","card_id":"konami:9999",
                             "rationale":"未確認","verification":"HYPOTHESIS",
                             "source_ids":[]}])

    def test_no_explicit_main_replacement_rejected(self):
        b,m=sample()
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",m)

    def test_ur_as_replacement_rejected(self):
        b,m=sample()
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",m,additions=[addition("konami:114")])

    def test_unresolved_article_rows_rejected(self):
        b,m=sample();b["recipe_refs"][0]["main_count"]=41
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",m,additions=[addition()])

    def test_missing_master_rarity_rejected(self):
        b,m=sample()
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",[x for x in m if x[0]!="konami:202"],
                additions=[addition()])

    def test_copy_limit_rejected(self):
        b,m=sample()
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",m,additions=[addition(quantity=4)])

    def test_evidence_required(self):
        b,m=sample()
        bad=addition();bad["source_ids"]=["unknown-source"]
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",m,additions=[bad])
        bad=addition();bad["verification"]="GAME_TESTED"
        with self.assertRaises(VariantError):
            assess_low_cost_variant(b,"r1",m,additions=[bad])

    def test_new_ur_zero_without_owned_preflight_cannot_pass(self):
        b,m=sample()
        result=assess_low_cost_variant(b,"r1",m,policy="NEW_UR_CRAFT_ZERO")
        self.assertEqual("UNKNOWN_OR_FAIL",result["cost"]["new_ur_craft_zero"])
        self.assertEqual(2,len(result["cost"]["insufficient_or_unconfirmed_ur"]))

    def test_new_ur_zero_requires_explicit_owned_counts(self):
        b,m=sample()
        result=assess_low_cost_variant(b,"r1",m,policy="NEW_UR_CRAFT_ZERO",
            owned_counts={"konami:114":1,"konami:201":1})
        self.assertEqual("PASS_CONDITIONAL",result["cost"]["new_ur_craft_zero"])
        self.assertEqual("REVIEW_REQUIRED",result["outcome"])

    def test_removed_mandatory_sr_core_does_not_pass(self):
        b,m=sample()
        result=assess_low_cost_variant(b,"r1",m,additions=[addition()],
            mandatory_core_ids=["konami:202"],
            exclusions=[{"section":"EXTRA","card_id":"konami:202",
                "rationale":"架空依存先なし","verification":"HYPOTHESIS",
                "source_ids":[]}])
        self.assertEqual("CORE_REMOVED",result["cost"]["required_core_ur_zero"])
        self.assertEqual(["konami:202"],result["cost"]["missing_candidate_core_ids"])

    def test_mandatory_ur_separate_from_crafting(self):
        b,m=sample()
        result=assess_low_cost_variant(b,"r1",m,policy="NEW_UR_CRAFT_ZERO",
            owned_counts={"konami:114":1,"konami:201":1},
            mandatory_core_ids=["konami:114"])
        self.assertEqual("FAIL",result["cost"]["required_core_ur_zero"])
        self.assertEqual("PASS_CONDITIONAL",result["cost"]["new_ur_craft_zero"])

    def test_missing_core_id_unknown(self):
        b,m=sample()
        result=assess_low_cost_variant(b,"r1",m,additions=[addition()],
            mandatory_core_ids=["konami:9999"])
        self.assertEqual("UNKNOWN",result["cost"]["required_core_ur_zero"])

    def test_unpinned_master_rejected(self):
        b,m=sample()
        with self.assertRaises(VariantError):
            _assess(b,"r1",m,additions=[addition()])

    def test_cannot_claim_game_tested_from_article(self):
        b,m=sample()
        result=assess_low_cost_variant(b,"r1",m,additions=[addition()])
        self.assertEqual("REVIEW_REQUIRED_NOT_GAME_TESTED",result["paths"]["status"])
        self.assertEqual("UNVERIFIED_SOURCE",result["md_regulation"])


if __name__ == "__main__":
    unittest.main()
