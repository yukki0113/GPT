import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_edge_v05_2026_pre_race_match_freeze import (  # noqa: E402
    FreezeError,
    build_matches,
    condition_matches,
    derive_first_blinkers,
    derive_first_surface,
    fingerprint_rows,
    load_cohort,
    validate_match_fact_schema,
)

COHORT = ROOT / "config/edgedb/v0_5/frozen/v05_positive_value_frozen_cohort.json"


def fact(**values):
    return {"race_date": "2026-07-01", "race_key": "202607010101", "race_horse_key": "20260701010101",
            "horse_id": "H1", "horse_no": 1, "venue_code": "09", "surface_code": "2",
            "distance_m": 1800, "frame_no": 5, "sire_name": "SIRE", "distance_change": "EXTEND",
            "surface_transition": "1->2", "first_dirt": True, "first_turf": True,
            "first_blinkers": True, "going_bucket": "GOOD", **values}


class MatchFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidates, cls.audit = load_cohort(COHORT)

    def candidate(self, key):
        return next(c for c in self.candidates if key in c["conditions"])

    def test_01_cohort_sha_exact(self):
        self.assertEqual(self.audit["cohort_sha256"], "a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9")

    def test_02_all_candidates_parse(self):
        self.assertEqual(len(self.candidates), 1620)
        self.assertEqual(self.audit["unsupported_condition_count"], 0)

    def test_03_unsupported_key_fails_closed(self):
        with self.assertRaisesRegex(FreezeError, "unsupported condition"):
            condition_matches({"mystery": 1}, fact())

    def test_04_t1_exact_match(self):
        candidate = self.candidate("going_bucket")
        self.assertTrue(condition_matches(candidate["conditions"], fact(sire_name=candidate["conditions"]["sire_name"], surface_code="2")))

    def test_05_t2_exact_match(self):
        candidate = self.candidate("distance_m")
        self.assertTrue(condition_matches(candidate["conditions"], fact(distance_m=1200, surface_code="1", venue_code="09", sire_name=candidate["conditions"]["sire_name"])))

    def test_06_t3_extend_and_shorten_exact(self):
        candidate = self.candidate("distance_change")
        cond = candidate["conditions"]
        self.assertTrue(condition_matches(cond, fact(distance_change=cond["distance_change"], sire_name=cond["sire_name"])))
        self.assertFalse(condition_matches(cond, fact(distance_change="SHORTEN", sire_name=cond["sire_name"])))

    def test_07_t4_surface_switch_exact(self):
        candidate = self.candidate("surface_transition")
        cond = candidate["conditions"]
        self.assertTrue(condition_matches(cond, fact(surface_transition=cond["surface_transition"], sire_name=cond["sire_name"])))

    def test_08_first_dirt_chronology_through_2026(self):
        self.assertTrue(derive_first_surface("2", "2", [], identity=True, target_ambiguous=False))
        self.assertFalse(derive_first_surface("2", "2", [{"race_date":"2026-03-01","surface_code":"2"}], identity=True, target_ambiguous=False))

    def test_09_first_turf_chronology_through_2026(self):
        self.assertTrue(derive_first_surface("1", "1", [], identity=True, target_ambiguous=False))
        self.assertFalse(derive_first_surface("1", "1", [{"race_date":"2026-03-01","surface_code":"1"}], identity=True, target_ambiguous=False))

    def test_10_first_blinkers_chronology(self):
        self.assertTrue(derive_first_blinkers("1", [], identity=True, target_ambiguous=False))
        self.assertFalse(derive_first_blinkers("1", [{"race_date":"2026-03-01","blinker_code":"1"}], identity=True, target_ambiguous=False))
        self.assertIsNone(derive_first_blinkers("2", [], identity=True, target_ambiguous=False))
        self.assertFalse(derive_first_blinkers("", [], identity=True, target_ambiguous=False))
        self.assertIsNone(derive_first_blinkers(None, [], identity=True, target_ambiguous=False))

    def test_11_future_2026_history_cannot_affect_earlier_target(self):
        future = {"race_date":"2026-08-01", "surface_code":"2"}
        self.assertTrue(derive_first_surface("2", "2", [future] if future["race_date"] < "2026-07-01" else [], identity=True, target_ambiguous=False))

    def test_12_target_row_not_prior_history(self):
        target = {"race_date":"2026-07-01", "surface_code":"2"}
        prior = [e for e in [target] if e["race_date"] < "2026-07-01"]
        self.assertTrue(derive_first_surface("2", "2", prior, identity=True, target_ambiguous=False))

    def test_13_unknown_never_matches_true(self):
        self.assertFalse(condition_matches({"first_dirt":"true"}, fact(first_dirt=None)))

    def test_14_result_field_rejected(self):
        with self.assertRaises(FreezeError): validate_match_fact_schema(fact(finish_position=1))

    def test_15_popularity_rejected(self):
        with self.assertRaises(FreezeError): validate_match_fact_schema(fact(popularity=1))

    def test_16_odds_rejected(self):
        with self.assertRaises(FreezeError): validate_match_fact_schema(fact(odds=2.1))

    def test_17_deterministic_match_order(self):
        c = self.candidate("going_bucket")
        f1 = fact(sire_name=c["conditions"]["sire_name"])
        f2 = fact(race_date="2026-06-30", race_key="202606300101", race_horse_key="20260630010101", sire_name=c["conditions"]["sire_name"])
        rows = build_matches([c], [f1, f2])
        self.assertEqual([r["race_date"] for r in rows], sorted(r["race_date"] for r in rows))

    def test_18_deterministic_fact_fingerprint(self):
        rows = [fact(), fact(race_key="b", race_horse_key="b")]
        self.assertEqual(fingerprint_rows(rows, ("race_key",)), fingerprint_rows(rows[::-1], ("race_key",)))

    def test_19_deterministic_match_fingerprint(self):
        c = self.candidate("going_bucket")
        rows = build_matches([c], [fact(sire_name=c["conditions"]["sire_name"])])
        self.assertEqual(fingerprint_rows(rows, ("race_key", "candidate_id")), fingerprint_rows(copy.deepcopy(rows), ("race_key", "candidate_id")))

    def test_20_identical_rerun_semantic_stability(self):
        c = self.candidate("going_bucket")
        facts = [fact(sire_name=c["conditions"]["sire_name"])]
        first, second = build_matches([c], facts), build_matches([c], copy.deepcopy(facts))
        self.assertEqual(first, second)
        self.assertEqual(fingerprint_rows(first, ("race_date", "race_key", "race_horse_key", "candidate_id")),
                         fingerprint_rows(second, ("race_date", "race_key", "race_horse_key", "candidate_id")))


if __name__ == "__main__":
    unittest.main()
