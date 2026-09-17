from __future__ import annotations

import csv
import io
import sys
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nar.canonical.reconciliation import parse_monthly_race_zip_reconciled
from nar.schema import HORSELIST_COLUMNS, PAYBACK_COLUMNS, RACELIST_COLUMNS


def _csv_payload(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in columns})
    return stream.getvalue().encode("utf-8-sig")


def _race_zip(race_rows, horse_rows, payback_rows):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("202601_racelist.csv", _csv_payload(RACELIST_COLUMNS, race_rows))
        archive.writestr("202601_horselist.csv", _csv_payload(HORSELIST_COLUMNS, horse_rows))
        archive.writestr("202601_payback.csv", _csv_payload(PAYBACK_COLUMNS, payback_rows))
    return stream.getvalue()


class HistoricalReconciliationTests(unittest.TestCase):
    def test_horselist_only_cancelled_race_reconstructs_identity_only(self):
        horse = {
            "競馬場": "園田",
            "競走年月日": "20260120",
            "レース番号": "3",
            "枠番": "1",
            "馬番": "1",
            "馬名": "中止馬",
            "生年月日": "20220101",
            "父馬名": "父",
            "馬体重": "－",
            "全成績": "0-0-0-3",
        }

        batch = parse_monthly_race_zip_reconciled(_race_zip([], [horse], []))

        self.assertEqual(len(batch.tables["pre_race"]), 1)
        pre_race = batch.tables["pre_race"][0]
        self.assertEqual(pre_race["race_id"], "20260120:園田:03")
        self.assertEqual(pre_race["venue"], "園田")
        self.assertEqual(pre_race["race_no"], 3)
        self.assertIsNone(pre_race["distance_m"])
        self.assertIsNone(pre_race["field_size"])
        self.assertEqual(pre_race["race_name"], "")
        self.assertEqual(pre_race["weather"], "")

        self.assertEqual(batch.tables["pre_runner"][0]["race_id"], pre_race["race_id"])
        self.assertIsNone(batch.tables["pre_runner_history_snapshot"][0]["distance_m"])

        status = batch.tables["control_race_status"][0]
        self.assertEqual(status["status"], "CANCELLED")
        self.assertEqual(status["reason"], "racelist_missing_horselist_present")
        self.assertFalse(status["is_model_target"])
        self.assertFalse(status["is_return_target"])
        self.assertEqual(status["runner_count"], 1)
        self.assertEqual(status["finish_count"], 0)
        self.assertEqual(status["payback_row_count"], 0)

    def test_racelist_less_race_with_result_fails_closed(self):
        horse = {
            "競馬場": "笠松",
            "競走年月日": "20260121",
            "レース番号": "1",
            "枠番": "1",
            "馬番": "1",
            "馬名": "異常馬",
            "生年月日": "20220101",
            "父馬名": "父",
            "着順": "1",
            "タイム": "1300",
        }

        batch = parse_monthly_race_zip_reconciled(_race_zip([], [horse], []))
        status = batch.tables["control_race_status"][0]

        self.assertEqual(status["status"], "DATA_MISSING")
        self.assertEqual(
            status["reason"],
            "racelist_missing_horselist_present_with_result_or_payback",
        )
        self.assertFalse(status["is_model_target"])
        self.assertFalse(status["is_return_target"])


if __name__ == "__main__":
    unittest.main()
