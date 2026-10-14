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

from jrdb_raw import BODY_LENGTHS, Parser, split_fixed_records  # noqa: E402
from jrdb_race_lap import (  # noqa: E402
    normalize_race_laps,
    read_sed_zip_race_laps,
    segment_distances,
)


def put(row: bytearray, start: int, width: int, value: str) -> None:
    encoded = str(value).encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    offset = start - 1
    row[offset : offset + width] = encoded.ljust(width, b" ")


def blank(kind: str) -> bytearray:
    return bytearray(b" " * BODY_LENGTHS[kind])


def make_sed(race_key: str, distance_m: int) -> bytes:
    row = blank("SED")
    put(row, 1, 8, race_key)
    put(row, 9, 2, "01")
    put(row, 11, 8, "20240001")
    put(row, 19, 8, "20260905")
    put(row, 63, 4, str(distance_m))
    return bytes(row)


def make_srb(
    race_key: str,
    lap_tenths: list[int],
    *,
    pace_up: int | None = None,
    comment: str | None = None,
) -> bytes:
    row = blank("SRB")
    put(row, 1, 8, race_key)
    for index, value in enumerate(lap_tenths):
        put(row, 9 + index * 3, 3, f"{value:03d}")
    if pace_up is not None:
        put(row, 319, 2, str(pace_up))
    if comment:
        put(row, 343, 500, comment)
    return bytes(row)


class JrdbRaceLapTest(unittest.TestCase):
    def test_srb_parser_uses_published_offsets(self) -> None:
        record = make_srb(
            "01262501",
            [70, 106, 119, 127, 123, 123, 124, 128, 132],
            pace_up=4,
            comment="テストコメント",
        )
        parsed = Parser().srb(record)
        self.assertEqual(parsed["race_key_raw"], "01262501")
        self.assertEqual(
            parsed["furlong_times_sec"][:9],
            [7.0, 10.6, 11.9, 12.7, 12.3, 12.3, 12.4, 12.8, 13.2],
        )
        self.assertEqual(parsed["furlong_times_sec"][9:], [None] * 9)
        self.assertEqual(parsed["pace_up_remaining_furlongs"], 4)
        self.assertEqual(parsed["race_comment"], "テストコメント")

    def test_srb_split_accepts_crlf_and_body_lines(self) -> None:
        body = make_srb("01262501", [120] * 8)
        self.assertEqual(
            len(split_fixed_records(body + b"\r\n" + body + b"\r\n", "SRB")),
            2,
        )
        self.assertEqual(
            len(split_fixed_records(body + b"\n" + body + b"\n", "SRB")),
            2,
        )

    def test_segment_distance_rules_cover_partial_first_segment(self) -> None:
        self.assertEqual(segment_distances(1400, 7), [200] * 7)
        self.assertEqual(segment_distances(1700, 9), [100] + [200] * 8)
        self.assertEqual(segment_distances(1150, 6), [150] + [200] * 5)

    def test_normalize_1700m_matches_explicit_intervals(self) -> None:
        parsed = Parser().srb(
            make_srb(
                "01262501",
                [70, 106, 119, 127, 123, 123, 124, 128, 132],
            )
        )
        rows = normalize_race_laps(parsed, distance_m=1700)
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0]["start_m"], 0)
        self.assertEqual(rows[0]["end_m"], 100)
        self.assertEqual(rows[0]["segment_distance_m"], 100)
        self.assertEqual(rows[-1]["start_m"], 1500)
        self.assertEqual(rows[-1]["end_m"], 1700)
        self.assertEqual(rows[-1]["lap_sec"], 13.2)

    def test_empty_srb_laps_are_not_invented(self) -> None:
        parsed = Parser().srb(make_srb("05264504", []))
        self.assertEqual(normalize_race_laps(parsed, distance_m=3000), [])

    def test_read_sed_zip_joins_distance_and_keeps_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "SED260905.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr(
                    "SED260905.txt",
                    make_sed("01262501", 1700) + b"\r\n",
                )
                zf.writestr(
                    "SRB260905.txt",
                    make_srb(
                        "01262501",
                        [70, 106, 119, 127, 123, 123, 124, 128, 132],
                    )
                    + b"\r\n",
                )

            rows = read_sed_zip_race_laps(archive)
            self.assertEqual(len(rows), 9)
            self.assertEqual(rows[0]["distance_m"], 1700)
            self.assertEqual(rows[0]["source_archive"], "SED260905.zip")
            self.assertEqual(rows[0]["source_sed_member"], "SED260905.txt")
            self.assertEqual(rows[0]["source_srb_member"], "SRB260905.txt")


if __name__ == "__main__":
    unittest.main()
