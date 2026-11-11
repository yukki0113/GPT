"""M6-2 synthetic-only candidate pool, package and lock checks."""
import copy
import unittest

from engine_m6.candidate_pool import build_candidate_pool
from engine_m6.dependency import inspect_packages, validate_package

SHA="a"*64
DB="b"*64


def bundle():
    return {"schema":"md-m5c-theme-knowledge-bundle-v1","profile_id":"fictional",
      "knowledge_sha256":SHA,"master_db_sha256":DB,
      "recommendation_eligible":False,
      "recipe_refs":[{"recipe_id":"r","main_count":40,"extra_count":1}],
      "recipe_cards":[{"recipe_id":"r","card_id":"konami:101","section":"MAIN",
                       "quantity":2,"role":"CORE","essentiality":"UNKNOWN",
                       "resolve_status":"RESOLVED"},
                      {"recipe_id":"r","card_id":"konami:201","section":"EXTRA",
                       "quantity":1,"role":"EX","essentiality":"UNKNOWN",
                       "resolve_status":"RESOLVED"}],
      "low_cost_variants":[{"source_profile_id":"fictional","variant_id":"v",
          "candidate_cards":[{"card_id":"konami:101","section":"MAIN",
                              "quantity":3,"rarity":"R"},
                             {"card_id":"konami:102","section":"MAIN",
                              "quantity":3,"rarity":"SR"}]}],
      "combo_routes":[{"route_id":"route","verification":"TEXT_CHECKED"}],
      "combo_nodes":[{"route_id":"route","actor_card_id":"konami:101",
                      "transfers":[{"card_id":"konami:201"}]}],
      "stale_dependencies":[],"conflicts":[],"unresolved_claims":[],
      "issues":[]}


def package(pid="engine", *, part="konami:301", section="MAIN",
            quantity=2, kind="ENGINE", deps=None, conflicts=None, locks=None,
            groups=None):
    return {"package_id":pid,"kind":kind,"verification":"HYPOTHESIS",
            "provenance":{"source_type":"M5A","source_id":"fictitious"},
            "parts":[{"card_id":part,"section":section,"minimum":quantity,
                      "maximum":3,"role":"STARTER"}],
            "choice_groups":groups or [],
            "dependencies":deps or [],"conflicts":conflicts or [],
            "locks":locks or []}


def get_pool(b=None, **kwargs):
    return build_candidate_pool(b or bundle(),
        expected_knowledge_sha256=SHA,expected_master_db_sha256=DB,**kwargs)


