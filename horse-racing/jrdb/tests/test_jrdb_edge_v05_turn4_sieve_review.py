import sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from jrdb_edge_v05_turn4_sieve_review import policy_members

class Turn4PolicyTests(unittest.TestCase):
    def source(self):
        return {
            "a":{"n_2024_2025":30,"place_roi_2024_2025":110,"place_roi_ex_top1":105,"hit_pop_8_plus":0,"hit_pop_10_plus":0},
            "b":{"n_2024_2025":10,"place_roi_2024_2025":130,"place_roi_ex_top1":60,"hit_pop_8_plus":1,"hit_pop_10_plus":1},
            "c":{"n_2024_2025":10,"place_roi_2024_2025":130,"place_roi_ex_top1":60,"hit_pop_8_plus":1,"hit_pop_10_plus":0},
            "d":{"n_2024_2025":30,"place_roi_2024_2025":90,"place_roi_ex_top1":90,"hit_pop_8_plus":2,"hit_pop_10_plus":1},
        }
    def evals(self):
        return {
            "a":{"oos_label":"CONFIRMED"},
            "b":{"oos_label":"INSUFFICIENT_OOS"},
            "c":{"oos_label":"CONTRADICTED"},
            "d":{"oos_label":"STILL_PLAUSIBLE"},
        }
    def test_01_baseline_all(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["P0_BASELINE_ALL"],{"a","b","c","d"})
    def test_02_n20(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["P1_STATIC_N20"],{"a","d"})
    def test_03_roi120(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["P2_STATIC_ROI120"],{"b","c"})
    def test_04_ex_top1(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["P3_STATIC_EX_TOP1_ROI100"],{"a"})
    def test_05_two_lane_10_rescues_rare_longshot(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["P4_STATIC_TWO_LANE_10PLUS_RESCUE"],{"a","b"})
    def test_06_two_lane_8_is_broader(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["P5_STATIC_TWO_LANE_8PLUS_RESCUE"],{"a","b","c"})
    def test_07_static_policy_does_not_use_oos_label(self):
        e=self.evals(); e["b"]["oos_label"]="CONTRADICTED"
        p=policy_members(self.source(),e)
        self.assertIn("b",p["P4_STATIC_TWO_LANE_10PLUS_RESCUE"])
    def test_08_oos_exclude_contradicted(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["D1_OOS_EXCLUDE_CONTRADICTED"],{"a","b","d"})
    def test_09_oos_positive(self):
        p=policy_members(self.source(),self.evals())
        self.assertEqual(p["D2_OOS_CONFIRMED_OR_PLAUSIBLE"],{"a","d"})
    def test_10_two_lane_stable_requires_ex_top1(self):
        p=policy_members(self.source(),self.evals())
        self.assertNotIn("d",p["P4_STATIC_TWO_LANE_10PLUS_RESCUE"])

if __name__=="__main__":
    unittest.main()
