"""Synthetic-only unit tests; no licensed inputs, no as-of promotion."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_brdb_m6_prospective_pair_candidate import checked_features, normalized_pairs


class TestProspectiveCandidate(unittest.TestCase):
    @staticmethod
    def fixture():
        import pandas as pd
        handoff = {"target_date": "2026-11-07", "race_roster": [
            {"venue": "東京", "race_no": 1, "horse_nos": [1, 2]}
        ]}
        d = pd.DataFrame([
            {"target_date": "2026-11-07", "venue": "東京", "race_no": 1,
             "race_key": "20261101", "horse_no": n, "horse_id": f"1234567{n}",
             "venue_code": "05", "surface_code": "1", "distance_m": 1600,
             "race_class_code": "A", "sire_line_code": str(n),
             "broodmare_sire_line_code": "4", "ukc_data_date": "20261107"}
            for n in [1, 2]
        ])
        return d, handoff

    def test_valid_exact_roster(self):
        d, h = self.fixture()
        out = checked_features(d, h)
        self.assertEqual(list(out.horse_no), [1, 2])
        self.assertEqual(list(out.month), ["11", "11"])

    def test_outcome_leak_rejected(self):
        d, h = self.fixture()
        d["winner"] = [1, 0]
        with self.assertRaisesRegex(ValueError, "forbidden"):
            checked_features(d, h)

    def test_future_observation_rejected(self):
        d, h = self.fixture()
        d.loc[0, "ukc_data_date"] = "20261108"
        with self.assertRaisesRegex(ValueError, "future UKC"):
            checked_features(d, h)

    def test_missing_horse_or_duplicate_rejected(self):
        d, h = self.fixture()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            checked_features(d.iloc[:1], h)
        d.loc[1, "horse_no"] = 1
        with self.assertRaisesRegex(ValueError, "duplicate"):
            checked_features(d, h)

    def test_bad_identity_rejected(self):
        d, h = self.fixture()
        d.loc[0, "horse_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "canonical"):
            checked_features(d, h)

    def test_normalized_pairs_sum_to_one(self):
        import pandas as pd
        d, h = self.fixture()
        tgt = checked_features(d, h)
        train = pd.DataFrame({"unused": [1]})
        with patch("run_brdb_m6_prospective_pair_candidate.fit_predict", side_effect=[
            [0.7, 0.1], [0.2, 0.6],
        ]) as model:
            pairs = normalized_pairs(train, tgt)
        self.assertEqual(model.call_count, 2)
        self.assertAlmostEqual(sum(p["p_baseline"] for p in pairs), 1)
        self.assertAlmostEqual(sum(p["p_blood_challenger"] for p in pairs), 1)
        self.assertEqual([p["horse_no"] for p in pairs], [1, 2])
        self.assertTrue(all(0 < p["p_baseline"] < 1 for p in pairs))


if __name__ == "__main__":
    unittest.main()
