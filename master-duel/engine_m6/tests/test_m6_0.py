"""M6-0 contract tests: all IDs, names and pins are synthetic."""
import copy
import unittest

from engine_m6.schema import (
    SCHEMA, validate_request, validate_source_pins,
    validate_inventory_audit, validate_candidate, validate_evaluation
)
from engine_m6.inputs import request_from_interpretation, pin_envelope, risk_summary

SHA = "a"*64


def request(**kwargs):
    return request_from_interpretation(request_id="fictional-1",
        as_of="2026-11-11T10:00:00+09:00", theme_query="架空テーマ",
        **kwargs)


def pins(**kwargs):
    from engine_m6.schema import REQUIRED_PINS, SHA_PINS
    p={key:SHA if key in SHA_PINS else "synthetic-v1"
       for key in REQUIRED_PINS}
    p["head_generation"]=2
    p["head_zip_generation"]=2
    p["inventory_generation"]=2
    p["m3_generation"]=2
    p["missing_reasons"]={}
    p.update(kwargs)
    for key in REQUIRED_PINS:
        if p[key] is None:
            p["missing_reasons"][key]="NOT_AVAILABLE"
        else:
            p["missing_reasons"].pop(key,None)
    return p


def decision(cid,n=1,**kwargs):
    d={"card_id":cid,"known_state":"KNOWN_POSITIVE",
       "owned_quantity":n,"rarity":"UR","regulation_limit":3,
       "regulation_confidence":"GAME_VERIFIED","disposition":"CONSIDER",
       "decision_reason":"not enough deck slots",
       "main_or_extra":"NONE","selected_quantity":0}
    d.update(kwargs)
    return d


def audit(ds,status="PASS",count=None):
    return {"schema":SCHEMA,"head_generation":2,"sqlite_sha":SHA,
            "inventory_total_registered":len(ds) if count is None else count,
            "inventory_rows_reviewed":len(ds),
            "owned_inventory_decisions":ds,"preflight_status":status}


def candidate():
    return {"schema":SCHEMA,"candidate_id":"fictitious-1",
            "theme":"架空テーマ","source_kind":"ASSEMBLED",
            "lineage":{"source":"synthetic"},
            "cards":[{"card_id":"konami:100","section":"MAIN","quantity":3,
                      "role":"STARTER","essentiality":"CORE",
                      "reason":"synthetic experiment","evidence_ids":["c1"]}]
                    + [{"card_id":f"konami:{101+i}","section":"MAIN","quantity":3,
                        "role":"FILLER","essentiality":"OPTIONAL",
                        "reason":"synthetic experiment","evidence_ids":["c1"]}
                       for i in range(12)]
                    + [{"card_id":"konami:113","section":"MAIN","quantity":1,
                        "role":"FILLER","essentiality":"OPTIONAL",
                        "reason":"synthetic experiment","evidence_ids":["c1"]}],
            "required_core_ids":["konami:100"],"route_ids":[],
            "reasons_by_card":{f"konami:{100+i}":"synthetic reasoning" for i in range(14)},
            "reasons_by_omitted_owned_card":{},"m5_status":"HYPOTHESIS",
            "declared_main":40,"declared_extra":0}


def evaluation():
    return {"schema":SCHEMA,"candidate_id":"fictitious-1",
            "source_pins":pins(),"preflight_status":"PASS",
            "structure":"PASS","mode_gates":{
                "CORE_UR_ZERO":"INDETERMINATE","NEW_UR_CRAFT_ZERO":"INDETERMINATE",
                "STRICT_NO_UR":"INDETERMINATE"},
            "regulation_verified":False,"ownership_verified":False,
            "craft_cost_verified":False,"gameplay_tested":False,
            "unknowns":["source unresolved"],"blocking_reasons":[],
            "proposal_status":"STRUCTURAL_CANDIDATE"}


