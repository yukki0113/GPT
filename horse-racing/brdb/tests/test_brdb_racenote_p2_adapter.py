from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brdb_racenote_p2_adapter import adapt_racenote_bundle, P2AdapterError
from brdb_blood_review import BloodReviewEngine

CONTEXT = {"target_date": "2025-10-26", "venue": "京都", "surface": "芝", "distance": 2000}


class FakeReader:
    def metadata(self):
        return {"generation_id": "eeca93556584a5b8", "schema_version": "v0.1"}

    def horse_pedigree(self, horse_id):
        return {
            "sire": {"name": "父", "lineage": None},
            "dam": {"name": "母"},
            "broodmare_sire": {"name": "母父", "lineage": None},
        }


def bundle():
    stat = {
        "starts": 10, "wins": 2, "top3": 4,
        "as_of_exclusive": "2025-10-26",
        "track_condition_scope": "all_conditions",
        "source": "JRDB Analysis canonical (as-of-exclusive)",
    }
    return {
        "race": {"date": "2025-10-26", "venue": "京都", "surface": "芝", "distance_m": 2000},
        "metadata": {"history_enrichment_poc": {
            "as_of_exclusive": "2025-10-26",
            "future_leakage_policy": "all rolling statistics from JRDB Analysis canonical with race_date < target_date",
        }},
        "horses": [{
            "basic": {"horse_id": "H1"},
            "pedigree": {"horse_id": "H1", "sire_name": "父", "broodmare_sire_name": "母父"},
            "pedigree_context": {
                "sire": dict(stat), "broodmare_sire": dict(stat),
                "scoring": False, "interpretation_policy": "descriptive_context_only",
            },
        }],
    }


class AdapterTest(unittest.TestCase):
    def test_real_p2_shape_to_review(self):
        p2 = adapt_racenote_bundle(bundle(), ["H1"])
        review = BloodReviewEngine(FakeReader()).horse_review(
            "H1", CONTEXT, pedigree_context=p2["H1"])
        self.assertEqual(review["status"], "AVAILABLE")
        self.assertEqual(review["review"]["pedigree_context"]["sire"]["starts"], 10)
        self.assertIsNone(review["review"]["overall_score"])

    def test_mismatched_aggregate_asof_rejected(self):
        raw = bundle()
        raw["horses"][0]["pedigree_context"]["sire"]["as_of_exclusive"] = "2025-10-27"
        result = adapt_racenote_bundle(raw, ["H1"])
        self.assertNotIn("sire", result["H1"])

    def test_no_future_policy_attestation(self):
        raw = bundle()
        raw["metadata"]["history_enrichment_poc"]["future_leakage_policy"] = "unknown"
        with self.assertRaises(P2AdapterError):
            adapt_racenote_bundle(raw, ["H1"])

    def test_duplicate_horse_id_rejected(self):
        raw = bundle()
        raw["horses"].append(raw["horses"][0])
        with self.assertRaises(P2AdapterError):
            adapt_racenote_bundle(raw, ["H1"])

    def test_identity_mismatch_not_adopted(self):
        raw = bundle()
        raw["horses"][0]["pedigree"]["horse_id"] = "OTHER"
        self.assertEqual(adapt_racenote_bundle(raw, ["H1"]), {})

    def test_all_requested_horses_get_review(self):
        p2 = adapt_racenote_bundle(bundle(), ["H1", "H2"])
        got = BloodReviewEngine(FakeReader()).reviews_for_horses(
            ["H1", "H2"], CONTEXT, pedigree_contexts=p2)
        self.assertEqual(set(got), {"H1", "H2"})
        self.assertEqual(got["H1"]["status"], "AVAILABLE")
        self.assertEqual(got["H2"]["status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
