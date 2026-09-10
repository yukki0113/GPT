from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import enrich_boatrace_racelist_metadata as enrich
import fetch_boatrace_event_meta as event_meta


class RacelistMetadataEnrichmentTest(unittest.TestCase):
    """公式開催メタデータの解析とCSV付与を検証する。"""

    def test_parse_official_index_extracts_g1_event_name(self) -> None:
        source = """
        <tbody class="table1">
          <tr><td><img alt="大村" src="/images/text_place2_24.png"></td></tr>
          <tr><td class="is-G1b"><a href="/owpc/pc/race/raceindex?jcd=24&hd=20260910">開設７４周年記念　海の王者決定戦</a></td></tr>
        </tbody>
        """
        rows = event_meta.parse_official_index(source, "20260910")
        self.assertEqual(1, len(rows))
        self.assertEqual("大村", rows[0]["会場"])
        self.assertEqual("開設７４周年記念　海の王者決定戦", rows[0]["開催グレード"])
        self.assertEqual("G1", rows[0]["グレード大分類"])

    def test_parse_official_index_classifies_g3(self) -> None:
        source = """
        <tbody>
          <tr><td><img alt="浜名湖" src="/images/text_place2_06.png"></td></tr>
          <tr><td class="is-G3b"><a href="/owpc/pc/race/raceindex?jcd=06&hd=20260904">オールレディース静岡クラウンメロン杯</a></td></tr>
        </tbody>
        """
        rows = event_meta.parse_official_index(source, "20260904")
        self.assertEqual("G3", rows[0]["グレード大分類"])

    def test_enrich_csv_adds_three_columns_and_preserves_race_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "race.csv"
            columns = ["日付", "会場", "R", "開催日目", "レース種別", "艇番"]
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerow({
                    "日付": "20260910",
                    "会場": "大村",
                    "R": "11",
                    "開催日目": "4日目",
                    "レース種別": "準優勝戦",
                    "艇番": "1",
                })

            enrich.enrich_csv(path, {
                "大村": {
                    "開催グレード": "G1",
                    "開催名": "開設７４周年記念　海の王者決定戦",
                }
            })

            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                fieldnames = list(reader.fieldnames or [])

            self.assertEqual(
                ["日付", "会場", "R", "開催日目", "開催グレード", "開催名", "レース名", "レース種別", "艇番"],
                fieldnames,
            )
            self.assertEqual("G1", rows[0]["開催グレード"])
            self.assertEqual("開設７４周年記念　海の王者決定戦", rows[0]["開催名"])
            self.assertEqual("準優勝戦", rows[0]["レース名"])
            self.assertEqual("準優勝戦", rows[0]["レース種別"])

    def test_build_event_map_fails_closed_when_grade_is_unresolved(self) -> None:
        official = [{
            "会場": "大村",
            "開催グレード": "開設７４周年記念　海の王者決定戦",
            "グレード大分類": "未分類",
        }]
        with patch.object(enrich, "fetch_event_meta", return_value=official):
            with self.assertRaises(enrich.MetadataEnrichmentError):
                enrich.build_event_map("20260910", [{"name": "大村", "code": "24", "day": "4日目"}])


if __name__ == "__main__":
    unittest.main()
