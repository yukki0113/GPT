"""Synthetic competitive selection regression; never print private deck details."""
from copy import deepcopy
import unittest

from engine_m6.decision_policy import validate_decision_policy,policy_score
from engine_m6.recompose import recompose_portfolio
from test_m6_5c import sample,run,PIN


def policy(annotations):
    rows=[]
    for a in annotations:
        cid=a["card_id"]
        score=4
        if cid=="konami:1200":score=1  # traditionally top priority, but weak fit
        if cid=="konami:1203":score=5  # lower static priority, good practical fit
        if cid=="konami:2004":score=1  # valid material, but low real utility
        if cid=="konami:2007":score=5  # low static priority, valuable EX role
        rows.append({
            "card_id":cid,"section":a["section"],
            "axes":{"baseline":score,"meta_fit":score,"deck_fit":score,
                    "tempo":score,"resource_efficiency":score,"role_need":score},
            "competitive_group":("GENERIC_"+a["role"] if a["category"].endswith("GENERIC")
                                 else "THEME_"+a["role"]),
            "recommended_max":1 if a["section"]=="EXTRA" and
                                  a["category"]=="GENERIC_EXTRA" else a["maximum"],
            "assessment_status":"UNVERIFIED_SOURCE",
            "evidence_refs":["SYNTHETIC:TEST_ONLY"],
            "reason":"Synthetic competitive annotation, not gameplay evidence",
            "role":a["role"],"summon_role":"SYNTHETIC_TEST",
            "lock_review":"REVIEW_REQUIRED","condition_review":"REVIEW_REQUIRED"})
    return {"schema":"md-m6-7-decision-policy-v1",
            "master_sqlite_sha256":PIN,
            "as_of":"2026-11-12T17:00:00+09:00",
            "min_main_score":55,"min_extra_score":75,
            "required_review_names":["SYNTHETIC-konami:1203"],
            "assessments":rows}


def generate(t,r,d,a,s,p,pol):
    return recompose_portfolio(r,t,discovery_results=d,annotations=a,
                               material_screen=s,engine_packages=p,
                               decision_policy=pol)


class CompetitiveSelectionTests(unittest.TestCase):
    def test_reject_unpinned_policy(self):
        t,r,d,a,s,p=sample()
        pol=policy(a);pol["master_sqlite_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"master SHA mismatch"):
            generate(t,r,d,a,s,p,pol)

    def test_cannot_silently_use_unassessed_generic(self):
        t,r,d,a,s,p=sample()
        pol=policy(a)
        pol["assessments"]=[x for x in pol["assessments"] if x["card_id"]!="konami:1200"]
        result=generate(t,r,d,a,s,p,pol)
        for option in result["solutions"]:
            self.assertNotIn("konami:1200",{x["card_id"] for x in option["candidate"]["cards"]})
            self.assertTrue(option["competitive_policy_applied"])

    def test_marginal_competitive_priority_beats_old_static_priority(self):
        t,r,d,a,s,p=sample()
        pol=policy(a)
        result=generate(t,r,d,a,s,p,pol)
        pure=next(x for x in result["solutions"] if x["family"]=="PURE_THEME")
        self.assertEqual(40,pure["candidate"]["declared_main"])
        ids={x["card_id"] for x in pure["candidate"]["cards"]}
        self.assertIn("konami:1203",ids)
        self.assertNotIn("konami:1200",ids)
        self.assertTrue(any(x["card_id"]=="konami:1203" for x in pure["competitive_decisions"]))

    def test_low_utility_extra_not_added_just_to_fill(self):
        t,r,d,a,s,p=sample()
        pol=policy(a)
        result=generate(t,r,d,a,s,p,pol)
        pure=next(x for x in result["solutions"] if x["family"]=="PURE_THEME")
        ids={x["card_id"] for x in pure["candidate"]["cards"]}
        self.assertNotIn("konami:2004",ids)
        self.assertIn("konami:2007",ids)
        self.assertLess(pure["extra_used"],15)

    def test_missing_trend_candidate_must_be_reported(self):
        t,r,d,a,s,p=sample()
        pol=policy(a)
        pol["required_review_names"].append("未発見の架空環境カード")
        result=generate(t,r,d,a,s,p,pol)
        self.assertEqual("REVIEW_REQUIRED",result["policy_coverage_status"])
        self.assertEqual([{"name":"未発見の架空環境カード","reason":"NOT_DISCOVERED"}],
                         result["required_name_gaps"])

    def test_named_candidate_unassessed_is_coverage_gap(self):
        t,r,d,a,s,p=sample()
        pol=policy(a)
        pol["assessments"]=[row for row in pol["assessments"]
                            if row["card_id"]!="konami:1203"]
        result=generate(t,r,d,a,s,p,pol)
        self.assertIn({"name":"SYNTHETIC-konami:1203",
                       "reason":"NOT_COMPETITIVELY_ASSESSED"},
                      result["required_name_gaps"])

    def test_bad_assessment_scores_fail_closed(self):
        t,r,d,a,s,p=sample()
        pol=policy(a);pol["assessments"][0]["axes"]["meta_fit"]=9
        with self.assertRaisesRegex(ValueError,"axes"):
            generate(t,r,d,a,s,p,pol)

    def test_wrong_assessed_role_is_rejected_not_reinterpreted(self):
        t,r,d,a,s,p=sample()
        pol=policy(a)
        row=next(x for x in pol["assessments"] if x["card_id"]=="konami:1203")
        row["role"]="DRAW"
        result=generate(t,r,d,a,s,p,pol)
        pure=next(x for x in result["solutions"] if x["family"]=="PURE_THEME")
        self.assertNotIn("konami:1203",{x["card_id"] for x in pure["candidate"]["cards"]})

    def test_no_input_mutation_and_deterministic(self):
        t,r,d,a,s,p=sample();pol=policy(a)
        before=deepcopy((t,r,d,a,s,p,pol))
        x=generate(t,r,d,a,s,p,pol)
        self.assertEqual(before,(t,r,d,a,s,p,pol))
        self.assertEqual(x,generate(t,r,d,a,s,p,pol))


if __name__=="__main__":
    unittest.main()
