import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_v02_alpha_predict import RULE_VERSION, generate_active


COLUMNS = [
    "日付","会場","場コード","R","締切時刻","開催日目","レース種別","艇番",
    "登録番号","選手名","級別","全国勝率","当地勝率","平均ST","コース別成績",
    "モーター番号","モーター2連率","今節成績","欠場状態",
]


def race_rows(race_no, deadline="12:00"):
    values = {
        1:("A1","7.20","7.00","0.13","45.0","1/1/.10/１ | 2/1/.12/２"),
        2:("A2","6.50","6.00","0.15","40.0","1/2/.12/２ | 2/2/.13/３"),
        3:("A2","6.00","5.50","0.16","38.0","1/3/.14/３ | 2/3/.15/４"),
        4:("B1","5.00","5.00","0.17","35.0","1/4/.16/４ | 2/4/.17/５"),
        5:("B1","4.50","4.50","0.18","30.0","1/5/.18/５ | 2/5/.18/６"),
        6:("B2","4.00","4.00","0.19","25.0","1/6/.19/６ | 2/6/.19/６"),
    }
    rows=[]
    for lane in range(1,7):
        klass,nat,local,st,motor,form=values[lane]
        rows.append({
            "日付":"20260917","会場":"テスト","場コード":"99","R":str(race_no),
            "締切時刻":deadline,"開催日目":"1日目","レース種別":"一般","艇番":str(lane),
            "登録番号":str(1000+lane),"選手名":f"艇{lane}","級別":klass,
            "全国勝率":nat,"当地勝率":local,"平均ST":st,"コース別成績":"",
            "モーター番号":str(lane),"モーター2連率":motor,"今節成績":form,"欠場状態":"",
        })
    return rows


def full_day(deadline="12:00"):
    rows=[]
    for race in range(1,13):
        rows.extend(race_rows(race, deadline))
    return rows


class ForwardTrialV02AlphaActiveTest(unittest.TestCase):
    def test_active_version_and_three_shapes(self):
        result=generate_active(full_day(), COLUMNS, "2026-09-17 11:00:00+09:00")
        self.assertEqual(RULE_VERSION, "ForwardTrial_Ver0.2-alpha1")
        self.assertEqual(len(result["predictions"]), 12)
        self.assertEqual(len(result["rationales"]), 72)
        self.assertEqual(len(result["sales"]), 12)
        self.assertTrue(all(row[5] == RULE_VERSION for row in result["predictions"]))
        self.assertTrue(all(row["試行仕様Ver"] == RULE_VERSION for row in result["sales"]))
        self.assertNotIn("CSVのみ", {row["掲載区分"] for row in result["sales"]})
        for row in result["sales"]:
            self.assertEqual(row["結果参照状態"], "未参照")
            if row["2連単1点対象"] == "対象":
                self.assertLessEqual(int(row["販売スコア"]), 4)
                self.assertEqual(
                    row["2連単1点"],
                    f"1→{min(int(row['2着本線']), int(row['2着押さえ']))}",
                )

    def test_deadline_equal_freeze_never_publishes(self):
        result=generate_active(full_day("12:00"), COLUMNS, "2026-09-17 12:00:00+09:00")
        self.assertEqual(result["paid_count"], 0)
        self.assertEqual(result["free_count"], 0)
        self.assertFalse(any(row["掲載区分"] in {"有料","無料"} for row in result["sales"]))

    def test_generation_is_deterministic(self):
        first=generate_active(full_day(), COLUMNS, "2026-09-17 11:00:00+09:00")
        second=generate_active(full_day(), COLUMNS, "2026-09-17 11:00:00+09:00")
        for key in ("predictions","rationales","sales","target_count","q0_count","eligible_count","paid_count","free_count"):
            self.assertEqual(first[key], second[key])


if __name__ == "__main__":
    unittest.main()
