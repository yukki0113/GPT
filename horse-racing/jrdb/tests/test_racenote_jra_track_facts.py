#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_jra_track_facts import (  # noqa: E402
    JraTrackFactsError,
    parse_jra_baba_html,
)


FIXTURE = """
<!doctype html>
<html lang="ja">
<head><title>馬場情報（中山競馬場） JRA</title></head>
<body>
  <h1>馬場情報</h1>
  <nav><a>中山競馬場</a><a>阪神競馬場</a></nav>
  <h2>第4回中山競馬第9日（2026年9月27日（日曜））</h2>
  <h3>馬場状態（9月27日（日曜）9時30分現在）</h3>
  <p>天候：雨</p>
  <h4>芝</h4>
  <p>重</p>
  <h4>ダート</h4>
  <p>不良</p>
  <h3>芝のクッション値</h3>
  <p>8.1</p>
</body>
</html>
"""


class RaceNoteJraTrackFactsTest(unittest.TestCase):
    def test_turf_facts_are_parsed_with_provenance(self) -> None:
        result = parse_jra_baba_html(
            FIXTURE,
            source_url="https://www.jra.go.jp/keiba/baba/index.html",
            venue="中山",
            surface="芝",
            target_date=date(2026, 9, 27),
        )

        self.assertEqual(
            result["source_kind"],
            "JRA_OFFICIAL_BABA",
        )
        self.assertEqual(
            result["source_url"],
            "https://www.jra.go.jp/keiba/baba/index.html",
        )
        self.assertEqual(
            result["as_of"],
            "2026-09-27T09:30:00+09:00",
        )
        self.assertEqual(result["weather"], "雨")
        self.assertEqual(result["track_condition"], "重")
        self.assertTrue(result["result_independent"])

    def test_dirt_condition_uses_dirt_section(self) -> None:
        result = parse_jra_baba_html(
            FIXTURE,
            source_url="https://www.jra.go.jp/keiba/baba/index.html",
            venue="中山",
            surface="ダート",
            target_date=date(2026, 9, 27),
        )

        self.assertEqual(
            result["track_condition"],
            "不良",
        )

    def test_status_date_must_match_target_date(self) -> None:
        with self.assertRaises(JraTrackFactsError):
            parse_jra_baba_html(
                FIXTURE,
                source_url="https://www.jra.go.jp/keiba/baba/index.html",
                venue="中山",
                surface="芝",
                target_date=date(2026, 9, 28),
            )

    def test_requested_venue_must_be_present(self) -> None:
        with self.assertRaises(JraTrackFactsError):
            parse_jra_baba_html(
                FIXTURE,
                source_url="https://www.jra.go.jp/keiba/baba/index.html",
                venue="東京",
                surface="芝",
                target_date=date(2026, 9, 27),
            )

    def test_missing_weather_fails_closed(self) -> None:
        broken = FIXTURE.replace(
            "<p>天候：雨</p>",
            "<p>天候：</p>",
        )
        with self.assertRaises(JraTrackFactsError):
            parse_jra_baba_html(
                broken,
                source_url="https://www.jra.go.jp/keiba/baba/index.html",
                venue="中山",
                surface="芝",
                target_date=date(2026, 9, 27),
            )


if __name__ == "__main__":
    unittest.main()
