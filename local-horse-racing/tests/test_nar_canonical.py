from __future__ import annotations

import csv
import io
import unittest
import zipfile
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nar.canonical.field_catalog import FIELD_CATALOG, POST_ONLY, PRE_ASOF_PENDING, PRE_SAFE, WEIGH_IN
from nar.canonical.leakage import validate_history_asof
from nar.canonical.parser import parse_monthly_race_zip
from nar.canonical.schema import TABLE_SPECS
from nar.canonical.storage import make_storage_config
from nar.schema import HORSELIST_COLUMNS, PAYBACK_COLUMNS, RACELIST_COLUMNS


def csv_payload(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in columns})
    return stream.getvalue().encode("utf-8-sig")


def race_zip(race_rows, horse_rows, payback_rows):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("202601_racelist.csv", csv_payload(RACELIST_COLUMNS, race_rows))
        archive.writestr("202601_horselist.csv", csv_payload(HORSELIST_COLUMNS, horse_rows))
        archive.writestr("202601_payback.csv", csv_payload(PAYBACK_COLUMNS, payback_rows))
    return stream.getvalue()


class CanonicalTests(unittest.TestCase):
    def test_catalog_classifies_leakage_boundaries(self):
        lookup = {(x.source_table, x.source_field): x for x in FIELD_CATALOG}
        self.assertEqual(lookup[("horselist", "馬名")].availability_class, PRE_SAFE)
        self.assertEqual(lookup[("horselist", "馬体重")].available_stage, WEIGH_IN)
        self.assertEqual(lookup[("horselist", "全成績")].availability_class, PRE_ASOF_PENDING)
        self.assertEqual(lookup[("horselist", "着順")].availability_class, POST_ONLY)
        self.assertEqual(lookup[("horselist", "人気")].availability_class, POST_ONLY)
        self.assertEqual(lookup[("racelist", "上がり3F")].availability_class, POST_ONLY)
        self.assertEqual(lookup[("payback", "単勝払戻金（円）")].availability_class, POST_ONLY)

    def test_parser_physically_separates_pre_and_post(self):
        race = {"競馬場": "園田", "競走年月日": "20260102", "レース番号": "1", "発走時刻": "1100", "芝ダート区分": "ダート", "回り": "右", "距離": "1400", "天候": "晴", "馬場": "良", "頭数": "2", "上がり3F": "39.0"}
        horses = [
            {"競馬場": "園田", "競走年月日": "20260102", "レース番号": "1", "枠番": "1", "馬番": "1", "馬名": "テストホース", "生年月日": "20220101", "父馬名": "テスト父", "騎手名": "騎手A", "負担重量": "☆53", "馬体重": "480", "馬体重増減": "+2", "全成績": "1-0-0-2", "当競馬場成績": "1-0-0-1", "うち当距離成績": "1-0-0-1", "着順": "1", "タイム": "1321", "上がり3F": "38.5", "人気": "2"},
            {"競馬場": "園田", "競走年月日": "20260102", "レース番号": "1", "枠番": "2", "馬番": "2", "馬名": "テストホース2", "生年月日": "20220202", "父馬名": "テスト父2", "騎手名": "騎手B", "負担重量": "54", "全成績": "0-1-0-2", "着順": "2", "タイム": "1325", "人気": "1"},
        ]
        payback = [{"競馬場": "園田", "競走年月日": "20260102", "レース番号": "1", "単勝組番": "1", "単勝払戻金（円）": "320", "単勝人気": "2", "複勝組番1": "1", "複勝払戻金1（円）": "120", "複勝人気1": "1"}]
        batch = parse_monthly_race_zip(race_zip([race], horses, payback))
        pre = batch.tables["pre_runner"][0]
        post = batch.tables["post_runner_result"][0]
        history = batch.tables["pre_runner_history_snapshot"][0]
        self.assertNotIn("finish_position", pre)
        self.assertNotIn("popularity", pre)
        self.assertEqual(post["finish_position"], 1)
        self.assertEqual(post["finish_time_seconds"], 92.1)
        self.assertEqual(pre["assigned_weight"], 53.0)
        self.assertEqual(pre["allowance_mark"], "☆")
        self.assertEqual(pre["body_weight_change_kg"], 2)
        self.assertEqual(history["leakage_status"], "PENDING_VALIDATION")
        wins = [row for row in batch.tables["post_payout"] if row["bet_type"] == "WIN"]
        self.assertEqual(wins[0]["payout_yen"], 320)

    def test_refund_race_is_not_model_or_return_target(self):
        race = {"競馬場": "名古屋", "競走年月日": "20260120", "レース番号": "1", "距離": "1400", "頭数": "1"}
        horse = {"競馬場": "名古屋", "競走年月日": "20260120", "レース番号": "1", "枠番": "1", "馬番": "1", "馬名": "取消馬", "生年月日": "20220101", "父馬名": "父"}
        payback = {"競馬場": "名古屋", "競走年月日": "20260120", "レース番号": "1", "単勝払戻金（円）": "100", "複勝払戻金1（円）": "100", "馬複払戻金（円）": "100"}
        batch = parse_monthly_race_zip(race_zip([race], [horse], [payback]))
        status = batch.tables["control_race_status"][0]
        self.assertEqual(status["status"], "REFUNDED")
        self.assertFalse(status["is_model_target"])
        self.assertFalse(status["is_return_target"])

    def test_asof_validator_matches_previous_result_delta(self):
        history = [
            {"runner_id": "r1", "horse_key": "h", "race_date": "2026-01-01", "race_no": 1, "venue": "園田", "distance_m": 1400, "surface": "ダート", "direction": "右", "track_condition": "良", "jockey_name": "A", "overall_record_raw": "1-2-3-4", "jockey_record_raw": "1-0-0-2", "venue_record_raw": "0-1-0-2", "venue_distance_record_raw": "0-1-0-1", "dirt_left_record_raw": "0-0-0-1", "dirt_right_record_raw": "1-2-3-3", "best_time_seconds": 90.0, "best_time_good_seconds": 90.0},
            {"runner_id": "r2", "horse_key": "h", "race_date": "2026-01-10", "race_no": 1, "venue": "園田", "distance_m": 1400, "surface": "ダート", "direction": "右", "track_condition": "良", "jockey_name": "A", "overall_record_raw": "2-2-3-4", "jockey_record_raw": "2-0-0-2", "venue_record_raw": "1-1-0-2", "venue_distance_record_raw": "1-1-0-1", "dirt_left_record_raw": "0-0-0-1", "dirt_right_record_raw": "2-2-3-3", "best_time_seconds": 89.0, "best_time_good_seconds": 89.0},
        ]
        results = [{"runner_id": "r1", "finish_position": 1, "finish_time_seconds": 89.0}]
        report = validate_history_asof(history, results)
        self.assertEqual(report["fields"]["overall_record_raw"]["matched_pairs"], 1)
        self.assertEqual(report["fields"]["dirt_right_record_raw"]["matched_pairs"], 1)
        self.assertEqual(report["fields"]["best_time_seconds"]["matched_pairs"], 1)

    def test_storage_config_uses_shared_data_storage_contract(self):
        spec = TABLE_SPECS["pre_runner"]
        cfg = make_storage_config(Path("stage/pre_runner.csv"), Path("canonical"), Path("audit"), spec)
        self.assertEqual(cfg["source"]["format"], "csv")
        self.assertEqual(cfg["target"]["format"], "parquet")
        self.assertEqual(cfg["target"]["compression"], "zstd")
        self.assertEqual(cfg["target"]["partition_by"], ["race_year"])
        self.assertEqual(cfg["keys"]["canonical"], ["runner_id"])


if __name__ == "__main__":
    unittest.main()
