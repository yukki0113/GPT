import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_deadline_gate import (
    DeadlineGateValidationError,
    apply_deadline_gate,
)


def racecard_rows():
    rows = []
    for race in range(1, 13):
        closing = "08:30" if race in (1, 2) else "12:00"
        for lane in range(1, 7):
            rows.append({
                "日付": "20260915",
                "会場": "テスト",
                "R": str(race),
                "艇番": str(lane),
                "締切時刻": closing,
            })
    return rows


def sales_rows():
    rows = []
    for race in range(1, 13):
        rows.append({
            "日付": "2026-09-15",
            "会場": "テスト",
            "R": str(race),
            "試行仕様Ver": "ForwardTrial_Ver0.1",
            "正式判定": "A",
            "1着軸": "1",
            "2着本線": "2",
            "2着押さえ": "3",
            "2連単1点対象": "対象",
            "2連単1点": "1→2",
            "軸警戒": "なし",
            "比較支持項目数": "5",
            "全国勝率差": "1.0",
            "2着候補分離度": f"{0.20 - race * 0.001:.3f}",
            "販売スコア": str(10 - (race // 4)),
            "内部販売評価": "",
            "掲載区分": "",
            "選別理由": "",
            "予想確定日時": "2026-09-15 08:33:00+09:00",
            "販売選別確定日時": "2026-09-15 08:33:00+09:00",
            "結果参照状態": "未参照",
        })
    return rows


class DeadlineGateTest(unittest.TestCase):
    def test_expired_targets_are_never_paid_or_free(self):
        rows = sales_rows()
        result = apply_deadline_gate(racecard_rows(), rows)
        expired = [row for row in rows if int(row["R"]) in (1, 2)]
        self.assertTrue(all(row["掲載区分"] == "CSVのみ" for row in expired))
        self.assertTrue(all("締切済み掲載除外" in row["選別理由"] for row in expired))
        self.assertEqual(result["paid_count"], 6)
        self.assertEqual(result["free_count"], 3)
        self.assertEqual(result["expired_target_count"], 2)

    def test_remaining_candidates_are_repacked(self):
        rows = sales_rows()
        apply_deadline_gate(racecard_rows(), rows)
        active = [row for row in rows if int(row["R"]) >= 3]
        active.sort(key=lambda row: int(row["R"]))
        self.assertEqual(sum(row["掲載区分"] == "有料" for row in active), 6)
        self.assertEqual(sum(row["掲載区分"] == "無料" for row in active), 3)

    def test_result_referenced_fails_closed(self):
        rows = sales_rows()
        rows[0]["結果参照状態"] = "参照済み"
        with self.assertRaises(DeadlineGateValidationError):
            apply_deadline_gate(racecard_rows(), rows)


if __name__ == "__main__":
    unittest.main()
