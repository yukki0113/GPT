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
            "min_main_score":50,"min_extra_score":75,
            "required_review_names":["SYNTHETIC-konami:1203"],
            "assessments":rows}


def regulation(annotations, *, as_of="2026-11-11"):
    return {"schema":"md-m6-7-regulation-gate-v1","format":"MD_STANDARD",
            "master_sqlite_sha256":PIN,"effective_on":as_of,
            "checked_on":as_of,"verification":"REVIEWED_MD_SOURCE",
            "source_refs":["https://example.org/synthetic-md-regulation"],
            "card_limits":{a["card_id"]:3 for a in annotations}}


def generate(t,r,d,a,s,p,pol,legality=None):
    return recompose_portfolio(r,t,discovery_results=d,annotations=a,
                               material_screen=s,engine_packages=p,
                               decision_policy=pol,
                               regulation_policy=regulation(a) if legality is None else legality)


class CompetitiveSelectionTests(unittest.TestCase):
    def test_regulation_required_before_competitive_construction(self):
        t,r,d,a,s,p=sample()
        with self.assertRaisesRegex(ValueError,"MD_REGULATION_POLICY_REQUIRED"):
            recompose_portfolio(r,t,discovery_results=d,annotations=a,
                                material_screen=s,engine_packages=p,
                                decision_policy=policy(a))

    def test_banned_and_limited_cards_cannot_be_adopted(self):
        t,r,d,a,s,p=sample();limits=regulation(a)
        limits["card_limits"]["konami:1203"]=0
        limits["card_limits"]["konami:1000"]=1
        result=generate(t,r,d,a,s,p,policy(a),limits)
        self.assertEqual(0,result["solution_count"])
        self.assertTrue(any(x["reason"]=="REQUIRED_THEME_CARD_UNAVAILABLE"
                            for x in result["rejected"]))
        limits["card_limits"]["konami:1000"]=3
        result=generate(t,r,d,a,s,p,policy(a),limits)
        self.assertGreater(result["solution_count"],0)
        for option in result["solutions"]:
            self.assertNotIn("konami:1203",{c["card_id"] for c in option["candidate"]["cards"]})
            self.assertTrue(option["md_regulation_gate_applied"])

    def test_regulation_coverage_unknown_and_stale_fail_closed(self):
        t,r,d,a,s,p=sample();policy_input=policy(a)
        missing=regulation(a);missing["card_limits"].pop("konami:2000")
        with self.assertRaisesRegex(ValueError,"MD_REGULATION_INCOMPLETE_CARD_COVERAGE"):
            generate(t,r,d,a,s,p,policy_input,missing)
        stale=regulation(a);stale["effective_on"]="2026-09-01";stale["checked_on"]="2026-09-01"
        with self.assertRaisesRegex(ValueError,"MD_REGULATION_STALE_REVIEW"):
            generate(t,r,d,a,s,p,policy_input,stale)
        wrong=regulation(a);wrong["format"]="OCG"
        with self.assertRaisesRegex(ValueError,"MD_REGULATION_FORMAT_MISMATCH"):
            generate(t,r,d,a,s,p,policy_input,wrong)
        unverified=regulation(a);unverified["verification"]="UNVERIFIED_SOURCE"
        with self.assertRaisesRegex(ValueError,"MD_REGULATION_UNVERIFIED_SOURCE"):
            generate(t,r,d,a,s,p,policy_input,unverified)

    def test_low_evidence_generic_filler_is_not_misreported_as_best(self):
        t,r,d,a,s,p=sample();pol=policy(a)
        item=next(x for x in pol["assessments"] if x["card_id"]=="konami:1202")
        item["axes"]={k:2 for k in item["axes"]}
        item["evidence_refs"]=["DB:konami:1202","SOURCE_ONLY"]
        pol["min_main_score"]=30
        result=generate(t,r,d,a,s,p,pol)
        pure=next(x for x in result["solutions"] if x["family"]=="PURE_THEME")
        self.assertIn("weak_generic_fillers",pure)
        self.assertTrue(all(x["reason_code"]=="LOW_EVIDENCE_GENERIC_FILLER_RESEARCH_REQUIRED"
                            for x in pure["weak_generic_fillers"]))

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

    def test_extra_threshold_does_not_silently_leave_usable_slots(self):
        t,r,d,a,s,p=sample()
        pol=policy(a)
        result=generate(t,r,d,a,s,p,pol)
        pure=next(x for x in result["solutions"] if x["family"]=="PURE_THEME")
        ids={x["card_id"] for x in pure["candidate"]["cards"]}
        self.assertIn("konami:2007",ids)
        self.assertEqual(11,pure["extra_used"])
        self.assertEqual("EX_SLOTS_UNFILLED_RESEARCH_REQUIRED",
                         pure["extra_completion_status"])
        self.assertEqual(4,pure["extra_shortfall"])
        self.assertTrue(any(x.get("below_standard_utility_threshold")
                            for x in pure["competitive_decisions"]
                            if x["section"]=="EXTRA"))

    def test_extra_reaches_fifteen_when_fifteenth_is_sourced(self):
        t,r,d,a,s,p=sample()
        # Four independently reviewed, one-copy generic alternatives fill
        # the four open slots without overriding recommended_max.
        for j in range(4):
            cid="konami:"+str(2010+j)
            extra=dict(d[0]["results"][-1])
            extra.update(card_id=cid,name="SYNTHETIC-"+cid,
                         rank=4,link=None,owned_state="UNKNOWN",owned_count=None)
            d[0]["results"].append(extra)
            template=dict(next(x for x in a if x["card_id"]=="konami:2007"))
            template.update(card_id=cid,category="GENERIC_EXTRA",
                            maximum=1,minimum=0,priority=4,
                            evidence_ref="DB:"+cid)
            a.append(template)
            s["results"].append({"card_id":cid,
                                 "screen":"POSSIBLE_ON_PAPER"})
        pol=policy(a)
        result=generate(t,r,d,a,s,p,pol)
        pure=next(x for x in result["solutions"] if x["family"]=="PURE_THEME")
        self.assertEqual(15,pure["extra_used"])
        self.assertEqual(0,pure["extra_shortfall"])
        self.assertEqual("FULL_15_OR_CONFIGURED_CAP",pure["extra_completion_status"])
        self.assertIn("konami:2010",
                      {x["card_id"] for x in pure["candidate"]["cards"]})

    def test_extra_theme_first_but_strong_other_method_can_win(self):
        t,r,d,a,s,p=sample()
        for row in d[0]["results"]:
            if row["card_id"]=="konami:2007":
                row["rank"]=None;row["link"]=2
        pol=policy(a)
        result=generate(t,r,d,a,s,p,pol)
        pure=next(x for x in result["solutions"] if x["family"]=="PURE_THEME")
        traces=[x for x in pure["competitive_decisions"] if x["section"]=="EXTRA"]
        self.assertTrue(any(x["card_id"]=="konami:2007" and
                            x["extra_search_stage"]==2 for x in traces))
        self.assertEqual(["XYZ"],pure["extra_primary_methods"])

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

    def test_truncated_discovery_does_not_claim_full_coverage(self):
        t,r,d,a,s,p=sample()
        d[0]["truncated"]=True
        result=generate(t,r,d,a,s,p,policy(a))
        self.assertEqual("REVIEW_REQUIRED",result["policy_coverage_status"])
        self.assertEqual(1,result["truncated_source_searches"])

    def test_discovered_extra_without_assessment_is_not_silent(self):
        t,r,d,a,s,p=sample()
        d[0]["results"].append({
            **deepcopy(d[0]["results"][-1]),
            "card_id":"konami:99999","name":"未評価の架空EX札"})
        result=generate(t,r,d,a,s,p,policy(a))
        self.assertEqual("REVIEW_REQUIRED",result["policy_coverage_status"])
        self.assertEqual(1,result["unscored_discovery_count"])
        self.assertIn({"section":"EXTRA","card_id":"konami:99999"},
                      result["unscored_discovery_sample"])

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
