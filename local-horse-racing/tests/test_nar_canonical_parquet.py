from __future__ import annotations

import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from nar.canonical.build import build_staging
from nar.canonical.storage import materialize_parquet
from nar.schema import HORSELIST_COLUMNS, PAYBACK_COLUMNS, RACELIST_COLUMNS

try:
    from data_storage.query import execute_query
except ImportError:
    execute_query = None


def _csv_payload(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in columns})
    return stream.getvalue().encode("utf-8-sig")


def _monthly_zip(path: Path) -> None:
    race = {
        "競馬場": "園田", "競走年月日": "20260102", "レース番号": "1", "発走時刻": "1100",
        "競走種類名称": "一般", "レース名": "テスト", "芝ダート区分": "ダート", "回り": "右",
        "距離": "1400", "天候": "晴", "馬場": "良", "頭数": "1", "条件": "C3",
        "1着賞金(円)": "600000", "上がり4F": "51.0", "上がり3F": "38.5",
    }
    horse = {
        "競馬場": "園田", "競走年月日": "20260102", "レース番号": "1", "枠番": "1", "帽色": "白",
        "馬番": "1", "馬名": "テストホース", "性": "牡", "齢": "4", "毛色": "鹿毛",
        "生年月日": "20220101", "父馬名": "テスト父", "母馬名": "テスト母", "母父馬名": "テスト母父",
        "騎手名": "騎手A", "騎手所属": "兵庫", "負担重量": "☆53", "騎手成績": "1-0-0-2",
        "調教師": "調教師A", "調教師所属": "兵庫", "馬主氏名": "馬主A", "生産牧場名": "牧場A",
        "馬体重": "480", "馬体重増減": "+2", "全成績": "1-0-0-2", "ダート左成績": "0-0-0-0",
        "ダート右成績": "1-0-0-2", "当競馬場成績": "1-0-0-1", "うち当距離成績": "1-0-0-1",
        "最高タイム": "1:32.0", "最高タイム良馬場": "良1:32.0", "着順": "1", "タイム": "1321",
        "着差": "", "上がり3F": "38.5", "人気": "2",
    }
    payback = {
        "競馬場": "園田", "競走年月日": "20260102", "レース番号": "1", "レース名": "テスト",
        "単勝組番": "1", "単勝払戻金（円）": "320", "単勝人気": "2",
        "複勝組番1": "1", "複勝払戻金1（円）": "120", "複勝人気1": "1",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("202601_racelist.csv", _csv_payload(RACELIST_COLUMNS, [race]))
        archive.writestr("202601_horselist.csv", _csv_payload(HORSELIST_COLUMNS, [horse]))
        archive.writestr("202601_payback.csv", _csv_payload(PAYBACK_COLUMNS, [payback]))


@unittest.skipUnless(execute_query is not None, "shared data_storage dependencies are unavailable")
class CanonicalParquetIntegrationTests(unittest.TestCase):
    def test_staging_to_parquet_with_shared_tooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "202601_test_race.zip"
            staging = root / "staging"
            parquet = root / "canonical"
            audit = root / "audit"
            _monthly_zip(source)

            summary = build_staging([source], staging, validate_asof=True)
            self.assertEqual(summary["status"], "success")
            self.assertEqual(summary["monthly_zip_count"], 1)

            results = materialize_parquet(staging, parquet, audit)
            self.assertEqual(set(results), {
                "pre_race", "pre_runner", "pre_runner_history_snapshot", "post_race_result",
                "post_runner_result", "post_payout", "control_race_status",
            })
            self.assertTrue(all(result["status"] == "success" for result in results.values()))
            self.assertEqual(len(list(audit.glob("*.audit.json"))), 7)

            columns, rows = execute_query(parquet / "pre/runner", "SELECT * FROM data LIMIT 1")
            self.assertEqual(len(rows), 1)
            self.assertNotIn("popularity", columns)
            self.assertNotIn("finish_position", columns)

            columns, rows = execute_query(
                parquet / "post/runner_result", "SELECT finish_position, popularity FROM data"
            )
            self.assertEqual(columns, ["finish_position", "popularity"])
            self.assertEqual(rows, [(1, 2)])

            _, rows = execute_query(
                parquet / "pre/runner_history_snapshot",
                "SELECT leakage_status FROM data",
            )
            self.assertEqual(rows, [("PENDING_VALIDATION",)])

            _, rows = execute_query(
                parquet / "control/race_status",
                "SELECT status, is_model_target, is_return_target FROM data",
            )
            self.assertEqual(rows, [("NORMAL", True, True)])


if __name__ == "__main__":
    unittest.main()
