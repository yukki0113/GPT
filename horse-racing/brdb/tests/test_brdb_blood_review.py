from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brdb_blood_review import BloodReviewEngine, CONTRACT_VERSION


class StubReader:
    def metadata(self):
        return {"generation_id": "eeca93556584a5b8", "schema_version": "v0.1"}

    def horse_pedigree(self, horse_id):
        if horse_id == "missing":
            return None
        return {
            "sire": {"name": "父", "lineage": {"lineage_code": "1206", "major_name": "ロイヤルチャージャー", "minor_name": "ヘイロー", "source_name": "JRDB"}},
            "dam": {"name": "母"},
            "broodmare_sire": {"name": "母父", "lineage": {"lineage_code": "1503", "major_name": "ネイティヴダンサー", "minor_name": "ミスタープロスペクター", "source_name": "JRDB"}},
        }


CTX = {"target_date": "2025-10-26", "venue": "京都", "surface": "芝", "distance": 2000}


def p2():
    return {
        "target_context": CTX,
        "as_of_exclusive": "2025-10-26",
        "pedigree_names": {"sire": "父", "broodmare_sire": "母父"},
        "sire": {"starts": 10, "wins": 2, "top3": 4, "source": "JRDB Analysis"},
        "broodmare_sire": {"starts": 5, "wins": 1, "top3": 2, "source": "JRDB Analysis"},
    }


class BloodReviewTest(unittest.TestCase):
    def setUp(self):
        self.engine = BloodReviewEngine(StubReader())

    def test_missing_identity(self):
        self.assertEqual(self.engine.horse_review("", CTX)["status"], "NO_HORSE_ID")

    def test_unknown_horse(self):
        self.assertEqual(self.engine.horse_review("missing", CTX)["status"], "NO_PEDIGREE")

    def test_invalid_context(self):
        self.assertEqual(self.engine.horse_review("H1", {**CTX, "surface": "unknown"})["status"], "UNSUPPORTED_CONTEXT")

    def test_without_p2_is_partial_and_non_scoring(self):
        got = self.engine.horse_review("H1", CTX)
        self.assertEqual(got["status"], "PARTIAL")
        self.assertIsNone(got["review"]["overall_score"])
        self.assertEqual(got["confidence"], "DESCRIPTIVE_ONLY")
        self.assertEqual(got["contract_version"], CONTRACT_VERSION)

    def test_with_scoped_p2_is_available(self):
        got = self.engine.horse_review("H1", CTX, pedigree_context=p2())
        self.assertEqual(got["status"], "AVAILABLE")
        self.assertEqual(got["review"]["pedigree_context"]["sire"]["starts"], 10)
        self.assertEqual(got["review"]["pedigree_context"]["sire"]["top3_rate"], .4)
        self.assertIsNone(got["review"]["overall_score"])

    def test_wrong_sire_identity_is_not_reused(self):
        context = p2()
        context["pedigree_names"]["sire"] = "別の父"
        got = self.engine.horse_review("H1", CTX, pedigree_context=context)
        self.assertEqual(got["status"], "PARTIAL")
        self.assertIsNone(got["review"]["pedigree_context"])

    def test_different_scope_is_not_reused(self):
        context = p2()
        context["target_context"] = {**CTX, "distance": 1800}
        got = self.engine.horse_review("H1", CTX, pedigree_context=context)
        self.assertEqual(got["status"], "PARTIAL")
        self.assertIsNone(got["review"]["pedigree_context"])

    def test_future_or_mismatched_asof_is_not_reused(self):
        context = p2()
        context["as_of_exclusive"] = "2025-10-27"
        self.assertEqual(self.engine.horse_review("H1", CTX, pedigree_context=context)["status"], "PARTIAL")

    def test_corrupt_counts_rejected(self):
        context = p2()
        context["sire"]["top3"] = 11
        got = self.engine.horse_review("H1", CTX, pedigree_context=context)
        self.assertEqual(got["status"], "PARTIAL")
        self.assertNotIn("sire", got["review"]["pedigree_context"])

    def test_batch_equals_single(self):
        ids = ["H1", "missing"]
        got = self.engine.reviews_for_horses(ids, CTX, pedigree_contexts={"H1": p2()})
        self.assertEqual(got["H1"], self.engine.horse_review("H1", CTX, pedigree_context=p2()))
        self.assertEqual(got["missing"], self.engine.horse_review("missing", CTX))


if __name__ == "__main__":
    unittest.main()
