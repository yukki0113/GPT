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
            "profile_data_date": "2025-10-25",
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
        "sample_size_band": "small", "period": "2021-2025YTD",
        "distance_ranges": [],
    }
    return {
        "race": {"date": "2025-10-26", "venue": "京都", "surface": "芝", "distance_m": 2000, "field_size": 1},
        "metadata": {"history_enrichment": {
            "as_of_exclusive": "2025-10-26",
            "future_leakage_policy": "all rolling statistics from JRDB Analysis canonical with race_date < target_date",
            "pedigree_enrichment": {
                "status": "ACTIVE", "scoring": False,
                "identity_version": "P1-0.1", "context_version": "P2-0.1",
                "identity_source": "JRDB Analysis canonical target identity projection",
                "historical_context_source": "JRDB Analysis canonical (as-of-exclusive)",
                "historical_dimensions": ["sire_name", "broodmare_sire_name"],
                "small_sample_policy": "retain_with_sample_size",
                "missing_field_policy": "null_no_guess",
                "condition_scope": "venue_surface_exact_distance_plus_target_distance_ranges",
                "as_of_exclusive": "2025-10-26", "result_fields_exposed": False,
            },
        }},
        "horses": [{
            "basic": {"horse_id": "H1"},
            "pedigree": {"horse_id": "H1", "sire_name": "父", "broodmare_sire_name": "母父",
                         "scoring": False, "source_policy": "approved_pre_race_identity_fields_only",
                         "source": "JRDB Analysis canonical target identity projection"},
            "pedigree_context": {
                "sire": dict(stat), "broodmare_sire": dict(stat),
                "scoring": False, "interpretation_policy": "descriptive_context_only",
                "small_sample_policy": "retain_with_sample_size",
            },
        }],
    }


class AdapterTest(unittest.TestCase):
    def test_real_p2_shape_to_review(self):
        p2 = adapt_racenote_bundle(bundle(), ["H1"], expected_context=CONTEXT)
        review = BloodReviewEngine(FakeReader()).horse_review(
            "H1", CONTEXT, pedigree_context=p2["H1"])
        self.assertEqual(review["status"], "AVAILABLE")
        self.assertEqual(review["review"]["pedigree_context"]["sire"]["starts"], 10)
        self.assertIsNone(review["review"]["overall_score"])

    def test_mismatched_aggregate_asof_rejected(self):
        raw = bundle()
        raw["horses"][0]["pedigree_context"]["sire"]["as_of_exclusive"] = "2025-10-27"
        result = adapt_racenote_bundle(raw, ["H1"], expected_context=CONTEXT)
        self.assertNotIn("sire", result["H1"])

    def test_no_future_policy_attestation(self):
        raw = bundle()
        raw["metadata"]["history_enrichment"]["future_leakage_policy"] = "unknown"
        with self.assertRaises(P2AdapterError):
            adapt_racenote_bundle(raw, ["H1"], expected_context=CONTEXT)

    def test_duplicate_horse_id_rejected(self):
        raw = bundle()
        raw["horses"].append(raw["horses"][0])
        raw["race"]["field_size"] = 2
        with self.assertRaises(P2AdapterError):
            adapt_racenote_bundle(raw, ["H1"], expected_context=CONTEXT)

    def test_identity_mismatch_not_adopted(self):
        raw = bundle()
        raw["horses"][0]["pedigree"]["horse_id"] = "OTHER"
        self.assertEqual(adapt_racenote_bundle(raw, ["H1"], expected_context=CONTEXT), {})

    def test_all_requested_horses_get_review(self):
        p2 = adapt_racenote_bundle(bundle(), ["H1"], expected_context=CONTEXT)
        got = BloodReviewEngine(FakeReader()).reviews_for_horses(
            ["H1", "H2"], CONTEXT, pedigree_contexts=p2)
        self.assertEqual(set(got), {"H1", "H2"})
        self.assertEqual(got["H1"]["status"], "AVAILABLE")
        self.assertEqual(got["H2"]["status"], "PARTIAL")

    def test_wrong_cohort_rejected(self):
        with self.assertRaisesRegex(P2AdapterError, "cohort"):
            adapt_racenote_bundle(bundle(), ["H1", "H2"], expected_context=CONTEXT)

    def test_wrong_race_scope_rejected(self):
        for changed in ({"venue": "東京"}, {"surface": "ダート"}, {"distance": 1800}):
            with self.subTest(changed=changed), self.assertRaisesRegex(P2AdapterError, "context"):
                adapt_racenote_bundle(bundle(), ["H1"],
                                      expected_context={**CONTEXT, **changed})

    def test_wrong_p2_producer_scope_rejected(self):
        raw = bundle()
        raw["metadata"]["history_enrichment"]["pedigree_enrichment"]["condition_scope"] = "date_only"
        with self.assertRaisesRegex(P2AdapterError, "producer contract"):
            adapt_racenote_bundle(raw, ["H1"], expected_context=CONTEXT)

    def test_zero_starts_remains_evidence(self):
        raw = bundle()
        raw["horses"][0]["pedigree_context"]["sire"].update(
            starts=0, wins=0, top3=0, sample_size_band="none")
        p2 = adapt_racenote_bundle(raw, ["H1"], expected_context=CONTEXT)
        self.assertEqual(p2["H1"]["sire"]["starts"], 0)

    def test_wrong_role_source_rejected(self):
        raw = bundle()
        raw["horses"][0]["pedigree_context"]["sire"]["source"] = "unknown"
        p2 = adapt_racenote_bundle(raw, ["H1"], expected_context=CONTEXT)
        self.assertNotIn("sire", p2["H1"])


if __name__ == "__main__":
    unittest.main()
