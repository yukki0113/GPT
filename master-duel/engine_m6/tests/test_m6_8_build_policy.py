"""M6-8 evidence and copy-level regression (fictional cards only)."""
from copy import deepcopy
from collections import Counter
import unittest

from engine_m6.decision_policy import validate_decision_policy, screened_choice
from engine_m6.recompose import recompose_portfolio
from test_m6_5c import sample, PIN
from test_m6_7_competitive import regulation


def v2(annotations):
    rows=[]
    for a in annotations:
        is_ss=a["card_id"]=="konami:1200"
        is_a=a["card_id"]=="konami:1201"
        tier="SS" if is_ss else "A" if is_a else "NOT_LISTED"
        rows.append({
            "card_id":a["card_id"],"section":a["section"],"role":a["role"],
            "competitive_group":"GENERIC_INTERRUPTION",
            "recommended_max":1 if a["category"]=="GENERIC_EXTRA" else a["maximum"],
            "quantity_reason":"Synthetic independent per-copy rationale",
            "assessment_status":"HUMAN_REVIEWED",
            "evidence_refs":["DB:"+a["card_id"],"SYNTHETIC:REVIEWED:FOOTPRINT"] +
                (["https://game8.jp/yugioh-masterduel/423814"] if tier!="NOT_LISTED" else []),
            "reason":"Synthetic suitability and effect review",
            "summon_role":"SYNTHETIC_REVIEW",
            "lock_review":"REVIEWED","condition_review":"REVIEWED",
            "general_value":(None if tier!="NOT_LISTED" else
                             (58 if a["category"]!="THEME_CORE" else 70)),
            "game8":{"tier":tier,
                     "source_url":"https://game8.jp/yugioh-masterduel/423814"
                     if tier!="NOT_LISTED" else None,
                     "checked_on":"2026-11-11",
                     "applicability":"APPLICABLE" if tier!="NOT_LISTED"
                     else "NOT_LISTED"},
            "deck_adjustment":0,
            "deck_reason":"Synthetic compatibility review, not game evidence",
            "copy_adjustments":[0,-4,-12],
            "copy_reasons":["Want first access","Second copy is useful",
                            "Third copy individually reviewed"]})
    return {"schema":"md-m6-8-evidence-build-policy-v2",
            "master_sqlite_sha256":PIN,
            "as_of":"2026-11-12T17:00:00+09:00",
            "min_main_score":0,"min_extra_score":0,
            "required_review_names":["SYNTHETIC-konami:1200"],
            "assessments":rows}


def run(pol, annotations=None):
    t,req,disc,anns,screen,packages=sample()
    if annotations is not None:anns=annotations
    return recompose_portfolio(req,t,discovery_results=disc,
        annotations=anns,material_screen=screen,engine_packages=packages,
        decision_policy=pol,regulation_policy=regulation(anns))


