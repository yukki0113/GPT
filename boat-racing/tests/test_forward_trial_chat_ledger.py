import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_analysis_import import FT2_HEADERS, GENUINE, records_to_sheet
from forward_trial_chat_ledger import (
    build_atomic_payload, build_batch_requests, legacy_detail_row,
    non_regression_audit, previous_completed_snapshot, upsert_daily_detail, values_rows,
)


class ForwardTrialChatLedgerTest(unittest.TestCase):
    def _row(self, row_id, day="2026-09-12"):
        row = {header: "" for header in FT2_HEADERS}
        row.update({
            "FT2_ID": row_id, "対象日": day, "会場": "戸田", "開催何日目": "1日目",
            "グレード大分類": "一般", "正式判定": "A", "1着軸": 1,
            "予想軸評価対象": "○", "予想軸1着成功": "○",
            "2着候補評価対象_全R": "○", "2着候補2艇カバー_全R": "○",
            "2連単1点対象": "対象", "2連単1点的中": "○",
            "2連単1点投資額": 100, "2連単1点回収額": 250,
            "掲載区分": "有料", "1号艇頭成功": "○",
            "2着候補2艇カバー": "○", "内側1点成功": "○",
            "forward_status": GENUINE, "genuine_forward_flag": True,
        })
        return row

    def test_values_export_ignores_blank_rows(self):
        values = [["FT2_ID", "対象日"], ["a", "2026-09-11"], ["", ""]]
        self.assertEqual(values_rows(values), [{"FT2_ID": "a", "対象日": "2026-09-11"}])

    def test_chat_payload_is_idempotent_and_complete(self):
        row = self._row("20260912_戸田_1_ForwardTrial_Ver0.1")
        daily = {"sheets": {"FT2_全R明細": records_to_sheet([row], FT2_HEADERS)}}
        first = build_atomic_payload([], daily, "2026-09-13 00:00:00+09:00", True)
        second = build_atomic_payload([row], daily, "2026-09-13 00:00:00+09:00", True)
        self.assertEqual(first["state"], "完了")
        self.assertEqual(first["aggregate_generation_id"], second["aggregate_generation_id"])
        self.assertEqual(len(second["sheets"]["FT2_全R明細"]["rows"]), 1)
        self.assertTrue(all(second["completion_checks"].values()))

    def test_crosscheck_failure_never_completes(self):
        row = self._row("20260912_戸田_1_ForwardTrial_Ver0.1")
        daily = {"sheets": {"FT2_全R明細": records_to_sheet([row], FT2_HEADERS)}}
        payload = build_atomic_payload([], daily, "2026-09-13 00:00:00+09:00", False)
        self.assertEqual(payload["state"], "要確認")

    def test_all_days_in_one_transaction_get_the_same_complete_state(self):
        first = self._row("20260912_戸田_1_ForwardTrial_Ver0.1", "2026-09-12")
        second = self._row("20260913_戸田_1_ForwardTrial_Ver0.1", "2026-09-13")
        daily = {
            "sheets": {
                "FT2_全R明細": records_to_sheet([first, second], FT2_HEADERS),
                "FT2_取込管理": records_to_sheet(
                    [{"対象日": "2026-09-12"}, {"対象日": "2026-09-13"}],
                    ["対象日", "取込状態", "備考"],
                ),
            }
        }
        payload = build_atomic_payload([], daily, "2026-09-14 00:00:00+09:00", True)
        rows = payload["sheets"]["FT2_取込管理"]["rows"]
        self.assertEqual([row[1] for row in rows], ["完了", "完了"])

    def test_batch_builder_grows_small_grid_before_writing(self):
        row = self._row("20260912_戸田_1_ForwardTrial_Ver0.1")
        daily = {"sheets": {"FT2_全R明細": records_to_sheet([row], FT2_HEADERS)}}
        payload = build_atomic_payload([], daily, "2026-09-13 00:00:00+09:00", True)
        metadata = {"sheets": [{"title": title, "sheet_id": index + 1,
                    "row_count": 1, "column_count": 1}
                    for index, title in enumerate(payload["sheets"])]}
        requests = build_batch_requests(payload, metadata)
        self.assertTrue(any("appendDimension" in request for request in requests))
        self.assertTrue(any("updateCells" in request for request in requests))

    def test_repeat_import_rejects_frozen_value_change(self):
        row = self._row("20260912_戸田_1_ForwardTrial_Ver0.1")
        changed = dict(row)
        changed["販売順位"] = 99
        with self.assertRaises(Exception):
            upsert_daily_detail([row], [changed])

    def test_repair_can_rebind_only_source_provenance_ids(self):
        row = self._row("20260912_戸田_1_ForwardTrial_Ver0.1")
        rebound = dict(row)
        rebound["prediction_source_file_id"] = "drive-file-id"
        self.assertEqual(upsert_daily_detail([row], [rebound], allow_provenance_rebind=True)[0]
                         ["prediction_source_file_id"], "drive-file-id")

    def test_legacy_mapping_keeps_csv_out_of_published_money(self):
        row = self._row("20260912_戸田_1_ForwardTrial_Ver0.1")
        row["掲載区分"] = "CSVのみ"
        mapped = legacy_detail_row(row)
        self.assertEqual(mapped["2連単1点投資額"], 100)
        self.assertEqual(mapped["掲載対象投資額"], 0)

    def test_contaminated_day_still_has_a_stable_article_row(self):
        row = self._row("20260912_戸田_1_ForwardTrial_Ver0.1")
        row["forward_status"] = "CONTAMINATED"
        row["genuine_forward_flag"] = False
        daily = {"sheets": {"FT2_全R明細": records_to_sheet([row], FT2_HEADERS)}}
        payload = build_atomic_payload([], daily, "2026-09-13 00:00:00+09:00", True)
        articles = payload["sheets"]["販売記事台帳"]["rows"]
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0][0], "20260912")

    def test_missing_prior_date_fails_non_regression_guard(self):
        before = [self._row("a", "2026-09-11"), self._row("b", "2026-09-12")]
        audit = non_regression_audit(before, before[:1], before[:1], "daily_append")
        self.assertEqual(audit["missing_dates"], "2026-09-12")
        self.assertEqual(audit["non_regression_check"], "NON_REGRESSION_VIOLATION")
        self.assertFalse(audit["completion_ok"])

    def test_partial_prior_date_fails_with_date_row_count_regression(self):
        before = [self._row(f"a{index}", "2026-09-11") for index in range(72)]
        after = before[:31]
        audit = non_regression_audit(before, after, after, "daily_append")
        self.assertEqual(audit["regressed_dates"], "2026-09-11")
        self.assertEqual(audit["date_row_count_check"], "DATE_ROW_COUNT_REGRESSION")

    def test_source_total_reduction_fails_with_non_regression_violation(self):
        before = [self._row(f"a{index}", "2026-09-11") for index in range(684)]
        after = before[:643]
        audit = non_regression_audit(before, after, after, "daily_append")
        self.assertEqual(audit["non_regression_check"], "NON_REGRESSION_VIOLATION")
        self.assertFalse(audit["completion_ok"])

    def test_normal_append_and_same_day_rerun_are_idempotently_accepted(self):
        before = [self._row("a", "2026-09-14")]
        incoming = [self._row("b", "2026-09-15")]
        appended = upsert_daily_detail(before, incoming)
        self.assertEqual(non_regression_audit(before, appended, incoming, "daily_append")["non_regression_check"], "OK")
        self.assertEqual(non_regression_audit(appended, appended, incoming, "daily_append")["non_regression_check"], "OK")

    def test_repair_mode_requires_a_reason_and_records_changed_keys(self):
        before = [self._row("a", "2026-09-11"), self._row("b", "2026-09-12")]
        after = before[:1]
        blocked = non_regression_audit(before, after, after, "repair_rebuild")
        self.assertFalse(blocked["completion_ok"])
        repaired = non_regression_audit(before, after, after, "repair_rebuild", repair_reason="official source rebuild")
        self.assertTrue(repaired["completion_ok"])
        self.assertEqual(repaired["execution_mode"], "repair_rebuild")

    def test_previous_completed_snapshot_uses_latest_normal_audit_generation(self):
        generation, snapshot = previous_completed_snapshot([
            {"aggregate_generation_id": "old", "更新日時": "2026-09-14", "検証状態": "OK",
             "non_regression_check": "OK", "source_raw_R": 684, "source_genuine_R": 681,
             "source_contaminated_R": 3, "source_exacta_R": 140, "source_max_date": "2026-09-13"},
            {"aggregate_generation_id": "failed", "更新日時": "2026-09-15", "検証状態": "NG",
             "non_regression_check": "NON_REGRESSION_VIOLATION"},
        ])
        self.assertEqual(generation, "old")
        self.assertEqual(snapshot["raw"], 684)


if __name__ == "__main__":
    unittest.main()
