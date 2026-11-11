"""M6-3 synthetic structural assembly regressions; no private cards or recipes."""
from copy import deepcopy
import unittest

from engine_m6.assemble import assemble_candidates
from engine_m6.inputs import request_from_interpretation
from engine_m6.schema import validate_candidate

A = "a"*64
B = "b"*64


def sample():
    # Exactly 40 MAIN: 13 three-copy cards and a singleton.
    main = [{"card_id":f"konami:{100+i}","section":"MAIN",
             "quantity":3 if i<13 else 1,
             "role":"SOURCE_REFERENCE","essentiality":"UNKNOWN",
             "resolve_status":"RESOLVED","recipe_id":"recipe"}
            for i in range(14)]
    ref={"recipe_id":"recipe","main_count":40,"extra_count":1}
    ref_cards=main+[{"card_id":"konami:300","section":"EXTRA","quantity":1,
                     "role":"SOURCE_REFERENCE","essentiality":"UNKNOWN",
                     "resolve_status":"RESOLVED","recipe_id":"recipe"}]
    modified=[{"card_id":row["card_id"],"section":row["section"],
               "quantity":row["quantity"],"rarity":"R"} for row in ref_cards]
    modified[-2]["card_id"]="konami:201"  # replace one singleton
    variant={"source_recipe_id":"recipe","source_profile_id":"fictional",
             "variant_id":"lowcost","main_count":40,"extra_count":1,
             "verification":"REVIEW_REQUIRED","candidate_cards":modified}
    bundle={"schema":"md-m5c-theme-knowledge-bundle-v1",
            "profile_id":"fictional","theme_key":"FICTIONAL_THEME",
            "master_db_sha256":B,"knowledge_sha256":A,
            "recommendation_eligible":False,
            "recipe_refs":[ref],"recipe_cards":ref_cards,
            "low_cost_variants":[variant],"stale_dependencies":[]}
    observation=[]
    for row in ref_cards:
        observation.append((row["section"],row["card_id"],
                            "M5C:RECIPE:recipe",row["quantity"]))
    for row in modified:
        observation.append((row["section"],row["card_id"],
                            "M5C:VARIANT:lowcost",row["quantity"]))
    cards={}
    for section,cid,src,n in observation:
        obj=cards.setdefault((section,cid),{"section":section,"card_id":cid,
            "observations":[],"disposition":"REVIEW_REQUIRED"})
        obj["observations"].append({"source_ref":src,"observed_quantity":n,
            "role":"REFERENCE","essentiality":"UNKNOWN",
            "verification":"REVIEW_REQUIRED","status":"CANDIDATE"})
    pool={"schema":"md-m6-2-candidate-pool-v1","profile_id":"fictional",
          "master_db_sha256":B,"knowledge_sha256":A,
          "recommendation_eligible":False,
          "ready_for_recipe_assembly":False,
          "cards":list(cards.values()),"packages":[],"issues":[]}
    return bundle,pool


def req(**kwargs):
    return request_from_interpretation(request_id="synthetic",as_of="2026-11-11T12:00:00+09:00",
                                       theme_query="架空",**kwargs)


def run(b=None,p=None,r=None,**kwargs):
    x,y=sample()
    return assemble_candidates(r or req(),b or x,p or y,**kwargs)


