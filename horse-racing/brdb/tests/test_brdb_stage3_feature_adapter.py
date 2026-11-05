"""Stage 3 sire/BMS non-scoring adapter safety regressions."""
import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brdb_stage2_master_registry import load_json
from brdb_stage3_feature_adapter import (
    FeatureAdapterError, attach_features, attach_field,
)

SEED = ROOT / "taxonomy" / "stallion_master_stage2_external_profiles_v0_1.json"


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.seed = load_json(SEED)
        self.base = {
            "horse_id": "12345678",
            "sire_name": "サンデーサイレンス",
            "sire_birth_year": 1986,
            "sire_line_code": "1206",
            "broodmare_sire_name": "ストームキャット",
            "broodmare_sire_birth_year": 1983,
            "broodmare_sire_line_code": "1108",
        }

    def call(self, record=None, seed=None, depth=5):
        return attach_features(
            self.base if record is None else record,
            self.seed if seed is None else seed,
            source_generation="RESEARCH-TEST",
            max_depth=depth,
        )

    def test_two_lanes_resolve_as_proxies_only(self):
        output = self.call()
        sire = output["lanes"]["sire"]
        bms = output["lanes"]["broodmare_sire"]
        self.assertEqual(sire["status"], "GUARDED_NAME_YEAR_LINEAGE_PROXY_ONLY")
        self.assertEqual(bms["status"], "GUARDED_NAME_YEAR_LINEAGE_PROXY_ONLY")
        self.assertFalse(sire["person_identity_verified"])
        self.assertFalse(bms["person_identity_verified"])
        self.assertEqual(sire["verified_ancestor_paths"], [])
        self.assertEqual(bms["verified_ancestor_paths"], [])
        self.assertEqual(sire["observed_ancestor_paths"][0]["path"], "S")
        self.assertEqual(bms["observed_ancestor_paths"][0]["path"], "DS")
        self.assertFalse(output["prediction_safe"])

    def test_ancestor_path_prefixing(self):
        output = self.call()
        sire = output["lanes"]["sire"]["observed_ancestor_paths"]
        bms = output["lanes"]["broodmare_sire"]["observed_ancestor_paths"]
        self.assertIn("SS", {row["path"] for row in sire})
        self.assertIn("SDS", {row["path"] for row in sire})
        self.assertIn("DSS", {row["path"] for row in bms})
        self.assertIn("DSDS", {row["path"] for row in bms})
        self.assertTrue(all(not row["identity_verified_for_target"] for row in sire+bms))

    def test_code_conflict_not_silent_identity_match(self):
        record = dict(self.base)
        record["broodmare_sire_line_code"] = "1206"
        result = self.call(record)
        self.assertEqual(result["lanes"]["broodmare_sire"]["status"], "GUARD_CONFLICT")
        self.assertIsNone(result["lanes"]["broodmare_sire"]["matched_subject_key"])
        self.assertEqual(result["lanes"]["broodmare_sire"]["observed_ancestor_paths"], [])

    def test_birth_year_conflict(self):
        record = dict(self.base)
        record["sire_birth_year"] = 1985
        result = self.call(record)
        self.assertEqual(result["lanes"]["sire"]["status"], "GUARD_CONFLICT")

    def test_missing_horse_is_not_negative(self):
        record = dict(self.base)
        record["sire_name"] = "非収録種牡馬"
        result = self.call(record)
        self.assertEqual(result["lanes"]["sire"]["status"], "NOT_IN_SEED")
        self.assertEqual(result["lanes"]["sire"]["regional_roots"], [])
        self.assertEqual(result["lanes"]["sire"]["aptitude_claims"], [])

    def test_halo_path_not_verified_for_target_by_source_only(self):
        result = self.call()
        sunday_sire = next(row for row in result["lanes"]["sire"]["observed_ancestor_paths"]
                           if row["path"] == "SS")
        self.assertEqual(sunday_sire["display_name"], "Halo")
        self.assertFalse(sunday_sire["identity_verified_for_target"])
        self.assertFalse(result["lanes"]["sire"]["can_assert_cross"])

    def test_limit_depth_marks_truncation(self):
        result = self.call(depth=2)
        self.assertGreater(result["lanes"]["sire"]["path_truncated_count"], 0)
        self.assertGreater(result["lanes"]["broodmare_sire"]["path_truncated_count"], 0)
        self.assertTrue(all(len(row["path"]) <= 2
                            for v in result["lanes"].values()
                            for row in v["observed_ancestor_paths"]))

    def test_future_asof_approval_and_jrdb_id_rejected(self):
        altered = copy.deepcopy(self.seed)
        altered["subjects"][0]["identity"]["jrdb_horse_id"] = "11111111"
        with self.assertRaises(FeatureAdapterError):
            self.call(seed=altered)
        altered = copy.deepcopy(self.seed)
        altered["subjects"][0]["historical_asof_status"] = "AS_OF_VERIFIED"
        with self.assertRaises(FeatureAdapterError):
            self.call(seed=altered)

    def test_invalid_target_and_duplicate_field_rejected(self):
        altered = dict(self.base)
        altered["horse_id"] = "ABC"
        with self.assertRaises(FeatureAdapterError):
            self.call(altered)
        with self.assertRaises(FeatureAdapterError):
            attach_field([self.base, self.base], self.seed, source_generation="RESEARCH")

    def test_field_sorted_and_never_publishes_insights(self):
        a = dict(self.base)
        a["horse_id"] = "22222222"
        b = dict(self.base)
        b["horse_id"] = "11111111"
        rows = attach_field([a, b], self.seed, source_generation="RESEARCH")
        self.assertEqual([r["horse_id"] for r in rows], ["11111111", "22222222"])
        self.assertTrue(all(not r["can_change_primary_review"] and
                            r["supplemental_insights"] == [] for r in rows))


if __name__ == "__main__":
    unittest.main()
