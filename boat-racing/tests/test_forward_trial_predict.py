import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_predict import (
    ForwardTrialValidationError,
    current_series_average,
    generate,
    non1_a_candidate,
    parse_boats,
    strongest_non1,
    support_flags,
)


COLUMNS = [
    "日付","会場","場コード","R","締切時刻","開催日目","レース種別","艇番",
    "登録番号","選手名","級別","全国勝率","当地勝率","平均ST","コース別成績",
    "モーター番号","モーター2連率","今節成績","欠場状態",
]


def race_rows(race_no, overrides=None):
    values = {
        1:("A1","7.20","7.00","0.13","45.0","1/1/.10/１ | 2/1/.12/２"),
        2:("A2","6.50","6.00","0.15","40.0","1/2/.12/２ | 2/2/.13/３"),
        3:("A2","6.00","5.50","0.16","38.0","1/3/.14/３ | 2/3/.15/４"),
        4:("B1","5.00","5.00","0.17","35.0","1/4/.16/４ | 2/4/.17/５"),
        5:("B1","4.50","4.50","0.18","30.0","1/5/.18/５ | 2/5/.18/６"),
        6:("B2","4.00","4.00","0.19","25.0","1/6/.19/６ | 2/6/.19/６"),
    }
    if overrides:
        values.update(overrides)
    rows=[]
    for lane in range(1,7):
        klass,nat,local,st,motor,form=values[lane]
        rows.append({"日付":"20260910","会場":"テスト","場コード":"99","R":str(race_no),"締切時刻":"12:00","開催日目":"1日目","レース種別":"一般","艇番":str(lane),"登録番号":str(1000+lane),"選手名":f"艇{lane}","級別":klass,"全国勝率":nat,"当地勝率":local,"平均ST":st,"コース別成績":"","モーター番号":str(lane),"モーター2連率":motor,"今節成績":form,"欠場状態":""})
    return rows


class ForwardTrialPredictTest(unittest.TestCase):
    def test_current_series_average_uses_only_numeric_finishes(self):
        self.assertEqual(current_series_average("1/1/.10/１ | 2/1/.11/失 | 3/1/.12/6"), 3.5)
        self.assertIsNone(current_series_average("1/1/.10/失 | 2/1/.11/転"))

    def test_strongest_non1_uses_fixed_order(self):
        self.assertEqual(strongest_non1(parse_boats(race_rows(1)))["lane"], 2)

    def test_non1_a_is_limited_to_lane_2_or_3(self):
        overrides={
            1:("B1","5.00","5.00","0.18","30.0","1/1/.18/５"),
            2:("A1","6.00","6.00","0.14","40.0","1/2/.14/２"),
            4:("A1","9.00","9.00","0.10","60.0","1/4/.10/１"),
        }
        self.assertEqual(non1_a_candidate(parse_boats(race_rows(1,overrides)))["lane"], 2)

    def test_zero_local_rate_is_a_value_not_missing(self):
        overrides={
            1:("A1","7.00","0.00","0.13","45.0","1/1/.10/１"),
            2:("A1","6.00","1.00","0.14","40.0","1/2/.12/２"),
        }
        boats=parse_boats(race_rows(1,overrides))
        self.assertFalse(support_flags(boats[1],strongest_non1(boats))["当地勝率"])

    def test_generate_exacta_inner_opponent_and_listing(self):
        rows=[]
        for race in range(1,13):
            rows.extend(race_rows(race))
        result=generate(rows,COLUMNS,"2026-09-10 08:00:00+09:00")
        self.assertEqual((len(result["predictions"]),len(result["rationales"])),(12,72))
        targets=[row for row in result["sales"] if row["2連単1点対象"]=="対象"]
        self.assertEqual(len(targets),12)
        for row in targets:
            inner=min(int(row["2着本線"]),int(row["2着押さえ"]))
            self.assertEqual(row["2連単1点"],f"1→{inner}")
            self.assertEqual(row["結果参照状態"],"未参照")
        self.assertEqual((sum(r["掲載区分"]=="有料" for r in targets),sum(r["掲載区分"]=="無料" for r in targets),sum(r["掲載区分"]=="CSVのみ" for r in targets)),(6,3,3))

    def test_forbidden_column_fails_closed(self):
        rows=[]
        for race in range(1,13):
            rows.extend(race_rows(race))
        with self.assertRaises(ForwardTrialValidationError):
            generate(rows,COLUMNS+["オッズ"],"2026-09-10 08:00:00+09:00")


if __name__ == "__main__":
    unittest.main()
