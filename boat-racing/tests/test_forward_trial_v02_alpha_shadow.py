import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_predict import ForwardTrialValidationError
from forward_trial_v02_alpha_shadow import (
    OS_ALPHA1_WEIGHTS,
    generate_shadow,
    pair_risk_q0,
    product_split,
    shadow_sales_score,
)


COLUMNS = [
    "日付","会場","場コード","R","締切時刻","開催日目","レース種別","艇番",
    "登録番号","選手名","級別","全国勝率","当地勝率","平均ST","コース別成績",
    "モーター番号","モーター2連率","今節成績","欠場状態",
]


def race_rows(race_no):
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
            "締切時刻":"12:00","開催日目":"1日目","レース種別":"一般","艇番":str(lane),
            "登録番号":str(1000+lane),"選手名":f"艇{lane}","級別":klass,
            "全国勝率":nat,"当地勝率":local,"平均ST":st,"コース別成績":"",
            "モーター番号":str(lane),"モーター2連率":motor,"今節成績":form,"欠場状態":"",
        })
    return rows


class ForwardTrialV02AlphaShadowTest(unittest.TestCase):
    def test_weights_are_frozen_alpha1(self):
        self.assertAlmostEqual(sum(OS_ALPHA1_WEIGHTS.values()), 1.0)
        self.assertEqual(OS_ALPHA1_WEIGHTS, {
            "全国勝率": 0.35,
            "当地勝率": 0.15,
            "平均ST": 0.05,
            "モーター2連率": 0.15,
            "今節平均着順": 0.15,
            "級別": 0.15,
        })

    def test_q0_definition_boundary(self):
        self.assertTrue(pair_risk_q0(0.079999, False, 3))
        self.assertTrue(pair_risk_q0(0.0, False, 5))
        self.assertFalse(pair_risk_q0(0.08, False, 3))
        self.assertFalse(pair_risk_q0(0.079, True, 3))
        self.assertFalse(pair_risk_q0(0.079, False, 4))

    def test_sales_score_is_exactly_four_binary_factors(self):
        self.assertEqual(
            shadow_sales_score(national_gap=0.50, separation=0.08, inner=2, second_main=2), 4
        )
        self.assertEqual(
            shadow_sales_score(national_gap=0.49, separation=0.079, inner=5, second_main=3), 0
        )

    def test_product_volume_rule(self):
        self.assertEqual(product_split(5), (0, 0, False))
        self.assertEqual(product_split(6), (4, 2, True))
        self.assertEqual(product_split(7), (5, 2, True))
        self.assertEqual(product_split(8), (5, 3, True))
        self.assertEqual(product_split(9), (6, 3, True))
        self.assertEqual(product_split(10), (7, 3, True))
        self.assertEqual(product_split(15), (7, 3, True))

    def test_generation_is_deterministic_and_has_no_csv_only(self):
        rows=[]
        for race in range(1,13):
            rows.extend(race_rows(race))
        first=generate_shadow(rows,COLUMNS,"2026-09-17 00:30:00+09:00")
        second=generate_shadow(rows,COLUMNS,"2026-09-17 00:30:00+09:00")
        self.assertEqual(first, second)
        self.assertEqual(len(first["rows"]), 12)
        self.assertNotIn("CSVのみ", {row["掲載区分"] for row in first["rows"]})
        for row in first["rows"]:
            self.assertEqual(row["結果参照状態"], "未参照")
            if row["2連単1点対象"] == "対象":
                self.assertEqual(
                    row["2連単1点"],
                    f"1→{min(int(row['2着本線']), int(row['2着押さえ']))}",
                )

    def test_result_like_input_is_rejected_by_control_guard(self):
        rows=[]
        for race in range(1,13):
            rows.extend(race_rows(race))
        with self.assertRaises(ForwardTrialValidationError):
            generate_shadow(rows, COLUMNS + ["オッズ"], "2026-09-17 00:30:00+09:00")


if __name__ == "__main__":
    unittest.main()