class CandidatePoolTests(unittest.TestCase):
    def test_incomplete_recipe_cannot_be_considered_complete(self):
        r=get_pool()
        self.assertEqual("INCOMPLETE_SOURCE_RECIPE",r["issues"][0]["type"])
        self.assertFalse(r["ready_for_recipe_assembly"])
        self.assertEqual("UNKNOWN",r["core_verification"])

    def test_article_and_variant_not_double_counted(self):
        r=get_pool()
        card=next(x for x in r["cards"] if x["card_id"]=="konami:101")
        self.assertEqual([2,3],[x["observed_quantity"] for x in card["observations"]])
        self.assertTrue(card["quantity_conflict"])

    def test_stale_route_never_enabled(self):
        b=bundle();b["stale_dependencies"]=[{"object_type":"ROUTE","object_id":"route"}]
        r=get_pool(b)
        self.assertEqual("STALE",r["routes"][0]["status"])
        self.assertFalse(r["recommendation_eligible"])

    def test_master_pin_fails_closed(self):
        with self.assertRaises(ValueError):
            build_candidate_pool(bundle(),expected_knowledge_sha256=SHA,
                                 expected_master_db_sha256="c"*64)

    def test_owned_unknown_not_assumed_zero(self):
        r=get_pool()
        self.assertTrue(all(x["owned_quantity"] is None for x in r["cards"]))
        self.assertTrue(all(x["owned_state"]=="UNKNOWN" for x in r["cards"]))

    def test_full_owned_preflight_and_actual_known_zero(self):
        owned={"sqlite_sha":DB,"preflight_status":"PARTIAL",
               "inventory_total_registered":2,"inventory_rows_reviewed":2,
               "owned_inventory_decisions":[
                 {"card_id":"konami:101","known_state":"KNOWN_POSITIVE",
                  "owned_quantity":2},
                 {"card_id":"konami:102","known_state":"KNOWN_ZERO",
                  "owned_quantity":0}]}
        r=get_pool(owned_audit=owned)
        q={x["card_id"]:x for x in r["cards"]}
        self.assertEqual(0,q["konami:102"]["owned_quantity"])
        self.assertIsNone(q["konami:201"]["owned_quantity"])
        self.assertEqual(2,r["registered_owned_rows_seen"])

    def test_incomplete_owned_preflight_rejected(self):
        with self.assertRaises(ValueError):
            get_pool(owned_audit={"sqlite_sha":DB,"preflight_status":"PASS",
                    "inventory_total_registered":2,"inventory_rows_reviewed":1,
                    "owned_inventory_decisions":[{"card_id":"konami:1",
                        "known_state":"KNOWN_ZERO","owned_quantity":0}]})

    def test_external_engines_require_independent_pin_argument(self):
        with self.assertRaises(ValueError):
            get_pool(engine_packages=[package()])
        r=get_pool(engine_packages=[package()],engine_index_sha256="d"*64)
        self.assertIn("konami:301",{x["card_id"] for x in r["cards"]})
        self.assertFalse(r["recommendation_eligible"])

    def test_support_not_promoted_to_formal_archetype(self):
        row={"card_id":"konami:409","section":"MAIN","source_id":"m5b-1",
             "effect_sha256":"e"*64,"verification":"HYPOTHESIS",
             "match_kind":"PROPERTY_COOCCURRENCE_CANDIDATE","role":"SEARCH"}
        r=get_pool(support_candidates=[row],support_index_sha256="f"*64)
        card=next(x for x in r["cards"] if x["card_id"]=="konami:409")
        self.assertEqual("HYPOTHESIS",card["observations"][0]["verification"])
        self.assertFalse(r["recommendation_eligible"])
        row["verification"]="GAME_TESTED"
        with self.assertRaises(ValueError):
            get_pool(support_candidates=[row],support_index_sha256="f"*64)

    def test_shared_part_uses_max_not_sum(self):
        a=package("a",quantity=2);b=package("b",quantity=3)
        p=inspect_packages([a,b],["a","b"])
        self.assertEqual(3,p["minimum_main"])
        self.assertEqual(1,len(p["shared_parts"]))

    def test_missing_dependency_rejected_with_status(self):
        a=package("a",deps=["b"]);b=package("b",part="konami:302")
        p=inspect_packages([a,b],["a"])
        self.assertEqual("BLOCKED",p["status"])
        self.assertEqual(["b"],p["missing_dependencies"])

    def test_conflicting_packages_blocked(self):
        a=package("a",conflicts=["b"]);b=package("b",part="konami:302")
        self.assertEqual("BLOCKED",inspect_packages([a,b],["a","b"])["status"])

    def test_exceed_ex_budget_blocked(self):
        a=package("a",section="EXTRA",part="konami:301",quantity=3)
        b=package("b",section="EXTRA",part="konami:302",quantity=3)
        self.assertEqual("BLOCKED",
            inspect_packages([a,b],["a","b"],extra_budget=5)["status"])

    def test_conditional_lock_not_automatically_unconditional(self):
        lock={"lock_id":"wind-after-effect","scope":"OPTIONAL_LINE",
              "predicate":"WIND-only AFTER effect","effect_evidence":"effect:2"}
        a=package("a",locks=[lock])
        p=inspect_packages([a],["a"])
        self.assertEqual("OPTIONAL_LINE",p["active_or_conditional_locks"][0]["scope"])
        self.assertEqual("REVIEW_REQUIRED",p["status"])

    def test_choice_group_not_treated_as_fixed_part(self):
        a=package("a",quantity=1,groups=[{"group_id":"g",
               "min_choices":1,"options":[{"card_id":"konami:305","section":"MAIN",
                                           "copies":1},
                                          {"card_id":"konami:306","section":"MAIN",
                                           "copies":1}]}])
        p=inspect_packages([a],["a"])
        self.assertEqual(2,p["minimum_main"])
        self.assertEqual("UNRESOLVED",p["unresolved_choices"][0]["selection"])

    def test_duplicate_package_ids_and_bad_numbers(self):
        a=package()
        with self.assertRaises(ValueError):
            inspect_packages([a,a],["engine"])
        a["parts"][0]["minimum"]=4
        with self.assertRaises(ValueError):
            validate_package(a)

    def test_not_mutating_input(self):
        b=bundle();old=copy.deepcopy(b)
        get_pool(b)
        self.assertEqual(b,old)


if __name__=="__main__":
    unittest.main()
