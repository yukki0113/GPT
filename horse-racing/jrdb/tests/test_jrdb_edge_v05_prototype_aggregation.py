import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parents[1] / "src" / "jrdb_edge_v05_prototype_aggregation.py"
SPEC = importlib.util.spec_from_file_location("edgedb_v05", MODULE_PATH)
edgedb_v05 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(edgedb_v05)


class PrototypeAggregationTests(unittest.TestCase):
    def test_discovery_windows_exclude_context_and_2026(self):
        eligible = {"is_pre_race_eligible": 1}
        self.assertFalse(edgedb_v05.discovery_member({**eligible, "race_date": "2023-12-31"}))
        self.assertTrue(edgedb_v05.discovery_member({**eligible, "race_date": "2024-01-01"}))
        self.assertTrue(edgedb_v05.discovery_member({**eligible, "race_date": "2025-12-31"}))
        self.assertFalse(edgedb_v05.discovery_member({**eligible, "race_date": "2026-01-01"}))
        self.assertFalse(edgedb_v05.discovery_member({"race_date": "2024-05-01", "is_pre_race_eligible": 0}))

    def test_candidate_identity_is_market_blind_and_order_stable(self):
        conditions = {"venue_code": "05", "surface_code": "1", "distance_m": "1600", "frame_no": "3"}
        shuffled = dict(reversed(list(conditions.items())))
        self.assertEqual(edgedb_v05.candidate_id("T1_COURSE_FRAME", conditions), edgedb_v05.candidate_id("T1_COURSE_FRAME", shuffled))
        self.assertTrue(edgedb_v05.FORBIDDEN_MEMBERSHIP_FIELDS.isdisjoint(edgedb_v05.SPECS["T1_COURSE_FRAME"]["conditions"]))
        self.assertTrue(edgedb_v05.FORBIDDEN_MEMBERSHIP_FIELDS.isdisjoint(edgedb_v05.PRE_RACE_FIELDS))

    def test_canonical_distance_change_and_same_band_exclusion(self):
        self.assertEqual(edgedb_v05.distance_change("EXTEND"), "EXTEND")
        self.assertEqual(edgedb_v05.distance_change("LARGE_EXTEND"), "EXTEND")
        self.assertEqual(edgedb_v05.distance_change("SHORTEN"), "SHORTEN")
        self.assertEqual(edgedb_v05.distance_change("LARGE_SHORTEN"), "SHORTEN")
        self.assertIsNone(edgedb_v05.distance_change("SAME_BAND"))

    def test_surface_switch_only_accepts_canonical_transitions(self):
        self.assertTrue(edgedb_v05.surface_switch("1->2"))
        self.assertTrue(edgedb_v05.surface_switch("2->1"))
        self.assertFalse(edgedb_v05.surface_switch("1->1"))
        self.assertFalse(edgedb_v05.surface_switch("2->2"))

    def test_unavailable_first_exposure_and_topology_are_blocked(self):
        self.assertEqual(edgedb_v05.BLOCKED_FEATURES, {"first_dirt", "first_turf", "first_blinkers", "course_topology"})
        self.assertNotIn("T5_FIRST_BLINKERS", edgedb_v05.SPECS)

    def test_going_bucket_mapping(self):
        self.assertEqual(edgedb_v05.going_bucket("1"), "GOOD")
        for value in ("2", "3", "4"):
            self.assertEqual(edgedb_v05.going_bucket(value), "SOFT_OR_WORSE")
        self.assertIsNone(edgedb_v05.going_bucket("0"))

    def test_support_bands_keep_micro_candidates_regardless_of_returns(self):
        self.assertEqual([edgedb_v05.support_class(n) for n in (1, 4, 5, 9, 10, 19, 20, 49, 50)],
                         ["RAW_ONLY", "RAW_ONLY", "MICRO", "MICRO", "SMALL", "SMALL", "MEDIUM", "MEDIUM", "LARGE"])
        self.assertFalse(edgedb_v05.shortlist_eligible(4))
        self.assertTrue(edgedb_v05.shortlist_eligible(5))

    def test_metric_lanes_are_separate(self):
        self.assertTrue(edgedb_v05.PERFORMANCE_FIELDS.isdisjoint(edgedb_v05.RETURN_FIELDS))
        self.assertTrue(edgedb_v05.PERFORMANCE_FIELDS.isdisjoint(edgedb_v05.MARKET_FIELDS))
        self.assertTrue(edgedb_v05.RETURN_FIELDS.isdisjoint(edgedb_v05.MARKET_FIELDS))
        for spec in edgedb_v05.SPECS.values():
            self.assertTrue(set(spec["conditions"]).isdisjoint(edgedb_v05.FORBIDDEN_MEMBERSHIP_FIELDS))

    def test_no_duplicate_ids_from_duplicate_condition_set(self):
        rows = [{"venue_code": "05", "surface_code": "1", "distance_m": "1600", "frame_no": "3"} for _ in range(2)]
        ids = [edgedb_v05.candidate_id("T1_COURSE_FRAME", row) for row in rows]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(len(set(ids)), 1)


if __name__ == "__main__":
    unittest.main()