class EvidencePolicyV2Tests(unittest.TestCase):
    def test_tier_prior_is_predeclared_and_not_silent_six_axis_override(self):
        a=sample()[3];p=v2(a)
        mapping=validate_decision_policy(p,master_sha256=PIN)
        self.assertEqual(90,mapping["MAIN","konami:1200"]["score_by_copy"][0])
        self.assertEqual(70,mapping["MAIN","konami:1201"]["score_by_copy"][0])
        self.assertEqual("SS",mapping["MAIN","konami:1200"]["score_components"]["tier"])

    def test_independent_copy_value_and_explainability(self):
        a=sample()[3];p=v2(a);mapping=validate_decision_policy(p,master_sha256=PIN)
        record={"annotation":{"card_id":"konami:1200","role":"INTERRUPTION"}}
        values=[]
        for count in range(3):
            score,trace=screened_choice(record,mapping,
                counts=Counter({("MAIN","konami:1200"):count}),zone="MAIN")
            values.append(score)
            self.assertEqual(count+1,trace["copy_number"])
            self.assertTrue(trace["copy_reason"])
            self.assertEqual("SS",trace["game8_tier"])
        self.assertEqual([90,86,78],values)
        self.assertEqual([0,-4,-12],
                         mapping["MAIN","konami:1200"]["score_components"]["copy_adjustments"])

    def test_different_cards_same_role_do_not_lose_value(self):
        m=validate_decision_policy(v2(sample()[3]),master_sha256=PIN)
        r={"annotation":{"card_id":"konami:1201","role":"INTERRUPTION"}}
        first,_=screened_choice(r,m,counts=Counter(),zone="MAIN")
        other,_=screened_choice(r,m,counts=Counter({("MAIN","konami:1200"):3}),
                                zone="MAIN")
        self.assertEqual(70,first)
        self.assertEqual(first,other)

    def test_missing_game8_evidence_fails_preconstruction(self):
        p=v2(sample()[3]);row=p["assessments"][0]
        row["game8"]["tier"]="SS"
        row["general_value"]=None
        row["game8"]["source_url"]=None
        row["game8"]["applicability"]="APPLICABLE"
        with self.assertRaisesRegex(ValueError,"V2_GAME8_SOURCE_REQUIRED"):
            validate_decision_policy(p,master_sha256=PIN)

    def test_high_tier_override_needs_deck_constraint_evidence(self):
        p=v2(sample()[3]);r=next(x for x in p["assessments"]
                                if x["card_id"]=="konami:1200")
        r["deck_adjustment"]=-40
        with self.assertRaisesRegex(ValueError,"V2_APPLICABLE_HIGH_TIER"):
            validate_decision_policy(p,master_sha256=PIN)
        r["game8"]["applicability"]="CONSTRAINED"
        with self.assertRaisesRegex(ValueError,"V2_CONSTRAINED_CARD_REQUIRES"):
            validate_decision_policy(p,master_sha256=PIN)
        r["evidence_refs"].append("CONSTRAINT:SYNTHETIC_CARD_TEXT_REVIEW")
        reviewed=validate_decision_policy(p,master_sha256=PIN)
        self.assertEqual(50,reviewed["MAIN","konami:1200"]["score_by_copy"][0])

    def test_cross_theme_not_forced_when_reviewed_zero(self):
        p=v2(sample()[3])
        r=next(x for x in p["assessments"] if x["card_id"]=="konami:1400")
        r["recommended_max"]=0
        result=run(p)
        self.assertFalse(any(x["family"]=="MIXED_REDESIGN" for x in result["solutions"]))
        self.assertTrue(any(x["reason"]=="CROSS_THEME_NOT_REVIEWED_OR_USABLE"
                            for x in result["rejected"]))

    def test_engine_package_minimum_respects_reviewed_limit(self):
        p=v2(sample()[3])
        row=next(x for x in p["assessments"] if x["card_id"]=="konami:1500")
        row["recommended_max"]=0
        result=run(p)
        self.assertFalse(any(x["family"]=="THEME_WITH_ENGINE" for x in result["solutions"]))
        self.assertTrue(any(x["reason"]=="ENGINE_REQUIRED_PART_MISSING"
                            for x in result["rejected"]))

    def test_not_listed_not_assigned_zero(self):
        m=validate_decision_policy(v2(sample()[3]),master_sha256=PIN)
        a=m["MAIN","konami:1000"]
        self.assertEqual(70,a["score_by_copy"][0])
        self.assertEqual("NOT_LISTED",a["game8"]["tier"])

    def test_inapplicable_tier_never_adopted(self):
        p=v2(sample()[3]);r=next(x for x in p["assessments"]
                                 if x["card_id"]=="konami:1200")
        r["game8"]["applicability"]="NOT_APPLICABLE"
        r["recommended_max"]=0
        r["deck_adjustment"]=-60
        out=run(p)
        self.assertGreater(out["solution_count"],0)
        for sol in out["solutions"]:
            self.assertNotIn("konami:1200",
                             {x["card_id"] for x in sol["candidate"]["cards"]})

    def test_unreviewed_or_missing_candidate_never_silent(self):
        p=v2(sample()[3])
        p["assessments"].pop()
        with self.assertRaisesRegex(ValueError,"V2_ALL_ANNOTATED_CARDS_REQUIRE_REVIEW"):
            run(p)
        p=v2(sample()[3]);p["assessments"][0]["assessment_status"]="UNVERIFIED_SOURCE"
        with self.assertRaisesRegex(ValueError,"V2_ROLE_OR_REVIEW"):
            run(p)

    def test_mandatory_theme_quantity_cannot_exceed_review(self):
        p=v2(sample()[3])
        c=next(x for x in p["assessments"] if x["card_id"]=="konami:1000")
        c["recommended_max"]=1
        with self.assertRaisesRegex(ValueError,"V2_MANDATORY_COPIES_EXCEED_REVIEWED_MAX"):
            run(p)

    def test_full_engine_uses_v2_scores(self):
        a=sample()[3];out=run(v2(a))
        self.assertEqual("EVIDENCE_COPY_SCORING_V2",out["policy_mode"])
        self.assertTrue(out["solutions"])
        pure=next(x for x in out["solutions"] if x["family"]=="PURE_THEME")
        self.assertEqual(40,pure["candidate"]["declared_main"])
        traces=[x for x in pure["competitive_decisions"]
                if x["card_id"]=="konami:1200"]
        self.assertTrue(traces)
        self.assertTrue(all(x["score_components"]["tier"]=="SS" for x in traces))
        self.assertTrue(all(x["copy_reason"] for x in traces))

    def test_no_automatically_filled_unowned_ur(self):
        out=run(v2(sample()[3]))
        for sol in out["solutions"]:
            self.assertNotIn("konami:1300",
                             {x["card_id"] for x in sol["candidate"]["cards"]})

if __name__=="__main__":
    unittest.main()
