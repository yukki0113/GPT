#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Characterize common Raw parser against the legacy RaceNote parser."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(TEST_ROOT))

from jrdb_raw import Parser as CommonParser  # noqa: E402
from racenote_jrdb import (  # noqa: E402
    Audit,
    LegacyParser,
    Parser as ProductionRaceNoteParser,
)
from test_jrdb_raw_common import (  # noqa: E402
    make_bac,
    make_kyi,
    make_sed,
    make_skb,
)


class RaceNoteCompatibilityTest(unittest.TestCase):
    """Prevent byte-position drift while consumers migrate to jrdb_raw."""

    def setUp(self) -> None:
        self.common = CommonParser()
        self.legacy = LegacyParser(Audit())

    def test_production_parser_is_common_parser(self) -> None:
        self.assertIs(ProductionRaceNoteParser, CommonParser)

    def test_bac_exact_match(self) -> None:
        record = make_bac()
        self.assertEqual(self.common.bac(record), self.legacy.bac(record))

    def test_kyi_exact_match(self) -> None:
        record = make_kyi()
        self.assertEqual(self.common.kyi(record), self.legacy.kyi(record))

    def test_zed_exact_match(self) -> None:
        record = make_sed("20231001", "20260830", "0526A101", "01")
        self.assertEqual(self.common.zed(record), self.legacy.zed(record))

    def test_zkb_exact_match(self) -> None:
        record = make_skb()
        self.assertEqual(self.common.zkb(record), self.legacy.zkb(record))


if __name__ == "__main__":
    unittest.main()
