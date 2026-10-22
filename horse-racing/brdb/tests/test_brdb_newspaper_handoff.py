import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brdb_newspaper_handoff import project_review, project_field, BRDBHandoffError


def review(horse_id="12345678", status="AVAILABLE"):
    return {
        "horse_id": horse_id, "status": status,
        "contract_version": "brdb-review-v0.1",
        "facts": {"sire_name": "父", "dam_name": "母", "broodmare_sire_name": "母父"},
        "classification": {"sire_line": None, "broodmare_sire_line": None, "regional_type": None},
        "review": {"overall_score": None, "components": [], "positive_factors": [],
                   "negative_factors": [], "summary": "description", "pedigree_context": None},
        "coverage": {"status": "FULL", "pedigree_fields": 3, "pedigree_context": "NONE"},
        "confidence": "DESCRIPTIVE_ONLY",
        "provenance": {"generation_id": "eeca93556584a5b8"},
        "untrusted_raw_result": {"finish": 1, "odds": 2.5},
    }


class HandoffTest(unittest.TestCase):
    def test_projection_filters_unlisted_fields(self):
        result = project_review(review())
        self.assertEqual(result["contract_version"], "brdb-newspaper-handoff-v0.1")
        self.assertNotIn("untrusted_raw_result", result["detail"])
        self.assertNotIn("finish", str(result))

    def test_unavailable_keeps_status(self):
        result = project_review(review(status="AS_OF_UNVERIFIED"))
        self.assertFalse(result["display_available"])

    def test_no_score(self):
        r = review()
        r["review"]["overall_score"] = 88
        with self.assertRaises(BRDBHandoffError):
            project_review(r)

    def test_no_regional_type(self):
        r = review()
        r["classification"]["regional_type"] = "JAPAN"
        with self.assertRaises(BRDBHandoffError):
            project_review(r)

    def test_cohort_exact(self):
        with self.assertRaises(BRDBHandoffError):
            project_field({"12345678": review()}, ["12345678", "87654321"])

    def test_identity_exact(self):
        with self.assertRaises(BRDBHandoffError):
            project_field({"12345678": review(horse_id="98765432")}, ["12345678"])

    def test_field_preserves_unavailable(self):
        got = project_field(
            {"12345678": review(), "87654321": review("87654321", "AS_OF_UNVERIFIED")},
            ["12345678", "87654321"],
        )
        self.assertEqual(len(got), 2)
        self.assertFalse(got["87654321"]["display_available"])


if __name__ == "__main__":
    unittest.main()
