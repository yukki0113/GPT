#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jrdb_raw import Parser
from jrdb_result_query import assemble_result, normalize_bet_types, normalize_venue
from test_jrdb_hjc_common import sample_body


def payout_rows_from_sample():
    parsed = Parser().hjc(sample_body())
    rows = []
    for bet_type in ("win","place","frame_quinella","quinella","wide","exacta","trio","trifecta"):
        for slot_no, slot in enumerate(parsed[bet_type], 1):
            numbers = slot["numbers"]
            rows.append({
                "race_key_raw":parsed["race_key_raw"],"bet_type":bet_type,"slot_no":slot_no,
                "combination_raw":slot["combination_raw"],
                "horse_no_1":numbers[0] if len(numbers)>0 else None,
                "horse_no_2":numbers[1] if len(numbers)>1 else None,
                "horse_no_3":numbers[2] if len(numbers)>2 else None,
                "payout":slot["payout"],
            })
    return rows


def sed_rows_matching_sample():
    rows = {
        4: {"race_key_raw":"06244901","horse_no":4,"horse_name":"WINNER","finish":1,"abnormal_code":"0","final_popularity":2,"final_win_odds":7.5,"win_payout":None,"place_payout":None},
        12:{"race_key_raw":"06244901","horse_no":12,"horse_name":"SECOND","finish":2,"abnormal_code":"0","final_popularity":5,"final_win_odds":18.0,"win_payout":None,"place_payout":None},
        15:{"race_key_raw":"06244901","horse_no":15,"horse_name":"THIRD","finish":3,"abnormal_code":"0","final_popularity":1,"final_win_odds":3.1,"win_payout":None,"place_payout":None},
        8: {"race_key_raw":"06244901","horse_no":8,"horse_name":"FOURTH","finish":4,"abnormal_code":"0","final_popularity":6,"final_win_odds":25.0,"win_payout":None,"place_payout":None},
    }
    parsed = Parser().hjc(sample_body())
    for slot in parsed["win"]:
        n = slot["numbers"][0]
        if n in rows and slot["payout"]:
            rows[n]["win_payout"] = slot["payout"]
    for slot in parsed["place"]:
        n = slot["numbers"][0]
        if n in rows and slot["payout"]:
            rows[n]["place_payout"] = slot["payout"]
    return list(rows.values())


class ResultQueryTests(unittest.TestCase):
    def test_default_top3_and_all_payouts(self):
        result = assemble_result(
            date=dt.date(2024,9,29),
            sed_rows=sed_rows_matching_sample(),
            payout_rows=payout_rows_from_sample(),
            source_provenance={"source_mode":"fixture"},
            venue_code="06",race_no=1,
        )
        self.assertEqual(result["status"],"success")
        race = result["races"][0]
        self.assertEqual([row["horse_no"] for row in race["top3"]],[4,12,15])
        self.assertEqual(len(race["payouts"]),8)
        self.assertEqual(race["payouts"]["win"][0]["payout_yen"],750)
        self.assertEqual(race["payouts"]["trifecta"][0]["numbers"],[4,12,15])
        self.assertEqual(race["payouts"]["trifecta"][0]["payout_yen"],39040)
        self.assertTrue(race["payouts"]["trifecta"][0]["ordered"])
        self.assertEqual(race["cross_validation"]["status"],"pass")
        self.assertFalse(result["provenance"]["web_used"])

    def test_all_runners_opt_in(self):
        result = assemble_result(
            date=dt.date(2024,9,29),sed_rows=sed_rows_matching_sample(),
            payout_rows=payout_rows_from_sample(),source_provenance={"source_mode":"fixture"},
            include_all_runners=True,
        )
        self.assertEqual(len(result["races"][0]["top3"]),3)
        self.assertEqual(len(result["races"][0]["all_runners"]),4)

    def test_aliases_and_bet_filter(self):
        self.assertEqual(normalize_bet_types(["ワイド","3連複"]),["wide","trio"])
        self.assertEqual(normalize_venue("阪神"),"09")
        result = assemble_result(
            date=dt.date(2024,9,29),sed_rows=sed_rows_matching_sample(),
            payout_rows=payout_rows_from_sample(),source_provenance={"source_mode":"fixture"},
            bet_types=["wide"],
        )
        self.assertEqual(list(result["races"][0]["payouts"]),["wide"])

    def test_missing_hjc_is_partial_without_web_fallback(self):
        result = assemble_result(
            date=dt.date(2024,9,29),sed_rows=sed_rows_matching_sample(),
            payout_rows=[],source_provenance={"source_mode":"fixture"},
        )
        self.assertEqual(result["status"],"partial")
        self.assertEqual(result["missing_sources"],["HJC"])
        self.assertEqual(result["races"][0]["payouts_status"],"unavailable")
        self.assertFalse(result["provenance"]["web_used"])


if __name__ == "__main__":
    unittest.main()
