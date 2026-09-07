import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ledger_daily_result_import import LedgerValidationError, build_update_plan, classify_structure, plan_as_json


FREEZE_0906 = "2026-09-06 02:28:00+09:00"


def row(kind, listing_class, payout=0):
    common = {"target": True, "listing_class": listing_class, "investment": 100, "payout": payout,
              "axis": 1, "second_main": 2, "second_backup": 3}
    if kind == "hit": return {**common, "actual_first": 1, "actual_second": 2, "bet": (1, 2)}
    if kind == "inner": return {**common, "actual_first": 1, "actual_second": 3, "bet": (1, 2)}
    if kind == "pair": return {**common, "actual_first": 1, "actual_second": 4, "bet": (1, 2)}
    if kind == "head": return {**common, "actual_first": 2, "actual_second": 1, "bet": (1, 2)}
    raise AssertionError(kind)


def plan(article_id, day, freeze, rows):
    return build_update_plan(article_id=article_id, data_dates=[day], detail_dates=[day],
                             prediction_freezes=[freeze], sales_freezes=[freeze], details=rows)


class LedgerDailyResultImportTest(unittest.TestCase):
    def test_midnight_process_time_cannot_change_target_day(self):
        result = plan("20260906", "2026-09-06", FREEZE_0906, [])
        self.assertEqual(result["target_date"], "2026-09-06")
        self.assertEqual(result["prediction_freeze"], FREEZE_0906)

    def test_date_mismatch_stops_instead_of_autocorrecting(self):
        with self.assertRaises(LedgerValidationError):
            build_update_plan(article_id="20260906", data_dates=["2026-09-06"], detail_dates=["2026-09-07"],
                              prediction_freezes=[FREEZE_0906], sales_freezes=[FREEZE_0906], details=[])

    def test_0906_published_csv_split_and_conditional_kpi(self):
        rows = [
        row("hit", "有料", 300), row("hit", "有料", 220), row("inner", "有料"),
        row("pair", "有料"), row("pair", "有料"), row("head", "有料"),
        row("hit", "無料", 310), row("pair", "無料"), row("head", "無料"),
        row("hit", "CSVのみ", 450), row("inner", "CSVのみ"), row("pair", "CSVのみ"),
        row("head", "CSVのみ"), row("head", "CSVのみ"),
    ]
        result = plan("20260906", "2026-09-06", FREEZE_0906, rows)
        self.assertEqual((result["published"].count, result["published"].hits, result["published"].investment,
                          result["published"].payout, result["published"].profit), (9, 3, 900, 830, -70))
        self.assertEqual((result["csv_only"].count, result["csv_only"].investment, result["csv_only"].payout), (5, 500, 450))
        self.assertEqual((result["all_target"].count, result["all_target"].hits, result["all_target"].investment,
                          result["all_target"].payout), (14, 4, 1400, 1280))
        kpi = result["structure"]
        self.assertEqual((kpi.target_count, kpi.head_success, kpi.pair_success, kpi.inner_success), (14, 10, 6, 4))
        self.assertEqual((kpi.head_rate, kpi.pair_rate, kpi.inner_rate), (10 / 14, 6 / 10, 4 / 6))

    def test_0905_regression_fixture(self):
        rows = [row("hit", "有料", 300), row("hit", "有料", 300), row("hit", "有料", 340),
            row("inner", "有料"), row("pair", "有料"), row("head", "有料"),
            row("hit", "無料", 320), row("pair", "無料"), row("head", "無料"),
            row("pair", "CSVのみ"), row("pair", "CSVのみ"), row("head", "CSVのみ")]
        result = plan("20260905", "2026-09-05", "2026-09-05 01:31:00+09:00", rows)
        self.assertEqual((result["published"].count, result["published"].investment, result["published"].payout), (9, 900, 1260))
        self.assertEqual((result["all_target"].count, result["structure"].head_success,
                          result["structure"].pair_success, result["structure"].inner_success), (12, 9, 5, 4))

    def test_failure_labels_and_downstream_out_of_scope(self):
        self.assertEqual(classify_structure(row("head", "有料")), {"head": "×", "pair": "対象外", "inner": "対象外", "failure": "1号艇頭失敗"})
        self.assertEqual(classify_structure(row("pair", "有料"))["failure"], "2着候補2艇外")
        self.assertEqual(classify_structure(row("inner", "有料"))["failure"], "内側1点選択ミス")

    def test_plan_is_json_ready_for_sheet_update_review(self):
        output = plan_as_json(plan("20260906", "2026-09-06", FREEZE_0906, [row("hit", "有料", 100)]))
        self.assertEqual(output["published"]["roi"], 1.0)
        self.assertEqual(output["detail_structure"][0]["failure"], "的中")


if __name__ == "__main__":
    unittest.main()
