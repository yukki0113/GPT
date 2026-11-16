"""Synthetic source-only checks: no private inventory in GitHub."""
import unittest
from engine_m6.generic_coverage import (
    owned_generic_research_query, audit_owned_generic_coverage)


def row(cid,name,owned,section="MAIN"):
    return {"card_id":cid,"name":name,"section_candidate":section,
            "owned_state":"KNOWN_POSITIVE" if owned>0 else "KNOWN_ZERO",
            "owned_count":owned}


class OwnedGenericCoverageTests(unittest.TestCase):
    def test_query_is_generic_and_not_named(self):
        self.assertEqual({"section":"MAIN","owned_only":True,"limit":300},
                         owned_generic_research_query())

    def test_owned_unannotated_candidate_remains_visible(self):
        discoveries=[{"results":[
            row("konami:123","架空候補A",1),
            row("konami:124","架空候補B",2),
            row("konami:125","架空未所持",0),
            row("konami:126","架空EX",1,"EXTRA")]}]
        anns=[{"section":"MAIN","card_id":"konami:123"}]
        policy={("MAIN","konami:123"):{"role":"UTILITY"}}
        x=audit_owned_generic_coverage(discoveries,anns,policy)
        self.assertEqual(2,x["owned_main_discovered"])
        self.assertEqual(1,x["missing_assessment_count"])
        self.assertEqual("konami:124",x["missing_assessment"][0]["card_id"])
        self.assertEqual("OWNED_MAIN_NOT_ANNOTATED",
                         x["missing_assessment"][0]["reason"])

    def test_annotation_without_competitive_review_is_gap(self):
        discoveries=[{"results":[row("konami:123","架空候補A",1)]}]
        x=audit_owned_generic_coverage(
            discoveries,[{"section":"MAIN","card_id":"konami:123"}],{})
        self.assertEqual("OWNED_MAIN_NOT_ASSESSED",
                         x["missing_assessment"][0]["reason"])
        self.assertFalse(x["gameplay_verified"])

    def test_full_coverage_is_not_gameplay_certification(self):
        discoveries=[{"results":[row("konami:123","架空候補A",1)]}]
        x=audit_owned_generic_coverage(
            discoveries,[{"section":"MAIN","card_id":"konami:123"}],
            {("MAIN","konami:123"):{"role":"UTILITY"}})
        self.assertEqual("COVERED_SOURCE_SCOPE",x["status"])
        self.assertFalse(x["gameplay_verified"])


if __name__=="__main__":
    unittest.main()
