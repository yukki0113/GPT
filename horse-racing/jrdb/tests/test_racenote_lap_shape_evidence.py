#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_raw import BODY_LENGTHS  # noqa: E402
from racenote_lap_shape_evidence import build_evidence  # noqa: E402


def put(row: bytearray, start: int, width: int, value: str) -> None:
    raw = str(value).encode("cp932")
    row[start - 1 : start - 1 + width] = raw.ljust(width, b" ")


def make_sed(key: str, date: str, distance: int, surface: str = "1") -> bytes:
    row = bytearray(b" " * BODY_LENGTHS["SED"])
    put(row, 1, 8, key)
    put(row, 9, 2, "01")
    put(row, 11, 8, "20240001")
    put(row, 19, 8, date)
    put(row, 63, 4, str(distance))
    put(row, 67, 1, surface)
    return bytes(row)


def make_srb(key: str, laps: list[int], pace_up: str = "") -> bytes:
    row = bytearray(b" " * BODY_LENGTHS["SRB"])
    put(row, 1, 8, key)
    for index, value in enumerate(laps):
        put(row, 9 + index * 3, 3, f"{value:03d}")
    if pace_up:
        put(row, 319, 2, pace_up)
    return bytes(row)


class RaceNoteLapShapeEvidenceTest(unittest.TestCase):
    def test_builds_neutral_shape_for_1400m(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "SED261012.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr(
                    "SED261012.txt",
                    make_sed("05264501", "20261012", 1400, "2") + b"\r\n",
                )
                zf.writestr(
                    "SRB261012.txt",
                    make_srb("05264501", [125,110,121,132,128,118,121], "3") + b"\r\n",
                )

            evidence = build_evidence([archive])
            self.assertEqual(evidence["policy"]["score_status"], "NO_ADDITIVE_SCORE")
            race = evidence["races"][0]
            self.assertEqual(race["race_date"], "2026-10-12")
            self.assertEqual(race["lap_count"], 7)
            self.assertEqual(race["lap_shape"]["early3f_sec"], 35.6)
            self.assertEqual(race["lap_shape"]["late3f_sec"], 36.7)
            self.assertEqual(race["lap_shape"]["early_late_delta_sec"], 1.1)
            self.assertEqual(race["lap_shape"]["fastest_lap_sec"], 11.0)
            self.assertEqual(race["lap_shape"]["fastest_segment_no"], 2)
            self.assertEqual(race["lap_shape"]["max_accel_sec"], 1.5)
            self.assertEqual(race["lap_shape"]["max_decel_sec"], 1.1)
            self.assertTrue(race["coverage"]["optional_srb_context_available"])

    def test_partial_first_segment_is_excluded_from_comparable_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "SED260905.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr(
                    "SED260905.txt",
                    make_sed("01262501", "20260905", 1700, "2") + b"\r\n",
                )
                zf.writestr(
                    "SRB260905.txt",
                    make_srb("01262501", [70,106,119,127,123,123,124,128,132]) + b"\r\n",
                )

            race = build_evidence([archive])["races"][0]
            self.assertEqual(race["coverage"]["comparable_200m_lap_count"], 8)
            self.assertFalse(race["coverage"]["early_late_delta_available"])
            self.assertIsNone(race["lap_shape"]["early3f_sec"])
            self.assertEqual(race["lap_shape"]["fastest_lap_sec"], 10.6)
            self.assertEqual(race["lap_shape"]["fastest_segment_no"], 2)
            self.assertFalse(race["coverage"]["optional_srb_context_available"])


if __name__ == "__main__":
    unittest.main()
