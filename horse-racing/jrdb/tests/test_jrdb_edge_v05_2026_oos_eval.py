import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from jrdb_edge_v05_2026_oos_eval import diagnostic_label, build_evaluation, summarize

def candidate(cid="c1", family="T2"):
    return {
        "candidate_id":cid,"template_id":"T","family":family,
        "support_class":"SMALL","freshness":"CURRENT","memo":"m",
        "n_2024_2025":10,"places_2024_2025":3,"wins_2024_2025":1,
        "place_roi_2024_2025":120.0,"win_roi_2024_2025":110.0,
    }

def match(cid="c1", horse_no=1, race_key="01010101"):
    return {
        "race_date":"2026-01-01","race_key":race_key,
        "race_horse_key":race_key+f"{horse_no:02d}","horse_id":"H",
        "horse_no":horse_no,"candidate_id":cid,"template_id":"T","family":"T2",
        "condition_fingerprint":"x","memo":"m","matched_conditions":"{}",
        "pre_race_fact_fingerprint":"f",
    }

def result(finish=1, place_payout=150, win_payout=300, pop=5, abnormal=""):
    return {
        "finish":finish,"place_payout":place_payout,"win_payout":win_payout,
        "final_popularity":pop,"final_win_odds":3.0,"abnormal_code":abnormal,
    }

class OOSTests(unittest.TestCase):
    def test_01_insufficient(self):
        self.assertEqual(diagnostic_label(4,200,0.1,80),"INSUFFICIENT_OOS")
    def test_02_confirmed(self):
        self.assertEqual(diagnostic_label(10,120,-0.02,0),"CONFIRMED")
    def test_03_still_plausible_roi_only(self):
        self.assertEqual(diagnostic_label(10,110,-0.10,-10),"STILL_PLAUSIBLE")
    def test_04_still_plausible_rate_only(self):
        self.assertEqual(diagnostic_label(10,80,-0.01,-40),"STILL_PLAUSIBLE")
    def test_05_contradicted(self):
        self.assertEqual(diagnostic_label(20,50,-0.05,-70),"CONTRADICTED")
    def test_06_decaying(self):
        self.assertEqual(diagnostic_label(10,70,-0.05,-50),"DECAYING")
    def test_07_abnormal_excluded_from_n(self):
        m=[match()]
        r={("01010101",1):result(abnormal="3")}
        _,ev=build_evaluation(m,{"c1":candidate()},r)
        self.assertEqual(ev[0]["n_2026"],0)
    def test_08_place_hit_uses_payout(self):
        m=[match()]
        r={("01010101",1):result(finish=4,place_payout=150)}
        _,ev=build_evaluation(m,{"c1":candidate()},r)
        self.assertEqual(ev[0]["places_2026"],1)
    def test_09_win_hit_finish_one(self):
        m=[match()]
        r={("01010101",1):result(finish=1,win_payout=300)}
        _,ev=build_evaluation(m,{"c1":candidate()},r)
        self.assertEqual(ev[0]["wins_2026"],1)
    def test_10_popularity_longshot_counts(self):
        m=[match()]
        r={("01010101",1):result(pop=10)}
        _,ev=build_evaluation(m,{"c1":candidate()},r)
        self.assertEqual(ev[0]["place_hits_pop_5_plus"],1)
        self.assertEqual(ev[0]["place_hits_pop_8_plus"],1)
        self.assertEqual(ev[0]["place_hits_pop_10_plus"],1)
    def test_11_missing_result_fails(self):
        with self.assertRaisesRegex(Exception,"unjoined match rows"):
            build_evaluation([match()],{"c1":candidate()},{})
    def test_12_all_candidates_retained(self):
        m=[match("c1")]
        r={("01010101",1):result()}
        _,ev=build_evaluation(m,{"c1":candidate("c1"),"c2":candidate("c2")},r)
        self.assertEqual(len(ev),2)
        self.assertEqual(next(x for x in ev if x["candidate_id"]=="c2")["n_2026"],0)
    def test_13_roi_per_100yen_stake(self):
        m=[match()]
        r={("01010101",1):result(place_payout=150)}
        _,ev=build_evaluation(m,{"c1":candidate()},r)
        self.assertEqual(ev[0]["place_roi_2026"],150.0)
    def test_14_delta_place_rate(self):
        m=[match()]
        r={("01010101",1):result(place_payout=150)}
        _,ev=build_evaluation(m,{"c1":candidate()},r)
        self.assertAlmostEqual(ev[0]["delta_place_rate"],0.7)
    def test_15_summary_groups_all_candidates(self):
        m=[match("c1")]
        r={("01010101",1):result()}
        _,ev=build_evaluation(m,{"c1":candidate("c1","T1"),"c2":candidate("c2","T2")},r)
        s=summarize(ev)
        self.assertEqual(s["candidate_count"],2)
        self.assertEqual(s["by_family"]["T1"]["candidates"],1)
        self.assertEqual(s["by_family"]["T2"]["candidates"],1)

if __name__=="__main__":
    unittest.main()
