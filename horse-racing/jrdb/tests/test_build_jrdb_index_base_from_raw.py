#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthetic parser/integration tests for the JRDB independent-index base builder."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from build_jrdb_index_base_from_raw import (  # noqa: E402
    _put_bac_revision,
    build,
    parse_bac,
    parse_cha,
    parse_cyb,
    parse_kyi,
    parse_sed,
    profile_observation,
)


def put(buffer: bytearray, offset: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width test field."""
    encoded = str(value).encode("cp932")
    if len(encoded) > width:
        raise ValueError(f"field too wide: offset={offset} width={width} value={value!r}")
    buffer[offset : offset + width] = encoded.ljust(width, b" ")


def make_bac() -> bytes:
    """Create one synthetic BAC body record."""
    row = bytearray(b" " * 181)
    put(row, 0, 8, "0526A101")
    put(row, 8, 8, "20260830")
    put(row, 16, 4, "1540")
    put(row, 20, 4, "1600")
    put(row, 24, 1, "1")
    put(row, 25, 1, "2")
    put(row, 26, 1, "1")
    put(row, 27, 2, "13")
    put(row, 29, 2, "OP")
    put(row, 31, 3, "500")
    put(row, 34, 1, "4")
    put(row, 35, 1, "3")
    put(row, 36, 50, "テスト")
    put(row, 94, 2, "16")
    put(row, 96, 1, "1")
    put(row, 97, 1, "1")
    return bytes(row)


def make_kyi() -> bytes:
    """Create one synthetic KYI body record."""
    row = bytearray(b" " * 1022)
    put(row, 0, 8, "0526A101")
    put(row, 8, 2, "03")
    put(row, 10, 8, "20231001")
    put(row, 18, 36, "テストホース")
    put(row, 54, 5, "72.5")
    put(row, 89, 1, "2")
    put(row, 90, 1, "3")
    put(row, 91, 1, "1")
    put(row, 92, 3, "  2")
    put(row, 144, 5, "12.3")
    put(row, 149, 5, " 5.4")
    put(row, 154, 1, "2")
    put(row, 155, 1, "1")
    put(row, 170, 1, "1")
    put(row, 171, 12, "騎手名")
    put(row, 183, 3, "570")
    put(row, 187, 12, "調教師")
    put(row, 203, 16, "2023100120260810")
    put(row, 283, 8, "0526A001")
    put(row, 323, 1, "2")
    put(row, 335, 5, "01234")
    put(row, 340, 5, "54321")
    put(row, 357, 1, "3")
    put(row, 358, 5, "10.5")
    put(row, 363, 5, "11.5")
    put(row, 368, 5, "12.5")
    put(row, 373, 5, "13.5")
    put(row, 378, 1, "H")
    put(row, 396, 3, "480")
    put(row, 399, 3, "+04")
    put(row, 403, 1, "1")
    put(row, 519, 4, "12.3")
    put(row, 523, 4, " 5.5")
    put(row, 559, 2, " 2")
    put(row, 561, 8, "20260801")
    put(row, 569, 3, " 29")
    return bytes(row)


def make_sed() -> bytes:
    """Create one synthetic SED body record."""
    row = bytearray(b" " * 374)
    put(row, 0, 8, "0526A101")
    put(row, 8, 2, "03")
    put(row, 10, 8, "20231001")
    put(row, 18, 8, "20260830")
    put(row, 26, 36, "テストホース")
    put(row, 62, 4, "1600")
    put(row, 66, 1, "1")
    put(row, 67, 1, "2")
    put(row, 68, 1, "1")
    put(row, 69, 2, "10")
    put(row, 71, 2, "13")
    put(row, 73, 2, "OP")
    put(row, 75, 3, "500")
    put(row, 78, 1, "4")
    put(row, 79, 1, "3")
    put(row, 80, 50, "テスト")
    put(row, 130, 2, "16")
    put(row, 140, 2, "01")
    put(row, 142, 1, "0")
    put(row, 143, 4, "1325")
    put(row, 147, 3, "570")
    put(row, 150, 12, "騎手名")
    put(row, 162, 12, "調教師")
    put(row, 174, 6, "  3.5")
    put(row, 180, 2, "02")
    put(row, 182, 3, " 72")
    put(row, 185, 3, " 68")
    put(row, 188, 3, "-10")
    put(row, 191, 3, "  5")
    put(row, 194, 3, " -2")
    put(row, 197, 3, "  1")
    put(row, 200, 3, "  0")
    put(row, 203, 3, "  1")
    put(row, 206, 3, "  0")
    put(row, 209, 3, " -1")
    put(row, 212, 3, "  3")
    put(row, 215, 1, "3")
    put(row, 216, 1, "1")
    put(row, 217, 2, "OP")
    put(row, 219, 1, "3")
    put(row, 220, 1, "1")
    put(row, 221, 1, "H")
    put(row, 222, 1, "M")
    put(row, 223, 5, " 10.5")
    put(row, 228, 5, " 20.5")
    put(row, 233, 5, " 30.5")
    put(row, 238, 5, " 40.5")
    put(row, 255, 3, " 05")
    put(row, 258, 3, "358")
    put(row, 261, 3, "342")
    put(row, 290, 6, "  1.4")
    put(row, 308, 2, "03")
    put(row, 310, 2, "03")
    put(row, 312, 2, "02")
    put(row, 314, 2, "01")
    put(row, 316, 3, " 02")
    put(row, 319, 3, " 01")
    put(row, 322, 5, "01234")
    put(row, 327, 5, "54321")
    put(row, 332, 3, "480")
    put(row, 335, 3, "+04")
    put(row, 338, 1, "1")
    put(row, 339, 1, "1")
    put(row, 340, 1, "1")
    put(row, 341, 7, "    350")
    put(row, 348, 7, "    140")
    put(row, 369, 1, "2")
    put(row, 370, 4, "1540")
    return bytes(row)


def make_cha() -> bytes:
    """Create one synthetic CHA body record."""
    row = bytearray(b" " * 62)
    put(row, 0, 8, "0526A101")
    put(row, 8, 2, "03")
    put(row, 10, 2, "水")
    put(row, 12, 8, "20260827")
    put(row, 20, 1, "1")
    put(row, 21, 2, "CW")
    put(row, 23, 1, "3")
    put(row, 24, 2, "01")
    put(row, 26, 1, "3")
    put(row, 27, 1, "5")
    put(row, 28, 3, "147")
    put(row, 31, 3, "138")
    put(row, 34, 3, "125")
    put(row, 37, 3, " 60")
    put(row, 40, 3, " 62")
    put(row, 43, 3, " 65")
    put(row, 46, 3, " 64")
    put(row, 49, 1, "1")
    put(row, 50, 1, "2")
    put(row, 51, 2, "03")
    put(row, 53, 2, "OP")
    return bytes(row)


def make_cyb() -> bytes:
    """Create one synthetic CYB body record."""
    row = bytearray(b" " * 94)
    put(row, 0, 8, "0526A101")
    put(row, 8, 2, "03")
    put(row, 10, 2, "01")
    put(row, 12, 1, "3")
    for offset, value in [
        (13, "01"),
        (15, "01"),
        (17, "00"),
        (19, "00"),
        (21, "00"),
        (23, "00"),
        (25, "00"),
    ]:
        put(row, offset, 2, value)
    put(row, 27, 1, "1")
    put(row, 28, 1, "3")
    put(row, 29, 3, " 64")
    put(row, 32, 3, " 66")
    put(row, 35, 1, "B")
    put(row, 36, 1, "+")
    put(row, 85, 1, "1")
    put(row, 86, 3, " 60")
    put(row, 89, 2, "12")
    return bytes(row)


def make_ukc(data_date: str = "20260829") -> bytes:
    """Create one synthetic UKC body record; blank data_date tests member fallback."""
    row = bytearray(b" " * 290)
    put(row, 0, 8, "20231001")
    put(row, 8, 36, "テストホース")
    put(row, 44, 1, "1")
    put(row, 49, 36, "テスト父")
    put(row, 85, 36, "テスト母")
    put(row, 121, 36, "テスト母父")
    put(row, 157, 8, "20230301")
    put(row, 165, 4, "2010")
    put(row, 169, 4, "2012")
    put(row, 173, 4, "2008")
    put(row, 219, 40, "生産者")
    put(row, 259, 8, "北海道")
    if data_date:
        put(row, 268, 8, data_date)
    put(row, 276, 4, "1001")
    put(row, 280, 4, "2001")
    return bytes(row)


class IndexBaseBuilderTest(unittest.TestCase):
    """Verify fixed-width parsing and one-year synthetic integration."""

    def test_bac_parser_marks_pre_race_availability(self) -> None:
        parsed = parse_bac(make_bac(), "BAC260830.txt")
        self.assertEqual(parsed["race_date"], "2026-08-30")
        self.assertEqual(parsed["distance_m"], 1600)
        self.assertEqual(parsed["turn_code"], "2")
        self.assertEqual(parsed["availability_class"], "PRE_RACE")

    def test_bac_postponement_revision_keeps_later_date(self) -> None:
        first = parse_bac(make_bac(), "BAC260830.txt")
        postponed_raw = bytearray(make_bac())
        put(postponed_raw, 8, 8, "20260831")
        postponed = parse_bac(bytes(postponed_raw), "BAC260831.txt")

        races: dict[str, dict[str, object]] = {}
        _put_bac_revision(races, first)
        _put_bac_revision(races, postponed)

        self.assertEqual(races["0526A101"]["race_date"], "2026-08-31")
        self.assertEqual(races["0526A101"]["source_member"], "BAC260831.txt")

    def test_bac_revision_with_material_difference_is_rejected(self) -> None:
        first = parse_bac(make_bac(), "BAC260830.txt")
        changed_raw = bytearray(make_bac())
        put(changed_raw, 8, 8, "20260831")
        put(changed_raw, 20, 4, "1800")
        changed = parse_bac(bytes(changed_raw), "BAC260831.txt")

        races: dict[str, dict[str, object]] = {}
        _put_bac_revision(races, first)
        with self.assertRaisesRegex(ValueError, "non-identical duplicate BAC"):
            _put_bac_revision(races, changed)

    def test_kyi_parser_keeps_previous_links_and_pre_race_material(self) -> None:
        runner, links = parse_kyi(make_kyi(), "KYI260830.txt")
        self.assertEqual(runner["carried_weight_kg"], 57.0)
        self.assertEqual(runner["body_weight_change_pre_kg"], 4)
        self.assertEqual(runner["stable_entry_date"], "2026-08-01")
        self.assertEqual(links[0]["prev_result_key"], "2023100120260810")
        self.assertEqual(links[0]["prev_race_key"], "0526A001")
        self.assertEqual(len(links), 5)

    def test_sed_parser_separates_result_context_from_pre_race_context(self) -> None:
        result, result_context, fallback = parse_sed(make_sed(), "SED260830.txt")
        self.assertAlmostEqual(result["time_sec"], 92.5)
        self.assertEqual(result["first3f_sec"], 35.8)
        self.assertEqual(result["last3f_sec"], 34.2)
        self.assertEqual(result["jrdb_track_diff"], -10)
        self.assertEqual(result["body_weight_change_kg"], 4)
        self.assertEqual(result["result_key"], "2023100120260830")
        self.assertEqual(result_context["track_condition_code"], "10")
        self.assertEqual(result_context["weather_code"], "1")
        self.assertEqual(fallback["race_date"], "2026-08-30")
        self.assertEqual(fallback["start_time"], "15:40")
        self.assertEqual(fallback["availability_class"], "CURRENT_RESULT_FALLBACK")

    def test_training_parsers_keep_raw_and_jrdb_prepared_fields(self) -> None:
        workout = parse_cha(make_cha(), "CHA260830.txt")
        self.assertEqual(workout["final_segment_sec"], 12.5)
        self.assertEqual(workout["jrdb_workout_index"], 64)

        training = parse_cyb(make_cyb(), "CYB260830.txt")
        self.assertEqual(training["used_slope"], 1)
        self.assertEqual(training["used_dirt"], 0)
        self.assertEqual(training["finish_index"], 66)

    def test_profile_date_falls_back_to_member_business_date(self) -> None:
        profile = profile_observation(make_ukc(data_date=""), "UKC260830.txt")
        self.assertEqual(profile["data_date"], "2026-08-30")
        self.assertEqual(profile["sire_name"], "テスト父")

    def test_schema_declares_availability_boundaries(self) -> None:
        schema = (PROJECT_ROOT / "schema" / "jrdb_index_base_schema_v0_1.sql").read_text(encoding="utf-8")
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(schema)
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("race_context", tables)
            self.assertIn("race_result_context", tables)
            self.assertIn("runner_pre", tables)
            self.assertIn("runner_result", tables)
            self.assertIn("horse_profile_observation", tables)
        finally:
            connection.close()

    def test_full_synthetic_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            for kind in ["BAC", "KYI", "SED", "CHA", "CYB", "UKC"]:
                (root / kind).mkdir(parents=True, exist_ok=True)

            bodies = {
                "BAC": make_bac(),
                "KYI": make_kyi(),
                "SED": make_sed(),
                "CHA": make_cha(),
                "CYB": make_cyb(),
                "UKC": make_ukc(),
            }
            for kind, body in bodies.items():
                archive_path = root / kind / f"{kind}_2026.zip"
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr(f"{kind}260830.txt", body + b"\r\n")

            output = root / "index.sqlite"
            result = build(
                raw_root=root,
                years=[2026],
                output=output,
                schema_path=PROJECT_ROOT / "schema" / "jrdb_index_base_schema_v0_1.sql",
                hash_archives=False,
            )

            self.assertEqual(result["race_count"], 1)
            self.assertEqual(result["race_result_context_count"], 1)
            self.assertEqual(result["runner_pre_count"], 1)
            self.assertEqual(result["runner_result_count"], 1)
            self.assertEqual(result["workout_count"], 1)
            self.assertEqual(result["training_count"], 1)
            self.assertEqual(result["anomaly_count"], 0)

            connection = sqlite3.connect(output)
            try:
                row = connection.execute(
                    """
                    SELECT time_sec,first3f_sec,final_segment_sec,track_condition_code,
                           race_context_availability
                    FROM v_runner_longitudinal_base
                    """
                ).fetchone()
                self.assertEqual(row, (92.5, 35.8, 12.5, "10", "PRE_RACE"))
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
