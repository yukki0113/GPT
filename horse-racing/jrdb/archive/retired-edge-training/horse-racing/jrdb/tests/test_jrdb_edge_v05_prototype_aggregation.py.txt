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
        self.assertEqual(edgedb_v05.going_bucket("GOOD"), "GOOD")
        self.assertEqual(edgedb_v05.going_bucket("SOFT_OR_WORSE"), "SOFT_OR_WORSE")
        self.assertIsNone(edgedb_v05.going_bucket("0"))

    def test_support_bands_keep_micro_candidates_regardless_of_returns(self):
        self.assertEqual([edgedb_v05.support_class(n) for n in (1, 4, 5, 9, 10, 19, 20, 49, 50)],
                         ["RAW_ONLY", "RAW_ONLY", "MICRO", "MICRO", "SMALL", "SMALL", "MEDIUM", "MEDIUM", "LARGE"])
        self.assertFalse(edgedb_v05.shortlist_eligible(4))
        self.assertTrue(edgedb_v05.shortlist_eligible(5))

    def test_positive_value_gate_boundaries_and_one_hit_micro(self):
        self.assertTrue(edgedb_v05.positive_value_eligible(5, 100))
        self.assertFalse(edgedb_v05.positive_value_eligible(5, 99.9))
        self.assertFalse(edgedb_v05.positive_value_eligible(4, 500))
        # Year-level returns may diverge (e.g. 72 and 156); membership uses
        # only their combined 2024-2025 ROI, supplied here as 112.
        self.assertTrue(edgedb_v05.positive_value_eligible(10, 112))
        # One 810-yen place return from five 100-yen stakes is ROI 162%;
        # ex-top1 ROI is diagnostic and is not an input to this gate.
        self.assertEqual(100 * 810 / (5 * 100), 162)
        self.assertTrue(edgedb_v05.positive_value_eligible(5, 162))
        self.assertEqual(edgedb_v05.value_strength_band(162), "VALUE_150_PLUS")

    def test_performance_and_value_are_independent(self):
        labels=edgedb_v05.performance_labels(.02,-.01)
        self.assertEqual(labels, ["PERFORMANCE_POSITIVE", "PERFORMANCE_NEGATIVE"])
        self.assertFalse(edgedb_v05.positive_value_eligible(20, 71.3))
        self.assertTrue(edgedb_v05.positive_value_eligible(20, 101))
        self.assertIsNone(edgedb_v05.value_strength_band(99.9))
        self.assertEqual(edgedb_v05.value_strength_band(100), "VALUE_100_119")
        self.assertEqual(edgedb_v05.value_strength_band(120), "VALUE_120_149")

    def test_negative_value_requires_material_dual_deterioration(self):
        self.assertTrue(edgedb_v05.negative_value_eligible(5,-.03,-20,True))
        self.assertFalse(edgedb_v05.negative_value_eligible(5,-.029,-30,True))
        self.assertFalse(edgedb_v05.negative_value_eligible(5,-.04,-19.9,True))
        self.assertFalse(edgedb_v05.negative_value_eligible(5,-.04,-30,False))
        self.assertFalse(edgedb_v05.negative_value_eligible(4,-.04,-30,True))

    def test_positive_redundancy_preserves_rows_and_selects_one_simple_representative(self):
        rows=[{"candidate_id":"a","positive_value_eligible":True,"depth":1,"metrics":{"overall_2024_2025":{"n":10}}},
              {"candidate_id":"b","positive_value_eligible":True,"depth":2,"metrics":{"overall_2024_2025":{"n":20}}},
              {"candidate_id":"c","positive_value_eligible":False,"depth":1,"metrics":{"overall_2024_2025":{"n":50}}}]
        pairs=[{"candidate_a":"a","candidate_b":"b","status":"SUGGESTED_REVIEW"},
               {"candidate_a":"a","candidate_b":"c","status":"SUGGESTED_REVIEW"}]
        reps,suppressed=edgedb_v05.positive_value_representatives(rows,pairs)
        self.assertEqual(reps,["a"])
        self.assertEqual(suppressed,{"a":["b"]})
        self.assertEqual(len(rows),3)

    def test_first_surface_and_blinker_chronology_exclude_target_from_prior_history(self):
        surfaces=[
            {"horse_id":"h1","race_key":"r1","race_date":"2020-01-01","surface_code":"1","history_complete":True},
            {"horse_id":"h1","race_key":"r2","race_date":"2021-01-01","surface_code":"2","history_complete":True},
            {"horse_id":"h1","race_key":"r3","race_date":"2022-01-01","surface_code":"2","history_complete":True},
            {"horse_id":"h2","race_key":"r4","race_date":"2022-01-01","surface_code":"2","history_complete":False},
        ]
        flags=edgedb_v05.derive_first_surface_flags(surfaces)
        self.assertEqual(flags["r1"],{"first_dirt":False,"first_turf":True})
        self.assertEqual(flags["r2"],{"first_dirt":True,"first_turf":False})
        self.assertEqual(flags["r3"],{"first_dirt":False,"first_turf":False})
        self.assertIsNone(flags["r4"]["first_dirt"])
        blinkers=[
            {"horse_id":"h1","race_key":"r1","race_date":"2020-01-01","blinker_code":"0","history_complete":True},
            {"horse_id":"h1","race_key":"r2","race_date":"2021-01-01","blinker_code":"1","history_complete":True},
            {"horse_id":"h1","race_key":"r3","race_date":"2022-01-01","blinker_code":"3","history_complete":True},
            {"horse_id":"h2","race_key":"r4","race_date":"2022-01-01","blinker_code":"1","history_complete":False},
        ]
        derived=edgedb_v05.derive_first_blinkers(blinkers)
        self.assertFalse(derived["r1"])
        self.assertTrue(derived["r2"])
        self.assertFalse(derived["r3"])
        self.assertIsNone(derived["r4"])

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
