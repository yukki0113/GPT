import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forward_trial_analysis_import import (
    CONTAMINATED,
    GENUINE,
    ForwardTrialValidationError,
    audit_freeze,
    initial_backfill_rows,
    metric_block,
    stable_key,
    structure_result,
    upsert_rows,
    validate_source_dates,
)


class ForwardTrialAnalysisImportTest(unittest.TestCase):
    def test_stable_key_and_idempotent_upsert(self):
        row = {"FT2_ID": stable_key("2026-09-01", "若松", 1), "value": 1}
        self.assertEqual(upsert_rows([row], [row]), [row])
        with self.assertRaises(ForwardTrialValidationError):
            upsert_rows([row], [{**row, "value": 2}])

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

    @staticmethod
    def _target(label, hit, payout):
        return {"2連単1点対象": "対象", "2連単1点的中": hit, "2連単1点投資額": 100,
                "2連単1点回収額": payout, "掲載区分": label,
                "1号艇頭成功": "×", "2着候補2艇カバー": "対象外", "内側1点成功": "対象外"}


if __name__ == "__main__":
    unittest.main()
