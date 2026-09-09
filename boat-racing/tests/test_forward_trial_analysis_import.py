import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_analysis_import import (
    CONTAMINATED,
    GENUINE,
    ForwardTrialValidationError,
    audit_freeze,
    completion_state,
    cumulative_acceptance,
    daily_aggregate,
    grade_category,
    initial_backfill_rows,
    metric_block,
    stable_key,
    structure_result,
    upsert_rows,
    validate_source_dates,
)
from fetch_boatrace_event_meta import parse_official_index


class ForwardTrialAnalysisImportTest(unittest.TestCase):
    def test_stable_key_and_idempotent_upsert(self):
        row = {"FT2_ID": stable_key("2026-09-01", "若松", 1), "value": 1}
        self.assertEqual(upsert_rows([row], [row]), [row])
        with self.assertRaises(ForwardTrialValidationError):
            upsert_rows([row], [{**row, "value": 2}])

    def test_detail_success_but_aggregate_failure_never_completes(self):
        self.assertEqual(completion_state(checks={"detail": True, "daily": False}), "要確認")
        self.assertEqual(completion_state(checks={"detail": True}, aggregation_error=RuntimeError("boom")), "エラー")

    def test_reimport_is_idempotent_for_counts_and_money(self):
        row = {"FT2_ID": stable_key("2026-09-09", "鳴門", 1), **self._target("有料", "×", 0)}
        once = upsert_rows([], [row])
        twice = upsert_rows(once, [row])
        self.assertEqual((len(once), metric_block(once)["投資"], metric_block(once)["回収"]),
                         (len(twice), metric_block(twice)["投資"], metric_block(twice)["回収"]))

    def test_0909_fixture(self):
        rows = []
        for i in range(60):
            formal = "A" if i < 21 else ("B" if i < 50 else "C")
            target = i < 8
            rows.append({"対象日": "2026-09-09", "会場": f"v{i // 12}", "正式判定": formal,
                "1着軸": 1 if i < 8 else 2, "予想軸評価対象": "○" if i < 50 else "対象外",
                "予想軸1着成功": "○" if i < 30 else "×", "2着候補評価対象_全R": "○" if i < 30 else "対象外",
                "2着候補2艇カバー_全R": "○" if i < 20 else "×", "2連単1点対象": "対象" if target else "対象外",
                "2連単1点的中": "×" if target else "対象外", "2連単1点投資額": 100 if target else 0,
                "2連単1点回収額": 0, "掲載区分": "有料" if i < 6 else ("無料" if i < 8 else "対象外"),
                "1号艇頭成功": "○" if i < 4 else ("×" if target else "対象外"),
                "2着候補2艇カバー": "○" if i == 0 else ("×" if i < 4 else "対象外"),
                "内側1点成功": "×" if i == 0 else "対象外", "forward_status": GENUINE})
        result = daily_aggregate(rows)[0]
        self.assertEqual((result["全R数"], result["A数"], result["B数"], result["C数"]), (60, 21, 29, 10))
        self.assertEqual((result["全適格_R数"], result["全適格_的中数"], result["有料_R数"], result["無料_R数"], result["CSVのみ_R数"]), (8, 0, 6, 2, 0))

    def test_grade_classification_is_fail_closed(self):
        self.assertEqual(grade_category("G1"), "G1")
        self.assertEqual(grade_category("G3"), "その他")
        self.assertEqual(grade_category("unknown"), "未分類")
        self.assertEqual(completion_state(checks={"all": True}, grade_unresolved=1), "要確認")

    def test_official_grade_parser(self):
        source = '''<tbody><img alt="大村"><td class="is-G1b"></td>
        <a href="/owpc/pc/race/raceindex?jcd=24&amp;hd=20260909">海の王者決定戦</a></tbody>'''
        row = parse_official_index(source, "20260909")[0]
        self.assertEqual((row["会場"], row["グレード大分類"]), ("大村", "G1"))

    def test_initial_acceptance_scope_excludes_future_days(self):
        rows = [{"対象日": "2026-09-01"}, {"対象日": "2026-09-09"}]
        self.assertEqual(initial_backfill_rows(rows), [rows[0]])

    def test_date_mismatch_fails_closed(self):
        with self.assertRaises(ForwardTrialValidationError):
            validate_source_dates("2026-09-01", ("prediction", [{"日付": "2026-09-02"}]))

    def test_freeze_audit_uses_source_freeze(self):
        audited, result, flag, status = audit_freeze(
            "2026-09-03 09:54:00+09:00", "2026-09-03 09:54:00+09:00", "2026-09-03 09:39:00+09:00"
        )
        self.assertEqual(audited, "2026-09-03 09:54:00+09:00")
        self.assertEqual((result, flag, status), ("締切後", False, CONTAMINATED))

    def test_non_target_never_gets_virtual_bet(self):
        result = structure_result(
            target=False, refunded=False, first=1, second=2, axis=1,
            second_main=2, second_backup=3, bet=None,
        )
        self.assertEqual(result, ("対象外",) * 5)

    def test_conditional_kpi(self):
        result = structure_result(
            target=True, refunded=False, first=2, second=1, axis=1,
            second_main=2, second_backup=3, bet=(1, 2),
        )
        self.assertEqual(result, ("×", "×", "対象外", "対象外", "1号艇頭失敗"))

    def test_published_excludes_csv_only(self):
        rows = [self._target("有料", "○", 300), self._target("無料", "×", 0), self._target("CSVのみ", "○", 200)]
        published = [row for row in rows if row["掲載区分"] in {"有料", "無料"}]
        self.assertEqual(metric_block(published)["投資"], 200)
        self.assertEqual(metric_block(rows)["投資"], 300)

    def test_0903_contamination_boundaries(self):
        freeze = "2026-09-03 09:54:00+09:00"
        statuses = [audit_freeze(freeze, freeze, f"2026-09-03 {cutoff}:00+09:00")[3]
                    for cutoff in ("08:44", "09:10", "09:39", "10:05")]
        self.assertEqual(statuses, [CONTAMINATED, CONTAMINATED, CONTAMINATED, GENUINE])

    def test_0908_regression_shape(self):
        rows = [self._target("有料", "○", payout) for payout in (250, 240, 280, 200)]
        rows += [self._target("有料", "×", 0) for _ in range(2)]
        rows += [self._target("無料", "○", 200)] + [self._target("無料", "×", 0) for _ in range(2)]
        rows += [self._target("CSVのみ", "○", 240), self._target("CSVのみ", "○", 250)]
        for index, row in enumerate(rows):
            row["1号艇頭成功"] = "○" if index < 9 else "×"
            row["2着候補2艇カバー"] = "○" if index < 8 else "対象外"
            row["内側1点成功"] = "○" if index < 7 else "対象外"
        metrics = metric_block(rows)
        self.assertEqual((metrics["R数"], metrics["的中数"], metrics["回収"]), (11, 7, 1660))
        self.assertEqual((metrics["1号艇頭成功"], metrics["2艇カバー"], metrics["内側成功"]), (9, 8, 7))

    def test_cumulative_regression(self):
        rows = []
        specs = {
            "有料": (39, 32, 24, 19, 4930),
            "無料": (21, 14, 7, 4, 1210),
            "CSVのみ": (18, 13, 7, 6, 1770),
        }
        counter = 0
        for label, (count, head, pair, hits, payout) in specs.items():
            for index in range(count):
                row = self._target(label, "○" if index < hits else "×", payout if index == 0 else 0)
                row.update({
                    "FT2_ID": f"g{counter}", "forward_status": GENUINE,
                    "1号艇頭成功": "○" if index < head else "×",
                    "2着候補2艇カバー": "○" if index < pair else "対象外",
                    "内側1点成功": "○" if index < hits else "対象外",
                    "対象日": "2026-09-01",
                })
                rows.append(row)
                counter += 1
        for index in range(3):
            row = self._target("CSVのみ", "×", 0)
            row.update({"FT2_ID": f"c{index}", "forward_status": CONTAMINATED,
                        "1号艇頭成功": "×", "2着候補2艇カバー": "対象外",
                        "内側1点成功": "対象外", "対象日": "2026-09-03"})
            rows.append(row)
        for index in range(255):
            rows.append({"FT2_ID": f"n{index}", "2連単1点対象": "対象外", "2連単1点的中": "対象外",
                         "2連単1点投資額": 0, "2連単1点回収額": 0, "掲載区分": "対象外",
                         "1号艇頭成功": "対象外", "2着候補2艇カバー": "対象外", "内側1点成功": "対象外",
                         "forward_status": GENUINE, "対象日": "2026-09-02"})
        raw = metric_block(rows)
        genuine = metric_block([row for row in rows if row["forward_status"] == GENUINE])
        self.assertEqual((len(rows), raw["R数"], raw["的中数"], raw["投資"], raw["回収"]), (336, 81, 29, 8100, 7910))
        self.assertEqual((genuine["R数"], genuine["的中数"], genuine["投資"], genuine["回収"]), (78, 29, 7800, 7910))
        self.assertEqual((genuine["1号艇頭成功"], genuine["2艇カバー"], genuine["内側成功"]), (59, 38, 29))
        for index in range(60):
            row = self._target("有料" if index < 6 else "無料", "×", 0) if index < 8 else {
                "2連単1点対象": "対象外", "2連単1点的中": "対象外", "2連単1点投資額": 0,
                "2連単1点回収額": 0, "掲載区分": "対象外", "1号艇頭成功": "対象外",
                "2着候補2艇カバー": "対象外", "内側1点成功": "対象外"}
            row.update({"FT2_ID": f"d9-{index}", "forward_status": GENUINE, "対象日": "2026-09-09"})
            rows.append(row)
        self.assertEqual(cumulative_acceptance(rows), {"Raw全R": 396, "genuine全R": 393,
            "genuine2連単": 86, "的中": 29, "投資": 8600, "回収": 7910,
            "CONTAMINATED": 3, "重複": 0})

    @staticmethod
    def _target(label, hit, payout):
        return {"2連単1点対象": "対象", "2連単1点的中": hit, "2連単1点投資額": 100,
                "2連単1点回収額": payout, "掲載区分": label,
                "1号艇頭成功": "×", "2着候補2艇カバー": "対象外", "内側1点成功": "対象外"}


if __name__ == "__main__":
    unittest.main()