class AssemblyTests(unittest.TestCase):
    def test_two_distinct_source_variants(self):
        result=run()
        self.assertEqual(2,result["candidate_count"])
        self.assertEqual(["ARTICLE_RECIPE","M5C_VARIANT"],
                         [x["candidate"]["source_kind"] for x in result["candidates"]])
        for item in result["candidates"]:
            self.assertEqual("STRUCTURAL_CANDIDATE_ONLY",item["assembly_status"])
            self.assertEqual(40,validate_candidate(item["candidate"])["main_count"])
            self.assertEqual("PENDING_M6_4",item["requested_mode_evaluation"])
            self.assertFalse(item["regulation_verified"])

    def test_reproducible_candidate_identity(self):
        self.assertEqual(run(),run())

    def test_article_main39_not_silently_filled(self):
        b,p=sample()
        b["recipe_cards"]= [x for x in b["recipe_cards"] if x["card_id"]!="konami:113"]
        result=run(b,p)
        self.assertEqual(1,result["candidate_count"])
        self.assertIn("SOURCE_RECIPE_COUNT_MISMATCH",result["rejected"][0]["reasons"])
        self.assertEqual("M5C_VARIANT",result["candidates"][0]["candidate"]["source_kind"])

    def test_missing_recipe_and_variant_reports_insufficient_evidence(self):
        b,p=sample()
        b["recipe_refs"]=[];b["recipe_cards"]=[];b["low_cost_variants"]=[]
        result=run(b,p)
        self.assertEqual("INSUFFICIENT_EVIDENCE",result["status"])
        self.assertEqual(0,result["candidate_count"])

    def test_source_sha_mismatch_rejected(self):
        b,p=sample();p["master_db_sha256"]="c"*64
        with self.assertRaisesRegex(ValueError,"source pin"):
            run(b,p)

    def test_cross_profile_rejected(self):
        b,p=sample();p["profile_id"]="another"
        with self.assertRaisesRegex(ValueError,"profile mismatch"):
            run(b,p)

    def test_stale_recipe_and_dependent_variant_blocked(self):
        b,p=sample();b["stale_dependencies"]=[{"object_type":"RECIPE","object_id":"recipe"}]
        result=run(b,p)
        self.assertEqual(0,result["candidate_count"])
        self.assertEqual(2,len(result["rejected"]))

    def test_stale_variant_only_blocks_variant(self):
        b,p=sample();b["stale_dependencies"]=[{"object_type":"VARIANT","object_id":"lowcost"}]
        result=run(b,p)
        self.assertEqual(1,result["candidate_count"])

    def test_excluded_card_not_silently_removed(self):
        result=run(r=req(constraints={"excluded_card_ids":["konami:101"]}))
        self.assertEqual(0,result["candidate_count"])
        self.assertTrue(all("EXCLUDED_CARD_PRESENT" in x["reasons"]
                            for x in result["rejected"]))

    def test_required_card_missing_blocks_source(self):
        result=run(r=req(constraints={"required_card_ids":["konami:998"]}))
        self.assertEqual(0,result["candidate_count"])

    def test_no_uncited_explicit_card(self):
        edits=[{"section":"MAIN","card_id":"konami:999","quantity_delta":1,
                "source_ref":"user-wish","reason":"add a new unsupported card"}]
        result=run(explicit_edits=edits)
        self.assertEqual(0,result["candidate_count"])
        self.assertIn("UNCITED_EDIT_CARD",result["rejected"][0]["reasons"])

    def test_cited_explicit_edit_only_as_assembled(self):
        # A cited swap of the variant-only singleton for a source singleton,
        # requested as a separate ASSEMBLED card list.
        edits=[{"section":"MAIN","card_id":"konami:113","quantity_delta":-1,
                "source_ref":"M5C:RECIPE:recipe","reason":"replace singleton"},
               {"section":"MAIN","card_id":"konami:201","quantity_delta":1,
                "source_ref":"M5C:VARIANT:lowcost","reason":"try alternate singleton"}]
        result=run(explicit_edits=edits)
        self.assertEqual(1,result["candidate_count"])
        self.assertEqual("ASSEMBLED",result["candidates"][0]["candidate"]["source_kind"])
        self.assertEqual(40,result["candidates"][0]["candidate"]["declared_main"])

    def test_cited_edit_cannot_fix_incomplete_article(self):
        b,p=sample()
        b["recipe_cards"]=[x for x in b["recipe_cards"] if x["card_id"]!="konami:113"]
        edits=[{"section":"MAIN","card_id":"konami:201","quantity_delta":1,
                "source_ref":"M5C:VARIANT:lowcost","reason":"try a cited option"}]
        result=run(b,p,explicit_edits=edits)
        self.assertIn("SOURCE_RECIPE_COUNT_MISMATCH",result["rejected"][0]["reasons"])

    def test_max_candidates_and_bounded_source_examination(self):
        result=run(r=req(max_variants=1))
        self.assertEqual(1,result["candidate_count"])
        with self.assertRaises(ValueError):
            run(max_examined=0)

    def test_duplicate_versions_not_returned_twice(self):
        b,p=sample()
        b["low_cost_variants"][0]["candidate_cards"]= [
          {"card_id":x["card_id"],"section":x["section"],
           "quantity":x["quantity"],"rarity":"R"}
          for x in b["recipe_cards"]]
        result=run(b,p)
        self.assertEqual(1,result["candidate_count"])
        self.assertEqual("DUPLICATE_CANDIDATE",result["rejected"][0]["status"])

    def test_extra_budget_explicit_zero_blocks_present_ex(self):
        result=run(r=req(constraints={"extra_max":0}))
        self.assertEqual(0,result["candidate_count"])

    def test_no_evidence_for_package_additions(self):
        b,p=sample()
        p["packages"]=[{
          "package_id":"engine","kind":"ENGINE","verification":"HYPOTHESIS",
          "provenance":{"source_type":"M5A","source_id":"s"},
          "parts":[{"card_id":"konami:400","section":"MAIN","minimum":1,
                    "maximum":2,"role":"starter"}],"choice_groups":[],
          "dependencies":[],"conflicts":[],"locks":[]}]
        result=run(b,p,selected_packages=["engine"])
        self.assertEqual(0,result["candidate_count"])
        self.assertIn("PACKAGE_PARTS_NOT_ASSEMBLED",result["rejected"][0]["reasons"])

    def test_no_input_mutation(self):
        b,p=sample();r=req()
        previous=deepcopy((b,p,r))
        run(b,p,r)
        self.assertEqual(previous,(b,p,r))


if __name__=="__main__":
    unittest.main()