class M6ContractTests(unittest.TestCase):
    def test_default_ur0_reuses_owned_ur_pool(self):
        r=request()
        self.assertEqual("LOW_RARITY_CORE",r["mode"])
        self.assertEqual("DEFAULTED",r["mode_origin"])

    def test_explicit_strict(self):
        r=request(strict_no_ur=True)
        self.assertEqual("STRICT_NO_UR",r["mode"])
        self.assertEqual("EXPLICIT",r["mode_origin"])

    def test_strict_conflict_rejected(self):
        with self.assertRaises(ValueError):
            request(strict_no_ur=True,mode="LOW_RARITY_CORE")

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            request(mode="FREE_UR")

    def test_cp_budget_must_use_each_currency(self):
        with self.assertRaises(ValueError):
            request(mode="CP_BUDGET",constraints={"cp_budget_by_rarity":{"ANY":120}})
        self.assertEqual("CP_BUDGET",request(
            mode="CP_BUDGET",constraints={"cp_budget_by_rarity":{"SR":300,"UR":0}})["mode"])

    def test_ur_budget_requires_limit(self):
        with self.assertRaises(ValueError):
            request(mode="UR_BUDGET")
        self.assertEqual("UR_BUDGET",request(
            mode="UR_BUDGET",constraints={"new_ur_max":1})["mode"])

    def test_invalid_timezone_and_unsupported_fields(self):
        p=request()
        p["as_of"]="2026-11-11T10:00:00"
        with self.assertRaises(ValueError):validate_request(p)
        p=request();p["extra_flag"]="unsafe"
        with self.assertRaises(ValueError):validate_request(p)

    def test_explicit_conflicting_cards(self):
        with self.assertRaises(ValueError):
            request(constraints={"required_card_ids":["konami:99"],
                                 "excluded_card_ids":["konami:99"]})

    def test_deck_request_needs_lookup_identity(self):
        with self.assertRaises(ValueError):
            request_from_interpretation(request_id="r",as_of="2026-11-11T10:00:00+09:00",
                use_registered_deck=True)

    def test_sha_formats_not_actual_byte_verification(self):
        self.assertEqual("PINS_PRESENT_NOT_BYTES_VERIFIED",
                         validate_source_pins(pins())["status"])
        with self.assertRaises(ValueError):
            validate_source_pins(pins(sqlite_sha="not-a-sha"))

    def test_missing_sha_is_blocked_with_reason(self):
        self.assertEqual("BLOCKED",
                         validate_source_pins(pins(sqlite_zip_sha=None))["status"])

    def test_head_generation_mismatch_blocked(self):
        self.assertEqual("BLOCKED",
                         validate_source_pins(pins(inventory_generation=1))["status"])
        self.assertEqual("BLOCKED",
                         pin_envelope(pins(),expected_generation=1)["status"])

    def test_m5_sidecar_missing_partial(self):
        self.assertEqual("PARTIAL",
                         validate_source_pins(pins(m5_c_zip_sha=None,
                                                  m5_c_manifest_sha=None))["status"])

    def test_owned_deck_catalog_required_when_requested(self):
        p=pins(owned_deck_catalog_sha=None)
        self.assertEqual("BLOCKED",validate_source_pins(p,registered_deck=True)["status"])

    def test_incomplete_owned_audit_cannot_pass(self):
        a=audit([decision("konami:1")],count=2)
        with self.assertRaises(ValueError):
            validate_inventory_audit(a)
        a["preflight_status"]="PARTIAL"
        self.assertEqual("COVERAGE_INCOMPLETE",validate_inventory_audit(a)["status"])

    def test_full_registered_coverage(self):
        ds=[decision(f"konami:{i}") for i in range(1,6)]
        ds[0].update({"disposition":"ADOPT","selected_quantity":1,
                      "main_or_extra":"MAIN","decision_reason":"synthetic fit"})
        ds[1].update({"disposition":"ADOPT","selected_quantity":1,
                      "main_or_extra":"MAIN"})
        self.assertEqual(5,validate_inventory_audit(audit(ds))["count"])

    def test_unknown_ownership_not_zero(self):
        d=decision("konami:1",n=None,known_state="UNKNOWN",
                   disposition="REVIEW_REQUIRED",decision_reason="not registered")
        with self.assertRaises(ValueError):
            validate_inventory_audit(audit([d],status="PASS"))
        self.assertEqual("COVERAGE_COMPLETE",
                         validate_inventory_audit(audit([d],status="PARTIAL"))["status"])

    def test_known_zero_and_positive_distinct(self):
        zero=decision("konami:1",n=0,known_state="KNOWN_ZERO")
        positive=decision("konami:2",n=2)
        validate_inventory_audit(audit([zero,positive]))
        positive["known_state"]="KNOWN_ZERO"
        with self.assertRaises(ValueError):
            validate_inventory_audit(audit([zero,positive]))

    def test_duplicate_owned_decision_rejected(self):
        with self.assertRaises(ValueError):
            validate_inventory_audit(audit([decision("konami:1"),decision("konami:1")]))

    def test_owned_forbidden_candidate_not_adopted(self):
        d=decision("konami:1",regulation_limit=0,
                   disposition="ADOPT",main_or_extra="MAIN",selected_quantity=1)
        with self.assertRaises(ValueError):
            validate_inventory_audit(audit([d]))

    def test_missing_component_generation_partial(self):
        self.assertEqual("PARTIAL",
                         validate_source_pins(pins(m3_generation=None))["status"])

    def test_missing_core_cannot_pass_structural_candidate(self):
        c=candidate()
        c["required_core_ids"]=["konami:999"]
        with self.assertRaises(ValueError):
            validate_candidate(c)

    def test_candidate_40_main(self):
        self.assertEqual(40,validate_candidate(candidate())["main_count"])

    def test_candidate_exceeds_3_aggregate(self):
        c=candidate()
        c["cards"].append(copy.deepcopy(c["cards"][0]))
        c["declared_main"]=43
        with self.assertRaises(ValueError):
            validate_candidate(c)

    def test_candidate_under_40_rejected(self):
        c=candidate();c["cards"].pop();c["declared_main"]=39
        with self.assertRaises(ValueError):
            validate_candidate(c)

    def test_candidate_cross_section_duplicate(self):
        c=candidate()
        c["cards"][1]["section"]="EXTRA"
        c["declared_main"]=37;c["declared_extra"]=3
        c["cards"].append({"card_id":"konami:101","section":"MAIN","quantity":1,
                           "role":"FILLER","essentiality":"OPTIONAL","reason":"synth",
                           "evidence_ids":[]})
        with self.assertRaises(ValueError):
            validate_candidate(c)

    def test_candidate_missing_reason_rejected(self):
        c=candidate();c["reasons_by_card"].pop("konami:100")
        with self.assertRaises(ValueError):
            validate_candidate(c)

    def test_candidate_cannot_silently_fill_article(self):
        c=candidate()
        c["declared_main"]=39
        with self.assertRaises(ValueError):
            validate_candidate(c)

    def test_only_structural_evaluation_not_verified(self):
        self.assertEqual("CONTRACT_VALIDATED_NOT_FACT_VERIFIED",
                         validate_evaluation(evaluation())["status"])

    def test_unknown_gates_may_not_be_verified_recommendation(self):
        e=evaluation();e["proposal_status"]="VERIFIED_RECOMMENDATION"
        with self.assertRaises(ValueError):
            validate_evaluation(e)

    def test_all_pass_claim_cannot_be_authenticated_by_m6_zero(self):
        e=evaluation()
        e["proposal_status"]="VERIFIED_RECOMMENDATION"
        e["mode_gates"]={k:"PASS" for k in e["mode_gates"]}
        e.update(regulation_verified=True,ownership_verified=True,
                 craft_cost_verified=True,gameplay_tested=True,unknowns=[])
        with self.assertRaises(ValueError):
            validate_evaluation(e)

    def test_blocked_pins_no_provisional(self):
        e=evaluation();e["proposal_status"]="PROVISIONAL_RECOMMENDATION"
        e["source_pins"]=pins(sqlite_sha=None)
        with self.assertRaises(ValueError):
            validate_evaluation(e)

    def test_bundle_uncertainty_honored(self):
        p=risk_summary(pins=pins(),preflight_status="PASS",
                       source_bundle={"recommendation_eligible":False,
                                      "stale_dependencies":[{"id":"s"}],"conflicts":[]})
        self.assertIn("M5_STALE",p["blocked_or_unverified"])
        self.assertFalse(p["recommendation_eligible"])

    def test_source_bundle_must_not_assert_recommendation(self):
        with self.assertRaises(ValueError):
            risk_summary(pins=pins(),preflight_status="PASS",
                         source_bundle={"recommendation_eligible":True})

    def test_no_input_mutation(self):
        a=audit([decision("konami:1")]);c=candidate();p=pins()
        old=copy.deepcopy((a,c,p))
        validate_inventory_audit(a);validate_candidate(c);validate_source_pins(p)
        self.assertEqual((a,c,p),old)


if __name__=="__main__":
    unittest.main()
